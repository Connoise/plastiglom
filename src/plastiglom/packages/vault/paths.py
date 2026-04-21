"""Canonical path conventions for the private vault. See §5 of DESIGN.md."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from plastiglom.packages.core.slugs import exercise_slug_from_id


def entry_path(vault: Path, fired: datetime, exercise_id: str) -> Path:
    slug = exercise_slug_from_id(exercise_id)
    return (
        vault
        / "entries"
        / f"{fired.year:04d}"
        / f"{fired.month:02d}"
        / f"{fired.day:02d}-{slug}.md"
    )


def daily_index_path(vault: Path, day: date) -> Path:
    return (
        vault
        / "daily_index"
        / f"{day.year:04d}"
        / f"{day.month:02d}"
        / f"{day.isoformat()}.md"
    )


def exercise_path(vault: Path, exercise_id: str, category: str) -> Path:
    return vault / "exercises" / category / f"{exercise_id}.md"


def exercise_history_path(vault: Path, day: date, exercise_id: str) -> Path:
    return vault / "exercise_history" / f"{day.isoformat()}-{exercise_id}.md"


def analysis_weekly_path(vault: Path, iso_year: int, iso_week: int) -> Path:
    return vault / "analysis" / "weekly" / f"{iso_year:04d}-W{iso_week:02d}.md"


def analysis_monthly_path(vault: Path, year: int, month: int) -> Path:
    return vault / "analysis" / "monthly" / f"{year:04d}-{month:02d}.md"


def analysis_query_path(vault: Path, day: date, slug: str) -> Path:
    return vault / "analysis" / "queries" / f"{day.isoformat()}-{slug}.md"


def analysis_history_path(vault: Path, day: date, slug: str) -> Path:
    return vault / "analysis_history" / f"{day.isoformat()}-{slug}.md"
