from datetime import UTC, datetime, timedelta

import pytest

from plastiglom.apps.seeder import seed_memory_from_yaml
from plastiglom.packages.memory import (
    MemoryFile,
    append_observation,
    list_subjects,
    load_memory,
    memory_path,
    reorganize,
    write_memory,
)


def test_memory_path_rejects_unsafe_subjects(tmp_path):
    with pytest.raises(ValueError):
        memory_path(tmp_path, "../etc")
    with pytest.raises(ValueError):
        memory_path(tmp_path, "Has Spaces")


def test_write_and_load_roundtrip(tmp_path):
    when = datetime(2026, 1, 1, tzinfo=UTC)
    mem = MemoryFile(
        subject="outlook",
        description="forward-looking attitude",
        created_at=when,
        updated_at=when,
        version=1,
        body="Initial seed.\n",
    )
    write_memory(tmp_path, mem)
    loaded = load_memory(tmp_path, "outlook")
    assert loaded.subject == "outlook"
    assert "Initial seed." in loaded.body
    assert loaded.version == 1


def test_append_observation_preserves_prior_body(tmp_path):
    when = datetime(2026, 1, 1, tzinfo=UTC)
    write_memory(
        tmp_path,
        MemoryFile(
            subject="emotional_patterns",
            created_at=when,
            updated_at=when,
            version=1,
            body="The user has flagged X as a recurring tension.\n",
        ),
    )
    later = when + timedelta(days=14)
    updated = append_observation(
        tmp_path,
        "emotional_patterns",
        "Renewed evidence of X surfaced this week.",
        when=later,
    )
    assert "The user has flagged X" in updated.body
    assert "Renewed evidence of X" in updated.body
    assert "## 2026-01-15" in updated.body
    assert updated.version == 2
    assert updated.updated_at == later


def test_append_creates_file_when_missing(tmp_path):
    when = datetime(2026, 5, 1, tzinfo=UTC)
    updated = append_observation(
        tmp_path,
        "open_questions",
        "First observation.",
        when=when,
        source="seed",
    )
    assert updated.version == 1
    assert "## 2026-05-01 (seed)" in updated.body
    assert "First observation." in updated.body


def test_reorganize_replaces_body_and_bumps_version(tmp_path):
    when = datetime(2026, 1, 1, tzinfo=UTC)
    write_memory(
        tmp_path,
        MemoryFile(
            subject="outlook",
            created_at=when,
            updated_at=when,
            version=3,
            body="Old.\n",
        ),
    )
    later = when + timedelta(days=1)
    updated = reorganize(tmp_path, "outlook", "Reorganized body.", when=later)
    assert updated.body.strip() == "Reorganized body."
    assert updated.version == 4
    # Re-read confirms the disk state.
    assert load_memory(tmp_path, "outlook").body.strip() == "Reorganized body."


def test_reorganize_missing_subject_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        reorganize(tmp_path, "missing", "x", when=datetime(2026, 1, 1, tzinfo=UTC))


def test_list_subjects_alphabetic(tmp_path):
    when = datetime(2026, 1, 1, tzinfo=UTC)
    for subject in ("outlook", "emotional_patterns", "open_questions"):
        write_memory(
            tmp_path,
            MemoryFile(
                subject=subject, created_at=when, updated_at=when, version=1
            ),
        )
    assert list_subjects(tmp_path) == [
        "emotional_patterns",
        "open_questions",
        "outlook",
    ]


def test_seed_memory_creates_files(tmp_path):
    yaml_path = tmp_path / "seed.yaml"
    yaml_path.write_text(
        """
memory:
  - subject: outlook
    description: "forward-looking"
    body: "starting body"
  - subject: open_questions
    body: ""
""",
        encoding="utf-8",
    )
    subjects = seed_memory_from_yaml(tmp_path, yaml_path, when=datetime(2026, 1, 1, tzinfo=UTC))
    assert subjects == ["outlook", "open_questions"]
    outlook = load_memory(tmp_path, "outlook")
    assert "starting body" in outlook.body


def test_seed_memory_appends_when_subject_exists(tmp_path):
    when = datetime(2026, 1, 1, tzinfo=UTC)
    write_memory(
        tmp_path,
        MemoryFile(subject="outlook", created_at=when, updated_at=when, version=1, body="orig\n"),
    )
    yaml_path = tmp_path / "seed.yaml"
    yaml_path.write_text(
        """
memory:
  - subject: outlook
    body: "second pass"
""",
        encoding="utf-8",
    )
    seed_memory_from_yaml(tmp_path, yaml_path, when=when + timedelta(days=10))
    loaded = load_memory(tmp_path, "outlook")
    assert "orig" in loaded.body  # prior body preserved
    assert "second pass" in loaded.body
    assert loaded.version == 2
