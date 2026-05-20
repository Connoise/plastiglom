"""Scheduler CLI integration: secondary firing + no-reuse plumbing."""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from plastiglom.apps.archiver.archiver import Archiver, FireEvent
from plastiglom.apps.scheduler.__main__ import (
    SECONDARIES_PER_DAY,
    _fire_eligible_secondaries,
    _load_active_secondary,
    _recent_main_exercise_ids,
    _todays_firings,
)
from plastiglom.apps.scheduler.scheduler import FiringClock, Scheduler
from plastiglom.packages.core.exercise import (
    Exercise,
    ExerciseCategory,
    ExerciseStatus,
    Schedule,
    ScheduleWindow,
    WeightFactors,
)
from plastiglom.packages.vault.markdown import write_markdown_file
from plastiglom.packages.vault.serializers import exercise_to_document


def _make_exercise(
    *,
    id_: str,
    category: ExerciseCategory,
    parent_id: str | None = None,
    window: ScheduleWindow = ScheduleWindow.CONTEXTUAL,
    status: ExerciseStatus = ExerciseStatus.ACTIVE,
) -> Exercise:
    when = datetime(2026, 5, 1, tzinfo=UTC)
    return Exercise(
        id=id_,
        title=id_,
        category=category,
        parent_id=parent_id,
        version=1,
        status=status,
        schedule=Schedule(window=window, weight_factors=WeightFactors()),
        prompts=["q?"],
        tags=[],
        created_at=when,
        created_by="t",
        updated_at=when,
        updated_by="t",
    )


def _seed_exercise_files(exercises_dir: Path, exercises: list[Exercise]) -> None:
    for ex in exercises:
        sub = "main" if ex.category is ExerciseCategory.MAIN else "secondary"
        path = exercises_dir / sub / f"{ex.id}.md"
        write_markdown_file(path, exercise_to_document(ex))


class _StubSettings:
    def __init__(self, vault: Path) -> None:
        self.vault_path = vault
        self.exercises_dir = vault / "exercises"
        self.entries_dir = vault / "entries"
        # Telegram notification path is short-circuited when these are None.
        self.telegram_bot_token = None
        self.telegram_chat_id = None
        self.web_base_url = "http://plastiglom.test"


def test_load_active_secondary_filters_inactive(tmp_path: Path) -> None:
    active = _make_exercise(
        id_="secondary-a",
        category=ExerciseCategory.SECONDARY,
        parent_id="main-a",
    )
    retired = _make_exercise(
        id_="secondary-b",
        category=ExerciseCategory.SECONDARY,
        parent_id="main-a",
        status=ExerciseStatus.RETIRED,
    )
    _seed_exercise_files(tmp_path / "exercises", [active, retired])
    pool = _load_active_secondary(tmp_path / "exercises")
    assert {ex.id for ex in pool} == {"secondary-a"}


def test_todays_firings_partitions_by_prefix(tmp_path: Path, main_exercise: Exercise) -> None:
    archiver = Archiver(tmp_path)
    today_morning = datetime(2026, 5, 14, 7, 30, tzinfo=UTC)
    today_evening = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    yesterday = datetime(2026, 5, 13, 7, 30, tzinfo=UTC)
    lock = today_evening + timedelta(hours=10, minutes=30)

    morning_main = _make_exercise(
        id_="main-morning-intentions",
        category=ExerciseCategory.MAIN,
        window=ScheduleWindow.MORNING,
    )
    secondary = _make_exercise(
        id_="secondary-morning-intentions-recheck",
        category=ExerciseCategory.SECONDARY,
        parent_id="main-morning-intentions",
    )
    archiver.on_fire(FireEvent(exercise=morning_main, fired_at=today_morning, lock_at=lock))
    archiver.on_fire(FireEvent(exercise=secondary, fired_at=today_evening, lock_at=lock))
    archiver.on_fire(FireEvent(exercise=main_exercise, fired_at=yesterday, lock_at=lock))

    mains, secs = _todays_firings(tmp_path / "entries", date(2026, 5, 14))
    assert mains == {"main-morning-intentions"}
    assert secs == {"secondary-morning-intentions-recheck"}


