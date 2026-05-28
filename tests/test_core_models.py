from datetime import UTC, datetime

import pytest

from plastiglom.packages.core.exercise import (
    Exercise,
    ExerciseCategory,
    ExerciseStatus,
    Schedule,
    ScheduleWindow,
    WeightFactors,
    active_followups,
)


def _exercise(**overrides):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    base = dict(
        id="main-x",
        title="x",
        category=ExerciseCategory.MAIN,
        parent_id=None,
        version=1,
        status=ExerciseStatus.ACTIVE,
        schedule=Schedule(window=ScheduleWindow.MORNING, weight_factors=WeightFactors()),
        prompts=["q?"],
        tags=[],
        created_at=now,
        created_by="t",
        updated_at=now,
        updated_by="t",
    )
    base.update(overrides)
    return Exercise(**base)


def test_main_rejects_parent_id():
    with pytest.raises(ValueError):
        _exercise(parent_id="main-other")


def test_secondary_requires_parent_id():
    with pytest.raises(ValueError):
        _exercise(category=ExerciseCategory.SECONDARY, id="secondary-x")


def test_secondary_with_parent_id_ok():
    ex = _exercise(
        category=ExerciseCategory.SECONDARY,
        id="secondary-x",
        parent_id="main-y",
    )
    assert ex.parent_id == "main-y"


def test_id_must_be_slug():
    with pytest.raises(ValueError):
        _exercise(id="not a slug!")


def test_weight_factors_bounded():
    with pytest.raises(ValueError):
        WeightFactors(recent_relevance=1.5)


def test_prompts_stripped_and_nonempty():
    ex = _exercise(prompts=["  q1?  ", "q2?"])
    assert ex.prompts == ["q1?", "q2?"]
    with pytest.raises(ValueError):
        _exercise(prompts=["", "q?"])


def test_active_followups_matches_active_children_only():
    main = _exercise(id="main-x")
    child_active = _exercise(
        id="secondary-x", category=ExerciseCategory.SECONDARY, parent_id="main-x"
    )
    child_retired = _exercise(
        id="secondary-x2",
        category=ExerciseCategory.SECONDARY,
        parent_id="main-x",
        status=ExerciseStatus.RETIRED,
    )
    other_child = _exercise(
        id="secondary-y", category=ExerciseCategory.SECONDARY, parent_id="main-y"
    )
    pool = [main, child_active, child_retired, other_child]

    followups = active_followups("main-x", pool)
    assert [f.id for f in followups] == ["secondary-x"]
    # A main with no connected secondary returns nothing.
    assert active_followups("main-y", [main, child_active]) == []
