from datetime import UTC, datetime

from plastiglom.apps.telegram_bot.notifier import (
    FOLLOWUP_NOTE,
    format_notification,
    format_reminder,
)
from plastiglom.packages.core.entry import Entry, EntryStatus


def _entry(prompt_snapshot=None) -> Entry:
    return Entry(
        id="2026-05-14-evening-review",
        exercise_id="main-evening-review",
        exercise_version=1,
        title="2026-05-14 - Evening review",
        timestamp_fired=datetime(2026, 5, 14, 21, 0, tzinfo=UTC),
        lock_at=datetime(2026, 5, 15, 7, 30, tzinfo=UTC),
        status=EntryStatus.OPENED_UNRESPONDED,
        tags=[],
        prompt_snapshot=prompt_snapshot or ["p1?", "p2?"],
        response="",
    )


def test_format_notification_includes_prompt_and_link():
    notif = format_notification(_entry(), "http://plastiglom.local/")
    assert "p1?" in notif.body
    assert "p2?" in notif.body
    assert notif.deep_link == "http://plastiglom.local/entry/2026-05-14-evening-review"
    # No follow-up note unless requested.
    assert FOLLOWUP_NOTE not in notif.body


def test_format_notification_mentions_followup_when_present():
    notif = format_notification(_entry(), "http://plastiglom.local/", has_followup=True)
    assert FOLLOWUP_NOTE in notif.body
    # Prompt and link still present alongside the note.
    assert "p1?" in notif.body
    assert "http://plastiglom.local/entry/2026-05-14-evening-review" in notif.body


def test_format_reminder_carries_title_prompt_excerpt_and_link():
    notif = format_reminder(_entry(), "http://plastiglom.local/")
    assert "2026-05-14 - Evening review" in notif.title
    assert notif.title.lower().startswith("reminder")
    # A slice of the prompt rides along, not just the title.
    assert "p1?" in notif.body
    assert "http://plastiglom.local/entry/2026-05-14-evening-review" in notif.body


def test_format_reminder_truncates_long_prompt():
    long_prompt = "A" * 400
    notif = format_reminder(_entry([long_prompt]), "http://plastiglom.local/")
    # Excerpt is bounded and ellipsized; full 400 chars never sent.
    assert long_prompt not in notif.body
    assert "…" in notif.body
