"""Helpers for listing and safely resolving analysis-report files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from plastiglom.packages.vault.markdown import read_markdown_file


@dataclass(frozen=True)
class AnalysisItem:
    relative_path: str  # POSIX-style, relative to vault/analysis/
    cadence: str  # weekly, monthly, queries
    title: str
    has_correction: bool


def list_analysis(vault: Path) -> list[AnalysisItem]:
    """All analysis files, newest first within each cadence."""
    root = vault / "analysis"
    if not root.exists():
        return []
    items: list[AnalysisItem] = []
    for cadence_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        cadence = cadence_dir.name
        for md in sorted(cadence_dir.glob("*.md"), reverse=True):
            relative = md.relative_to(root).as_posix()
            try:
                doc = read_markdown_file(md)
                title = str(doc.metadata.get("query") or md.stem)
                has_correction = bool(doc.metadata.get("correction_of"))
            except Exception:
                title = md.stem
                has_correction = False
            items.append(
                AnalysisItem(
                    relative_path=relative,
                    cadence=cadence,
                    title=title,
                    has_correction=has_correction,
                )
            )
    return items


def resolve_analysis_path(vault: Path, relative: str) -> Path:
    """Resolve `relative` under vault/analysis/, refusing path traversal."""
    if relative.startswith("/") or ".." in Path(relative).parts:
        raise ValueError("invalid analysis path")
    root = (vault / "analysis").resolve()
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("analysis path escapes vault/analysis") from exc
    if not target.is_file():
        raise FileNotFoundError(f"no analysis file at {relative!r}")
    return target
