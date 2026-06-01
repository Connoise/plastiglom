"""Follow-up reminder pass. See §7.2 of DESIGN.md.

The firing notification is the first nudge; this is the *second*. When an
entry is still unanswered and its `lock_at` (the next main firing) is within
the reminder window, we send one more Telegram ping carrying the exercise
title plus a slice of the prompt. `reminder_sent_at` is stamped on the entry
so the heartbeat never double-pings, and the pass is otherwise idempotent —
safe to run on a frequent cron tick.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

from plastiglom.apps.telegram_bot import format_reminder, send_text
from plastiglom.packages.core.entry import Entry, EntryStatus
from plastiglom.packages.vault.markdown import read_markdown_file, write_markdown_file
from plastiglom.packages.vault.paths import entry_path
from plastiglom.packages.vault.serializers import entry_to_document, parse_entry

logger = logging.getLogger(__name__)

# "1 hour left before a new exercise is given" — the next main firing is the
# entry's `lock_at`, so the default window is one hour ahead of it.
DEFAULT_REMINDER_WINDOW = timedelta(hours=1)


def due_for_reminder(
    entry: Entry,
    now: datetime,
    window: timedelta = DEFAULT_REMINDER_WINDOW,
) -> bool:
    """True when `entry` should get a follow-up reminder right now.

    Conditions: no reminder sent yet, no substantive response, not already
    submitted, still editable (not past `lock_at`), and within `window` of
    `lock_at`.
    """
    if entry.reminder_sent_at is not None:
        return False
    if entry.status is EntryStatus.SUBMITTED or entry.has_response():
        return False
    if entry.is_locked(now):
        return False
    return entry.lock_at - now <= window


def run_reminders(
    vault_path: Path,
    *,
    now: datetime,
    web_base_url: str,
    bot_token: str,
    chat_id: str,
    window: timedelta = DEFAULT_REMINDER_WINDOW,
) -> list[Entry]:
    """Send a reminder for every due entry; stamp `reminder_sent_at` on send.

    Returns the entries actually reminded. Send failures are swallowed by
    `send_text`; on failure we leave `reminder_sent_at` unset so the next
    tick retries (mirrors the LLM scheduler's retry-on-failure stance).
    """
    entries_root = vault_path / "entries"
    if not entries_root.exists():
        return []

    reminded: list[Entry] = []
    for md_path in sorted(entries_root.rglob("*.md")):
        try:
            entry = parse_entry(read_markdown_file(md_path))
        except Exception:  # corrupt or partial file; skip
            continue
        if not due_for_reminder(entry, now, window):
            continue
        notif = format_reminder(entry, web_base_url)
        text = f"{notif.title}\n\n{notif.body}"
        if not send_text(text, bot_token=bot_token, chat_id=chat_id):
            logger.warning("reminder send failed for entry=%s", entry.id)
            continue
        entry.reminder_sent_at = now
        path = entry_path(vault_path, entry.timestamp_fired, entry.exercise_id)
        write_markdown_file(path, entry_to_document(entry))
        logger.info("reminder sent for entry=%s", entry.id)
        reminded.append(entry)
    return reminded
