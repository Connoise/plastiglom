"""Seed the tag pool from a YAML file.

YAML shape:

    tags:
      - tag: values
        gloss: "identity and what the user cares about"
      - tag: relationships
        gloss: ""
    hubs:
      - name: Identity
        description: "Who am I questions."
        tags: [values, identity]

Existing entries in the pool are preserved unless `--replace` is passed.
Hub files are written one per entry under `hubs/`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from plastiglom.packages.core.tags import TagPool, TagPoolEntry
from plastiglom.packages.hubs import Hub, write_hub
from plastiglom.packages.tagpool import load_pool, write_pool


def seed_tagpool_from_yaml(
    vault_path: Path,
    yaml_path: Path,
    *,
    replace: bool = False,
) -> tuple[TagPool, list[Hub]]:
    """Apply a YAML seed to the vault. Returns the resulting pool and hubs."""
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    pool = _merge_pool(vault_path, data.get("tags") or [], replace=replace)
    hubs = _write_hubs(vault_path, data.get("hubs") or [])
    return pool, hubs


def _merge_pool(vault_path: Path, tag_specs: list[dict[str, Any]], *, replace: bool) -> TagPool:
    pool_path = vault_path / "tags" / "pool.md"
    existing = TagPool() if replace else load_pool(pool_path)
    by_tag = {e.tag: e for e in existing.entries}

    for spec in tag_specs:
        tag = str(spec["tag"]).strip()
        if not tag:
            continue
        gloss = str(spec.get("gloss") or "").strip()
        if tag in by_tag:
            # Never overwrite an existing gloss silently.
            if gloss and not by_tag[tag].gloss:
                by_tag[tag].gloss = gloss
        else:
            by_tag[tag] = TagPoolEntry(tag=tag, gloss=gloss)

    pool = TagPool(entries=sorted(by_tag.values(), key=lambda e: e.tag))
    write_pool(pool_path, pool)
    return pool


def _write_hubs(vault_path: Path, hub_specs: list[dict[str, Any]]) -> list[Hub]:
    hubs: list[Hub] = []
    for spec in hub_specs:
        hub = Hub(
            name=str(spec["name"]).strip(),
            description=str(spec.get("description") or "").strip(),
            tags=[str(t).strip() for t in (spec.get("tags") or []) if str(t).strip()],
            representative_entries=[
                str(r).strip() for r in (spec.get("representative_entries") or []) if str(r).strip()
            ],
            body=str(spec.get("body") or ""),
        )
        write_hub(vault_path, hub)
        hubs.append(hub)
    return hubs
