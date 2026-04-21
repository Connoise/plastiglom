"""Tag assignment via Sonnet 4.6.

Given an entry and the active tag pool, produce:
  - `applied_tags`: tags pulled from the existing pool that fit this entry.
  - `suggested_tags`: candidate new tags for Opus to consider in pool edits.

The LLM call is routed through `packages/llm`; the parser is defensive — a
malformed response yields empty lists rather than raising, so tagging failure
never blocks archival.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from plastiglom.packages.core.entry import Entry
from plastiglom.packages.core.tags import TagPool
from plastiglom.packages.llm.router import LLMCall, LLMRouter, Task

logger = logging.getLogger(__name__)


@dataclass
class TagAssignment:
    applied_tags: list[str] = field(default_factory=list)
    suggested_tags: list[str] = field(default_factory=list)


_SYSTEM = (
    "You are a tagger for a personal self-reflection archive. "
    "Given the active tag pool and an entry, return JSON with two arrays: "
    "`applied_tags` (tags drawn only from the pool that fit this entry) and "
    "`suggested_tags` (new candidate tags that would improve the pool if adopted). "
    "Prefer precision over recall. Never apply a tag not in the pool."
)


@dataclass
class Tagger:
    router: LLMRouter

    def tag(self, entry: Entry, pool: TagPool) -> TagAssignment:
        pool_block = _render_pool(pool)
        user = _render_entry(entry)
        call = LLMCall(
            system=_SYSTEM,
            user=user,
            cacheable_system=[pool_block],
            max_tokens=512,
            temperature=0.1,
        )
        resp = self.router.invoke(Task.TAG_ASSIGNMENT, call)
        return _parse(resp.text, pool.tag_names())


def _render_pool(pool: TagPool) -> str:
    lines = ["ACTIVE TAG POOL:"]
    for entry in sorted(pool.entries, key=lambda e: e.tag):
        gloss = f" — {entry.gloss}" if entry.gloss else ""
        lines.append(f"- {entry.tag}{gloss}")
    return "\n".join(lines)


def _render_entry(entry: Entry) -> str:
    prompts = "\n".join(f"- {p}" for p in entry.prompt_snapshot)
    return (
        f"ENTRY: {entry.id}\nEXERCISE: {entry.exercise_id}\n"
        f"PROMPTS:\n{prompts}\n\nRESPONSE:\n{entry.response}\n\n"
        "Respond with JSON only."
    )


def _parse(text: str, known: set[str]) -> TagAssignment:
    try:
        data = json.loads(_extract_json(text))
    except (json.JSONDecodeError, ValueError):
        logger.warning("tagger response was not parseable JSON; returning empty")
        return TagAssignment()
    applied = [t for t in data.get("applied_tags", []) if isinstance(t, str) and t in known]
    suggested = [t for t in data.get("suggested_tags", []) if isinstance(t, str) and t]
    return TagAssignment(applied_tags=applied, suggested_tags=suggested)


def _extract_json(text: str) -> str:
    """Pull the first balanced JSON object out of a response."""
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("unbalanced JSON object")
