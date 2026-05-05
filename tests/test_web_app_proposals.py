"""Tests for the web app's proposal approval routes."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from plastiglom.apps.meta_engine import (
    ExerciseProposal,
    ProposalAction,
    ProposalStatus,
    apply_proposal,
    compute_diff,
    list_proposals,
    load_proposal,
    make_record,
    save_proposal,
)
from plastiglom.apps.web_app.app import create_app
from plastiglom.packages.core.exercise import (
    Exercise,
    ExerciseCategory,
    ExerciseStatus,
    Schedule,
    ScheduleWindow,
    WeightFactors,
)


def _exercise(*, version: int, prompts=None) -> Exercise:
    when = datetime(2026, 1, 1, tzinfo=UTC)
    return Exercise(
        id="main-edit-target",
        title="Edit target",
        category=ExerciseCategory.MAIN,
        parent_id=None,
        version=version,
        status=ExerciseStatus.ACTIVE,
        schedule=Schedule(window=ScheduleWindow.EVENING, weight_factors=WeightFactors()),
        prompts=list(prompts or ["original?"]),
        tags=["values"],
        created_at=when,
        created_by="seed",
        updated_at=when,
        updated_by="seed",
    )


def _seed_pending(vault) -> str:
    # Persist v1 on disk so apply_proposal has something to update.
    apply_proposal(
        vault,
        ExerciseProposal(action=ProposalAction.CREATE, exercise=_exercise(version=1), rationale="seed"),
        approved_by="seed",
    )
    proposed = _exercise(version=2, prompts=["refined?"])
    proposal = ExerciseProposal(
        action=ProposalAction.EDIT,
        exercise=proposed,
        rationale="probe Y instead of X",
        prior_version=1,
        diff=compute_diff(_exercise(version=1), proposed),
        tags_touched=["values"],
    )
    record = make_record(proposal, proposed_by="opus", when=datetime(2026, 5, 14, 9, 0, tzinfo=UTC))
    save_proposal(vault, record)
    return record.id


def _client(vault) -> TestClient:
    app = create_app(
        vault_path=vault,
        tz=ZoneInfo("UTC"),
        now=lambda: datetime(2026, 5, 20, tzinfo=UTC),
    )
    return TestClient(app)


def test_index_lists_pending(vault):
    pid = _seed_pending(vault)
    client = _client(vault)
    r = client.get("/proposals")
    assert r.status_code == 200
    assert pid in r.text
    assert "main-edit-target" in r.text


def test_view_shows_rationale_and_diff(vault):
    pid = _seed_pending(vault)
    client = _client(vault)
    r = client.get(f"/proposals/{pid}")
    assert r.status_code == 200
    assert "probe Y instead of X" in r.text
    assert "refined?" in r.text


def test_approve_applies_proposal_and_marks_status(vault):
    pid = _seed_pending(vault)
    client = _client(vault)
    r = client.post(f"/proposals/{pid}/approve", follow_redirects=False)
    assert r.status_code == 303
    record = load_proposal(vault, pid)
    assert record.status is ProposalStatus.APPROVED
    # Exercise on disk is now v2 with the refined prompt.
    from plastiglom.packages.vault.markdown import read_markdown_file
    from plastiglom.packages.vault.serializers import exercise_from_document

    on_disk = exercise_from_document(
        read_markdown_file(vault / "exercises" / "main" / "main-edit-target.md")
    )
    assert on_disk.version == 2
    assert "refined?" in on_disk.prompts


def test_approve_already_decided_returns_409(vault):
    pid = _seed_pending(vault)
    client = _client(vault)
    client.post(f"/proposals/{pid}/approve", follow_redirects=False)
    r = client.post(f"/proposals/{pid}/approve", follow_redirects=False)
    assert r.status_code == 409


def test_reject_records_note_and_does_not_apply(vault):
    pid = _seed_pending(vault)
    client = _client(vault)
    r = client.post(
        f"/proposals/{pid}/reject",
        data={"note": "want to keep the original prompt"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    record = load_proposal(vault, pid)
    assert record.status is ProposalStatus.REJECTED
    assert record.decision_note == "want to keep the original prompt"

    # Exercise on disk is still v1.
    from plastiglom.packages.vault.markdown import read_markdown_file
    from plastiglom.packages.vault.serializers import exercise_from_document

    on_disk = exercise_from_document(
        read_markdown_file(vault / "exercises" / "main" / "main-edit-target.md")
    )
    assert on_disk.version == 1


def test_index_separates_pending_and_decided(vault):
    pid = _seed_pending(vault)
    client = _client(vault)
    client.post(f"/proposals/{pid}/reject", data={"note": ""}, follow_redirects=False)
    pending = list_proposals(vault, status=ProposalStatus.PENDING)
    rejected = list_proposals(vault, status=ProposalStatus.REJECTED)
    assert pending == []
    assert len(rejected) == 1
    r = client.get("/proposals")
    assert "Decided" in r.text
    assert "rejected" in r.text
