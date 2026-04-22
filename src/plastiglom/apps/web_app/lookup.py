"""Read-side helpers for the web app.

The entry layout `YYYY/MM/DD-<slug>.md` lets us resolve an id to a path
without an index — the id is `YYYY-MM-DD-<slug>`. We still rglob when
scanning for open entries; vault sizes stay small so cost is negligible.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from plastiglom.packages.core.entry import Entry, EntryStatus
from plastiglom.packages.vault.markdown import read_markdown_file
from plastiglom.packages.vault.serializers import parse_entry

_ENTRY_ID = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-(?P<slug>[A-Za-z0-9_-]+)$")


def entry_path_from_id(vault: Path, entry_id: str) -> Path:
    m = _ENTRY_ID.match(entry_id)
    if not m:
        raise ValueError(f"malformed entry id: {entry_id!r}")
    y, mo, d = m.group(1), m.group(2), m.group(3)
    slug = m.group("slug")
    return vault / "entries" / y / mo / f"{d}-{slug}.md"


def load_entry(vault: Path, entry_id: str) -> Entry:
    return parse_entry(read_markdown_file(entry_path_from_id(vault, entry_id)))


def iter_entries_for_day(vault: Path, day: date) -> list[Entry]:
    directory = vault / "entries" / f"{day.year:04d}" / f"{day.month:02d}"
    if not directory.exists():
        return []
    entries: list[Entry] = []
    for path in sorted(directory.glob(f"{day.day:02d}-*.md")):
        try:
            entries.append(parse_entry(read_markdown_file(path)))
        except Exception:
            continue
    entries.sort(key=lambda e: e.timestamp_fired)
    return entries


def latest_open_entry(vault: Path, now: datetime) -> Entry | None:
    """Return the most-recently fired entry that's still unlocked, if any.

    "Open" means `lock_at > now` and status is not finalized-null. This is
    what the home page surfaces: the prompt the user should be answering.
    """
    entries_root = vault / "entries"
    if not entries_root.exists():
        return None
    best: Entry | None = None
    for md in entries_root.rglob("*.md"):
        try:
            entry = parse_entry(read_markdown_file(md))
        except Exception:
            continue
        if entry.lock_at <= now:
            continue
        if entry.status is EntryStatus.NULL:
            continue
        if best is None or entry.timestamp_fired > best.timestamp_fired:
            best = entry
    return best
