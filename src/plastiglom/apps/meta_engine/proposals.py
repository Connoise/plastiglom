"""Exercise proposals and approval persistence.

The meta-engine emits proposals; the web app surfaces them to the user who
may refine and then approve. Only `apply_proposal` persists changes, and it
always writes an `exercise_history/` note alongside the updated exercise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path

from plastiglom.packages.core.exercise import Exercise, ExerciseCategory
from plastiglom.packages.vault.markdown import (
    FrontmatterDocument,
    read_markdown_file,
    write_markdown_file,
)
from plastiglom.packages.vault.paths import exercise_history_path, exercise_path
from plastiglom.packages.vault.serializers import (
    exercise_from_document,
    exercise_to_document,
)


class ProposalAction(StrEnum):
    CREATE = "create"
    EDIT = "edit"
    RETIRE = "retire"


@dataclass
class ExerciseProposal:
    action: ProposalAction
    exercise: Exercise
    rationale: str
    prior_version: int | None = None
    diff: str = ""
    tags_touched: list[str] = field(default_factory=list)


def apply_proposal(
    vault_path: Path,
    proposal: ExerciseProposal,
    *,
    approved_by: str,
    approved_at: datetime | None = None,
) -> Path:
    approved_at = approved_at or datetime.now(tz=UTC)
    category = (
        "main" if proposal.exercise.category is ExerciseCategory.MAIN else "secondary"
    )
    target = exercise_path(vault_path, proposal.exercise.id, category)
    exercise = proposal.exercise
    exercise.updated_at = approved_at
    exercise.updated_by = approved_by
    write_markdown_file(target, exercise_to_document(exercise))
    record_history(vault_path, proposal, approved_by=approved_by, approved_at=approved_at)
    return target


def record_history(
    vault_path: Path,
    proposal: ExerciseProposal,
    *,
    approved_by: str,
    approved_at: datetime,
) -> Path:
    path = exercise_history_path(
        vault_path,
        approved_at.date() if isinstance(approved_at, datetime) else date.today(),
        proposal.exercise.id,
    )
    metadata = {
        "exercise_id": proposal.exercise.id,
        "action": proposal.action.value,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "prior_version": proposal.prior_version,
        "new_version": proposal.exercise.version,
        "tags_touched": proposal.tags_touched,
    }
    body = (
        f"## Rationale\n\n{proposal.rationale.strip()}\n\n"
        f"## Diff\n\n```\n{proposal.diff or '(no diff)'}\n```\n"
    )
    write_markdown_file(path, FrontmatterDocument(metadata=metadata, content=body))
    return path


def load_exercise(vault_path: Path, exercise_id: str, category: str) -> Exercise:
    return exercise_from_document(
        read_markdown_file(exercise_path(vault_path, exercise_id, category))
    )
