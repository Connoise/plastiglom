"""CLI entrypoint: pick the next main exercise and fire it.

Wires together: config -> scheduler -> archiver.on_fire -> telegram notify.
This is deliberately minimal; a real deployment would invoke this from cron
or a systemd timer keyed to PLASTIGLOM_MORNING_FIRE and PLASTIGLOM_EVENING_FIRE,
plus a `--secondaries` pass SECONDARY_DELAY (4h) after each of those to
prompt any connected follow-up exercise.
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from plastiglom.apps.archiver.archiver import Archiver, FireEvent
from plastiglom.apps.memory_indexer import QMDCLIIndexer, StubIndexer
from plastiglom.apps.scheduler.reminders import run_reminders
from plastiglom.apps.scheduler.scheduler import (
    SECONDARY_DELAY,
    FiringClock,
    Scheduler,
    _window_for,
    compute_lock_at,
)
from plastiglom.apps.telegram_bot import format_notification, send_text
from plastiglom.packages.config import load_settings
from plastiglom.packages.core.exercise import (
    ExerciseCategory,
    ExerciseStatus,
    ScheduleWindow,
    active_followups,
)
from plastiglom.packages.vault.markdown import read_markdown_file
from plastiglom.packages.vault.serializers import exercise_from_document, parse_entry

logger = logging.getLogger(__name__)

# Per §7.7: "Maintains enough exercises to fill a week without unintentional
# repeats." We enforce that by excluding the (pool_size - 1) most recent firings
# *of the same window* from selection, so a window rotates through its entire
# pool before any exercise can fire again. The lookback is window-scoped because
# the global lookback used to be eaten by the other window's firings, making
# repeats reappear every ~3-4 days. The cap is a safety net — the active pool
# size is the real bound.
RECENT_FIRINGS_LOOKBACK_CAP = 50

# Per §7.1: at most three secondaries per day. We let at most one fire on
# each `--secondaries` pass so the user isn't blasted with two prompts at
# once; the daily cap still applies across invocations. Secondaries never
# fire together with their parent — each prompts SECONDARY_DELAY after the
# parent main fired.
SECONDARIES_PER_DAY = 3
SECONDARIES_PER_FIRING = 1


def _load_active_main(exercises_dir: Path) -> list:
    main_dir = exercises_dir / "main"
    if not main_dir.exists():
        return []
    pool = []
    for path in sorted(main_dir.glob("*.md")):
        try:
            exercise = exercise_from_document(read_markdown_file(path))
        except Exception as exc:  # pragma: no cover
            logger.warning("skipping exercise %s: %s", path, exc)
            continue
        if exercise.status is ExerciseStatus.ACTIVE and exercise.category is ExerciseCategory.MAIN:
            pool.append(exercise)
    return pool


def _load_active_secondary(exercises_dir: Path) -> list:
    sec_dir = exercises_dir / "secondary"
    if not sec_dir.exists():
        return []
    pool = []
    for path in sorted(sec_dir.glob("*.md")):
        try:
            exercise = exercise_from_document(read_markdown_file(path))
        except Exception as exc:  # pragma: no cover
            logger.warning("skipping exercise %s: %s", path, exc)
            continue
        if (
            exercise.status is ExerciseStatus.ACTIVE
            and exercise.category is ExerciseCategory.SECONDARY
        ):
            pool.append(exercise)
    return pool


def _entries_for_day(entries_root: Path, day: date) -> list:
    """Parse every entry fired on `day`. Reads only the day's directory."""
    day_dir = entries_root / f"{day.year:04d}" / f"{day.month:02d}"
    if not day_dir.exists():
        return []
    entries = []
    for md_path in day_dir.glob(f"{day.day:02d}-*.md"):
        try:
            entries.append(parse_entry(read_markdown_file(md_path)))
        except Exception:
            continue
    return entries


def _recent_main_exercise_ids(
    entries_root: Path,
    *,
    limit: int,
    window: ScheduleWindow | None = None,
    clock: FiringClock | None = None,
) -> set[str]:
    """Return main exercise IDs from the most recent `limit` firings.

    Used to forbid reuse so morning/evening windows don't repeat the same
    exercise within a pool rotation. Secondaries (id prefix `secondary-`) are
    ignored — the secondary picker enforces its own per-day uniqueness.

    When `window` and `clock` are supplied, only firings that fell in that
    window are counted. This is the path the CLI uses so a morning selection
    excludes recent *morning* firings (and likewise for evenings); without the
    window scope, an active evening pool would consume half the lookback and
    let morning exercises repeat after only ~3 days.
    """
    if limit <= 0 or not entries_root.exists():
        return set()
    if (window is None) != (clock is None):
        raise ValueError("window and clock must be provided together")
    fired: list[tuple[datetime, str]] = []
    for md_path in entries_root.rglob("*.md"):
        try:
            entry = parse_entry(read_markdown_file(md_path))
        except Exception:
            continue
        if not entry.exercise_id.startswith("main-"):
            continue
        if window is not None and _window_for(entry.timestamp_fired, clock) is not window:
            continue
        fired.append((entry.timestamp_fired, entry.exercise_id))
    fired.sort(key=lambda r: r[0], reverse=True)
    return {ex_id for _, ex_id in fired[:limit]}


