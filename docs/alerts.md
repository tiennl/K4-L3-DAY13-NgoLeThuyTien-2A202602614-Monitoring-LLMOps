# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: `fast_successful_requests` (`latency_ms <= 2000`, target 99.5%); P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 2000ms` liên tục 5 phút (baseline P95 dưới 1s)
- Ảnh hưởng tới người dùng: câu trả lời đến chậm hơn 2 giây, mỗi request chậm đều tiêu tốn error budget
- Ba bước kiểm tra đầu tiên:
  1. Metrics: mở panel Latency, xác nhận P95/P99 vượt đường threshold và thời điểm bắt đầu tăng; xem TTFT P95 có tăng cùng không (TTFT không tăng nghĩa là chậm ở khâu retrieval, không phải ở model).
  2. Logs: lọc `data/logs.jsonl` theo `event == "response_sent"` trong khoảng đó, sắp xếp theo `latency_ms` giảm dần và lấy một `correlation_id` chậm nhất.
  3. Traces: mở trace có `correlation_id` đó trên Langfuse; trong waterfall so thời gian `retrieval` với `generation`. Nếu `retrieval` chiếm gần hết thời gian thì nguyên nhân là retrieval chậm (practice: `rag_slow`).
- Mitigation tạm thời: tắt nguồn gây chậm (practice: `POST /incidents/rag_slow/disable`); nếu bắt đầu ngay sau khi promote prompt thì rollback label `production` về version cũ; nếu do tải cao thì giảm tải/`--concurrency`. Xác nhận P95 về dưới 2000ms trong 5 phút.
- Owner: `student-2A202602614`

## Alert 2

- Tên: `HighErrorRateOrRetrievalFailure`
- Severity: `critical`
- Duration: `3m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: `fast_successful_requests` (request lỗi không có `response_sent` nên là request "xấu"); guardrail `error_rate_pct_max: 2` và `retrieval_success_rate_pct_min: 90`
- Điều kiện và thời gian duy trì: error rate (`request_failed / request_received`) > 2% **hoặc** retrieval success (`tool_success == true` trên mọi event có `tool_success`) < 90%, liên tục 3 phút
- Ảnh hưởng tới người dùng: người dùng nhận HTTP 500 và không có câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Metrics: mở panel Errors, xem error rate và retrieval success có vượt threshold không và bắt đầu từ lúc nào.
  2. Logs: lọc `event == "request_failed"`, nhóm theo `error_type` và `tool_name`; ghi lại một `correlation_id` (practice: `RuntimeError`, `tool_name=retrieval`, `payload.detail = "Vector store timeout"`).
  3. Traces: mở trace theo `correlation_id`; observation `retrieval` phải có level ERROR và sinh ra lỗi, `generation` không xuất hiện vì request dừng ở retrieval.
- Mitigation tạm thời: khôi phục vector store/cấu hình retrieval (practice: `POST /incidents/tool_fail/disable`); nếu cần, trả câu trả lời fallback không dùng context thay vì lỗi 500. Xác nhận error rate về dưới 2% và retrieval success trên 90% trong 3 phút.
- Owner: `student-2A202602614`

## Alert 3

- Tên: `CostPerRequestSpike`
- Severity: `warning`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: guardrail `daily_cost_usd_max: 2.5`; chi phí trung bình mỗi `response_sent` (baseline khoảng 0.002 USD)
- Điều kiện và thời gian duy trì: `avg(cost_usd) > 0.005 USD` liên tục 10 phút (khoảng 2.5 lần baseline); dùng chi phí mỗi request để không phụ thuộc lưu lượng
- Ảnh hưởng tới người dùng: người dùng không thấy lỗi ngay, nhưng chi phí vận hành tăng nhanh và có thể vượt ngân sách ngày
- Ba bước kiểm tra đầu tiên:
  1. Metrics: mở panel Cost và Tokens, xem `tokens_out` hay `tokens_in` tăng (practice `cost_spike` làm `tokens_out` tăng khoảng 4 lần).
  2. Logs: lọc `event == "response_sent"`, sắp xếp theo `cost_usd` giảm dần, đối chiếu `tokens_in`/`tokens_out` và `feature` để xem tăng ở một feature hay toàn bộ.
  3. Traces: mở trace theo `correlation_id`, xem observation `generation` (usage input/output, cost) và `prompt_version`; nếu chi phí tăng ngay sau khi đổi prompt thì đó là nguyên nhân.
- Mitigation tạm thời: rollback label `production` về prompt version trước đó; giới hạn độ dài output hoặc chuyển sang model rẻ hơn cho feature bị ảnh hưởng (practice: `POST /incidents/cost_spike/disable`). Xác nhận `avg(cost_usd)` về dưới 0.005.
- Owner: `student-2A202602614`
