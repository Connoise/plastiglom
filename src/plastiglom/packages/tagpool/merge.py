"""Merge logic for Opus-proposed additions into the live tag pool.

Opus proposes additions and edits; Sonnet proposes `suggested_tags` alongside
each entry. This module answers: "given an existing pool and a batch of
suggested tags, what's new?" It does not mutate; callers decide whether to
persist.
"""

from __future__ import annotations

from dataclasses import dataclass

from plastiglom.packages.core.tags import TagPool, TagPoolEntry


@dataclass
class MergeResult:
    added: list[TagPoolEntry]
    existing: list[str]


def merge_suggestions(
    pool: TagPool,
    suggested: list[str],
    *,
    entry_id: str | None = None,
    max_representatives: int = 3,
) -> tuple[TagPool, MergeResult]:
    """Fold a list of suggested tags into the pool.

    - Unknown tags are added with empty glosses (Opus fills them in later).
    - Known tags gain `entry_id` as a representative, capped at
      `max_representatives`.
    - No gloss is overwritten.
    """
    existing_by_tag = {e.tag: e for e in pool.entries}
    added: list[TagPoolEntry] = []
    existing: list[str] = []

    for tag in suggested:
        tag_norm = tag.strip()
        if not tag_norm:
            continue
        if tag_norm in existing_by_tag:
            entry = existing_by_tag[tag_norm]
            existing.append(tag_norm)
            if (
                entry_id
                and entry_id not in entry.representative_entries
                and len(entry.representative_entries) < max_representatives
            ):
                entry.representative_entries.append(entry_id)
        else:
            new_entry = TagPoolEntry(
                tag=tag_norm,
                gloss="",
                representative_entries=[entry_id] if entry_id else [],
            )
            existing_by_tag[tag_norm] = new_entry
            added.append(new_entry)

    new_pool = TagPool(entries=list(existing_by_tag.values()))
    return new_pool, MergeResult(added=added, existing=existing)
