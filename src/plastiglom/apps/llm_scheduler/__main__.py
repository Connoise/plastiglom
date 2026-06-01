"""CLI for the LLM scheduler.

  python -m plastiglom.apps.llm_scheduler run            # fire any due jobs
  python -m plastiglom.apps.llm_scheduler run --only X   # restrict to one job
  python -m plastiglom.apps.llm_scheduler run --dry-run  # report only
  python -m plastiglom.apps.llm_scheduler force <name>   # run a single job now
  python -m plastiglom.apps.llm_scheduler status         # show registry + state
  python -m plastiglom.apps.llm_scheduler list           # show registry only

`run` is the cron-facing form: schedule it frequently (hourly is plenty) and
the runner will execute each job at most once per canonical tick. `force` and
the existing per-app CLIs remain for on-demand execution.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime

from plastiglom.apps.llm_scheduler.runner import (
    Job,
    SchedulerReport,
    build_default_jobs,
    build_telegram_notifier,
    force_run,
    is_due,
    run_due,
)
from plastiglom.apps.llm_scheduler.state import load_state
from plastiglom.packages.config import Settings, load_settings
from plastiglom.packages.llm.router import LLMRouter

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run scheduled LLM jobs.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Fire any jobs whose cadence has ticked.")
    run.add_argument(
        "--only",
        action="append",
        default=None,
        help="Restrict this pass to the named job (repeatable).",
    )
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would fire without executing or persisting state.",
    )

    force = sub.add_parser(
        "force", help="Run a named job immediately, ignoring its cadence."
    )
    force.add_argument("name")

    sub.add_parser("status", help="Show each job's schedule, last run, and next run.")
    sub.add_parser("list", help="List registered jobs (registry only).")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = load_settings()
    jobs = build_default_jobs(settings)

    if args.command == "list":
        return _cmd_list(jobs)
    if args.command == "status":
        return _cmd_status(jobs, settings)
    if args.command == "run":
        return _cmd_run(jobs, settings, only=args.only, dry_run=args.dry_run)
    if args.command == "force":
        return _cmd_force(jobs, settings, name=args.name)

    parser.error(f"unknown command {args.command!r}")
    return 2


def _cmd_list(jobs: list[Job]) -> int:
    for job in jobs:
        print(f"{job.name}\t{job.cadence.describe()}\t{job.description}")
    return 0


def _cmd_status(jobs: list[Job], settings: Settings) -> int:
    now = datetime.now(tz=settings.timezone)
    state = load_state(settings.logs_dir)
    rows = []
    for job in jobs:
        last = state.get(job.name)
        rows.append(
            {
                "name": job.name,
                "cadence": job.cadence.describe(),
                "last_run": last.isoformat() if last else None,
                "previous_tick": job.cadence.previous_tick(now).isoformat(),
                "next_tick": job.cadence.next_tick(now).isoformat(),
                "due_now": is_due(job, now=now, last_run=last),
            }
        )
    print(json.dumps(rows, indent=2))
    return 0


def _cmd_run(
    jobs: list[Job], settings: Settings, *, only: list[str] | None, dry_run: bool
) -> int:
    now = datetime.now(tz=settings.timezone)
    if dry_run:
        state = load_state(settings.logs_dir)
        due_now = [j.name for j in jobs if is_due(j, now=now, last_run=state.get(j.name))]
        if only:
            due_now = [n for n in due_now if n in set(only)]
        print(json.dumps({"now": now.isoformat(), "would_fire": due_now}, indent=2))
        return 0
    router = _build_router(settings)
    report = run_due(
        jobs,
        settings=settings,
        router=router,
        now=now,
        only=set(only) if only else None,
        notifier=build_telegram_notifier(settings),
    )
    _print_report(report)
    return 0 if not report.errors else 1


def _cmd_force(jobs: list[Job], settings: Settings, *, name: str) -> int:
    router = _build_router(settings)
    now = datetime.now(tz=settings.timezone)
    try:
        result = force_run(
            jobs,
            name,
            settings=settings,
            router=router,
            now=now,
            notifier=build_telegram_notifier(settings),
        )
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if result.error:
        print(f"job {result.name} failed: {result.error}", file=sys.stderr)
        return 1
    print(f"fired {result.name} at {result.ran_at}")
    return 0


def _build_router(settings: Settings) -> LLMRouter:
    return LLMRouter(
        sonnet_model=settings.model_sonnet,
        opus_model=settings.model_opus,
        api_key=settings.anthropic_api_key,
        usage_log_path=settings.logs_dir / "llm_usage.jsonl",
        thinking_budget_tokens=settings.thinking_budget_tokens,
    )


def _print_report(report: SchedulerReport) -> None:
    summary = {
        "now": report.now.isoformat(),
        "results": [
            {
                "name": r.name,
                "fired": r.fired,
                "skipped_reason": r.skipped_reason,
                "error": r.error,
                "ran_at": r.ran_at.isoformat() if r.ran_at else None,
            }
            for r in report.results
        ],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    sys.exit(main())
