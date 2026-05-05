"""Persisted proposal queue. See §7.7 of DESIGN.md.

Proposals live at `proposals/<id>.md`. The full proposed exercise is nested
in frontmatter; rationale and diff sit in the body. Status is one of:
  - `pending`: awaiting user review
  - `approved`: applied via `apply_proposal`; record kept for audit
  - `rejected`: explicitly declined; record kept for audit
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from plastiglom.apps.meta_engine.proposals import ExerciseProposal, ProposalAction
from plastiglom.packages.core.exercise import Exercise
from plastiglom.packages.vault.markdown import (
    FrontmatterDocument,
    read_markdown_file,
    write_markdown_file,
)
from plastiglom.packages.vault.serializers import (
    exercise_from_document,
    exercise_to_document,
)


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


_ID_SAFE = re.compile(r"^[A-Za-z0-9_\-:.]+$")


@dataclass
class ProposalRecord:
    """Disk-backed proposal record."""

    id: str
    proposal: ExerciseProposal
    status: ProposalStatus
    proposed_by: str
    proposed_at: datetime
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_note: str | None = None


def proposal_path(vault: Path, proposal_id: str) -> Path:
    if not _ID_SAFE.match(proposal_id):
        raise ValueError(f"unsafe proposal id: {proposal_id!r}")
    return vault / "proposals" / f"{proposal_id}.md"


def make_proposal_id(when: datetime, exercise_id: str, action: ProposalAction) -> str:
    return f"{when.strftime('%Y-%m-%dT%H-%M-%S')}-{action.value}-{exercise_id}"


def save_proposal(vault: Path, record: ProposalRecord) -> Path:
    path = proposal_path(vault, record.id)
    write_markdown_file(path, _to_doc(record))
    return path


def load_proposal(vault: Path, proposal_id: str) -> ProposalRecord:
    return _from_doc(read_markdown_file(proposal_path(vault, proposal_id)))


def list_proposals(
    vault: Path,
    *,
    status: ProposalStatus | None = None,
) -> list[ProposalRecord]:
    """Return proposals on disk, optionally filtered by status."""
    directory = vault / "proposals"
    if not directory.exists():
        return []
    records: list[ProposalRecord] = []
    for path in sorted(directory.glob("*.md"), reverse=True):
        try:
            record = _from_doc(read_markdown_file(path))
        except Exception:
            continue
        if status is None or record.status is status:
            records.append(record)
    return records


def decide(
    vault: Path,
    proposal_id: str,
    *,
    status: ProposalStatus,
    decided_by: str,
    note: str | None = None,
    when: datetime | None = None,
) -> ProposalRecord:
    """Record an approve/reject decision on a proposal.

    This does NOT call `apply_proposal`; that is the caller's responsibility
    so they can decide ordering (e.g. apply first, then mark approved on the
    same write).
    """
    if status is ProposalStatus.PENDING:
        raise ValueError("decide() requires a non-pending status")
    when = when or datetime.now(tz=UTC)
    record = load_proposal(vault, proposal_id)
    record.status = status
    record.decided_by = decided_by
    record.decided_at = when
    record.decision_note = note
    save_proposal(vault, record)
    return record


def make_record(
    proposal: ExerciseProposal,
    *,
    proposed_by: str,
    when: datetime | None = None,
) -> ProposalRecord:
    """Wrap an ExerciseProposal in a fresh ProposalRecord (status=pending)."""
    when = when or datetime.now(tz=UTC)
    proposal_id = make_proposal_id(when, proposal.exercise.id, proposal.action)
    return ProposalRecord(
        id=proposal_id,
        proposal=proposal,
        status=ProposalStatus.PENDING,
        proposed_by=proposed_by,
        proposed_at=when,
    )


def compute_diff(prior: Exercise | None, proposed: Exercise) -> str:
    """Unified diff between two exercise YAML serializations.

    Pass `prior=None` for create/retire actions; in those cases the diff is
    a one-sided rendering for the user's review.
    """
    proposed_yaml = _exercise_yaml(proposed)
    prior_yaml = _exercise_yaml(prior) if prior is not None else ""
    diff = difflib.unified_diff(
        prior_yaml.splitlines(),
        proposed_yaml.splitlines(),
        fromfile=f"{proposed.id}@v{prior.version if prior else 0}",
        tofile=f"{proposed.id}@v{proposed.version}",
        lineterm="",
    )
    return "\n".join(diff)


def _exercise_yaml(exercise: Exercise) -> str:
    doc = exercise_to_document(exercise)
    return yaml.safe_dump(doc.metadata, sort_keys=False, default_flow_style=False).rstrip()


# ---------- on-disk serialization ----------


def _to_doc(record: ProposalRecord) -> FrontmatterDocument:
    proposal = record.proposal
    metadata: dict[str, Any] = {
        "id": record.id,
        "action": proposal.action.value,
        "status": record.status.value,
        "exercise_id": proposal.exercise.id,
        "prior_version": proposal.prior_version,
        "new_version": proposal.exercise.version,
        "proposed_by": record.proposed_by,
        "proposed_at": record.proposed_at,
        "decided_by": record.decided_by,
        "decided_at": record.decided_at,
        "tags_touched": list(proposal.tags_touched),
        "exercise": exercise_to_document(proposal.exercise).metadata,
    }
    body_parts = [f"## Rationale\n\n{proposal.rationale.strip()}\n"]
    if proposal.diff.strip():
        body_parts.append(f"## Diff\n\n```\n{proposal.diff.rstrip()}\n```\n")
    if record.decision_note:
        body_parts.append(f"## Decision note\n\n{record.decision_note.strip()}\n")
    return FrontmatterDocument(metadata=metadata, content="\n".join(body_parts))


def _from_doc(doc: FrontmatterDocument) -> ProposalRecord:
    m = doc.metadata
    exercise_meta = dict(m["exercise"])
    exercise = exercise_from_document(
        FrontmatterDocument(metadata=exercise_meta, content="")
    )
    rationale, diff = _split_rationale_diff(doc.content)
    proposal = ExerciseProposal(
        action=ProposalAction(m["action"]),
        exercise=exercise,
        rationale=rationale,
        prior_version=m.get("prior_version"),
        diff=diff,
        tags_touched=list(m.get("tags_touched") or []),
    )
    return ProposalRecord(
        id=m["id"],
        proposal=proposal,
        status=ProposalStatus(m["status"]),
        proposed_by=m["proposed_by"],
        proposed_at=_as_dt(m["proposed_at"]),
        decided_by=m.get("decided_by"),
        decided_at=_as_dt(m["decided_at"]) if m.get("decided_at") else None,
        decision_note=_extract_decision_note(doc.content),
    )


def _split_rationale_diff(body: str) -> tuple[str, str]:
    rationale = ""
    diff = ""
    if "## Rationale" in body:
        _, rest = body.split("## Rationale", 1)
        if "## Diff" in rest:
            rationale_block, after = rest.split("## Diff", 1)
            rationale = rationale_block.strip()
            diff = _extract_fenced(after)
        elif "## Decision note" in rest:
            rationale_block, _ = rest.split("## Decision note", 1)
            rationale = rationale_block.strip()
        else:
            rationale = rest.strip()
    return rationale, diff


def _extract_fenced(text: str) -> str:
    if "```" not in text:
        return text.strip()
    after_open = text.split("```", 1)[1]
    return after_open.split("```", 1)[0].strip()


def _extract_decision_note(body: str) -> str | None:
    if "## Decision note" not in body:
        return None
    _, rest = body.split("## Decision note", 1)
    return rest.strip() or None


def _as_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"cannot coerce {value!r} to datetime")
