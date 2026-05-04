"""Memory file I/O.

File format:

    ---
    subject: emotional_patterns
    description: ""
    created_at: 2026-01-01T00:00:00Z
    updated_at: 2026-05-14T00:00:00Z
    version: 4
    ---

    Body of accumulated observations, in whatever shape Opus has organized
    it into. Append calls add a date-tagged subsection at the bottom;
    reorganize calls replace the whole body.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from plastiglom.packages.memory.model import MemoryFile
from plastiglom.packages.vault.markdown import (
    FrontmatterDocument,
    read_markdown_file,
    write_markdown_file,
)

_SUBJECT_SLUG = re.compile(r"^[a-z0-9_-]+$")


def memory_path(vault: Path, subject: str) -> Path:
    if not _SUBJECT_SLUG.match(subject):
        raise ValueError(f"memory subject must be a snake-case slug: {subject!r}")
    return vault / "memory" / f"{subject}.md"


def load_memory(vault: Path, subject: str) -> MemoryFile:
    doc = read_markdown_file(memory_path(vault, subject))
    return _from_doc(doc)


def write_memory(vault: Path, memory: MemoryFile) -> Path:
    path = memory_path(vault, memory.subject)
    write_markdown_file(path, _to_doc(memory))
    return path


def list_subjects(vault: Path) -> list[str]:
    directory = vault / "memory"
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.md"))


def append_observation(
    vault: Path,
    subject: str,
    observation: str,
    *,
    when: datetime,
    source: str = "analyzer",
) -> MemoryFile:
    """Append a date-tagged observation section to the subject's body.

    Never rewrites prior body content. Increments `version` and updates
    `updated_at`. Creates the file with empty body if it didn't exist.
    """
    path = memory_path(vault, subject)
    section = (
        f"## {when.strftime('%Y-%m-%d')} ({source})\n\n"
        f"{observation.strip()}\n"
    )
    if path.exists():
        memory = _from_doc(read_markdown_file(path))
        memory.body = (memory.body.rstrip() + "\n\n" + section).lstrip()
        memory.version += 1
        memory.updated_at = when
    else:
        memory = MemoryFile(
            subject=subject,
            created_at=when,
            updated_at=when,
            version=1,
            body=section,
        )
    write_memory(vault, memory)
    return memory


def reorganize(
    vault: Path,
    subject: str,
    new_body: str,
    *,
    when: datetime,
) -> MemoryFile:
    """Replace the body wholesale.

    Reorganization is allowed during routine analysis (see §6.4). The vault's
    private git repo captures the diff; no sidecar history is needed.
    Corrections go through the analyzer's `analysis_history/` channel.
    """
    path = memory_path(vault, subject)
    if not path.exists():
        raise FileNotFoundError(f"no memory file for subject {subject!r}")
    memory = _from_doc(read_markdown_file(path))
    memory.body = new_body.strip() + "\n"
    memory.updated_at = when
    memory.version += 1
    write_memory(vault, memory)
    return memory


def _from_doc(doc: FrontmatterDocument) -> MemoryFile:
    m = doc.metadata
    return MemoryFile(
        subject=m["subject"],
        description=m.get("description", ""),
        created_at=_as_datetime(m["created_at"]),
        updated_at=_as_datetime(m["updated_at"]),
        version=int(m.get("version", 1)),
        body=doc.content,
    )


def _to_doc(memory: MemoryFile) -> FrontmatterDocument:
    metadata: dict[str, Any] = {
        "subject": memory.subject,
        "description": memory.description,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
        "version": memory.version,
    }
    return FrontmatterDocument(metadata=metadata, content=memory.body)


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"cannot coerce {value!r} to datetime")
