from datetime import UTC, datetime

from plastiglom.apps.telegram_bot.notifier import format_notification
from plastiglom.packages.core.entry import Entry, EntryStatus


def test_format_notification_includes_prompt_and_link():
    entry = Entry(
        id="2026-05-14-evening-review",
        exercise_id="main-evening-review",
        exercise_version=1,
        title="2026-05-14 - Evening review",
        timestamp_fired=datetime(2026, 5, 14, 21, 0, tzinfo=UTC),
        lock_at=datetime(2026, 5, 15, 7, 30, tzinfo=UTC),
        status=EntryStatus.OPENED_UNRESPONDED,
        tags=[],
        prompt_snapshot=["p1?", "p2?"],
        response="",
    )
    notif = format_notification(entry, "http://plastiglom.local/")
    assert "p1?" in notif.body
    assert "p2?" in notif.body
    assert notif.deep_link == "http://plastiglom.local/entry/2026-05-14-evening-review"
