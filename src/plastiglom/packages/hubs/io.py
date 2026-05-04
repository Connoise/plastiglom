"""Hub file I/O.

File format is frontmatter + free-form body. The frontmatter is the
machine-readable surface; the body is for the user (or Opus) to explain
what the hub means.

    ---
    name: Identity
    description: "The 'who am I' family of themes."
    tags: [values, identity, temporal-self]
    representative_entries:
      - 2026-05-14-values-drift
    ---

    Notes, questions, threads. Free-form.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plastiglom.packages.hubs.hub import Hub
from plastiglom.packages.vault.markdown import (
    FrontmatterDocument,
    read_markdown_file,
    write_markdown_file,
)


def hub_path(vault: Path, name: str) -> Path:
    return vault / "hubs" / f"{_slugify(name)}.md"


def load_hub(path: Path) -> Hub:
    doc = read_markdown_file(path)
    meta = doc.metadata
    return Hub(
        name=meta["name"],
        description=meta.get("description", ""),
        tags=list(meta.get("tags") or []),
        representative_entries=list(meta.get("representative_entries") or []),
        body=doc.content,
    )


def write_hub(vault: Path, hub: Hub) -> Path:
    path = hub_path(vault, hub.name)
    metadata: dict[str, Any] = {
        "name": hub.name,
        "description": hub.description,
        "tags": list(hub.tags),
        "representative_entries": list(hub.representative_entries),
    }
    write_markdown_file(path, FrontmatterDocument(metadata=metadata, content=hub.body))
    return path


def list_hubs(vault: Path) -> list[Hub]:
    directory = vault / "hubs"
    if not directory.exists():
        return []
    hubs: list[Hub] = []
    for path in sorted(directory.glob("*.md")):
        try:
            hubs.append(load_hub(path))
        except Exception:
            continue
    return hubs


def _slugify(name: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "hub"
