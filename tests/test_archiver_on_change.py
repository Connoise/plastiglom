from datetime import UTC, datetime, timedelta
from pathlib import Path

from plastiglom.apps.archiver.archiver import Archiver, FireEvent, SubmitRequest


def test_on_change_fires_for_entry_and_daily_index(vault, main_exercise):
    seen: list[Path] = []
    archiver = Archiver(vault, on_change=seen.append)
    fired = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    archiver.on_fire(
        FireEvent(
            exercise=main_exercise,
            fired_at=fired,
            lock_at=fired + timedelta(hours=10),
        )
    )
    # We should see one entry write + one daily-index write.
    assert any(p.name.endswith("evening-review.md") for p in seen)
    assert any("daily_index" in p.parts for p in seen)


def test_on_change_callback_failure_does_not_break_archive(vault, main_exercise):
    def raising(_p: Path) -> None:
        raise RuntimeError("indexer down")

    archiver = Archiver(vault, on_change=raising)
    fired = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    # Archiver must not propagate the indexer failure.
    archiver.on_fire(
        FireEvent(
            exercise=main_exercise,
            fired_at=fired,
            lock_at=fired + timedelta(hours=10),
        )
    )
    archiver.on_submit(
        SubmitRequest(
            entry_id="2026-05-14-evening-review",
            exercise_id=main_exercise.id,
            fired_at=fired,
            response="ok",
            submitted_at=fired + timedelta(minutes=5),
        )
    )
