"""Job registry + dispatch loop for the LLM scheduler.

Jobs are pure registrations: a name, a cadence rule, and a `run(context)`
callable. The runner asks each job whether its most recent canonical tick
is later than the last persisted fire; if so, it executes the callable and
records the new `last_run_at`. Failures don't poison the state — the job's
`last_run_at` is only advanced on success, so the next cron tick will retry.

On-demand execution stays available through:
  - the existing per-app CLIs (`plastiglom-analyzer`, `plastiglom-meta`)
  - this scheduler's `force <job>` subcommand, which bypasses the cadence
    check and runs a registered job immediately (and updates state).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from plastiglom.apps.analyzer.analyzer import (
    AnalysisRequest,
    Analyzer,
)
from plastiglom.apps.analyzer.analyzer import (
    Cadence as AnalyzerCadence,
)
from plastiglom.apps.analyzer.digest import WeeklyDigest
from plastiglom.apps.analyzer.digest import week_bounds as digest_week_bounds
from plastiglom.apps.llm_scheduler.cadence import Cadence, MonthlyDay, Weekly
from plastiglom.apps.llm_scheduler.state import load_state, save_state
from plastiglom.apps.meta_engine.blind_spots import detect_blind_spots
from plastiglom.apps.meta_engine.generator import Generator
from plastiglom.apps.meta_engine.proposals import load_active_pool
from plastiglom.packages.config import Settings
from plastiglom.packages.llm.router import LLMRouter

logger = logging.getLogger(__name__)


@dataclass
class JobContext:
    """Everything a job needs at run time. Built once per scheduler tick."""

    settings: Settings
    router: LLMRouter
    now: datetime


@dataclass
class Job:
    name: str
    description: str
    cadence: Cadence
    run: Callable[[JobContext], None]


@dataclass
class JobResult:
    name: str
    fired: bool
    skipped_reason: str | None = None
    error: str | None = None
    ran_at: datetime | None = None


@dataclass
class SchedulerReport:
    now: datetime
    results: list[JobResult] = field(default_factory=list)

    @property
    def fired(self) -> list[JobResult]:
        return [r for r in self.results if r.fired]

    @property
    def errors(self) -> list[JobResult]:
        return [r for r in self.results if r.error is not None]


# ---------------------------------------------------------------------------
# Job implementations
# ---------------------------------------------------------------------------


def _run_weekly_digest(ctx: JobContext) -> None:
    """Sonnet weekly digest over the most recently completed ISO week."""
    today = ctx.now.astimezone(ctx.settings.timezone).date()
    # Anchor on yesterday so we always cover a fully elapsed week.
    start, end = digest_week_bounds(today - timedelta(days=1))
    digest = WeeklyDigest(vault_path=ctx.settings.vault_path, router=ctx.router)
    path = digest.run(start, end)
    logger.info("weekly digest wrote %s", path)


def _run_analyzer_weekly(ctx: JobContext) -> None:
    """Opus weekly analysis over the most recently completed ISO week."""
    today = ctx.now.astimezone(ctx.settings.timezone).date()
    from plastiglom.apps.analyzer.analyzer import week_bounds

    start, end = week_bounds(today - timedelta(days=1))
    analyzer = Analyzer(vault_path=ctx.settings.vault_path, router=ctx.router)
    report = analyzer.run(
        AnalysisRequest(
            cadence=AnalyzerCadence.WEEKLY,
            window_start=start,
            window_end=end,
        )
    )
    logger.info("weekly analysis wrote %s", report)


def _run_analyzer_monthly(ctx: JobContext) -> None:
    """Opus monthly analysis — also drives proposal generation via meta_generator.

    Per §9 Phase 4 / analyzer.py:129, a monthly run automatically invokes the
    blind-spot detector when a Generator is wired in. That is the canonical
    coupling and we preserve it here, so a scheduled monthly fire produces
    both the analysis report and a fresh batch of pending proposals.
    """
    local_today = ctx.now.astimezone(ctx.settings.timezone).date()
    # Window is the previous calendar month in the user's local zone.
    first_of_this_month = local_today.replace(day=1)
    last_of_prev = first_of_this_month - timedelta(days=1)
    start_local = date(last_of_prev.year, last_of_prev.month, 1)
    start = datetime.combine(start_local, datetime.min.time(), tzinfo=UTC)
    end = datetime.combine(first_of_this_month, datetime.min.time(), tzinfo=UTC)

    meta_generator = Generator(router=ctx.router, vault_path=ctx.settings.vault_path)
    analyzer = Analyzer(
        vault_path=ctx.settings.vault_path,
        router=ctx.router,
        meta_generator=meta_generator,
    )
    report = analyzer.run(
        AnalysisRequest(
            cadence=AnalyzerCadence.MONTHLY,
            window_start=start,
            window_end=end,
        )
    )
    logger.info("monthly analysis wrote %s", report)


# How many days back the standalone blind-spots pass scans. Matches the
# DEFAULT_BLIND_SPOTS_DAYS constant in apps.meta_engine.__main__.
BLIND_SPOTS_WINDOW_DAYS = 30


def _run_meta_blind_spots(ctx: JobContext) -> None:
    """Standalone proposal-generation pass.

    The monthly analyzer also triggers blind-spot detection automatically;
    this is a separate scheduled fire so that proposal generation remains on
    a cadence even if monthly Opus analysis is skipped, and so the meta-
    engine produces fresh proposals halfway through the month.
    """
    pool = load_active_pool(ctx.settings.exercises_dir)
    if not pool:
        logger.warning("blind-spots: no active exercises in %s", ctx.settings.exercises_dir)
        return
    end = ctx.now.astimezone(UTC)
    start = end - timedelta(days=BLIND_SPOTS_WINDOW_DAYS)
    generator = Generator(router=ctx.router, vault_path=ctx.settings.vault_path)
    records = detect_blind_spots(
        generator=generator,
        vault_path=ctx.settings.vault_path,
        pool=pool,
        window_start=start,
        window_end=end,
        dry_run=False,
    )
    logger.info("blind-spots filed %d proposal(s)", len(records))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def build_default_jobs(settings: Settings) -> list[Job]:
    """Construct the default LLM job registry.

    Defaults follow DESIGN.md §7.6:
      - digest_weekly: Sunday 22:00 local
      - analyzer_weekly: Sunday 22:30 local (after digest finishes)
      - analyzer_monthly: last day of the month at 23:00 local
      - meta_blind_spots: 15th of the month at 04:00 local
    """
    tz = settings.timezone
    return [
        Job(
            name="digest_weekly",
            description="Sonnet weekly digest (§9 Phase 2)",
            cadence=Weekly(weekday=6, at=_t(settings.digest_weekly_at), tz=tz),
            run=_run_weekly_digest,
        ),
        Job(
            name="analyzer_weekly",
            description="Opus weekly analysis (§7.6)",
            cadence=Weekly(weekday=6, at=_t(settings.analyzer_weekly_at), tz=tz),
            run=_run_analyzer_weekly,
        ),
        Job(
            name="analyzer_monthly",
            description="Opus monthly analysis + blind-spot proposals (§7.6, §7.7)",
            cadence=MonthlyDay(day=-1, at=_t(settings.analyzer_monthly_at), tz=tz),
            run=_run_analyzer_monthly,
        ),
        Job(
            name="meta_blind_spots",
            description="Standalone meta-engine proposal pass (§7.7)",
            cadence=MonthlyDay(day=15, at=_t(settings.meta_blind_spots_at), tz=tz),
            run=_run_meta_blind_spots,
        ),
    ]


def _t(value: object) -> datetime.time:
    """Coerce a `time` or `HH:MM` string into a `datetime.time`."""
    from datetime import time as _time

    if isinstance(value, _time):
        return value
    if isinstance(value, str):
        hh, mm = value.split(":", 1)
        return _time(int(hh), int(mm))
    raise TypeError(f"unsupported time value: {value!r}")


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def is_due(job: Job, *, now: datetime, last_run: datetime | None) -> bool:
    """A job is due when the most recent canonical tick hasn't been run yet."""
    tick = job.cadence.previous_tick(now)
    if last_run is None:
        return True
    return tick > last_run


