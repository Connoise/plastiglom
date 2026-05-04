"""Archiver core logic.

Responsibilities (see §7.4 of DESIGN.md):
  - Create an entry file at prompt firing (status = opened_unresponded / empty).
  - Snapshot the prompt text at firing time; never rewrite it afterwards.
  - Accept a submission, updating status and response, editable until lock_at.
  - On each main firing, finalize prior unlocked entries:
      * no response  -> status = null
      * submitted    -> lock edits (nothing to do beyond the lock_at gate).
  - Maintain a daily index note per day with links to that day's entries.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from plastiglom.packages.core.entry import Entry, EntryStatus
from plastiglom.packages.core.exercise import Exercise, ExerciseCategory
from plastiglom.packages.vault.markdown import (
    FrontmatterDocument,
    read_markdown_file,
    write_markdown_file,
)
from plastiglom.packages.vault.paths import daily_index_path, entry_path
from plastiglom.packages.vault.serializers import entry_to_document, parse_entry


@dataclass
class FireEvent:
    exercise: Exercise
    fired_at: datetime
    lock_at: datetime


@dataclass
class SubmitRequest:
    entry_id: str
    exercise_id: str
    fired_at: datetime
    response: str
    submitted_at: datetime


class Archiver:
    """File-system writer for entries + daily index.

    Pass `on_change` to receive a callback after every successful write so
    the QMD memory indexer can reindex without the archiver knowing about
    QMD specifically. The callback runs in-process; failures are swallowed
    so a flaky indexer can't block archival.
    """

    def __init__(
        self,
        vault_path: Path,
        *,
        on_change: Callable[[Path], None] | None = None,
    ) -> None:
        self.vault_path = vault_path
        self._on_change = on_change

    def _notify_change(self, path: Path) -> None:
        if self._on_change is None:
            return
        # Reindexing is advisory; never fail an archive write because of it.
        with contextlib.suppress(Exception):
            self._on_change(path)

    # ----- firing / submission -----

    def on_fire(self, event: FireEvent) -> Entry:
        """Create the entry file at firing time in `opened_unresponded` state.

        `opened_unresponded` is really "pending" here until the user opens it.
        The web app flips it to `opened_unresponded` when viewed without
        submission, and to `submitted` on submit. If the user never opens it,
        finalization leaves it at the initial state (treated as `null`).
        """
        entry = Entry(
            id=f"{event.fired_at.date().isoformat()}-{_exercise_slug(event.exercise.id)}",
            exercise_id=event.exercise.id,
            exercise_version=event.exercise.version,
            title=f"{event.fired_at.date().isoformat()} - {event.exercise.title}",
            timestamp_fired=event.fired_at,
            timestamp_submitted=None,
            timestamp_last_edited=None,
            lock_at=event.lock_at,
            status=EntryStatus.OPENED_UNRESPONDED,
            tags=list(event.exercise.tags),
            prompt_snapshot=list(event.exercise.prompts),
            response="",
        )
        self._write_entry(entry)
        self._update_daily_index(event.fired_at.date())
        return entry

    def on_submit(self, request: SubmitRequest) -> Entry:
        """Record a submission or edit. Rejects writes after `lock_at`."""
        path = self._entry_path(request.fired_at, request.exercise_id)
        entry = parse_entry(read_markdown_file(path))
        if entry.is_locked(request.submitted_at):
            raise ValueError(f"entry {entry.id} is locked; edits are not accepted")

        if entry.timestamp_submitted is None:
            entry.timestamp_submitted = request.submitted_at
        entry.timestamp_last_edited = request.submitted_at
        entry.response = request.response
        entry.status = EntryStatus.SUBMITTED if request.response.strip() else EntryStatus.NULL
        self._write_entry(entry)
        self._update_daily_index(request.fired_at.date())
        return entry

    # ----- finalization -----

    def finalize_prior(self, now: datetime) -> list[Entry]:
        """Finalize every entry whose lock_at <= now and whose status is still live.

        Returns the list of entries touched. Typically called at each main
        firing so that the previous window's entries are sealed before the new
        prompt is issued.
        """
        touched: list[Entry] = []
        entries_root = self.vault_path / "entries"
        if not entries_root.exists():
            return touched

        for md_path in sorted(entries_root.rglob("*.md")):
            doc = read_markdown_file(md_path)
            try:
                entry = parse_entry(doc)
            except Exception:  # corrupt or partial file; skip
                continue
            if not entry.is_locked(now):
                continue
            if entry.status is EntryStatus.SUBMITTED:
                continue  # already finalized
            if entry.status is EntryStatus.OPENED_UNRESPONDED and not entry.response.strip():
                entry.status = EntryStatus.NULL
                self._write_entry(entry)
                touched.append(entry)
            elif entry.status is EntryStatus.NULL:
                # Already null; ensure it stays on disk with a stable representation.
                continue
        return touched

    # ----- helpers -----

    def _entry_path(self, fired: datetime, exercise_id: str) -> Path:
        return entry_path(self.vault_path, fired, exercise_id)

    def _write_entry(self, entry: Entry) -> None:
        doc = entry_to_document(entry)
        path = entry_path(self.vault_path, entry.timestamp_fired, entry.exercise_id)
        write_markdown_file(path, doc)
        self._notify_change(path)

    def _update_daily_index(self, day: date) -> None:
        """Regenerate the daily index for `day` from on-disk entries."""
        day_dir = (
            self.vault_path
            / "entries"
            / f"{day.year:04d}"
            / f"{day.month:02d}"
        )
        if not day_dir.exists():
            return

        rows: list[tuple[datetime, Entry, Path]] = []
        for md_path in sorted(day_dir.glob(f"{day.day:02d}-*.md")):
            try:
                entry = parse_entry(read_markdown_file(md_path))
            except Exception:
                continue
            rows.append((entry.timestamp_fired, entry, md_path))
        rows.sort(key=lambda r: r[0])

        lines = [f"# {day.isoformat()}", ""]
        for _fired, entry, _path in rows:
            link = f"[[{entry.id}]]"
            lines.append(f"- {entry.timestamp_fired.strftime('%H:%M')} {link} — {entry.status.value}")
        index_doc = FrontmatterDocument(
            metadata={"date": day.isoformat(), "kind": "daily_index"},
            content="\n".join(lines) + "\n",
        )
        index_path = daily_index_path(self.vault_path, day)
        write_markdown_file(index_path, index_doc)
        self._notify_change(index_path)


def _exercise_slug(exercise_id: str) -> str:
    # Mirror packages.core.slugs.exercise_slug_from_id without importing upstream, to
    # keep archiver resilient to refactors. Same behavior intentionally.
    for prefix in ("main-", "secondary-"):
        if exercise_id.startswith(prefix):
            return exercise_id[len(prefix) :]
    return exercise_id


def is_main(exercise: Exercise) -> bool:
    return exercise.category is ExerciseCategory.MAIN
