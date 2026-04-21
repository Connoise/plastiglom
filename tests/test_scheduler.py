import random
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

import pytest

from plastiglom.apps.scheduler.scheduler import (
    FiringClock,
    Scheduler,
    compute_lock_at,
    next_main_firing,
    weight_for,
)
from plastiglom.packages.core.exercise import (
    Exercise,
    ExerciseCategory,
    ExerciseStatus,
    Schedule,
    ScheduleWindow,
    WeightFactors,
)

TZ = ZoneInfo("America/Los_Angeles")
CLOCK = FiringClock(morning=time(7, 30), evening=time(21, 0))


def _ex(id_: str, window: ScheduleWindow, *, weights: WeightFactors | None = None) -> Exercise:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return Exercise(
        id=id_,
        title=id_,
        category=ExerciseCategory.MAIN,
        parent_id=None,
        version=1,
        status=ExerciseStatus.ACTIVE,
        schedule=Schedule(window=window, weight_factors=weights or WeightFactors()),
        prompts=["q?"],
        tags=[],
        created_at=now,
        created_by="t",
        updated_at=now,
        updated_by="t",
    )


def test_next_main_firing_before_morning():
    now = datetime(2026, 5, 14, 6, 0, tzinfo=TZ)
    assert next_main_firing(now, CLOCK, TZ) == datetime(2026, 5, 14, 7, 30, tzinfo=TZ)


def test_next_main_firing_between_windows():
    now = datetime(2026, 5, 14, 12, 0, tzinfo=TZ)
    assert next_main_firing(now, CLOCK, TZ) == datetime(2026, 5, 14, 21, 0, tzinfo=TZ)


def test_next_main_firing_after_evening():
    now = datetime(2026, 5, 14, 22, 0, tzinfo=TZ)
    assert next_main_firing(now, CLOCK, TZ) == datetime(2026, 5, 15, 7, 30, tzinfo=TZ)


def test_compute_lock_at_equals_next_main():
    fired = datetime(2026, 5, 14, 7, 30, tzinfo=TZ)
    assert compute_lock_at(fired, CLOCK, TZ) == datetime(2026, 5, 14, 21, 0, tzinfo=TZ)


def test_select_next_main_respects_window():
    morning_only = _ex("main-morning", ScheduleWindow.MORNING)
    evening_only = _ex("main-evening", ScheduleWindow.EVENING)
    contextual = _ex("main-contextual", ScheduleWindow.CONTEXTUAL)
    scheduler = Scheduler(clock=CLOCK, tz=TZ, rng=random.Random(7))

    morning = datetime(2026, 5, 14, 7, 30, tzinfo=TZ)
    for _ in range(20):
        choice = scheduler.select_next_main(
            [morning_only, evening_only, contextual], when=morning
        )
        assert choice.id in {"main-morning", "main-contextual"}


def test_select_next_main_excludes_recent_ids():
    a = _ex("main-a", ScheduleWindow.MORNING)
    b = _ex("main-b", ScheduleWindow.MORNING)
    scheduler = Scheduler(clock=CLOCK, tz=TZ, rng=random.Random(1))
    morning = datetime(2026, 5, 14, 7, 30, tzinfo=TZ)
    choice = scheduler.select_next_main([a, b], when=morning, recent_ids={"main-a"})
    assert choice.id == "main-b"


def test_select_next_main_raises_when_empty():
    scheduler = Scheduler(clock=CLOCK, tz=TZ, rng=random.Random(0))
    with pytest.raises(RuntimeError):
        scheduler.select_next_main([], when=datetime(2026, 5, 14, 7, 30, tzinfo=TZ))


def test_weight_for_prefers_weekend_factor_on_weekend():
    ex = _ex(
        "main-x",
        ScheduleWindow.EVENING,
        weights=WeightFactors(weekday_weight=0.1, weekend_weight=1.0),
    )
    sunday = datetime(2026, 5, 17, 21, 0, tzinfo=TZ)
    monday = datetime(2026, 5, 18, 21, 0, tzinfo=TZ)
    assert weight_for(ex, sunday) > weight_for(ex, monday)
