"""Frontmatter-aware markdown I/O.

Uses python-frontmatter when available, falls back to a small YAML parser shim.
All writes go through an atomic rename to avoid torn files during sync.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class FrontmatterDocument:
    metadata: dict[str, Any] = field(default_factory=dict)
    content: str = ""


_FRONTMATTER_FENCE = "---"


def load_markdown(text: str) -> FrontmatterDocument:
    """Parse a markdown string with optional YAML frontmatter."""
    lines = text.splitlines(keepends=False)
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        return FrontmatterDocument(metadata={}, content=text)

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _FRONTMATTER_FENCE:
            end = i
            break
    if end is None:
        return FrontmatterDocument(metadata={}, content=text)

    fm_text = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :])
    if body.startswith("\n"):
        body = body[1:]
    metadata = yaml.safe_load(fm_text) or {}
    if not isinstance(metadata, dict):
        raise ValueError("frontmatter must be a mapping")
    return FrontmatterDocument(metadata=metadata, content=body)


def dump_markdown(doc: FrontmatterDocument) -> str:
    fm = yaml.safe_dump(
        doc.metadata,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    ).rstrip()
    body = doc.content
    if not body.endswith("\n"):
        body = body + "\n"
    return f"{_FRONTMATTER_FENCE}\n{fm}\n{_FRONTMATTER_FENCE}\n\n{body}"


def read_markdown_file(path: Path) -> FrontmatterDocument:
    return load_markdown(path.read_text(encoding="utf-8"))


def write_markdown_file(path: Path, doc: FrontmatterDocument) -> None:
    """Atomically write a markdown file, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = dump_markdown(doc)
    # NamedTemporaryFile with delete=False, then os.replace for atomicity on the same filesystem.
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp.write(text)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)
