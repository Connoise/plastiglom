"""Phase 2 weekly digest. See §9 Phase 2 of DESIGN.md.

This is explicitly *not* the Opus weekly analysis from Phase 3. It runs on
Sonnet, touches no memory files, and produces a compact report of:
  - counts by status (submitted / null / opened_unresponded)
  - counts by exercise id
  - most common tags
  - Sonnet-generated themes from the entry corpus

Output is written to `analysis/weekly/YYYY-WW-digest.md` to stay distinct
from the Opus `YYYY-WW.md` report path.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
from pathlib import Path

from plastiglom.packages.core.entry import Entry, EntryStatus
from plastiglom.packages.llm.router import LLMCall, LLMRouter, Task
from plastiglom.packages.vault.markdown import (
    FrontmatterDocument,
    read_markdown_file,
    write_markdown_file,
)
from plastiglom.packages.vault.serializers import parse_entry


@dataclass
class DigestStats:
    count_total: int
    count_by_status: dict[str, int]
    count_by_exercise: dict[str, int]
    top_tags: list[tuple[str, int]]
    submitted_words: int


def compute_stats(entries: list[Entry], *, top_n_tags: int = 10) -> DigestStats:
    status_counts: Counter[str] = Counter()
    exercise_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    submitted_words = 0

    for entry in entries:
        status_counts[entry.status.value] += 1
        exercise_counts[entry.exercise_id] += 1
        for tag in entry.tags:
            tag_counts[tag] += 1
        if entry.status is EntryStatus.SUBMITTED:
            submitted_words += len(entry.response.split())

    return DigestStats(
        count_total=len(entries),
        count_by_status=dict(status_counts),
        count_by_exercise=dict(exercise_counts),
        top_tags=tag_counts.most_common(top_n_tags),
        submitted_words=submitted_words,
    )


def render_stats_markdown(stats: DigestStats) -> str:
    lines = ["## Stats", "", f"- total entries: {stats.count_total}"]
    lines.append("- by status:")
    for status, count in sorted(stats.count_by_status.items()):
        lines.append(f"    - {status}: {count}")
    lines.append("- by exercise:")
    for ex_id, count in sorted(stats.count_by_exercise.items()):
        lines.append(f"    - `{ex_id}`: {count}")
    if stats.top_tags:
        lines.append("- top tags:")
        for tag, count in stats.top_tags:
            lines.append(f"    - `{tag}`: {count}")
    lines.append(f"- submitted words: {stats.submitted_words}")
    return "\n".join(lines)


@dataclass
class WeeklyDigest:
    vault_path: Path
    router: LLMRouter | None = None  # None -> skip the LLM themes section

    def run(self, window_start: datetime, window_end: datetime) -> Path:
        entries = _collect_window(self.vault_path, window_start, window_end)
        stats = compute_stats(entries)
        body_parts = [render_stats_markdown(stats)]

        themes = self._themes(entries) if self.router is not None else None
        if themes:
            body_parts.append("## Themes (Sonnet)\n\n" + themes.strip())

        iso = window_start.isocalendar()
        path = (
            self.vault_path
            / "analysis"
            / "weekly"
            / f"{iso.year:04d}-W{iso.week:02d}-digest.md"
        )
        write_markdown_file(
            path,
            FrontmatterDocument(
                metadata={
                    "cadence": "weekly-digest",
                    "window_start": window_start,
                    "window_end": window_end,
                    "count_total": stats.count_total,
                },
                content="\n\n".join(body_parts).rstrip() + "\n",
            ),
        )
        return path

    def _themes(self, entries: list[Entry]) -> str:
        if not entries:
            return ""
        assert self.router is not None
        user = _render_entries_compact(entries)
        call = LLMCall(
            system=(
                "You summarize a week of short self-reflection entries into themes. "
                "Produce 3-6 bullet points naming recurring subject matter or tone. "
                "Neutral, blunt, no softening. No advice, no memory updates."
            ),
            user=user,
            cacheable_system=[],
            max_tokens=512,
            temperature=0.2,
        )
        resp = self.router.invoke(Task.DAILY_INDEX_SUMMARY, call)
        return resp.text


def _collect_window(vault: Path, start: datetime, end: datetime) -> list[Entry]:
    root = vault / "entries"
    if not root.exists():
        return []
    collected: list[Entry] = []
    for md in sorted(root.rglob("*.md")):
        try:
            entry = parse_entry(read_markdown_file(md))
        except Exception:
            continue
        if start <= entry.timestamp_fired < end:
            collected.append(entry)
    return collected


def _render_entries_compact(entries: list[Entry]) -> str:
    lines = ["ENTRIES:"]
    for entry in entries:
        prompts = " / ".join(entry.prompt_snapshot)
        # Keep each entry short; the digest is not supposed to carry full prose.
        snippet = entry.response.strip().replace("\n", " ")
        if len(snippet) > 400:
            snippet = snippet[:400] + "…"
        lines.append(
            f"- {entry.id} ({entry.status.value}) :: {prompts} :: {snippet}"
        )
    return "\n".join(lines)


def week_bounds(anchor: date, tz: tzinfo | None = None) -> tuple[datetime, datetime]:
    """Monday-to-Monday bounds for the ISO week containing `anchor`.

    Pass `tz` when comparing against timezone-aware entry timestamps; the
    returned bounds are aware in that case and naive otherwise.
    """
    monday = anchor - timedelta(days=anchor.weekday())
    start = datetime.combine(monday, datetime.min.time(), tzinfo=tz)
    return start, start + timedelta(days=7)
