from datetime import UTC, datetime, timedelta

from plastiglom.apps.analyzer.digest import WeeklyDigest, compute_stats, week_bounds
from plastiglom.apps.archiver.archiver import Archiver, FireEvent, SubmitRequest
from plastiglom.packages.core.entry import Entry, EntryStatus


def _entry(exercise_id: str, fired: datetime, response: str, status: EntryStatus) -> Entry:
    return Entry(
        id=f"{fired.date().isoformat()}-{exercise_id.removeprefix('main-')}",
        exercise_id=exercise_id,
        exercise_version=1,
        title="t",
        timestamp_fired=fired,
        timestamp_submitted=fired if response else None,
        timestamp_last_edited=fired if response else None,
        lock_at=fired + timedelta(hours=12),
        status=status,
        tags=["values"],
        prompt_snapshot=["q?"],
        response=response,
    )


def test_compute_stats_counts_by_status_exercise_and_tags():
    fired = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    entries = [
        _entry("main-a", fired, "ten words " * 5, EntryStatus.SUBMITTED),
        _entry("main-a", fired + timedelta(days=1), "", EntryStatus.NULL),
        _entry("main-b", fired + timedelta(days=2), "x", EntryStatus.SUBMITTED),
    ]
    stats = compute_stats(entries)
    assert stats.count_total == 3
    assert stats.count_by_status == {"submitted": 2, "null": 1}
    assert stats.count_by_exercise == {"main-a": 2, "main-b": 1}
    assert dict(stats.top_tags) == {"values": 3}
    # "ten words " * 5 -> 10 tokens; second submitted entry is "x" -> 1 token.
    assert stats.submitted_words == 11


def test_weekly_digest_writes_report_and_stats(vault, main_exercise):
    # Seed two submitted entries via the archiver.
    archiver = Archiver(vault)
    fired1 = datetime(2026, 5, 11, 21, 0, tzinfo=UTC)  # Monday
    fired2 = datetime(2026, 5, 13, 7, 30, tzinfo=UTC)
    for fired in (fired1, fired2):
        archiver.on_fire(
            FireEvent(
                exercise=main_exercise,
                fired_at=fired,
                lock_at=fired + timedelta(hours=12),
            )
        )
        archiver.on_submit(
            SubmitRequest(
                entry_id=f"{fired.date().isoformat()}-evening-review",
                exercise_id=main_exercise.id,
                fired_at=fired,
                response="some content",
                submitted_at=fired + timedelta(minutes=30),
            )
        )

    start, end = week_bounds(fired1.date(), tz=UTC)
    digest = WeeklyDigest(vault_path=vault, router=None)
    out = digest.run(start, end)
    text = out.read_text(encoding="utf-8")
    assert "total entries: 2" in text
    assert "`main-evening-review`: 2" in text
    assert "Themes (Sonnet)" not in text  # router is None -> no LLM themes section


def test_week_bounds_is_monday_to_monday():
    thursday = datetime(2026, 5, 14).date()
    start, end = week_bounds(thursday)
    assert start.weekday() == 0  # Monday
    assert (end - start).days == 7
