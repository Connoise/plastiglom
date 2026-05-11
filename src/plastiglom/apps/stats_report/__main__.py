"""CLI for the streak / coverage report.

  plastiglom-stats summary
  plastiglom-stats summary --since-days 30
  plastiglom-stats summary --since 2026-04-01 --until 2026-05-01
  plastiglom-stats summary --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date

from plastiglom.apps.stats_report.stats import (
    ExerciseCoverage,
    StatsReport,
    build_report,
    collect_entries,
    parse_today,
    parse_window,
)
from plastiglom.packages.config import load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plastiglom streak / coverage report.")
    sub = parser.add_subparsers(dest="command", required=True)

    summ = sub.add_parser("summary")
    summ.add_argument("--since-days", type=int, default=None)
    summ.add_argument("--since", default=None, help="Local date YYYY-MM-DD.")
    summ.add_argument("--until", default=None, help="Local date YYYY-MM-DD.")
    summ.add_argument("--today", default=None, help="Override today (YYYY-MM-DD).")
    summ.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    settings = load_settings()
    entries = collect_entries(settings.entries_dir)
    today = parse_today(args.today, settings.timezone)
    start, end = parse_window(
        since_days=args.since_days, since=args.since, until=args.until, today=today
    )
    report = build_report(entries, tz=settings.timezone, window_start=start, window_end=end)

    if args.command == "summary":
        return _emit_summary(report, json_out=args.json)
    parser.error(f"unknown command {args.command!r}")
    return 2


def _emit_summary(report: StatsReport, *, json_out: bool) -> int:
    if json_out:
        print(json.dumps(_report_to_dict(report), indent=2, default=_default))
        return 0
    print(f"window:     {_format_window(report)}")
    print(f"entries:    {report.entry_count}")
    print(
        f"submitted:  {report.submitted_count} "
        f"({report.submission_rate:.1%})"
    )
    print(f"null:       {report.null_count}")
    print(f"open:       {report.open_count}")
    print(f"words:      {report.submitted_words}")
    print()
    s = report.streak
    print(
        f"streak:     current={s.current}d longest={s.longest}d "
        f"submitted-days={s.submission_days} fired-days={s.fire_days}"
    )
    if s.last_submission_day:
        print(f"last submit: {s.last_submission_day.isoformat()}")
    if s.last_fire_day:
        print(f"last fire:   {s.last_fire_day.isoformat()}")
    print()
    print("by exercise (sorted by skip rate desc):")
    rows = sorted(
        report.by_exercise.values(), key=lambda c: c.skip_rate, reverse=True
    )
    for cov in rows:
        _print_coverage(cov)
    if report.top_tags:
        print()
        print("top tags:")
        for tag, count in report.top_tags:
            print(f"  {tag:<24} {count}")
    return 0


def _print_coverage(cov: ExerciseCoverage) -> None:
    print(
        f"  {cov.exercise_id:<34} fired={cov.fired:>3} "
        f"sub={cov.submitted:>3} null={cov.null:>3} open={cov.opened_unresponded:>3} "
        f"sub_rate={cov.submission_rate:>5.1%} skip_rate={cov.skip_rate:>5.1%}"
    )


def _format_window(report: StatsReport) -> str:
    s = report.window_start.isoformat() if report.window_start else "-inf"
    e = report.window_end.isoformat() if report.window_end else "+inf"
    return f"{s} .. {e}"


def _report_to_dict(report: StatsReport) -> dict:
    return {
        "window_start": report.window_start.isoformat() if report.window_start else None,
        "window_end": report.window_end.isoformat() if report.window_end else None,
        "entry_count": report.entry_count,
        "submitted_count": report.submitted_count,
        "null_count": report.null_count,
        "open_count": report.open_count,
        "submitted_words": report.submitted_words,
        "submission_rate": round(report.submission_rate, 4),
        "streak": {
            **asdict(report.streak),
            "last_submission_day": (
                report.streak.last_submission_day.isoformat()
                if report.streak.last_submission_day
                else None
            ),
            "last_fire_day": (
                report.streak.last_fire_day.isoformat()
                if report.streak.last_fire_day
                else None
            ),
        },
        "by_exercise": {
            k: {
                **asdict(v),
                "submission_rate": round(v.submission_rate, 4),
                "skip_rate": round(v.skip_rate, 4),
            }
            for k, v in report.by_exercise.items()
        },
        "by_day": {d.isoformat(): counts for d, counts in report.by_day.items()},
        "top_tags": report.top_tags,
    }


def _default(value):
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"unserialisable: {type(value).__name__}")


if __name__ == "__main__":
    sys.exit(main())
