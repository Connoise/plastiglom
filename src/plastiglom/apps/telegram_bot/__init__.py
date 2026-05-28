"""Telegram bot. Phase 1.

Sends a notification at each firing: exercise name + prompt + deep link to
the web app. No response collection happens here (see §7.2).
"""

from plastiglom.apps.telegram_bot.notifier import (
    Notification,
    format_notification,
    format_reminder,
    send_text,
)

__all__ = ["Notification", "format_notification", "format_reminder", "send_text"]
