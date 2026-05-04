"""Analyzer skeleton.

The Phase 3 wiring is intentionally narrow here:
  - Gather entries for the window from the vault.
  - Retrieve top-K related chunks via the memory indexer (QMD).
  - Compose an Opus prompt with the window entries verbatim and retrievals as
    cached shared context.
  - Write the report to `analysis/<cadence>/...` via the vault helpers.
  - Append a pointer in `analysis_history/` when a prior report is corrected.

Memory updates are a separate pass (see `memory.py` when implemented).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from plastiglom.packages.core.entry import Entry
from plastiglom.packages.llm.router import LLMCall, LLMRouter, Task
from plastiglom.packages.vault.markdown import (
    FrontmatterDocument,
    read_markdown_file,
    write_markdown_file,
)
from plastiglom.packages.vault.paths import (
    analysis_history_path,
    analysis_monthly_path,
    analysis_query_path,
    analysis_weekly_path,
)
from plastiglom.packages.vault.serializers import parse_entry

logger = logging.getLogger(__name__)


class Cadence(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ADHOC = "adhoc"


@dataclass
class AnalysisRequest:
    cadence: Cadence
    window_start: datetime
    window_end: datetime
    query: str | None = None
    slug: str | None = None
    correction_of: Path | None = None
    correction_note: str | None = None


@dataclass
class Analyzer:
    vault_path: Path
    router: LLMRouter

    def run(self, request: AnalysisRequest) -> Path:
        entries = _collect_window(self.vault_path, request.window_start, request.window_end)
        system = _analyzer_system_prompt()
        cacheable = [
            _render_entries(entries),
            _render_memory_snapshot(self.vault_path),
        ]
        user = _render_user_ask(request)
        task = {
            Cadence.WEEKLY: Task.WEEKLY_ANALYSIS,
            Cadence.MONTHLY: Task.MONTHLY_ANALYSIS,
            Cadence.ADHOC: Task.ADHOC_QUERY,
        }[request.cadence]
        call = LLMCall(
            system=system,
            user=user,
            cacheable_system=cacheable,
            max_tokens=4096,
        )
        response = self.router.invoke(task, call)

        report_path = _report_path(self.vault_path, request)
        write_markdown_file(
            report_path,
            FrontmatterDocument(
                metadata={
                    "cadence": request.cadence.value,
                    "window_start": request.window_start,
                    "window_end": request.window_end,
                    "query": request.query,
                    "slug": request.slug,
                    "correction_of": str(request.correction_of) if request.correction_of else None,
                },
                content=response.text.rstrip() + "\n",
            ),
        )
        if request.correction_of:
            history_slug = request.slug or request.correction_of.stem
            write_markdown_file(
                analysis_history_path(self.vault_path, date.today(), history_slug),
                FrontmatterDocument(
                    metadata={
                        "supersedes": str(request.correction_of),
                        "superseded_by": str(report_path),
                        "note": request.correction_note,
                    },
                    content="",
                ),
            )
        return report_path


def correction_request(prior_report_path: Path, correction_note: str) -> AnalysisRequest:
    """Build a re-run request from an existing report's frontmatter.

    The new report will be written next to the prior one with a `-corrected-`
    suffix, and a pointer is logged to `analysis_history/`.
    """
    doc = read_markdown_file(prior_report_path)
    meta = doc.metadata
    return AnalysisRequest(
        cadence=Cadence(meta["cadence"]),
        window_start=_as_dt(meta["window_start"]),
        window_end=_as_dt(meta["window_end"]),
        query=meta.get("query"),
        slug=meta.get("slug"),
        correction_of=prior_report_path,
        correction_note=correction_note,
    )


def _as_dt(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"cannot coerce {value!r} to datetime")


def _collect_window(vault: Path, start: datetime, end: datetime) -> list[Entry]:
    entries_root = vault / "entries"
    if not entries_root.exists():
        return []
    collected: list[Entry] = []
    for md_path in sorted(entries_root.rglob("*.md")):
        try:
            entry = parse_entry(read_markdown_file(md_path))
        except Exception:
            continue
        if start <= entry.timestamp_fired < end:
            collected.append(entry)
    return collected


def _render_entries(entries: list[Entry]) -> str:
    if not entries:
        return "NO ENTRIES IN WINDOW"
    chunks = ["ENTRIES IN WINDOW:"]
    for entry in entries:
        prompts = "\n".join(f"> {p}" for p in entry.prompt_snapshot)
        chunks.append(
            f"\n--- {entry.id} ({entry.status.value}) ---\n"
            f"fired: {entry.timestamp_fired.isoformat()}\n"
            f"{prompts}\n\n{entry.response}\n"
        )
    return "\n".join(chunks)


def _render_memory_snapshot(vault: Path) -> str:
    memory_dir = vault / "memory"
    if not memory_dir.exists():
        return "NO MEMORY FILES"
    pieces = ["MEMORY SNAPSHOT:"]
    for path in sorted(memory_dir.glob("*.md")):
        pieces.append(f"\n### {path.stem}\n{path.read_text(encoding='utf-8')}")
    return "\n".join(pieces)


def _render_user_ask(request: AnalysisRequest) -> str:
    base = (
        f"Produce a {request.cadence.value} analysis covering "
        f"{request.window_start.isoformat()} through {request.window_end.isoformat()}."
    )
    if request.query:
        base += f"\nUser query: {request.query}"
    if request.correction_note:
        base += (
            "\n\nThe prior report was flagged as wrong. Correction note from the user:\n"
            + request.correction_note
        )
    base += (
        "\n\nReport structure:\n"
        "- Observations (blunt; no softening)\n"
        "- Patterns and contradictions (named, not preserved as ambiguity)\n"
        "- Questions worth pressing on\n"
        "- Recommendations\n"
        "Do not overwrite memory; propose memory updates at the end as a list."
    )
    return base


def _analyzer_system_prompt() -> str:
    return (
        "You are the analyzer for Plastiglom. Analysis is neutral in tone but blunt "
        "in substance. Never soften content on emotional grounds. Name contradictions "
        "as patterns. Offer observations, questions, and recommendations. Never "
        "escalate outside the system. Never overwrite prior analysis or entries."
    )


def _report_path(vault: Path, request: AnalysisRequest) -> Path:
    if request.correction_of:
        # Corrections never overwrite the prior report. Land them next to it
        # with a `-corrected-<UTC unix>` suffix so prior + corrected coexist.
        prior = request.correction_of
        suffix = f"-corrected-{int(datetime.now(tz=UTC).timestamp())}"
        return prior.with_name(prior.stem + suffix + prior.suffix)
    if request.cadence is Cadence.WEEKLY:
        iso = request.window_start.isocalendar()
        return analysis_weekly_path(vault, iso.year, iso.week)
    if request.cadence is Cadence.MONTHLY:
        day = request.window_start
        return analysis_monthly_path(vault, day.year, day.month)
    slug = request.slug or f"adhoc-{int(request.window_start.timestamp())}"
    return analysis_query_path(vault, date.today(), slug)


def week_bounds(anchor: date) -> tuple[datetime, datetime]:
    """Return the [start, end) datetimes for the ISO week containing `anchor`."""
    monday = anchor - timedelta(days=anchor.weekday())
    start = datetime.combine(monday, datetime.min.time(), tzinfo=UTC)
    return start, start + timedelta(days=7)
