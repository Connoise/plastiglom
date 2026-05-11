"""Streak / coverage report.

Entries are constructed in-memory rather than via the archiver so each test
exercises exactly the timestamps / statuses it cares about.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from plastiglom.apps.stats_report import (
    build_report,
    collect_entries,
    compute_streaks,
)
from plastiglom.apps.stats_report.stats import parse_window
from plastiglom.packages.core.entry import Entry, EntryStatus


def _entry(
    *,
    fired: datetime,
    status: EntryStatus,
    exercise_id: str = "main-evening-review",
    response: str = "ok",
    tags: list[str] | None = None,
) -> Entry:
    return Entry(
        id=f"{fired.date().isoformat()}-{exercise_id.split('-', 1)[1]}",
        exercise_id=exercise_id,
        exercise_version=1,
        title=f"{fired.date().isoformat()} - {exercise_id}",
        timestamp_fired=fired,
        timestamp_submitted=fired if status is EntryStatus.SUBMITTED else None,
        lock_at=fired.replace(hour=23, minute=59),
        status=status,
        tags=tags or [],
        prompt_snapshot=["q?"],
        response=response if status is EntryStatus.SUBMITTED else "",
    )


def test_streak_zero_when_last_fire_day_unsubmitted() -> None:
    entries = [
        _entry(fired=datetime(2026, 5, 10, 21, tzinfo=UTC), status=EntryStatus.SUBMITTED),
        _entry(fired=datetime(2026, 5, 11, 21, tzinfo=UTC), status=EntryStatus.NULL),
    ]
    s = compute_streaks(entries, tz=UTC)
    assert s.current == 0
    assert s.longest == 1
    assert s.last_submission_day.isoformat() == "2026-05-10"
    assert s.last_fire_day.isoformat() == "2026-05-11"


def test_streak_consecutive_days_extends() -> None:
    days = ["2026-05-09", "2026-05-10", "2026-05-11"]
    entries = [
        _entry(
            fired=datetime.fromisoformat(d + "T21:00:00+00:00"),
            status=EntryStatus.SUBMITTED,
        )
        for d in days
    ]
    s = compute_streaks(entries, tz=UTC)
    assert s.current == 3
    assert s.longest == 3


def test_longest_streak_across_gaps() -> None:
    submits = ["2026-05-01", "2026-05-02", "2026-05-03", "2026-05-08", "2026-05-09"]
    entries = [
        _entry(
            fired=datetime.fromisoformat(d + "T21:00:00+00:00"),
            status=EntryStatus.SUBMITTED,
        )
        for d in submits
    ]
    s = compute_streaks(entries, tz=UTC)
    assert s.longest == 3
    assert s.current == 2  # 5-08 and 5-09


def test_streak_uses_local_timezone() -> None:
    tokyo = ZoneInfo("Asia/Tokyo")
    # 2026-05-10 22:00 UTC == 2026-05-11 07:00 Tokyo
    e1 = _entry(fired=datetime(2026, 5, 10, 22, tzinfo=UTC), status=EntryStatus.SUBMITTED)
    s_utc = compute_streaks([e1], tz=UTC)
    s_tokyo = compute_streaks([e1], tz=tokyo)
    assert s_utc.last_submission_day.isoformat() == "2026-05-10"
    assert s_tokyo.last_submission_day.isoformat() == "2026-05-11"


def test_streak_handles_no_entries() -> None:
    s = compute_streaks([], tz=UTC)
    assert s.current == 0
    assert s.longest == 0
    assert s.last_submission_day is None
    assert s.last_fire_day is None


def test_per_exercise_coverage_rates() -> None:
    entries = [
        _entry(
            fired=datetime(2026, 5, 1, 21, tzinfo=UTC),
            status=EntryStatus.SUBMITTED,
            exercise_id="main-evening-review",
        ),
        _entry(
            fired=datetime(2026, 5, 2, 21, tzinfo=UTC),
            status=EntryStatus.NULL,
            exercise_id="main-evening-review",
        ),
        _entry(
            fired=datetime(2026, 5, 3, 21, tzinfo=UTC),
            status=EntryStatus.OPENED_UNRESPONDED,
            exercise_id="main-evening-review",
        ),
        _entry(
            fired=datetime(2026, 5, 1, 7, tzinfo=UTC),
            status=EntryStatus.SUBMITTED,
            exercise_id="main-morning-intentions",
        ),
    ]
    report = build_report(entries, tz=UTC)
    evening = report.by_exercise["main-evening-review"]
    assert evening.fired == 3
    assert evening.submitted == 1
    assert abs(evening.submission_rate - 1 / 3) < 1e-9
    assert abs(evening.skip_rate - 2 / 3) < 1e-9
    morning = report.by_exercise["main-morning-intentions"]
    assert morning.submission_rate == 1.0


def test_build_report_filters_by_window() -> None:
    entries = [
        _entry(fired=datetime(2026, 5, 1, tzinfo=UTC), status=EntryStatus.SUBMITTED),
        _entry(fired=datetime(2026, 5, 15, tzinfo=UTC), status=EntryStatus.SUBMITTED),
    ]
    from datetime import date

    report = build_report(
        entries,
        tz=UTC,
        window_start=date(2026, 5, 10),
        window_end=date(2026, 5, 31),
    )
    assert report.entry_count == 1


def test_top_tags_returned_sorted_by_count() -> None:
    entries = [
        _entry(
            fired=datetime(2026, 5, 1, tzinfo=UTC),
            status=EntryStatus.SUBMITTED,
            tags=["reflection", "work"],
        ),
        _entry(
            fired=datetime(2026, 5, 2, tzinfo=UTC),
            status=EntryStatus.SUBMITTED,
            tags=["reflection"],
            exercise_id="main-morning-intentions",
        ),
    ]
    report = build_report(entries, tz=UTC, top_n_tags=5)
    assert report.top_tags[0] == ("reflection", 2)


def test_collect_entries_skips_unparsable(tmp_path) -> None:
    (tmp_path / "entries").mkdir()
    bad = tmp_path / "entries" / "broken.md"
    bad.write_text("not frontmatter", encoding="utf-8")
    assert collect_entries(tmp_path / "entries") == []


def test_collect_entries_returns_empty_when_missing(tmp_path) -> None:
    assert collect_entries(tmp_path / "no-such-dir") == []


def test_parse_window_since_days() -> None:
    from datetime import date

    start, end = parse_window(
        since_days=7, since=None, until=None, today=date(2026, 5, 11)
    )
    # 7-day inclusive window ending today.
    assert end == date(2026, 5, 11)
    assert start == date(2026, 5, 5)


def test_submission_rate_is_zero_when_no_entries() -> None:
    report = build_report([], tz=UTC)
    assert report.entry_count == 0
    assert report.submission_rate == 0.0
