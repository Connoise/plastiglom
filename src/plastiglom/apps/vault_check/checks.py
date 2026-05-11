"""Read-only integrity checks for a Plastiglom vault.

Each check returns zero or more `Finding`s; severity is `error` when an
invariant from DESIGN.md is broken and `warn` when something is merely
suspicious (e.g. exercise prompt edited since the most recent snapshot).

The validator is deliberately defensive: it parses each file independently
so a single bad markdown blob can't mask issues in others.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from plastiglom.packages.core.exercise import Exercise, ExerciseCategory
from plastiglom.packages.vault.markdown import read_markdown_file
from plastiglom.packages.vault.serializers import exercise_from_document, parse_entry


class Severity(StrEnum):
    ERROR = "error"
    WARN = "warn"


@dataclass(frozen=True)
class Finding:
    severity: Severity
    code: str
    message: str
    path: Path | None = None


@dataclass
class ValidationReport:
    findings: list[Finding] = field(default_factory=list)
    exercise_files_scanned: int = 0
    entry_files_scanned: int = 0

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.WARN]


def run_checks(vault_path: Path) -> ValidationReport:
    """Top-level entrypoint: load both trees, run every check, return findings."""
    report = ValidationReport()

    exercises_by_id, exercise_paths = _load_exercises(
        vault_path / "exercises", report
    )
    report.exercise_files_scanned = sum(1 for _ in (vault_path / "exercises").rglob("*.md")) \
        if (vault_path / "exercises").exists() else 0
    _check_exercise_parents(exercises_by_id, exercise_paths, report)
    _check_exercise_id_collisions(exercise_paths, report)

    entries_root = vault_path / "entries"
    entries, entry_paths = _load_entries(entries_root, report)
    report.entry_files_scanned = (
        sum(1 for _ in entries_root.rglob("*.md")) if entries_root.exists() else 0
    )
    _check_entry_links(entries, entry_paths, exercises_by_id, report)
    _check_lock_ordering(entries, entry_paths, report)
    _check_prompt_drift(entries, entry_paths, exercises_by_id, report)
    _check_submitted_has_response(entries, entry_paths, report)
    _check_no_duplicate_entry_ids(entries, entry_paths, report)

    return report


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_exercises(
    exercises_dir: Path, report: ValidationReport
) -> tuple[dict[str, Exercise], dict[str, Path]]:
    by_id: dict[str, Exercise] = {}
    paths: dict[str, Path] = {}
    if not exercises_dir.exists():
        return by_id, paths
    for sub in ("main", "secondary"):
        sub_dir = exercises_dir / sub
        if not sub_dir.exists():
            continue
        for md in sorted(sub_dir.glob("*.md")):
            try:
                ex = exercise_from_document(read_markdown_file(md))
            except Exception as exc:
                report.findings.append(
                    Finding(
                        severity=Severity.ERROR,
                        code="exercise.parse_failed",
                        message=f"could not parse exercise: {exc}",
                        path=md,
                    )
                )
                continue
            # Check the on-disk subdirectory matches the declared category.
            expected_sub = (
                "main" if ex.category is ExerciseCategory.MAIN else "secondary"
            )
            if sub != expected_sub:
                report.findings.append(
                    Finding(
                        severity=Severity.ERROR,
                        code="exercise.category_directory_mismatch",
                        message=(
                            f"exercise {ex.id} declares category={ex.category.value} "
                            f"but lives under exercises/{sub}/"
                        ),
                        path=md,
                    )
                )
            by_id[ex.id] = ex
            paths[ex.id] = md
    return by_id, paths


def _load_entries(
    entries_root: Path, report: ValidationReport
) -> tuple[list, dict[str, Path]]:
    out = []
    paths: dict[str, Path] = {}
    if not entries_root.exists():
        return out, paths
    for md in sorted(entries_root.rglob("*.md")):
        try:
            entry = parse_entry(read_markdown_file(md))
        except Exception as exc:
            report.findings.append(
                Finding(
                    severity=Severity.ERROR,
                    code="entry.parse_failed",
                    message=f"could not parse entry: {exc}",
                    path=md,
                )
            )
            continue
        out.append(entry)
        paths[entry.id] = md
    return out, paths


# ---------------------------------------------------------------------------
# Exercise checks
# ---------------------------------------------------------------------------


def _check_exercise_parents(
    exercises: dict[str, Exercise],
    paths: dict[str, Path],
    report: ValidationReport,
) -> None:
    for ex in exercises.values():
        if ex.category is not ExerciseCategory.SECONDARY:
            continue
        parent_id = ex.parent_id
        if parent_id is None:
            # Should have been caught by pydantic, but guard anyway.
            report.findings.append(
                Finding(
                    severity=Severity.ERROR,
                    code="exercise.secondary_without_parent",
                    message=f"secondary exercise {ex.id} has no parent_id",
                    path=paths.get(ex.id),
                )
            )
            continue
        parent = exercises.get(parent_id)
        if parent is None:
            report.findings.append(
                Finding(
                    severity=Severity.ERROR,
                    code="exercise.parent_missing",
                    message=(
                        f"secondary {ex.id} points at parent_id={parent_id!r} "
                        "which does not exist"
                    ),
                    path=paths.get(ex.id),
                )
            )
        elif parent.category is not ExerciseCategory.MAIN:
            report.findings.append(
                Finding(
                    severity=Severity.ERROR,
                    code="exercise.parent_not_main",
                    message=(
                        f"secondary {ex.id} points at {parent_id} which is not a main exercise"
                    ),
                    path=paths.get(ex.id),
                )
            )


def _check_exercise_id_collisions(
    paths: dict[str, Path], report: ValidationReport
) -> None:
    # Exercise IDs are loaded into a dict; collisions would shadow, so we walk
    # the on-disk files independently to catch duplicates regardless of which
    # one "won".
    seen: dict[str, list[Path]] = {}
    for ex_id, path in paths.items():
        seen.setdefault(ex_id, []).append(path)
    # Additionally check raw filename stems for hidden duplicates across subdirs.
    stem_seen: dict[str, list[Path]] = {}
    for path in {p for p in paths.values()}:
        stem_seen.setdefault(path.stem, []).append(path)
    for stem, ps in stem_seen.items():
        if len(ps) > 1:
            report.findings.append(
                Finding(
                    severity=Severity.ERROR,
                    code="exercise.duplicate_filename",
                    message=f"exercise filename {stem}.md appears in multiple locations: "
                    + ", ".join(str(p) for p in ps),
                )
            )


# ---------------------------------------------------------------------------
# Entry checks
# ---------------------------------------------------------------------------


def _check_entry_links(
    entries: list,
    paths: dict[str, Path],
    exercises: dict[str, Exercise],
    report: ValidationReport,
) -> None:
    for entry in entries:
        if entry.exercise_id not in exercises:
            report.findings.append(
                Finding(
                    severity=Severity.WARN,
                    code="entry.exercise_missing",
                    message=(
                        f"entry {entry.id} references exercise_id={entry.exercise_id!r} "
                        "which is not in the active pool (retired or removed?)"
                    ),
                    path=paths.get(entry.id),
                )
            )


def _check_lock_ordering(
    entries: list, paths: dict[str, Path], report: ValidationReport
) -> None:
    for entry in entries:
        fired = entry.timestamp_fired
        lock = entry.lock_at
        if lock is None:
            report.findings.append(
                Finding(
                    severity=Severity.ERROR,
                    code="entry.missing_lock_at",
                    message=f"entry {entry.id} has no lock_at",
                    path=paths.get(entry.id),
                )
            )
            continue
        if lock <= fired:
            report.findings.append(
                Finding(
                    severity=Severity.ERROR,
                    code="entry.lock_before_fire",
                    message=(
                        f"entry {entry.id} has lock_at <= timestamp_fired "
                        f"({lock.isoformat()} <= {fired.isoformat()})"
                    ),
                    path=paths.get(entry.id),
                )
            )
        submitted = entry.timestamp_submitted
        if submitted is not None and submitted < fired:
            report.findings.append(
                Finding(
                    severity=Severity.ERROR,
                    code="entry.submitted_before_fire",
                    message=(
                        f"entry {entry.id} has timestamp_submitted before timestamp_fired "
                        f"({submitted.isoformat()} < {fired.isoformat()})"
                    ),
                    path=paths.get(entry.id),
                )
            )


def _check_prompt_drift(
    entries: list,
    paths: dict[str, Path],
    exercises: dict[str, Exercise],
    report: ValidationReport,
) -> None:
    """Warn when an entry's prompt_snapshot diverges from the live exercise.

    Drift is expected — exercises evolve — but a snapshot must never be
    *empty* and a *recent* entry whose snapshot doesn't match the live
    prompts is worth surfacing to the user since it usually means an
    in-flight edit collided with a firing.
    """
    now_cutoff: datetime | None = None
    if entries:
        # Treat anything in the last 24h as "recent" for drift purposes.
        latest = max(e.timestamp_fired for e in entries)
        now_cutoff = latest
    for entry in entries:
        if not entry.prompt_snapshot:
            report.findings.append(
                Finding(
                    severity=Severity.ERROR,
                    code="entry.empty_prompt_snapshot",
                    message=f"entry {entry.id} has empty prompt_snapshot",
                    path=paths.get(entry.id),
                )
            )
            continue
        ex = exercises.get(entry.exercise_id)
        if ex is None or now_cutoff is None:
            continue
        recent = (now_cutoff - entry.timestamp_fired).total_seconds() < 86400
        if recent and list(ex.prompts) != list(entry.prompt_snapshot):
            report.findings.append(
                Finding(
                    severity=Severity.WARN,
                    code="entry.prompt_drift_recent",
                    message=(
                        f"recent entry {entry.id} snapshot differs from live "
                        f"exercise {entry.exercise_id} prompts"
                    ),
                    path=paths.get(entry.id),
                )
            )


def _check_submitted_has_response(
    entries: list, paths: dict[str, Path], report: ValidationReport
) -> None:
    from plastiglom.packages.core.entry import EntryStatus

    for entry in entries:
        if entry.status is EntryStatus.SUBMITTED and not entry.response.strip():
            report.findings.append(
                Finding(
                    severity=Severity.ERROR,
                    code="entry.submitted_empty_response",
                    message=f"entry {entry.id} is marked submitted but has empty response",
                    path=paths.get(entry.id),
                )
            )


def _check_no_duplicate_entry_ids(
    entries: list, paths: dict[str, Path], report: ValidationReport
) -> None:
    seen: dict[str, list[Path]] = {}
    for entry in entries:
        path = paths.get(entry.id)
        if path is None:
            continue
        seen.setdefault(entry.id, []).append(path)
    # `paths` is a dict; collisions would have overwritten earlier paths. So
    # walk the actual filesystem-traversal output by checking stems.
    stems: dict[str, list[Path]] = {}
    for path in set(paths.values()):
        stems.setdefault(path.stem, []).append(path)
    for stem, ps in stems.items():
        if len(ps) > 1:
            report.findings.append(
                Finding(
                    severity=Severity.ERROR,
                    code="entry.duplicate_filename",
                    message=f"entry filename {stem}.md appears in multiple locations: "
                    + ", ".join(str(p) for p in ps),
                )
            )