def test_recent_main_excludes_secondary_entries(tmp_path: Path, main_exercise: Exercise) -> None:
    archiver = Archiver(tmp_path)
    fired = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    lock = fired + timedelta(hours=10, minutes=30)
    secondary = _make_exercise(
        id_="secondary-evening-review-deepen",
        category=ExerciseCategory.SECONDARY,
        parent_id="main-evening-review",
    )
    archiver.on_fire(FireEvent(exercise=main_exercise, fired_at=fired, lock_at=lock))
    archiver.on_fire(FireEvent(exercise=secondary, fired_at=fired, lock_at=lock))

    recent = _recent_main_exercise_ids(tmp_path / "entries", limit=7)
    assert recent == {"main-evening-review"}


def test_recent_main_window_scoped_ignores_other_window(tmp_path: Path) -> None:
    """Morning lookup must not be polluted by evening firings (the bug fixed here)."""
    archiver = Archiver(tmp_path)
    lock = datetime(2026, 5, 20, 7, 30, tzinfo=UTC)
    morning_ex = _make_exercise(
        id_="main-morning-intentions",
        category=ExerciseCategory.MAIN,
        window=ScheduleWindow.MORNING,
    )
    evening_ex = _make_exercise(
        id_="main-evening-review",
        category=ExerciseCategory.MAIN,
        window=ScheduleWindow.EVENING,
    )
    # One morning firing on May 14, three evening firings since.
    archiver.on_fire(
        FireEvent(exercise=morning_ex, fired_at=datetime(2026, 5, 14, 7, 30, tzinfo=UTC), lock_at=lock)
    )
    for day in (15, 16, 17):
        archiver.on_fire(
            FireEvent(exercise=evening_ex, fired_at=datetime(2026, 5, day, 21, 0, tzinfo=UTC), lock_at=lock)
        )

    clock = FiringClock(morning=time(7, 30), evening=time(21, 0))

    morning_recent = _recent_main_exercise_ids(
        tmp_path / "entries", limit=6, window=ScheduleWindow.MORNING, clock=clock
    )
    evening_recent = _recent_main_exercise_ids(
        tmp_path / "entries", limit=6, window=ScheduleWindow.EVENING, clock=clock
    )
    assert morning_recent == {"main-morning-intentions"}
    assert evening_recent == {"main-evening-review"}


def test_recent_main_validates_window_and_clock_together(tmp_path: Path) -> None:
    """Passing one of (window, clock) without the other is a programmer error."""
    import pytest

    (tmp_path / "entries").mkdir()
    with pytest.raises(ValueError):
        _recent_main_exercise_ids(
            tmp_path / "entries", limit=5, window=ScheduleWindow.MORNING, clock=None
        )


def test_morning_pool_rotates_fully_before_repeating(tmp_path: Path) -> None:
    """The whole morning pool must fire before any morning exercise repeats."""
    from plastiglom.apps.scheduler.__main__ import _window_pool_size

    clock = FiringClock(morning=time(7, 30), evening=time(21, 0))
    scheduler = Scheduler(clock=clock, tz=UTC, rng=random.Random(0))
    archiver = Archiver(tmp_path)

    morning_pool = [
        _make_exercise(
            id_=f"main-morning-{i}",
            category=ExerciseCategory.MAIN,
            window=ScheduleWindow.MORNING,
        )
        for i in range(5)
    ]
    pool = list(morning_pool)
    pool_size = _window_pool_size(pool, ScheduleWindow.MORNING)
    lookback = pool_size - 1

    selections: list[str] = []
    for day in range(1, pool_size + 1):
        when = datetime(2026, 5, day, 7, 30, tzinfo=UTC)
        recent_ids = _recent_main_exercise_ids(
            tmp_path / "entries",
            limit=lookback,
            window=ScheduleWindow.MORNING,
            clock=clock,
        )
        picked = scheduler.select_next_main(pool, when=when, recent_ids=recent_ids)
        selections.append(picked.id)
        archiver.on_fire(FireEvent(exercise=picked, fired_at=when, lock_at=when + timedelta(hours=13, minutes=30)))

    # Every morning exercise fires exactly once over a full rotation.
    assert sorted(selections) == sorted(ex.id for ex in morning_pool)


