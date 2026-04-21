"""Tag-pool model. See §6.3 of DESIGN.md."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TagPoolEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag: str
    gloss: str = ""
    representative_entries: list[str] = Field(default_factory=list)


class TagPool(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[TagPoolEntry] = Field(default_factory=list)

    def tag_names(self) -> set[str]:
        return {e.tag for e in self.entries}

    def get(self, tag: str) -> TagPoolEntry | None:
        for e in self.entries:
            if e.tag == tag:
                return e
        return None
