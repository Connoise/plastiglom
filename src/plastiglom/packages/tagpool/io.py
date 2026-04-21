"""Read/write helpers for `tags/pool.md` and `tags/pool_history.md`.

Pool file format is deliberately human-editable:

    # Tag Pool

    - `tag-name` — short gloss. Representative: [[entry-id]] [[entry-id]]
    - `another-tag` — gloss.

`pool_history.md` is append-only; each append is a dated heading plus a
diff-style block describing additions, edits, and retirements.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from plastiglom.packages.core.tags import TagPool, TagPoolEntry

_POOL_LINE = re.compile(
    r"^\s*-\s+`(?P<tag>[^`]+)`\s*(?:[—-]\s*(?P<gloss>.*?))?"
    r"(?:\s+Representative:\s*(?P<repr>.*))?\s*$"
)
_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")


def load_pool(path: Path) -> TagPool:
    if not path.exists():
        return TagPool()
    entries: list[TagPoolEntry] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = _POOL_LINE.match(raw)
        if not m:
            continue
        tag = m.group("tag").strip()
        gloss = (m.group("gloss") or "").strip()
        repr_field = m.group("repr") or ""
        representatives = [w.strip() for w in _WIKILINK.findall(repr_field)]
        entries.append(
            TagPoolEntry(tag=tag, gloss=gloss, representative_entries=representatives)
        )
    return TagPool(entries=entries)


def write_pool(path: Path, pool: TagPool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = ["# Tag Pool", ""]
    for entry in sorted(pool.entries, key=lambda e: e.tag):
        line = f"- `{entry.tag}`"
        if entry.gloss:
            line += f" — {entry.gloss}"
        if entry.representative_entries:
            refs = " ".join(f"[[{r}]]" for r in entry.representative_entries)
            line += f" Representative: {refs}"
        lines.append(line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_history(path: Path, when: datetime, notes: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"## {when.isoformat(timespec='seconds')}\n\n"
    block = header + notes.rstrip() + "\n\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(block)
