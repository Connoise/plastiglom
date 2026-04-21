"""Slug helpers used for filenames, ids, and vault paths."""

from __future__ import annotations

import re
import unicodedata

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Produce a lowercase kebab-case slug suitable for filenames and ids."""
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    normalized = normalized.lower().strip()
    slug = _SLUG_STRIP.sub("-", normalized).strip("-")
    return slug or "untitled"


def exercise_slug_from_id(exercise_id: str) -> str:
    """Drop the leading `main-`/`secondary-` prefix if present, for filename use."""
    for prefix in ("main-", "secondary-"):
        if exercise_id.startswith(prefix):
            return exercise_id[len(prefix) :]
    return exercise_id
