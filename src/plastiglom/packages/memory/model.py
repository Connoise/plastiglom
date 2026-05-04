"""Memory file model.

The frontmatter is metadata only; the body is the durable observations
Opus has accumulated and reorganized for that subject.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemoryFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    description: str = ""
    created_at: datetime
    updated_at: datetime
    version: int = Field(default=1, ge=1)
    body: str = ""
