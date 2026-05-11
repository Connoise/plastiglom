"""Vault integrity validator.

Each test seeds a minimal vault, runs `run_checks`, and asserts which codes
fired. The validator never raises — every malformed file shows up as a
finding instead.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from plastiglom.apps.vault_check import Severity, run_checks
from plastiglom.packages.core.entry import Entry, EntryStatus
from plastiglom.packages.core.exercise import (
    Exercise,
    ExerciseCategory,
    ExerciseStatus,
    Schedule,
    ScheduleWindow,
    WeightFactors,
)
from plastiglom.packages.vault.markdown import write_markdown_file
from plastiglom.packages.vault.serializers import (
    entry_to_document,
    exercise_to_document,
)


def _make_main(id_: str = "main-evening-review", prompts: list[str] | None = None) -> Exercise:
    when = datetime(2026, 5, 1, tzinfo=UTC)
    return Exercise(
        id=id_,
        title=id_,
        category=ExerciseCategory.MAIN,
        parent_id=None,
        version=1,
        status=ExerciseStatus.ACTIVE,
        schedule=Schedule(window=ScheduleWindow.EVENING, weight_factors=WeightFactors()),
        prompts=prompts or ["What moment deserves a second look?"],
        tags=[],
        created_at=when,
        created_by="t",
        updated_at=when,
        updated_by="t",
    )


def _make_secondary(
    id_: str = "secondary-recheck", parent_id: str = "main-evening-review"
) -> Exercise:
    when = datetime(2026, 5, 1, tzinfo=UTC)
    return Exercise(
        id=id_,
        title=id_,
        category=ExerciseCategory.SECONDARY,
        parent_id=parent_id,
        version=1,
        status=ExerciseStatus.ACTIVE,
        schedule=Schedule(
            window=ScheduleWindow.CONTEXTUAL, weight_factors=WeightFactors()
        ),
        prompts=["Recheck?"],
        tags=[],
        created_at=when,
        created_by="t",
        updated_at=when,
        updated_by="t",
    )


def _seed_exercise(vault: Path, ex: Exercise, sub: str | None = None) -> Path:
    sub = sub or ("main" if ex.category is ExerciseCategory.MAIN else "secondary")
    path = vault / "exercises" / sub / f"{ex.id}.md"
    write_markdown_file(path, exercise_to_document(ex))
    return path


def _seed_entry(vault: Path, entry: Entry) -> Path:
    fired = entry.timestamp_fired
    path = (
        vault
        / "entries"
        / f"{fired.year:04d}"
        / f"{fired.month:02d}"
        / f"{fired.day:02d}-{entry.exercise_id.split('-', 1)[1]}.md"
    )
    write_markdown_file(path, entry_to_document(entry))
    return path


def _entry(
    *,
    exercise_id: str = "main-evening-review",
    fired: datetime | None = None,
    lock: datetime | None = None,
    status: EntryStatus = EntryStatus.SUBMITTED,
    prompts: list[str] | None = None,
    response: str = "ok",
    submitted: datetime | None = None,
) -> Entry:
    fired = fired or datetime(2026, 5, 10, 21, 0, tzinfo=UTC)
    lock = lock or datetime(2026, 5, 11, 7, 30, tzinfo=UTC)
    submitted = submitted if submitted is not None else (fired if status is EntryStatus.SUBMITTED else None)
    return Entry(
        id=f"{fired.date().isoformat()}-{exercise_id.split('-', 1)[1]}",
        exercise_id=exercise_id,
        exercise_version=1,
        title=f"{fired.date().isoformat()} - {exercise_id}",
        timestamp_fired=fired,
        timestamp_submitted=submitted,
        lock_at=lock,
        status=status,
        tags=[],
        prompt_snapshot=prompts or ["What moment deserves a second look?"],
        response=response if status is EntryStatus.SUBMITTED else "",
    )


def test_clean_vault_produces_no_findings(tmp_path: Path) -> None:
    main = _make_main()
    _seed_exercise(tmp_path, main)
    _seed_entry(tmp_path, _entry())
    report = run_checks(tmp_path)
    assert report.errors == []
    assert report.warnings == []


def test_orphan_entry_warns(tmp_path: Path) -> None:
    _seed_entry(tmp_path, _entry())  # no matching exercise
    report = run_checks(tmp_path)
    codes = {f.code for f in report.findings}
    assert "entry.exercise_missing" in codes
    assert {f.severity for f in report.findings if f.code == "entry.exercise_missing"} == {
        Severity.WARN
    }


def test_secondary_without_parent_errors(tmp_path: Path) -> None:
    sec = _make_secondary(id_="secondary-x", parent_id="main-not-here")
    _seed_exercise(tmp_path, sec)
    report = run_checks(tmp_path)
    codes = {f.code for f in report.errors}
    assert "exercise.parent_missing" in codes


def test_secondary_pointing_at_secondary_errors(tmp_path: Path) -> None:
    parent = _make_secondary(id_="secondary-parent", parent_id="main-evening-review")
    # Put a main with the same id as the parent_id we want to reference so
    # we can then point another secondary at the *secondary* and catch the
    # not-main check.
    _seed_exercise(tmp_path, _make_main())
    _seed_exercise(tmp_path, parent)
    child = _make_secondary(id_="secondary-child", parent_id="secondary-parent")
    _seed_exercise(tmp_path, child)
    report = run_checks(tmp_path)
    codes = {f.code for f in report.errors}
    assert "exercise.parent_not_main" in codes


def test_category_directory_mismatch_errors(tmp_path: Path) -> None:
    # Place a main-categorized exercise inside the secondary/ folder.
    main = _make_main()
    _seed_exercise(tmp_path, main, sub="secondary")
    report = run_checks(tmp_path)
    codes = {f.code for f in report.errors}
    assert "exercise.category_directory_mismatch" in codes


def test_lock_before_fire_errors(tmp_path: Path) -> None:
    _seed_exercise(tmp_path, _make_main())
    bad = _entry(
        fired=datetime(2026, 5, 10, 21, tzinfo=UTC),
        lock=datetime(2026, 5, 10, 20, tzinfo=UTC),
    )
    _seed_entry(tmp_path, bad)
    report = run_checks(tmp_path)
    codes = {f.code for f in report.errors}
    assert "entry.lock_before_fire" in codes


def test_submitted_before_fire_errors(tmp_path: Path) -> None:
    _seed_exercise(tmp_path, _make_main())
    bad = _entry(
        fired=datetime(2026, 5, 10, 21, tzinfo=UTC),
        lock=datetime(2026, 5, 11, 7, tzinfo=UTC),
        submitted=datetime(2026, 5, 10, 20, tzinfo=UTC),
    )
    _seed_entry(tmp_path, bad)
    report = run_checks(tmp_path)
    codes = {f.code for f in report.errors}
    assert "entry.submitted_before_fire" in codes


def test_submitted_empty_response_errors(tmp_path: Path) -> None:
    _seed_exercise(tmp_path, _make_main())
    # Build a submitted entry but blank the response after construction.
    e = _entry()
    e.response = ""
    _seed_entry(tmp_path, e)
    report = run_checks(tmp_path)
    codes = {f.code for f in report.errors}
    assert "entry.submitted_empty_response" in codes


def test_prompt_drift_recent_warns(tmp_path: Path) -> None:
    main = _make_main(prompts=["LIVE PROMPT v2"])
    _seed_exercise(tmp_path, main)
    drifted = _entry(prompts=["LIVE PROMPT v1"])
    _seed_entry(tmp_path, drifted)
    report = run_checks(tmp_path)
    codes = {f.code for f in report.warnings}
    assert "entry.prompt_drift_recent" in codes


def test_malformed_exercise_file_is_a_parse_error(tmp_path: Path) -> None:
    bad = tmp_path / "exercises" / "main" / "broken.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("---\nnot: yaml: structure\n---\nbody", encoding="utf-8")
    report = run_checks(tmp_path)
    codes = {f.code for f in report.errors}
    assert "exercise.parse_failed" in codes


def test_malformed_entry_file_is_a_parse_error(tmp_path: Path) -> None:
    bad = tmp_path / "entries" / "2026" / "05" / "10-mystery.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("not frontmatter at all", encoding="utf-8")
    report = run_checks(tmp_path)
    codes = {f.code for f in report.errors}
    assert "entry.parse_failed" in codes


def test_empty_vault_is_clean(tmp_path: Path) -> None:
    report = run_checks(tmp_path)
    assert report.errors == []
    assert report.warnings == []