def test_fire_eligible_secondaries_skips_when_no_parent_today(
    tmp_path: Path, main_exercise: Exercise
) -> None:
    """Morning firing has no prior parent today, so no secondary should fire."""
    secondary = _make_exercise(
        id_="secondary-evening-review-deepen",
        category=ExerciseCategory.SECONDARY,
        parent_id="main-evening-review",
    )
    _seed_exercise_files(tmp_path / "exercises", [secondary])
    settings = _StubSettings(tmp_path)

    scheduler = Scheduler(
        clock=FiringClock(morning=time(7, 30), evening=time(21, 0)),
        tz=UTC,
        rng=random.Random(0),
    )
    archiver = Archiver(tmp_path)
    now = datetime(2026, 5, 14, 7, 30, tzinfo=UTC)

    _fire_eligible_secondaries(
        archiver=archiver,
        scheduler=scheduler,
        settings=settings,
        now=now,
        lock_at=now + timedelta(hours=13, minutes=30),
    )
    # No secondary entry written.
    entries_dir = tmp_path / "entries" / "2026" / "05"
    assert not entries_dir.exists() or not list(entries_dir.glob("*-evening-review-deepen.md"))


def test_fire_eligible_secondaries_fires_one_after_parent(
    tmp_path: Path, main_exercise: Exercise
) -> None:
    """Evening firing after a morning parent should produce a secondary entry."""
    parent_main = _make_exercise(
        id_="main-morning-intentions",
        category=ExerciseCategory.MAIN,
        window=ScheduleWindow.MORNING,
    )
    secondary = _make_exercise(
        id_="secondary-morning-intentions-recheck",
        category=ExerciseCategory.SECONDARY,
        parent_id="main-morning-intentions",
    )
    _seed_exercise_files(tmp_path / "exercises", [parent_main, secondary])
    settings = _StubSettings(tmp_path)

    scheduler = Scheduler(
        clock=FiringClock(morning=time(7, 30), evening=time(21, 0)),
        tz=UTC,
        rng=random.Random(0),
    )
    archiver = Archiver(tmp_path)

    morning = datetime(2026, 5, 14, 7, 30, tzinfo=UTC)
    evening = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    lock = evening + timedelta(hours=10, minutes=30)
    archiver.on_fire(FireEvent(exercise=parent_main, fired_at=morning, lock_at=lock))

    _fire_eligible_secondaries(
        archiver=archiver,
        scheduler=scheduler,
        settings=settings,
        now=evening,
        lock_at=lock,
    )

    sec_entry = tmp_path / "entries" / "2026" / "05" / "14-morning-intentions-recheck.md"
    assert sec_entry.exists()


def test_fire_eligible_secondaries_respects_daily_cap(
    tmp_path: Path, main_exercise: Exercise
) -> None:
    """Once SECONDARIES_PER_DAY has fired, no more should fire."""
    parent_main = _make_exercise(
        id_="main-morning-intentions",
        category=ExerciseCategory.MAIN,
        window=ScheduleWindow.MORNING,
    )
    secondaries = [
        _make_exercise(
            id_=f"secondary-morning-intentions-{i}",
            category=ExerciseCategory.SECONDARY,
            parent_id="main-morning-intentions",
        )
        for i in range(SECONDARIES_PER_DAY + 2)
    ]
    _seed_exercise_files(tmp_path / "exercises", [parent_main, *secondaries])

    settings = _StubSettings(tmp_path)
    archiver = Archiver(tmp_path)
    morning = datetime(2026, 5, 14, 7, 30, tzinfo=UTC)
    lock = morning + timedelta(hours=13, minutes=30)
    archiver.on_fire(FireEvent(exercise=parent_main, fired_at=morning, lock_at=lock))
    # Pre-fire SECONDARIES_PER_DAY secondaries earlier today.
    for i in range(SECONDARIES_PER_DAY):
        archiver.on_fire(
            FireEvent(
                exercise=secondaries[i],
                fired_at=morning + timedelta(minutes=i + 1),
                lock_at=lock,
            )
        )

    scheduler = Scheduler(
        clock=FiringClock(morning=time(7, 30), evening=time(21, 0)),
        tz=UTC,
        rng=random.Random(0),
    )
    evening = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    _fire_eligible_secondaries(
        archiver=archiver,
        scheduler=scheduler,
        settings=settings,
        now=evening,
        lock_at=lock,
    )
    # No new secondary should have been written for the leftover IDs.
    day_dir = tmp_path / "entries" / "2026" / "05"
    leftovers = [
        secondaries[SECONDARIES_PER_DAY].id,
        secondaries[SECONDARIES_PER_DAY + 1].id,
    ]
    for ex_id in leftovers:
        slug = ex_id[len("secondary-") :]
        assert not list(day_dir.glob(f"14-{slug}.md")), f"unexpected fire of {ex_id}"
