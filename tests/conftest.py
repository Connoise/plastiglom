"""Shared fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from plastiglom.packages.core.exercise import (
    Exercise,
    ExerciseCategory,
    ExerciseStatus,
    Schedule,
    ScheduleWindow,
    WeightFactors,
)


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def main_exercise() -> Exercise:
    now = datetime(2026, 5, 1, tzinfo=UTC)
    return Exercise(
        id="main-evening-review",
        title="Evening review",
        category=ExerciseCategory.MAIN,
        parent_id=None,
        version=1,
        status=ExerciseStatus.ACTIVE,
        schedule=Schedule(window=ScheduleWindow.EVENING, weight_factors=WeightFactors()),
        prompts=["What moment deserves a second look?"],
        tags=["reflection"],
        created_at=now,
        created_by="seed",
        updated_at=now,
        updated_by="seed",
    )
