"""Tests for the meta-engine generator JSON parser.

We don't hit the LLM here; we feed canned response strings and verify the
parser rejects malformed inputs and accepts shaped ones.
"""

import json
from datetime import UTC, datetime

import pytest

from plastiglom.apps.meta_engine import ProposalAction
from plastiglom.apps.meta_engine.generator import parse_response
from plastiglom.packages.core.exercise import (
    Exercise,
    ExerciseCategory,
    ExerciseStatus,
    Schedule,
    ScheduleWindow,
    WeightFactors,
)


def _existing(*, id_="main-evening-review", version=1) -> Exercise:
    when = datetime(2026, 1, 1, tzinfo=UTC)
    return Exercise(
        id=id_,
        title="t",
        category=ExerciseCategory.MAIN,
        parent_id=None,
        version=version,
        status=ExerciseStatus.ACTIVE,
        schedule=Schedule(window=ScheduleWindow.EVENING, weight_factors=WeightFactors()),
        prompts=["q?"],
        tags=[],
        created_at=when,
        created_by="seed",
        updated_at=when,
        updated_by="seed",
    )


def _exercise_dict(**overrides) -> dict:
    when = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
    base = {
        "id": "main-evening-review",
        "title": "Evening review",
        "category": "main",
        "parent_id": None,
        "version": 2,
        "status": "active",
        "schedule": {
            "window": "evening",
            "weight_factors": {
                "recent_relevance": 0.5,
                "depth_potential": 0.5,
                "weekday_weight": 0.5,
                "weekend_weight": 0.5,
                "novelty_value": 0.5,
            },
        },
        "prompts": ["new prompt?"],
        "tags": [],
        "created_at": when,
        "created_by": "seed",
        "updated_at": when,
        "updated_by": "opus-4-7",
    }
    base.update(overrides)
    return base


def _wrap(*proposals_dicts) -> str:
    return json.dumps({"proposals": list(proposals_dicts)})


def test_parse_returns_empty_on_garbage():
    assert parse_response("nothing JSON here", []) == []


def test_parse_single_edit():
    pool = [_existing()]
    raw = _wrap(
        {
            "action": "edit",
            "exercise": _exercise_dict(version=2),
            "prior_version": 1,
            "rationale": "freshen the prompt",
            "tags_touched": ["values"],
        }
    )
    proposals = parse_response(raw, pool)
    assert len(proposals) == 1
    p = proposals[0]
    assert p.action is ProposalAction.EDIT
    assert p.exercise.version == 2
    assert p.prior_version == 1
    assert "freshen" in p.rationale
    assert "+- new prompt?" in p.diff or "+    - new prompt?" in p.diff


def test_parse_rejects_edit_without_version_bump():
    pool = [_existing(version=2)]
    raw = _wrap(
        {
            "action": "edit",
            "exercise": _exercise_dict(version=2),
            "prior_version": 2,
            "rationale": "no-op",
        }
    )
    assert parse_response(raw, pool) == []


def test_parse_rejects_edit_for_unknown_exercise():
    raw = _wrap(
        {
            "action": "edit",
            "exercise": _exercise_dict(version=2),
            "prior_version": 1,
            "rationale": "x",
        }
    )
    assert parse_response(raw, []) == []


def test_parse_rejects_create_when_id_collides():
    pool = [_existing()]
    raw = _wrap(
        {
            "action": "create",
            "exercise": _exercise_dict(version=1),
            "rationale": "x",
        }
    )
    assert parse_response(raw, pool) == []


def test_parse_accepts_create_for_new_id():
    pool = [_existing()]
    new_dict = _exercise_dict(id="main-fresh", version=1, prompts=["fresh?"])
    raw = _wrap(
        {
            "action": "create",
            "exercise": new_dict,
            "rationale": "probe Z",
        }
    )
    proposals = parse_response(raw, pool)
    assert len(proposals) == 1
    assert proposals[0].action is ProposalAction.CREATE
    assert proposals[0].exercise.id == "main-fresh"


def test_parse_rejects_retire_without_status_retired():
    pool = [_existing()]
    raw = _wrap(
        {
            "action": "retire",
            "exercise": _exercise_dict(version=2),  # status is still "active"
            "prior_version": 1,
            "rationale": "x",
        }
    )
    assert parse_response(raw, pool) == []


def test_parse_accepts_retire_with_status_retired():
    pool = [_existing()]
    raw = _wrap(
        {
            "action": "retire",
            "exercise": _exercise_dict(version=2, status="retired"),
            "prior_version": 1,
            "rationale": "no longer earning slot",
        }
    )
    proposals = parse_response(raw, pool)
    assert len(proposals) == 1
    assert proposals[0].action is ProposalAction.RETIRE
    assert proposals[0].exercise.status.value == "retired"


def test_one_bad_proposal_does_not_drop_others():
    pool = [_existing()]
    bad = {
        "action": "edit",
        "exercise": _exercise_dict(version=1),  # no version bump
        "prior_version": 1,
        "rationale": "x",
    }
    good = {
        "action": "edit",
        "exercise": _exercise_dict(version=2),
        "prior_version": 1,
        "rationale": "y",
    }
    proposals = parse_response(_wrap(bad, good), pool)
    assert len(proposals) == 1
    assert proposals[0].rationale == "y"


def test_parse_rejects_invalid_json_object():
    assert parse_response("{{ broken", []) == []
    with pytest.raises(json.JSONDecodeError):
        json.loads("{{ broken")  # sanity check on the input
