"""Seed memory files from a YAML manifest.

YAML shape:

    memory:
      - subject: emotional_patterns
        description: "Recurring emotional dynamics."
        body: |
          Initial seed observations. The user has flagged X and Y as
          things they want tracked. Opus extends this over time.
      - subject: outlook
        body: ""

Re-running the seeder is safe: if a memory file already exists for a subject,
the seed body is appended as a new dated section rather than overwriting.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from plastiglom.packages.memory import (
    MemoryFile,
    append_observation,
    memory_path,
    write_memory,
)


def seed_memory_from_yaml(
    vault_path: Path,
    yaml_path: Path,
    *,
    when: datetime | None = None,
) -> list[str]:
    """Apply a memory seed YAML; returns the list of subjects touched."""
    when = when or datetime.now(tz=UTC)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    subjects: list[str] = []

    for spec in data.get("memory") or []:
        subject = str(spec["subject"]).strip()
        if not subject:
            continue
        body = str(spec.get("body") or "").strip()
        description = str(spec.get("description") or "").strip()

        path = memory_path(vault_path, subject)
        if path.exists():
            if body:
                append_observation(vault_path, subject, body, when=when, source="seed")
        else:
            memory = MemoryFile(
                subject=subject,
                description=description,
                created_at=when,
                updated_at=when,
                version=1,
                body=(body + "\n") if body else "",
            )
            write_memory(vault_path, memory)
        subjects.append(subject)

    return subjects
