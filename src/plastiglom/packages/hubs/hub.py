"""Hub model. Intentionally small — hubs are editorial, not a canonical index."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Hub(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    representative_entries: list[str] = Field(default_factory=list)
    body: str = ""