def _window_pool_size(pool: list, window: ScheduleWindow) -> int:
    """Count active mains whose schedule targets `window` (contextual counts for both)."""
    return sum(
        1
        for ex in pool
        if ex.schedule.window is window or ex.schedule.window is ScheduleWindow.CONTEXTUAL
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fire the next main exercise.")
    parser.add_argument("--dry-run", action="store_true", help="Pick but do not write.")
    parser.add_argument(
        "--secondaries",
        action="store_true",
        help=(
            "Run the delayed secondary pass instead of firing a main: prompt "
            "any connected follow-up whose parent fired SECONDARY_DELAY (4h) "
            "ago and hasn't locked yet."
        ),
    )
    parser.add_argument(
        "--remind",
        action="store_true",
        help=(
            "Run the follow-up reminder pass instead of firing: ping any "
            "still-open entry whose lock is within the reminder window."
        ),
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()

    if args.remind:
        return _remind(settings)
    if args.secondaries:
        return _fire_due_secondaries(settings)

    pool = _load_active_main(settings.exercises_dir)
    if not pool:
        logger.error("no active main exercises in %s", settings.exercises_dir)
        return 2

    scheduler = Scheduler(
        clock=FiringClock(settings.morning_fire, settings.evening_fire),
        tz=settings.timezone,
        rng=random.Random(),
    )
    now = datetime.now(tz=settings.timezone)
    upcoming_window = _window_for(now, scheduler.clock)
    # One slot short of the per-window pool: leaves exactly one unseen exercise
    # to fire (or a couple, when the contextual fallback enlarges the pool),
    # which is what "fill a week without unintentional repeats" requires.
    pool_size = _window_pool_size(pool, upcoming_window)
    window_lookback = min(max(pool_size - 1, 0), RECENT_FIRINGS_LOOKBACK_CAP)
    recent_ids = _recent_main_exercise_ids(
        settings.entries_dir,
        limit=window_lookback,
        window=upcoming_window,
        clock=scheduler.clock,
    )
    exercise = scheduler.select_next_main(pool, when=now, recent_ids=recent_ids)
    lock_at = compute_lock_at(now, scheduler.clock, scheduler.tz)

    logger.info("selected exercise=%s lock_at=%s", exercise.id, lock_at.isoformat())

    if args.dry_run:
        return 0

    indexer = (
        QMDCLIIndexer(qmd_bin=settings.qmd_bin, vault_path=settings.vault_path)
        if settings.qmd_bin
        else StubIndexer()
    )

    def _on_change(_path: Path) -> None:
        indexer.reindex()

    archiver = Archiver(settings.vault_path, on_change=_on_change)
    archiver.finalize_prior(now)
    entry = archiver.on_fire(FireEvent(exercise=exercise, fired_at=now, lock_at=lock_at))
    logger.info("fired entry=%s", entry.id)

    # Tell the user up front when this main has a connected follow-up coming
    # (§7.1). Secondaries prompt SECONDARY_DELAY after the parent (via the
    # `--secondaries` pass), so the mention is gated on that moment landing
    # before this entry locks.
    secondary_pool = _load_active_secondary(settings.exercises_dir)
    has_followup = now + SECONDARY_DELAY < lock_at and bool(
        active_followups(exercise.id, secondary_pool)
    )
    _notify_fire(entry, settings, has_followup=has_followup)
    return 0


def _remind(settings) -> int:
    """Run the follow-up reminder heartbeat. No-op without Telegram creds."""
    token = settings.telegram_bot_token
    chat = settings.telegram_chat_id
    if not token or not chat:
        logger.info("reminders skipped: telegram not configured")
        return 0
    now = datetime.now(tz=settings.timezone)
    reminded = run_reminders(
        settings.vault_path,
        now=now,
        web_base_url=settings.web_base_url,
        bot_token=token,
        chat_id=chat,
        window=settings.reminder_window,
    )
    logger.info("reminder pass complete: %d sent", len(reminded))
    return 0


def _notify_fire(entry, settings, *, has_followup: bool = False) -> None:
    """Push a Telegram notification for a freshly fired entry.

    No-op when Telegram is not configured. Send failures are swallowed by
    `send_text`; we only log here so a bad chat-id can't break archival.
    `has_followup` adds a one-line mention that a connected exercise is coming.
    """
    token = settings.telegram_bot_token
    chat = settings.telegram_chat_id
    if not token or not chat:
        return
    notif = format_notification(entry, settings.web_base_url, has_followup=has_followup)
    text = f"{notif.title}\n\n{notif.body}"
    ok = send_text(text, bot_token=token, chat_id=chat)
    if not ok:
        logger.warning("telegram notify failed for entry=%s", entry.id)


def _fire_due_secondaries(settings, *, now: datetime | None = None) -> int:
    """Pick and fire context-triggered secondaries that have come due.

    A secondary prompts the user SECONDARY_DELAY (4h) after its parent main
    fired — never in the same breath as the parent. Eligibility: the parent's
    most recent firing is at least SECONDARY_DELAY old, its lock hasn't
    passed, and that firing hasn't produced a secondary yet (so the pass is
    idempotent on a cron tick). The fired secondary inherits the parent's
    `lock_at` so the pair's edits seal together. Capped per-pass and per-day
    per §7.1.

    Intended cron wiring: one invocation SECONDARY_DELAY after each main
    firing time, though a more frequent tick is safe.
    """
    secondary_pool = _load_active_secondary(settings.exercises_dir)
    if not secondary_pool:
        logger.info("no active secondary exercises")
        return 0

    now = now or datetime.now(tz=settings.timezone)
    # Scan today and yesterday: an evening parent's delay window crosses
    # midnight (e.g. 21:00 + 4h = 01:00 next day), so its entry lives in
    # yesterday's slot by the time the secondary comes due.
    recent = _entries_for_day(settings.entries_dir, now.date()) + _entries_for_day(
        settings.entries_dir, now.date() - timedelta(days=1)
    )
    mains: dict = {}
    for entry in recent:
        if not entry.exercise_id.startswith("main-"):
            continue
        seen = mains.get(entry.exercise_id)
        if seen is None or entry.timestamp_fired > seen.timestamp_fired:
            mains[entry.exercise_id] = entry
    fired_secondaries = [e for e in recent if e.exercise_id.startswith("secondary-")]

    # Parents whose current firing already produced a secondary are served.
    parent_of = {ex.id: ex.parent_id for ex in secondary_pool}
    served_parents = set()
    for sec in fired_secondaries:
        parent_id = parent_of.get(sec.exercise_id)
        parent = mains.get(parent_id) if parent_id else None
        if parent is not None and sec.timestamp_fired >= parent.timestamp_fired:
            served_parents.add(parent_id)

    eligible_parents = {
        ex_id
        for ex_id, entry in mains.items()
        if ex_id not in served_parents
        and entry.timestamp_fired + SECONDARY_DELAY <= now < entry.lock_at
    }

    fired_today = {
        e.exercise_id
        for e in fired_secondaries
        if e.timestamp_fired.astimezone(settings.timezone).date() == now.date()
    }
    remaining_today = SECONDARIES_PER_DAY - len(fired_today)
    if not eligible_parents or remaining_today <= 0:
        logger.info("no secondary due")
        return 0

    scheduler = Scheduler(
        clock=FiringClock(settings.morning_fire, settings.evening_fire),
        tz=settings.timezone,
        rng=random.Random(),
    )
    picks = scheduler.select_secondaries(
        secondary_pool,
        when=now,
        eligible_parent_ids=eligible_parents,
        already_fired_secondary_ids={e.exercise_id for e in fired_secondaries},
        max_count=min(SECONDARIES_PER_FIRING, remaining_today),
    )
    if not picks:
        logger.info("no secondary due")
        return 0

    indexer = (
        QMDCLIIndexer(qmd_bin=settings.qmd_bin, vault_path=settings.vault_path)
        if getattr(settings, "qmd_bin", "")
        else StubIndexer()
    )
    archiver = Archiver(settings.vault_path, on_change=lambda _path: indexer.reindex())
    for secondary in picks:
        parent_entry = mains[secondary.parent_id]
        sec_entry = archiver.on_fire(
            FireEvent(exercise=secondary, fired_at=now, lock_at=parent_entry.lock_at)
        )
        logger.info("fired secondary=%s entry=%s", secondary.id, sec_entry.id)
        _notify_fire(sec_entry, settings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
