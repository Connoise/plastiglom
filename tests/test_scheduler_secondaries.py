import random
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from plastiglom.apps.scheduler.scheduler import FiringClock, Scheduler
from plastiglom.packages.core.exercise import (
    Exercise,
    ExerciseCategory,
    ExerciseStatus,
    Schedule,
    ScheduleWindow,
    WeightFactors,
)

TZ = ZoneInfo("UTC")
CLOCK = FiringClock(morning=time(7, 30), evening=time(21, 0))


def _ex(*, id_, category, parent_id=None, status=ExerciseStatus.ACTIVE) -> Exercise:
    when = datetime(2026, 1, 1, tzinfo=UTC)
    return Exercise(
        id=id_,
        title=id_,
        category=category,
        parent_id=parent_id,
        version=1,
        status=status,
        schedule=Schedule(window=ScheduleWindow.CONTEXTUAL, weight_factors=WeightFactors()),
        prompts=["q?"],
        tags=[],
        created_at=when,
        created_by="t",
        updated_at=when,
        updated_by="t",
    )


def _scheduler(seed: int = 0) -> Scheduler:
    return Scheduler(clock=CLOCK, tz=TZ, rng=random.Random(seed))


def test_secondary_picker_requires_parent_to_have_fired():
    parent = _ex(id_="main-a", category=ExerciseCategory.MAIN)
    sec_a = _ex(id_="secondary-a-followup", category=ExerciseCategory.SECONDARY, parent_id="main-a")
    sec_orphan = _ex(id_="secondary-other", category=ExerciseCategory.SECONDARY, parent_id="main-b")
    chosen = _scheduler().select_secondaries(
        [parent, sec_a, sec_orphan],
        when=datetime(2026, 5, 14, 14, 0, tzinfo=UTC),
        parent_ids_fired_today={"main-a"},
        already_fired_secondary_ids=set(),
    )
    assert {ex.id for ex in chosen} == {"secondary-a-followup"}


def test_secondary_picker_excludes_already_fired():
    parent = _ex(id_="main-a", category=ExerciseCategory.MAIN)
    sec_a = _ex(id_="secondary-a", category=ExerciseCategory.SECONDARY, parent_id="main-a")
    sec_b = _ex(id_="secondary-a-2", category=ExerciseCategory.SECONDARY, parent_id="main-a")
    chosen = _scheduler().select_secondaries(
        [parent, sec_a, sec_b],
        when=datetime(2026, 5, 14, 14, 0, tzinfo=UTC),
        parent_ids_fired_today={"main-a"},
        already_fired_secondary_ids={"secondary-a"},
    )
    assert {ex.id for ex in chosen} == {"secondary-a-2"}


def test_secondary_picker_caps_at_max_count():
    parent = _ex(id_="main-a", category=ExerciseCategory.MAIN)
    pool = [parent] + [
        _ex(id_=f"secondary-a-{i}", category=ExerciseCategory.SECONDARY, parent_id="main-a")
        for i in range(5)
    ]
    chosen = _scheduler(seed=42).select_secondaries(
        pool,
        when=datetime(2026, 5, 14, 14, 0, tzinfo=UTC),
        parent_ids_fired_today={"main-a"},
        already_fired_secondary_ids=set(),
        max_count=3,
    )
    assert len(chosen) == 3
    # No duplicates.
    assert len({ex.id for ex in chosen}) == 3


def test_secondary_picker_returns_empty_when_max_count_zero():
    parent = _ex(id_="main-a", category=ExerciseCategory.MAIN)
    sec = _ex(id_="secondary-a", category=ExerciseCategory.SECONDARY, parent_id="main-a")
    chosen = _scheduler().select_secondaries(
        [parent, sec],
        when=datetime(2026, 5, 14, tzinfo=UTC),
        parent_ids_fired_today={"main-a"},
        already_fired_secondary_ids=set(),
        max_count=0,
    )
    assert chosen == []


def test_secondary_picker_skips_retired_exercises():
    parent = _ex(id_="main-a", category=ExerciseCategory.MAIN)
    retired = _ex(
        id_="secondary-old",
        category=ExerciseCategory.SECONDARY,
        parent_id="main-a",
        status=ExerciseStatus.RETIRED,
    )
    chosen = _scheduler().select_secondaries(
        [parent, retired],
        when=datetime(2026, 5, 14, tzinfo=UTC),
        parent_ids_fired_today={"main-a"},
        already_fired_secondary_ids=set(),
    )
    assert chosen == []
