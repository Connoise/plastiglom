"""Blind-spot detection. See §9 Phase 4 of DESIGN.md.

Builds a "what's underrepresented?" payload for the generator: tag/exercise
coverage stats, the user's seeded memory subjects, and the current pool.
The generator then proposes exercises targeted at gaps.

This module is deliberately thin: the heuristic is just to surface the
inputs and let Opus do the reasoning. Local heuristics would be opinionated
and would drift from the user's actual self-conception.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

from plastiglom.apps.analyzer.digest import compute_stats
from plastiglom.apps.meta_engine.generator import Generator, GeneratorInput
from plastiglom.apps.meta_engine.queue import ProposalRecord
from plastiglom.packages.core.entry import Entry
from plastiglom.packages.core.exercise import Exercise
from plastiglom.packages.memory import list_subjects
from plastiglom.packages.vault.markdown import read_markdown_file
from plastiglom.packages.vault.serializers import parse_entry


def detect_blind_spots(
    *,
    generator: Generator,
    vault_path: Path,
    pool: list[Exercise],
    window_start: datetime,
    window_end: datetime,
    dry_run: bool = False,
) -> list[ProposalRecord]:
    """Run a blind-spot pass over the given window. Returns persisted records."""
    entries = _collect_window(vault_path, window_start, window_end)
    excerpt = _render_excerpt(entries, pool, vault_path)
    payload = GeneratorInput(
        pool=pool,
        analysis_excerpt=excerpt,
        memory_excerpt=_render_memory_subjects(vault_path),
    )
    return generator.generate(payload, dry_run=dry_run)


def _collect_window(vault: Path, start: datetime, end: datetime) -> list[Entry]:
    root = vault / "entries"
    if not root.exists():
        return []
    out: list[Entry] = []
    for path in sorted(root.rglob("*.md")):
        try:
            entry = parse_entry(read_markdown_file(path))
        except Exception:
            continue
        if start <= entry.timestamp_fired < end:
            out.append(entry)
    return out


def _render_excerpt(entries: list[Entry], pool: list[Exercise], vault: Path) -> str:
    if not entries:
        return "WINDOW: empty"
    stats = compute_stats(entries, top_n_tags=20)
    lines = [
        f"WINDOW: {len(entries)} entries",
        f"submitted: {stats.count_by_status.get('submitted', 0)}",
        f"null: {stats.count_by_status.get('null', 0)}",
        "",
        "Exercises by frequency:",
    ]
    pool_ids = {ex.id for ex in pool}
    for ex_id, count in sorted(
        stats.count_by_exercise.items(), key=lambda kv: -kv[1]
    ):
        present = "" if ex_id in pool_ids else " [retired or absent]"
        lines.append(f"- {ex_id}: {count}{present}")
    lines.append("")
    lines.append("Pool exercises NOT used in window:")
    used = set(stats.count_by_exercise)
    for ex in pool:
        if ex.id not in used:
            lines.append(f"- {ex.id} (window={ex.schedule.window.value})")
    lines.append("")
    lines.append("Tag frequency (top):")
    for tag, count in stats.top_tags:
        lines.append(f"- {tag}: {count}")
    # Identify tags in the pool definitions but absent from entries.
    pool_tags = Counter(t for ex in pool for t in ex.tags)
    used_tags = {t for t, _ in stats.top_tags}
    missing = sorted(t for t in pool_tags if t not in used_tags)
    if missing:
        lines.append("")
        lines.append("Pool-declared tags absent from window:")
        lines += [f"- {t}" for t in missing]
    _ = vault  # reserved for future memory-aware excerpts
    return "\n".join(lines)


def _render_memory_subjects(vault: Path) -> str:
    subjects = list_subjects(vault)
    if not subjects:
        return ""
    return "Memory subjects in vault:\n" + "\n".join(f"- {s}" for s in subjects)