def run_due(
    jobs: list[Job],
    *,
    settings: Settings,
    router: LLMRouter,
    now: datetime,
    state: dict[str, datetime] | None = None,
    only: set[str] | None = None,
    state_dir: Path | None = None,
) -> SchedulerReport:
    """Fire every job whose cadence has ticked since its last run.

    If `state` is omitted it is loaded (and re-saved) from `state_dir`
    (defaults to the settings' logs dir). Pass `only` to restrict the pass
    to a subset of job names — useful for tests and for `--only`.
    """
    target_dir = state_dir or settings.logs_dir
    own_state = state is None
    state = state if state is not None else load_state(target_dir)
    report = SchedulerReport(now=now)

    for job in jobs:
        if only is not None and job.name not in only:
            continue
        last = state.get(job.name)
        if not is_due(job, now=now, last_run=last):
            report.results.append(
                JobResult(name=job.name, fired=False, skipped_reason="not due")
            )
            continue
        result = _execute(job, settings=settings, router=router, now=now)
        report.results.append(result)
        if result.fired:
            state[job.name] = now

    if own_state:
        save_state(target_dir, state)
    return report


def force_run(
    jobs: list[Job],
    name: str,
    *,
    settings: Settings,
    router: LLMRouter,
    now: datetime,
    state_dir: Path | None = None,
) -> JobResult:
    """Run a single named job immediately and update its last_run_at."""
    job = next((j for j in jobs if j.name == name), None)
    if job is None:
        raise KeyError(f"unknown job: {name!r}")
    target_dir = state_dir or settings.logs_dir
    state = load_state(target_dir)
    result = _execute(job, settings=settings, router=router, now=now)
    if result.fired:
        state[job.name] = now
        save_state(target_dir, state)
    return result


def _execute(
    job: Job, *, settings: Settings, router: LLMRouter, now: datetime
) -> JobResult:
    ctx = JobContext(settings=settings, router=router, now=now)
    logger.info("firing job %s", job.name)
    try:
        job.run(ctx)
    except Exception as exc:  # surfaced; state is left untouched so we retry
        logger.exception("job %s failed", job.name)
        return JobResult(name=job.name, fired=False, error=str(exc), ran_at=now)
    return JobResult(name=job.name, fired=True, ran_at=now)
