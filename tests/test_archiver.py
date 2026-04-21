from datetime import UTC, datetime, timedelta

import pytest

from plastiglom.apps.archiver.archiver import Archiver, FireEvent, SubmitRequest
from plastiglom.packages.core.entry import EntryStatus
from plastiglom.packages.vault.markdown import read_markdown_file
from plastiglom.packages.vault.serializers import parse_entry


def test_on_fire_writes_opened_unresponded(vault, main_exercise):
    archiver = Archiver(vault)
    fired = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    lock_at = fired + timedelta(hours=10, minutes=30)
    entry = archiver.on_fire(FireEvent(exercise=main_exercise, fired_at=fired, lock_at=lock_at))
    assert entry.status is EntryStatus.OPENED_UNRESPONDED
    assert entry.prompt_snapshot == main_exercise.prompts
    assert entry.timestamp_submitted is None

    # Daily index was updated.
    idx = vault / "daily_index" / "2026" / "05" / "2026-05-14.md"
    assert idx.exists()
    assert "evening-review" in idx.read_text()


def test_submit_before_lock_sets_submitted(vault, main_exercise):
    archiver = Archiver(vault)
    fired = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    lock_at = fired + timedelta(hours=10, minutes=30)
    archiver.on_fire(FireEvent(exercise=main_exercise, fired_at=fired, lock_at=lock_at))

    updated = archiver.on_submit(
        SubmitRequest(
            entry_id="2026-05-14-evening-review",
            exercise_id=main_exercise.id,
            fired_at=fired,
            response="A real response.",
            submitted_at=fired + timedelta(minutes=45),
        )
    )
    assert updated.status is EntryStatus.SUBMITTED
    assert "A real response." in updated.response
    assert updated.timestamp_submitted is not None


def test_submit_after_lock_raises(vault, main_exercise):
    archiver = Archiver(vault)
    fired = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    lock_at = fired + timedelta(hours=1)
    archiver.on_fire(FireEvent(exercise=main_exercise, fired_at=fired, lock_at=lock_at))
    with pytest.raises(ValueError):
        archiver.on_submit(
            SubmitRequest(
                entry_id="2026-05-14-evening-review",
                exercise_id=main_exercise.id,
                fired_at=fired,
                response="Too late.",
                submitted_at=lock_at + timedelta(minutes=1),
            )
        )


def test_finalize_prior_converts_opened_unresponded_to_null(vault, main_exercise):
    archiver = Archiver(vault)
    fired = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    lock_at = fired + timedelta(hours=1)
    archiver.on_fire(FireEvent(exercise=main_exercise, fired_at=fired, lock_at=lock_at))

    touched = archiver.finalize_prior(lock_at + timedelta(minutes=5))
    assert len(touched) == 1

    md = next((vault / "entries" / "2026" / "05").glob("14-*.md"))
    entry = parse_entry(read_markdown_file(md))
    assert entry.status is EntryStatus.NULL


def test_finalize_preserves_submitted(vault, main_exercise):
    archiver = Archiver(vault)
    fired = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    lock_at = fired + timedelta(hours=1)
    archiver.on_fire(FireEvent(exercise=main_exercise, fired_at=fired, lock_at=lock_at))
    archiver.on_submit(
        SubmitRequest(
            entry_id="2026-05-14-evening-review",
            exercise_id=main_exercise.id,
            fired_at=fired,
            response="Written.",
            submitted_at=fired + timedelta(minutes=5),
        )
    )
    touched = archiver.finalize_prior(lock_at + timedelta(minutes=5))
    assert touched == []  # submitted entries are already finalized

    md = next((vault / "entries" / "2026" / "05").glob("14-*.md"))
    entry = parse_entry(read_markdown_file(md))
    assert entry.status is EntryStatus.SUBMITTED
