"""Serializers between core models and FrontmatterDocument."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from plastiglom.packages.core.entry import Entry, EntryStatus
from plastiglom.packages.core.exercise import (
    Exercise,
    ExerciseCategory,
    ExerciseStatus,
    Schedule,
    ScheduleWindow,
    WeightFactors,
)
from plastiglom.packages.vault.markdown import FrontmatterDocument


def exercise_to_document(ex: Exercise) -> FrontmatterDocument:
    meta: dict[str, Any] = {
        "id": ex.id,
        "title": ex.title,
        "category": ex.category.value,
        "parent_id": ex.parent_id,
        "version": ex.version,
        "status": ex.status.value,
        "schedule": {
            "window": ex.schedule.window.value,
            "weight_factors": ex.schedule.weight_factors.model_dump(),
        },
        "prompts": list(ex.prompts),
        "tags": list(ex.tags),
        "created_at": ex.created_at,
        "created_by": ex.created_by,
        "updated_at": ex.updated_at,
        "updated_by": ex.updated_by,
    }
    return FrontmatterDocument(metadata=meta, content=ex.body)


def exercise_from_document(doc: FrontmatterDocument) -> Exercise:
    m = doc.metadata
    schedule = Schedule(
        window=ScheduleWindow(m["schedule"]["window"]),
        weight_factors=WeightFactors(**(m["schedule"].get("weight_factors") or {})),
    )
    return Exercise(
        id=m["id"],
        title=m["title"],
        category=ExerciseCategory(m["category"]),
        parent_id=m.get("parent_id"),
        version=m["version"],
        status=ExerciseStatus(m.get("status", "active")),
        schedule=schedule,
        prompts=list(m["prompts"]),
        tags=list(m.get("tags") or []),
        created_at=_as_datetime(m["created_at"]),
        created_by=m["created_by"],
        updated_at=_as_datetime(m["updated_at"]),
        updated_by=m["updated_by"],
        body=doc.content,
    )


def entry_to_document(entry: Entry) -> FrontmatterDocument:
    meta: dict[str, Any] = {
        "id": entry.id,
        "exercise_id": entry.exercise_id,
        "exercise_version": entry.exercise_version,
        "title": entry.title,
        "timestamp_fired": entry.timestamp_fired,
        "timestamp_submitted": entry.timestamp_submitted,
        "timestamp_last_edited": entry.timestamp_last_edited,
        "lock_at": entry.lock_at,
        "status": entry.status.value,
        "tags": list(entry.tags),
    }
    prompt_block = "\n".join(entry.prompt_snapshot)
    body = (
        "## Prompt (snapshot)\n\n"
        f"{prompt_block}\n\n"
        "## Response\n\n"
        f"{entry.response}"
    ).rstrip() + "\n"
    return FrontmatterDocument(metadata=meta, content=body)


def parse_entry(doc: FrontmatterDocument) -> Entry:
    m = doc.metadata
    prompts, response = _split_body(doc.content)
    return Entry(
        id=m["id"],
        exercise_id=m["exercise_id"],
        exercise_version=m["exercise_version"],
        title=m["title"],
        timestamp_fired=_as_datetime(m["timestamp_fired"]),
        timestamp_submitted=_as_optional_datetime(m.get("timestamp_submitted")),
        timestamp_last_edited=_as_optional_datetime(m.get("timestamp_last_edited")),
        lock_at=_as_datetime(m["lock_at"]),
        status=EntryStatus(m["status"]),
        tags=list(m.get("tags") or []),
        prompt_snapshot=prompts,
        response=response,
    )


def _split_body(body: str) -> tuple[list[str], str]:
    """Split the canonical entry body into (prompt_snapshot, response)."""
    prompt_marker = "## Prompt (snapshot)"
    response_marker = "## Response"
    if prompt_marker not in body or response_marker not in body:
        raise ValueError("entry body is missing required section headers")
    _, rest = body.split(prompt_marker, 1)
    prompt_block, response_block = rest.split(response_marker, 1)
    prompts = [ln.strip() for ln in prompt_block.strip().splitlines() if ln.strip()]
    if not prompts:
        raise ValueError("entry body has empty prompt snapshot")
    return prompts, response_block.lstrip("\n").rstrip() + ("\n" if response_block.strip() else "")


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"cannot coerce {value!r} to datetime")


def _as_optional_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    return _as_datetime(value)
