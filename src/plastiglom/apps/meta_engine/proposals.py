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

from plastiglom.packages.core.exercise import (
    Exercise,
    ExerciseCategory,
    ExerciseStatus,
)
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


def load_active_pool(exercises_dir: Path) -> list[Exercise]:
    """Load every active main + secondary exercise from the vault.

    Used as the validation set for proposals: edits must target a member,
    creates must not collide, retires must hit a member. Files that fail to
    parse or land in the wrong subdirectory are skipped silently rather
    than blocking the broader operation.
    """
    pool: list[Exercise] = []
    for sub, expected in (
        ("main", ExerciseCategory.MAIN),
        ("secondary", ExerciseCategory.SECONDARY),
    ):
        directory = exercises_dir / sub
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            try:
                exercise = exercise_from_document(read_markdown_file(path))
            except Exception:
                continue
            if (
                exercise.status is ExerciseStatus.ACTIVE
                and exercise.category is expected
            ):
                pool.append(exercise)
    return pool


def validate_exercise_for_action(
    exercise: Exercise,
    action: ProposalAction,
    *,
    pool_by_id: dict[str, Exercise],
    prior_version: int | None,
) -> int | None:
    """Enforce per-action invariants on a (possibly user-edited) exercise.

    Mirrors the rules the generator's parser applies, so refinement and
    LLM-generated proposals stay in sync. Returns the resolved
    `prior_version` (None for create). Raises ValueError on violation.
    """
    if action is ProposalAction.EDIT:
        prior = pool_by_id.get(exercise.id)
        if prior is None:
            raise ValueError(f"edit targets unknown exercise: {exercise.id}")
        if prior_version is None:
            prior_version = prior.version
        if exercise.version <= prior.version:
            raise ValueError(
                f"edit must bump version: {prior.version} -> {exercise.version}"
            )
    elif action is ProposalAction.CREATE:
        if exercise.id in pool_by_id:
            raise ValueError(f"create duplicates existing id: {exercise.id}")
    elif action is ProposalAction.RETIRE:
        if exercise.id not in pool_by_id:
            raise ValueError(f"retire targets unknown exercise: {exercise.id}")
        if exercise.status is not ExerciseStatus.RETIRED:
            raise ValueError("retire proposals must set status: retired")
    return prior_version
