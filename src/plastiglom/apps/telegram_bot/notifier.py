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
