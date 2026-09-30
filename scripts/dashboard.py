"""Vẽ dashboard 6 panel từ data/logs.jsonl theo config/dashboard.yaml.

Cần matplotlib + pandas + pyyaml. Cài vào venv riêng, không cài vào .venv của API:
    python -m venv .venv-dash && .venv-dash/bin/pip install matplotlib pandas pyyaml
    .venv-dash/bin/python scripts/dashboard.py --out submission/evidence/11-dashboard-overview.png
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_logs(path: Path) -> pd.DataFrame:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def per_minute(df: pd.DataFrame) -> pd.DataFrame:
    return df.set_index("ts").sort_index()


def threshold_line(ax, panel: dict) -> None:
    th = panel["threshold"]
    ax.axhline(th["value"], color="crimson", linestyle="--", linewidth=1.2,
               label=f"threshold {th['aggregation']} {'≤' if th['operator'] == 'lte' else '≥'} {th['value']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "dashboard.yaml")
    parser.add_argument("--logs", type=Path, default=REPO_ROOT / "data" / "logs.jsonl")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "submission" / "evidence" / "11-dashboard-overview.png")
    args = parser.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))["dashboard"]
    panels = {p["id"]: p for p in cfg["panels"]}
    df = load_logs(args.logs)
    end = df["ts"].max()
    df = df[df["ts"] >= end - pd.Timedelta(minutes=cfg["time_range_minutes"])]
    ts = per_minute(df)

    sent = ts[ts["event"] == "response_sent"]
    recv = ts[ts["event"] == "request_received"]
    failed = ts[ts["event"] == "request_failed"]
    tool = ts[ts["tool_success"].notna()] if "tool_success" in ts else ts.iloc[0:0]

    fig, axes = plt.subplots(2, 3, figsize=(19, 9))
    fig.suptitle(
        f"{cfg['title']} | last {cfg['time_range_minutes']} min | auto-refresh {cfg['refresh_seconds']}s | "
        f"{len(recv)} requests, {len(failed)} errors | UTC",
        fontsize=13,
    )

    # 1. Latency
    p = panels["latency"]; ax = axes[0, 0]
    g = sent["latency_ms"].resample("1min")
    for q, style in ((0.5, "-"), (0.95, "-"), (0.99, ":")):
        ax.plot(g.quantile(q).index, g.quantile(q).values, style, marker="o", ms=3, label=f"P{int(q*100)}")
    tg = sent["ttft_ms"].resample("1min").quantile(0.95)
    ax.plot(tg.index, tg.values, "--", label="TTFT P95")
    threshold_line(ax, p)
    ax.set_title(f"{p['title']} ({p['unit']})")

    # 2. Traffic
    p = panels["traffic"]; ax = axes[0, 1]
    tr = recv["event"].resample("1min").count()
    ax.bar(tr.index, tr.values, width=0.0006, color="tab:blue", label="requests/min")
    threshold_line(ax, p)
    ax.set_title(f"{p['title']} ({p['unit']})")

    # 3. Errors
    p = panels["errors"]; ax = axes[0, 2]
    n_recv = recv["event"].resample("1min").count()
    n_fail = failed["event"].resample("1min").count().reindex(n_recv.index, fill_value=0)
    err = (n_fail / n_recv.where(n_recv > 0) * 100).fillna(0)
    ax.plot(err.index, err.values, marker="o", ms=3, label="error rate %")
    if len(tool):
        ts_rate = tool["tool_success"].astype(float).resample("1min").mean() * 100
        ax.plot(ts_rate.index, ts_rate.values, marker="s", ms=3, label="retrieval success %")
    threshold_line(ax, p)
    ax.set_ylim(-5, 105)
    ax.set_title(f"{p['title']} ({p['unit']})")

    # 4. Cost (cumulative so it compares with the total threshold)
    p = panels["cost"]; ax = axes[1, 0]
    cost = sent["cost_usd"].resample("1min").sum()
    ax.bar(cost.index, cost.values, width=0.0006, label="USD/min")
    ax.plot(cost.index, cost.cumsum().values, "k-", marker="o", ms=3, label="cumulative USD")
    threshold_line(ax, p)
    ax.set_title(f"{p['title']} ({p['unit']}) total={sent['cost_usd'].sum():.4f}")

    # 5. Tokens
    p = panels["tokens"]; ax = axes[1, 1]
    for col in ("tokens_in", "tokens_out"):
        s = sent[col].resample("1min").sum()
        ax.plot(s.index, s.values, marker="o", ms=3, label=f"{col}/min")
    total = sent[["tokens_in", "tokens_out"]].sum()
    threshold_line(ax, p)
    ax.set_title(f"{p['title']} ({p['unit']}) in={int(total.tokens_in)} out={int(total.tokens_out)}")

    # 6. Quality
    p = panels["quality"]; ax = axes[1, 2]
    q = sent["quality_score"].resample("1min").mean()
    ax.plot(q.index, q.values, marker="o", ms=3, label="mean quality")
    threshold_line(ax, p)
    ax.set_ylim(0, 1.05)
    ax.set_title(f"{p['title']} ({p['unit']}) mean={sent['quality_score'].mean():.2f}")

    for ax in axes.flat:
        ax.legend(fontsize=8, loc="best")
        ax.grid(alpha=0.3)
        ax.tick_params(axis="x", labelrotation=30, labelsize=8)
        ax.set_xlim(df["ts"].min() - pd.Timedelta(minutes=1), end + pd.Timedelta(minutes=1))
        ax.xaxis.set_major_locator(matplotlib.dates.AutoDateLocator(minticks=4, maxticks=8))
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%H:%M"))

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=110)
    print(f"Đã ghi {args.out}")
    print(sent["latency_ms"].describe(percentiles=[0.5, 0.95, 0.99]).round(1).to_string())
    print("retrieval success %:", round(tool["tool_success"].astype(float).mean() * 100, 1) if len(tool) else "n/a")


if __name__ == "__main__":
    main()
