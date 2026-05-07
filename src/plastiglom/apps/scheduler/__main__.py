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
from datetime import datetime
from pathlib import Path

from plastiglom.apps.archiver.archiver import Archiver, FireEvent
from plastiglom.apps.memory_indexer import QMDCLIIndexer, StubIndexer
from plastiglom.apps.scheduler.scheduler import FiringClock, Scheduler, compute_lock_at
from plastiglom.packages.config import load_settings
from plastiglom.packages.core.exercise import ExerciseCategory, ExerciseStatus
from plastiglom.packages.vault.markdown import read_markdown_file
from plastiglom.packages.vault.serializers import exercise_from_document, parse_entry

logger = logging.getLogger(__name__)

# Span of recent firings used to suppress unintentional repeats. With the pool
# sized to fill a week of 2x-daily firings (§7.7), 7 covers the most recent
# ~3-4 days and still leaves ample candidates for the weighted draw.
RECENT_FIRINGS_LOOKBACK = 7


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
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
