"""Formatting + send logic for Plastiglom notifications.

The actual send is library-agnostic: implementations may use
python-telegram-bot or aiogram (see §10 of DESIGN.md). This module provides
a formatter that is testable without a Telegram dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from plastiglom.packages.core.entry import Entry


@dataclass(frozen=True)
class Notification:
    title: str
    body: str
    deep_link: str


def format_notification(entry: Entry, web_base_url: str) -> Notification:
    deep_link = f"{web_base_url.rstrip('/')}/entry/{quote(entry.id)}"
    prompt_text = "\n".join(entry.prompt_snapshot)
    title = f"{entry.title}"
    body = f"{prompt_text}\n\nRespond: {deep_link}"
    return Notification(title=title, body=body, deep_link=deep_link)
