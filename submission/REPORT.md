# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên: Ngô Lê Thuỷ Tiên**
- **MSSV: 2A202602614**
- **Lớp:** K4-L3B
- **Repository URL: https://github.com/tiennl/K4-L3-DAY13-NgoLeThuyTien-2A202602614-Monitoring-LLMOps**
- **Commit SHA cuối:**
- **Challenge ID:**
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602614`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08a-trace-metadata.png` (lab-agent-run), `evidence/08b-generation-prompt-link.png` (generation, link prompt) |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10a-promote-production-v2.png` (sau promote), `evidence/10b-rollback-production-v1.png` (sau rollback) |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 (21 log, thiếu required fields/context, 0 correlation ID) | 100/100 | 0 record thiếu field, 10 correlation ID |
| `validate_dashboard.py` | 6/6 (contract starter, chưa có dữ liệu) | HỢP LỆ: 6/6 panel | Đã dựng dashboard có dữ liệu thật, evidence 11 |
| `pytest` | | | |
| Số traces hợp lệ | 0 (chưa có retrieval/generation) | 51 trace đủ cây (48 có prompt link) | Kiểm tra bằng Langfuse observations API |
| Số PII leak | 0 | 0 | Log runtime chỉ còn `[REDACTED_*]` |
| Latency P95 / TTFT P95 | | P95 162 ms (P50 159 ms, P99 883 ms) | 43 request, không bật incident; TTFT P95 khoảng 50-55 ms |
| Retrieval success rate | | 100% | 43/43 response_sent có tool_success=true |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `CorrelationIdMiddleware` (`app/middleware.py`) gọi `clear_contextvars()` đầu mỗi request, nhận header `x-request-id` hoặc sinh `req-<8 hex>`, bind vào structlog contextvars và `request.state`, rồi trả lại qua header `x-request-id` cùng `x-response-time-ms`. ID dùng cho evidence 04: `req-cp2link01` (evidence 05: `req-cp1pii02`).
- **Các metadata được ghi vào structured log:** `ts`, `level`, `event`, `correlation_id`, `user_id_hash` (SHA-256 cắt 12 ký tự), `session_id`, `feature`, `model`, `env`; `response_sent` thêm `latency_ms`, `ttft_ms`, `tokens_in/out`, `cost_usd`, `quality_score`. Các field context được bind trong `app/main.py` trước log `request_received`.
- **Cách bảo đảm PII được scrub trước khi ghi:** processor `scrub_event` được đăng ký trong `app/logging_config.py` trước `JsonlFileProcessor`, nên payload và event đã được che trước khi ghi file/render JSON. `app/pii.py` che email, điện thoại VN, CCCD, thẻ và passport.
- **Cách kiểm chứng kết quả:** `validate_logs.py` từ 30/100 lên 100/100 (0 PII leak, 10 correlation ID khác nhau); `tests/test_pii.py` có test CCCD, thẻ, passport; gửi request chứa PII giả và thấy log hiện `[REDACTED_*]` (evidence 05).

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Mở project `day13-k4-l3b-2A202602614`, lọc Metadata `correlation_id` = `req-cp2link01`; các trace có `correlation_id` trùng với log local do tôi tự chạy `load_test.py` và request tay. Đếm bằng Langfuse observations API: 51 trace đủ cây, hơn 10 yêu cầu.
- **Cấu trúc root/retrieval/generation observations:** `day13-agent-request` (trace) → `lab-agent-run` (agent) → `retrieval` (retriever, `@observe` trên `retrieve`) và `generation` (generation, `@observe` trên `FakeLLM.generate`). Generation có `model`, `usage_details` (input/output), `cost_details` và link prompt qua `propagate_attributes(prompt=...)`. Tất cả `capture_input=False`, `capture_output=False` nên không có raw input/output.
- **Cách nối trace với log:** `correlation_id` (do middleware sinh/nhận) nằm trong metadata của trace và trong mọi dòng log. Ví dụ `req-cp2link01` ↔ trace `25c02ddaafb30251e4afaba59638282d` (evidence 04, 07, 08).
- **Prompt name:** `day13-chat` (text prompt, ba biến `{{feature}}`, `{{docs}}`, `{{message}}`)
- **Version/label baseline:** v1, labels `baseline` + `production`
- **Version/label candidate:** v2, label `candidate` (thêm dòng "Trả lời ngắn gọn."); `latest` do Langfuse tự gắn
- **Trace ID của mỗi version:** v1 (`baseline`): `ab8f7a455c51766fe08a4cd8294bc24f`; v2 (`candidate`): `3346641ad0a67a6bb31a747a985055a0`. Cả hai có `prompt_name`, `prompt_label`, `prompt_version` đúng trong metadata và generation link tới đúng version.
- **Cách promote và rollback `production`:** Không sửa code, chỉ dời label. Promote: `production` → v2, restart API, request `req-cp2-promote` cho `prompt_version=2`. Rollback: `production` → v1, restart, request `req-cp2-rollback` cho `prompt_version=1`. Mỗi lần restart API chờ vài giây sau request cuối để trace kịp gửi. Trạng thái cuối: `production` → v1.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `scripts/dashboard.py` (matplotlib, venv riêng) đọc `data/logs.jsonl` theo `config/dashboard.yaml`: Latency (P50/P95/P99 + TTFT P95), Traffic, Errors (error rate + retrieval success), Cost, Tokens, Quality; mỗi panel có đơn vị, time range 60 phút và đường threshold. Evidence 11: 43 request rải trong 10 phút, 0 lỗi. Retrieval success tính trên mọi event có `tool_success`.
- **SLO và lý do chọn:** 99.5% request `response_sent` với `latency_ms <= 2000` trong 28 ngày. Ngưỡng starter 3000ms quá rộng: `rag_slow` chỉ làm latency khoảng 2.7s nên vẫn "đạt". Baseline của tôi P95 162ms, P99 883ms nên 2000ms không báo nhầm mà vẫn bắt được `rag_slow`. Đã hạ cả threshold panel Latency xuống 2000.
- **Cách tính error budget:** 0.5% của tổng request. 10,000 request → 50 request được phép chậm hơn 2000ms hoặc lỗi; 1,000 request → 5; ở quy mô lab khoảng 100 request thì dưới 1, nghĩa là một request lỗi đã dùng hết budget.
- **Ba alert và runbook tương ứng:** `HighLatencyP95` (P95 > 2000ms, 5m, warning), `HighErrorRateOrRetrievalFailure` (error rate > 2% hoặc retrieval success < 90%, 3m, critical), `CostPerRequestSpike` (avg cost > 0.005 USD, 10m, warning; baseline khoảng 0.002). Cấu hình ở `config/alert_rules.yaml`, runbook Metrics → Logs → Traces và mitigation ở `docs/alerts.md#alert-1..3`; kênh Slack `#k4-l3b-alerts`, owner `student-2A202602614`.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:**
- **Khoảng thời gian điều tra:**
- **Triệu chứng từ metrics:**
- **Log line và correlation ID liên quan:**
- **Trace ID và span gây ảnh hưởng:**
- **Root cause:**
- **Fix action:**
- **Preventive measure:**

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
- **Một lỗi/blocker đã gặp:**
- **Cách tìm nguyên nhân và xử lý:**
- **Cách hiểu luồng Metrics → Logs → Traces:**
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
- **Điều quan trọng nhất đã học:**
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
