"""Follow-up reminder heartbeat: due-detection + the send/stamp pass."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from plastiglom.apps.archiver.archiver import Archiver, FireEvent, SubmitRequest
from plastiglom.apps.scheduler import reminders as reminders_mod
from plastiglom.apps.scheduler.reminders import due_for_reminder, run_reminders
from plastiglom.packages.core.entry import Entry, EntryStatus
from plastiglom.packages.vault.markdown import read_markdown_file
from plastiglom.packages.vault.paths import entry_path
from plastiglom.packages.vault.serializers import parse_entry


def _entry(**overrides) -> Entry:
    fired = datetime(2026, 5, 14, 7, 30, tzinfo=UTC)
    base = dict(
        id="2026-05-14-morning-intentions",
        exercise_id="main-morning-intentions",
        exercise_version=1,
        title="2026-05-14 - Morning intentions",
        timestamp_fired=fired,
        lock_at=datetime(2026, 5, 14, 21, 0, tzinfo=UTC),
        status=EntryStatus.OPENED_UNRESPONDED,
        tags=[],
        prompt_snapshot=["What's the single thing?"],
        response="",
    )
    base.update(overrides)
    return Entry(**base)


# ── due_for_reminder ────────────────────────────────────────────────


def test_due_within_window_and_unanswered():
    entry = _entry()
    now = datetime(2026, 5, 14, 20, 30, tzinfo=UTC)  # 30 min before lock
    assert due_for_reminder(entry, now) is True


def test_not_due_outside_window():
    entry = _entry()
    now = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)  # 9h before lock
    assert due_for_reminder(entry, now) is False


def test_not_due_when_already_submitted():
    entry = _entry(status=EntryStatus.SUBMITTED, response="done")
    now = datetime(2026, 5, 14, 20, 30, tzinfo=UTC)
    assert due_for_reminder(entry, now) is False


def test_not_due_when_response_present_even_if_status_open():
    entry = _entry(response="a draft")
    now = datetime(2026, 5, 14, 20, 30, tzinfo=UTC)
    assert due_for_reminder(entry, now) is False


def test_not_due_when_locked():
    entry = _entry()
    now = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)  # exactly at lock
    assert due_for_reminder(entry, now) is False


def test_not_due_when_reminder_already_sent():
    entry = _entry(reminder_sent_at=datetime(2026, 5, 14, 20, 0, tzinfo=UTC))
    now = datetime(2026, 5, 14, 20, 30, tzinfo=UTC)
    assert due_for_reminder(entry, now) is False


def test_custom_window():
    entry = _entry()
    now = datetime(2026, 5, 14, 18, 30, tzinfo=UTC)  # 2.5h before lock
    assert due_for_reminder(entry, now, timedelta(hours=3)) is True
    assert due_for_reminder(entry, now, timedelta(hours=1)) is False


# ── run_reminders ───────────────────────────────────────────────────


def _fire_open_entry(vault: Path, main_exercise) -> Entry:
    archiver = Archiver(vault)
    fired = datetime(2026, 5, 14, 7, 30, tzinfo=UTC)
    lock = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    return archiver.on_fire(FireEvent(exercise=main_exercise, fired_at=fired, lock_at=lock))


def test_run_reminders_sends_and_stamps(tmp_path: Path, main_exercise, monkeypatch):
    entry = _fire_open_entry(tmp_path, main_exercise)
    sent: list[str] = []
    monkeypatch.setattr(
        reminders_mod, "send_text", lambda text, **kw: sent.append(text) or True
    )

    now = datetime(2026, 5, 14, 20, 30, tzinfo=UTC)
    reminded = run_reminders(
        tmp_path,
        now=now,
        web_base_url="http://plastiglom.test",
        bot_token="T",
        chat_id="C",
    )

    assert len(reminded) == 1
    assert len(sent) == 1
    # The stamp is persisted so a re-run is a no-op.
    on_disk = parse_entry(
        read_markdown_file(entry_path(tmp_path, entry.timestamp_fired, entry.exercise_id))
    )
    assert on_disk.reminder_sent_at == now

    reminded_again = run_reminders(
        tmp_path,
        now=datetime(2026, 5, 14, 20, 45, tzinfo=UTC),
        web_base_url="http://plastiglom.test",
        bot_token="T",
        chat_id="C",
    )
    assert reminded_again == []
    assert len(sent) == 1  # not pinged twice


def test_run_reminders_skips_submitted(tmp_path: Path, main_exercise, monkeypatch):
    entry = _fire_open_entry(tmp_path, main_exercise)
    Archiver(tmp_path).on_submit(
        SubmitRequest(
            entry_id=entry.id,
            exercise_id=entry.exercise_id,
            fired_at=entry.timestamp_fired,
            response="answered already",
            submitted_at=datetime(2026, 5, 14, 9, 0, tzinfo=UTC),
        )
    )
    sent: list[str] = []
    monkeypatch.setattr(
        reminders_mod, "send_text", lambda text, **kw: sent.append(text) or True
    )

    reminded = run_reminders(
        tmp_path,
        now=datetime(2026, 5, 14, 20, 30, tzinfo=UTC),
        web_base_url="http://plastiglom.test",
        bot_token="T",
        chat_id="C",
    )
    assert reminded == []
    assert sent == []


def test_run_reminders_no_stamp_on_send_failure(tmp_path: Path, main_exercise, monkeypatch):
    entry = _fire_open_entry(tmp_path, main_exercise)
    monkeypatch.setattr(reminders_mod, "send_text", lambda text, **kw: False)

    reminded = run_reminders(
        tmp_path,
        now=datetime(2026, 5, 14, 20, 30, tzinfo=UTC),
        web_base_url="http://plastiglom.test",
        bot_token="T",
        chat_id="C",
    )
    assert reminded == []
    on_disk = parse_entry(
        read_markdown_file(entry_path(tmp_path, entry.timestamp_fired, entry.exercise_id))
    )
    assert on_disk.reminder_sent_at is None  # retried next tick
