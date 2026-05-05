from datetime import UTC, datetime

import pytest

from plastiglom.apps.meta_engine import (
    ExerciseProposal,
    ProposalAction,
    ProposalStatus,
    apply_proposal,
    compute_diff,
    decide,
    list_proposals,
    load_proposal,
    make_record,
    save_proposal,
)
from plastiglom.packages.core.exercise import (
    Exercise,
    ExerciseCategory,
    ExerciseStatus,
    Schedule,
    ScheduleWindow,
    WeightFactors,
)
from plastiglom.packages.vault.markdown import read_markdown_file
from plastiglom.packages.vault.serializers import exercise_from_document


def _exercise(*, id_="main-edit-target", version=1, status="active", prompts=("q?",)):
    when = datetime(2026, 1, 1, tzinfo=UTC)
    return Exercise(
        id=id_,
        title="t",
        category=ExerciseCategory.MAIN,
        parent_id=None,
        version=version,
        status=ExerciseStatus(status),
        schedule=Schedule(window=ScheduleWindow.EVENING, weight_factors=WeightFactors()),
        prompts=list(prompts),
        tags=["values"],
        created_at=when,
        created_by="seed",
        updated_at=when,
        updated_by="seed",
    )


def _proposal(action=ProposalAction.EDIT, **overrides) -> ExerciseProposal:
    base = _exercise()
    return ExerciseProposal(
        action=action,
        exercise=overrides.pop("exercise", _exercise(version=2, prompts=["new q?"])),
        rationale=overrides.pop("rationale", "shifts the prompt to probe Y"),
        prior_version=overrides.pop("prior_version", 1),
        diff=overrides.pop("diff", compute_diff(base, _exercise(version=2, prompts=["new q?"]))),
        tags_touched=overrides.pop("tags_touched", ["values"]),
    )


def test_record_roundtrip(vault):
    record = make_record(_proposal(), proposed_by="opus-4-7", when=datetime(2026, 5, 14, 9, 0, tzinfo=UTC))
    save_proposal(vault, record)
    loaded = load_proposal(vault, record.id)
    assert loaded.id == record.id
    assert loaded.proposal.action is ProposalAction.EDIT
    assert loaded.proposal.exercise.version == 2
    assert "new q?" in loaded.proposal.exercise.prompts
    assert loaded.proposal.rationale == "shifts the prompt to probe Y"
    assert "+- q?" not in loaded.proposal.diff  # diff was preserved verbatim
    assert loaded.status is ProposalStatus.PENDING


def test_list_filters_by_status(vault):
    a = make_record(_proposal(), proposed_by="opus", when=datetime(2026, 5, 14, 9, 0, tzinfo=UTC))
    b = make_record(
        _proposal(exercise=_exercise(id_="main-other-target", version=2, prompts=["x?"])),
        proposed_by="opus",
        when=datetime(2026, 5, 14, 10, 0, tzinfo=UTC),
    )
    save_proposal(vault, a)
    save_proposal(vault, b)
    decide(vault, a.id, status=ProposalStatus.REJECTED, decided_by="user", note="not now")
    pending = list_proposals(vault, status=ProposalStatus.PENDING)
    rejected = list_proposals(vault, status=ProposalStatus.REJECTED)
    assert [r.id for r in pending] == [b.id]
    assert [r.id for r in rejected] == [a.id]
    # Decision metadata persisted.
    assert rejected[0].decision_note == "not now"
    assert rejected[0].decided_by == "user"


def test_decide_pending_status_rejected(vault):
    record = make_record(_proposal(), proposed_by="opus", when=datetime(2026, 5, 14, 9, 0, tzinfo=UTC))
    save_proposal(vault, record)
    with pytest.raises(ValueError):
        decide(vault, record.id, status=ProposalStatus.PENDING, decided_by="user")


def test_apply_proposal_writes_exercise_and_history(vault):
    # Pre-populate the prior version on disk so apply_proposal updates it.
    prior = _exercise(version=1)
    apply_proposal(
        vault,
        ExerciseProposal(
            action=ProposalAction.CREATE,
            exercise=prior,
            rationale="seed",
        ),
        approved_by="seed",
    )

    record = make_record(_proposal(), proposed_by="opus", when=datetime(2026, 5, 14, 9, 0, tzinfo=UTC))
    save_proposal(vault, record)
    apply_proposal(vault, record.proposal, approved_by="user")

    on_disk = exercise_from_document(read_markdown_file(vault / "exercises" / "main" / "main-edit-target.md"))
    assert on_disk.version == 2
    assert "new q?" in on_disk.prompts

    history_files = list((vault / "exercise_history").glob("*main-edit-target*.md"))
    assert len(history_files) >= 1


def test_compute_diff_marks_create_when_prior_is_none():
    new = _exercise(id_="main-new", version=1, prompts=["fresh?"])
    diff = compute_diff(None, new)
    assert "+id: main-new" in diff
    assert "+prompts:" in diff
