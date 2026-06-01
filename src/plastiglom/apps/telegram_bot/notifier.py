"""Formatting + send logic for Plastiglom notifications.

`format_notification` is the entry-firing formatter and is library-agnostic
per §10 of DESIGN.md. `send_text` is a minimal Bot-API call used by
non-interactive jobs (the LLM scheduler) that just need to push a short
status line; it is best-effort and returns False on transport failure so
callers can keep going.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from plastiglom.packages.core.entry import Entry

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
DEFAULT_SEND_TIMEOUT_SECONDS = 10.0


# How much of the prompt a reminder ping carries. Reminders are a nudge, not
# the full prompt re-sent — enough to recall which exercise is waiting.
REMINDER_PROMPT_CHARS = 160

FOLLOWUP_NOTE = "A follow-up to this exercise will arrive later today."


@dataclass(frozen=True)
class Notification:
    title: str
    body: str
    deep_link: str


def _deep_link(entry: Entry, web_base_url: str) -> str:
    return f"{web_base_url.rstrip('/')}/entry/{quote(entry.id)}"


def format_notification(
    entry: Entry,
    web_base_url: str,
    *,
    has_followup: bool = False,
) -> Notification:
    deep_link = _deep_link(entry, web_base_url)
    prompt_text = "\n".join(entry.prompt_snapshot)
    title = f"{entry.title}"
    body = prompt_text
    if has_followup:
        body += f"\n\n↪ {FOLLOWUP_NOTE}"
    body += f"\n\nRespond: {deep_link}"
    return Notification(title=title, body=body, deep_link=deep_link)


def _prompt_excerpt(entry: Entry, limit: int = REMINDER_PROMPT_CHARS) -> str:
    """A short slice of the prompt, for reminders that nudge without re-sending."""
    text = " ".join(p.strip() for p in entry.prompt_snapshot).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def format_reminder(entry: Entry, web_base_url: str) -> Notification:
    """A follow-up nudge for an entry still unanswered as its lock nears.

    Carries the exercise title *and* a slice of the prompt (not just the
    title) so the message is actionable on its own, plus the deep link.
    """
    deep_link = _deep_link(entry, web_base_url)
    title = f"Reminder · {entry.title}"
    body = (
        f"Still open — a new exercise is coming soon.\n\n"
        f"{_prompt_excerpt(entry)}\n\nRespond: {deep_link}"
    )
    return Notification(title=title, body=body, deep_link=deep_link)


def send_text(
    text: str,
    *,
    bot_token: str,
    chat_id: str,
    timeout: float = DEFAULT_SEND_TIMEOUT_SECONDS,
    api_base: str = TELEGRAM_API_BASE,
    client: httpx.Client | None = None,
) -> bool:
    """Send a plain-text message via the Telegram Bot API.

    Returns True on a 2xx with `ok: true`, False otherwise. Errors are
    logged but never raised — notifications are best-effort and must not
    poison the job they describe.
    """
    url = f"{api_base.rstrip('/')}/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    try:
        if client is None:
            response = httpx.post(url, json=payload, timeout=timeout)
        else:
            response = client.post(url, json=payload, timeout=timeout)
    except httpx.HTTPError as exc:
        logger.warning("telegram send_text transport error: %s", exc)
        return False
    if response.status_code >= 300:
        logger.warning(
            "telegram send_text non-2xx: %s %s", response.status_code, response.text[:200]
        )
        return False
    try:
        body = response.json()
    except ValueError:
        logger.warning("telegram send_text: non-JSON response: %s", response.text[:200])
        return False
    if not body.get("ok", False):
        logger.warning("telegram send_text: ok=false: %s", body)
        return False
    return True
