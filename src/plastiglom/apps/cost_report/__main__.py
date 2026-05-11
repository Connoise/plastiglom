"""CLI for the LLM cost / usage report.

  plastiglom-cost summary                          # totals + breakdowns
  plastiglom-cost summary --since-days 7           # last 7 days only
  plastiglom-cost summary --since 2026-05-01 --until 2026-05-08
  plastiglom-cost summary --json                   # machine-readable
  plastiglom-cost top --by task --limit 5          # top spenders
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from plastiglom.apps.cost_report.report import (
    Report,
    Totals,
    build_report,
    load_usage,
    parse_window,
)
from plastiglom.packages.config import load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plastiglom LLM cost / usage report.")
    sub = parser.add_subparsers(dest="command", required=True)

    def _common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--since-days", type=int, default=None)
        p.add_argument("--since", default=None, help="ISO datetime (UTC if no tz).")
        p.add_argument("--until", default=None, help="ISO datetime (UTC if no tz).")
        p.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
        p.add_argument(
            "--usage-log",
            type=Path,
            default=None,
            help="Override path to llm_usage.jsonl (defaults to <vault>/logs/...).",
        )

    summ = sub.add_parser("summary")
    _common(summ)

    top = sub.add_parser("top")
    _common(top)
    top.add_argument("--by", choices=("task", "model", "day"), default="task")
    top.add_argument("--limit", type=int, default=10)

    args = parser.parse_args(argv)
    settings = load_settings()
    log_path: Path = args.usage_log or (settings.logs_dir / "llm_usage.jsonl")
    records = load_usage(log_path)
    start, end = parse_window(
        since_days=args.since_days, since=args.since, until=args.until
    )
    report = build_report(records, window_start=start, window_end=end)

    if args.command == "summary":
        return _emit_summary(report, log_path, json_out=args.json)
    if args.command == "top":
        return _emit_top(report, by=args.by, limit=args.limit, json_out=args.json)
    parser.error(f"unknown command {args.command!r}")
    return 2


def _emit_summary(report: Report, log_path: Path, *, json_out: bool) -> int:
    if json_out:
        print(json.dumps(_report_to_dict(report, log_path), indent=2, default=_default))
        return 0
    print(f"usage log: {log_path}")
    print(f"window:    {_format_window(report)}")
    print(f"records:   {report.record_count}  (skipped {report.skipped_undated} undated)")
    print()
    _print_totals_row("overall", report.overall)
    print()
    print("by task:")
    for task, t in sorted(report.by_task.items(), key=lambda kv: kv[1].cost_usd, reverse=True):
        _print_totals_row(f"  {task}", t)
    print()
    print("by model:")
    for model, t in sorted(report.by_model.items(), key=lambda kv: kv[1].cost_usd, reverse=True):
        suffix = " (unknown price)" if model in report.unknown_models else ""
        _print_totals_row(f"  {model}{suffix}", t)
    if report.unknown_models:
        print()
        print("WARN: unknown models priced at $0:", ", ".join(sorted(report.unknown_models)))
        print("      set PLASTIGLOM_LLM_PRICES_JSON to supply prices.")
    return 0


def _emit_top(report: Report, *, by: str, limit: int, json_out: bool) -> int:
    if by == "day":
        items: list[tuple[str, Totals]] = [
            (d.isoformat(), t) for d, t in report.by_day.items()
        ]
    elif by == "model":
        items = list(report.by_model.items())
    else:
        items = list(report.by_task.items())
    items.sort(key=lambda kv: kv[1].cost_usd, reverse=True)
    items = items[:limit]
    if json_out:
        print(
            json.dumps(
                [(k, _totals_to_dict(v)) for k, v in items], indent=2, default=_default
            )
        )
        return 0
    print(f"top {len(items)} by {by} (cost USD desc):")
    for key, t in items:
        _print_totals_row(f"  {key}", t)
    return 0


def _format_window(report: Report) -> str:
    if report.window_start is None and report.window_end is None:
        return "all time"
    s = report.window_start.isoformat() if report.window_start else "-inf"
    e = report.window_end.isoformat() if report.window_end else "now"
    return f"{s} .. {e}"


def _print_totals_row(label: str, t: Totals) -> None:
    print(
        f"{label:<36} calls={t.calls:>4} "
        f"in={t.input_tokens:>8} out={t.output_tokens:>7} "
        f"cache_r={t.cache_read_tokens:>8} cache_w={t.cache_creation_tokens:>7} "
        f"cost=${t.cost_usd:>7.4f} "
        f"avg_ms={t.avg_latency_ms:>6.0f} "
        f"cache_hit={t.cache_hit_rate:>5.1%}"
    )


def _totals_to_dict(t: Totals) -> dict:
    return {
        **asdict(t),
        "cache_hit_rate": round(t.cache_hit_rate, 4),
        "avg_latency_ms": round(t.avg_latency_ms, 2),
    }


def _report_to_dict(report: Report, log_path: Path) -> dict:
    return {
        "usage_log": str(log_path),
        "window_start": report.window_start.isoformat() if report.window_start else None,
        "window_end": report.window_end.isoformat() if report.window_end else None,
        "record_count": report.record_count,
        "skipped_undated": report.skipped_undated,
        "unknown_models": sorted(report.unknown_models),
        "overall": _totals_to_dict(report.overall),
        "by_task": {k: _totals_to_dict(v) for k, v in report.by_task.items()},
        "by_model": {k: _totals_to_dict(v) for k, v in report.by_model.items()},
        "by_day": {d.isoformat(): _totals_to_dict(v) for d, v in report.by_day.items()},
    }


def _default(value):  # JSON fallback for date/datetime
    if isinstance(value, datetime | date):
        return value.isoformat()
    raise TypeError(f"unserialisable: {type(value).__name__}")


if __name__ == "__main__":
    sys.exit(main())
