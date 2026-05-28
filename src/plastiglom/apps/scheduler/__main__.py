"""CLI entrypoint: pick the next main exercise and fire it.

Wires together: config -> scheduler -> archiver.on_fire -> telegram notify.
This is deliberately minimal; a real deployment would invoke this from cron
or a systemd timer keyed to PLASTIGLOM_MORNING_FIRE and PLASTIGLOM_EVENING_FIRE.
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
from datetime import date, datetime
from pathlib import Path

from plastiglom.apps.archiver.archiver import Archiver, FireEvent
from plastiglom.apps.memory_indexer import QMDCLIIndexer, StubIndexer
from plastiglom.apps.scheduler.reminders import run_reminders
from plastiglom.apps.scheduler.scheduler import FiringClock, Scheduler, compute_lock_at
from plastiglom.apps.telegram_bot import format_notification, send_text
from plastiglom.packages.config import load_settings
from plastiglom.packages.core.exercise import (
    ExerciseCategory,
    ExerciseStatus,
    active_followups,
)
from plastiglom.packages.vault.markdown import read_markdown_file
from plastiglom.packages.vault.serializers import exercise_from_document, parse_entry

logger = logging.getLogger(__name__)

# Span of recent firings used to suppress unintentional repeats. With the pool
# sized to fill a week of 2x-daily firings (§7.7), 7 covers the most recent
# ~3-4 days and still leaves ample candidates for the weighted draw.
RECENT_FIRINGS_LOOKBACK = 7

# Per §7.1: at most three secondaries per day. We let at most one fire on
# each scheduler invocation so the user isn't blasted with two prompts at
# once; the daily cap still applies across invocations.
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


def _todays_firings(entries_root: Path, day: date) -> tuple[set[str], set[str]]:
    """Return (main_ids_fired_today, secondary_ids_fired_today).

    Used to gate secondary picks: a secondary is only eligible if its parent
    main has already fired today, and we never fire the same secondary twice.
    Reads only the day's directory rather than the full tree.
    """
    main_ids: set[str] = set()
    sec_ids: set[str] = set()
    day_dir = (
        entries_root / f"{day.year:04d}" / f"{day.month:02d}"
    )
    if not day_dir.exists():
        return main_ids, sec_ids
    for md_path in day_dir.glob(f"{day.day:02d}-*.md"):
        try:
            entry = parse_entry(read_markdown_file(md_path))
        except Exception:
            continue
        if entry.exercise_id.startswith("main-"):
            main_ids.add(entry.exercise_id)
        elif entry.exercise_id.startswith("secondary-"):
            sec_ids.add(entry.exercise_id)
    return main_ids, sec_ids


def _recent_main_exercise_ids(entries_root: Path, *, limit: int) -> set[str]:
    """Return main exercise IDs from the most recent `limit` firings.

    Used to forbid reuse so morning/evening windows don't repeat the same
    exercise back-to-back. Secondaries (id prefix `secondary-`) are ignored —
    the secondary picker enforces its own per-day uniqueness.
    """
    if limit <= 0 or not entries_root.exists():
        return set()
    fired: list[tuple[datetime, str]] = []
    for md_path in entries_root.rglob("*.md"):
        try:
            entry = parse_entry(read_markdown_file(md_path))
        except Exception:
            continue
        if entry.exercise_id.startswith("main-"):
            fired.append((entry.timestamp_fired, entry.exercise_id))
    fired.sort(key=lambda r: r[0], reverse=True)
    return {ex_id for _, ex_id in fired[:limit]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fire the next main exercise.")
    parser.add_argument("--dry-run", action="store_true", help="Pick but do not write.")
    parser.add_argument(
        "--no-secondaries",
        action="store_true",
        help="Skip the secondary-exercise pass after firing the main.",
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
    recent_ids = _recent_main_exercise_ids(
        settings.entries_dir, limit=RECENT_FIRINGS_LOOKBACK
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

    # Tell the user up front when this main has a connected follow-up that
    # may fire later today (§7.1). Loaded once and reused by the secondary pass.
    # A secondary only fires while its parent's firing day is still going, so
    # the mention is gated on the entry locking later the *same* day it fired
    # (true for morning firings, false for evening ones that lock next morning).
    secondary_pool = _load_active_secondary(settings.exercises_dir)
    followup_possible_today = lock_at.date() == now.date()
    has_followup = followup_possible_today and bool(
        active_followups(exercise.id, secondary_pool)
    )
    _notify_fire(entry, settings, has_followup=has_followup)

    if not args.no_secondaries:
        _fire_eligible_secondaries(
            archiver=archiver,
            scheduler=scheduler,
            settings=settings,
            now=now,
            lock_at=lock_at,
            secondary_pool=secondary_pool,
        )
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


def _fire_eligible_secondaries(
    *,
    archiver: Archiver,
    scheduler: Scheduler,
    settings,
    now: datetime,
    lock_at: datetime,
    secondary_pool: list | None = None,
) -> None:
    """Pick and fire context-triggered secondaries.

    A secondary fires only when its parent main has already fired earlier
    today. Capped per-firing and per-day per §7.1; lock_at matches the
    main's so the day's edits seal together. `secondary_pool` may be passed
    in to avoid a re-read; when omitted it is loaded from disk.
    """
    if secondary_pool is None:
        secondary_pool = _load_active_secondary(settings.exercises_dir)
    if not secondary_pool:
        return

    parents_fired, secondaries_fired = _todays_firings(settings.entries_dir, now.date())
    remaining_today = SECONDARIES_PER_DAY - len(secondaries_fired)
    if remaining_today <= 0:
        return

    picks = scheduler.select_secondaries(
        secondary_pool,
        when=now,
        parent_ids_fired_today=parents_fired,
        already_fired_secondary_ids=secondaries_fired,
        max_count=min(SECONDARIES_PER_FIRING, remaining_today),
    )
    for secondary in picks:
        sec_entry = archiver.on_fire(
            FireEvent(exercise=secondary, fired_at=now, lock_at=lock_at)
        )
        logger.info("fired secondary=%s entry=%s", secondary.id, sec_entry.id)
        _notify_fire(sec_entry, settings)


if __name__ == "__main__":
    sys.exit(main())
