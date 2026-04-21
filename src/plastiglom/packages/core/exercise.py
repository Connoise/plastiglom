"""Exercise template schema. Mirrors the YAML frontmatter in §6.1 of DESIGN.md."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExerciseCategory(StrEnum):
    MAIN = "main"
    SECONDARY = "secondary"


class ExerciseStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"
    DRAFT = "draft"


class ScheduleWindow(StrEnum):
    MORNING = "morning"
    EVENING = "evening"
    CONTEXTUAL = "contextual"


class WeightFactors(BaseModel):
    """Weighting inputs consumed by the scheduler's sampling step."""

    model_config = ConfigDict(extra="forbid")

    recent_relevance: float = Field(0.5, ge=0.0, le=1.0)
    depth_potential: float = Field(0.5, ge=0.0, le=1.0)
    weekday_weight: float = Field(0.5, ge=0.0, le=1.0)
    weekend_weight: float = Field(0.5, ge=0.0, le=1.0)
    novelty_value: float = Field(0.5, ge=0.0, le=1.0)


class Schedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window: ScheduleWindow
    weight_factors: WeightFactors = Field(default_factory=WeightFactors)


class Exercise(BaseModel):
    """One exercise template file.

    Secondary exercises set `parent_id` to a main exercise's id.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    category: ExerciseCategory
    parent_id: str | None = None
    version: int = Field(ge=1)
    status: ExerciseStatus = ExerciseStatus.ACTIVE
    schedule: Schedule
    prompts: list[str] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    created_by: str
    updated_at: datetime
    updated_by: str
    body: str = ""

    @field_validator("id")
    @classmethod
    def _id_is_slug(cls, v: str) -> str:
        if not v or not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError("exercise id must be a slug of [A-Za-z0-9_-]")
        return v

    @field_validator("prompts")
    @classmethod
    def _prompts_nonempty(cls, v: list[str]) -> list[str]:
        stripped = [p.strip() for p in v]
        if any(not p for p in stripped):
            raise ValueError("prompts must be non-empty strings")
        return stripped

    def model_post_init(self, __context: object) -> None:  # type: ignore[override]
        if self.category is ExerciseCategory.SECONDARY and self.parent_id is None:
            raise ValueError("secondary exercises require parent_id")
        if self.category is ExerciseCategory.MAIN and self.parent_id is not None:
            raise ValueError("main exercises must not have parent_id")
