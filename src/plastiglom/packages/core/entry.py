"""Entry schema: one file per prompt-firing event. See §6.2 of DESIGN.md."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EntryStatus(StrEnum):
    SUBMITTED = "submitted"
    NULL = "null"
    OPENED_UNRESPONDED = "opened_unresponded"


class Entry(BaseModel):
    """A prompt-firing event's archived record.

    Invariants:
      - `prompt_snapshot` is captured at submission time and never rewritten.
      - Editable until `lock_at`; after that the archiver finalizes it.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    exercise_id: str
    exercise_version: int = Field(ge=1)
    title: str
    timestamp_fired: datetime
    timestamp_submitted: datetime | None = None
    timestamp_last_edited: datetime | None = None
    lock_at: datetime
    status: EntryStatus
    tags: list[str] = Field(default_factory=list)

    prompt_snapshot: list[str] = Field(min_length=1)
    response: str = ""

    def is_locked(self, now: datetime) -> bool:
        return now >= self.lock_at
