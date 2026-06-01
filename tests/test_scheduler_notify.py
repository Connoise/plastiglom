"""Exercise-firing Telegram notification path.

The scheduler CLI calls `_notify_fire` after every `on_fire`. This module
covers: no-op when unconfigured, send when both creds are present, and the
formatted text shape (title + prompt + deep link).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from plastiglom.apps.scheduler.__main__ import _notify_fire
from plastiglom.packages.core.entry import Entry, EntryStatus


def _entry() -> Entry:
    return Entry(
        id="2026-05-14-evening-review",
        exercise_id="main-evening-review",
        exercise_version=1,
        title="2026-05-14 - Evening review",
        timestamp_fired=datetime(2026, 5, 14, 21, 0, tzinfo=UTC),
        lock_at=datetime(2026, 5, 15, 7, 30, tzinfo=UTC),
        status=EntryStatus.OPENED_UNRESPONDED,
        tags=[],
        prompt_snapshot=["What moment deserves a second look?"],
        response="",
    )


@dataclass
class _StubSettings:
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    web_base_url: str = "http://plastiglom.local"


def test_notify_fire_no_op_when_unconfigured(monkeypatch) -> None:
    calls: list[tuple] = []

    def _spy(*args: Any, **kwargs: Any) -> bool:
        calls.append((args, kwargs))
        return True

    monkeypatch.setattr("plastiglom.apps.scheduler.__main__.send_text", _spy)
    _notify_fire(_entry(), _StubSettings())
    assert calls == []


def test_notify_fire_no_op_when_only_token_set(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        "plastiglom.apps.scheduler.__main__.send_text",
        lambda *a, **k: calls.append((a, k)) or True,
    )
    _notify_fire(_entry(), _StubSettings(telegram_bot_token="T"))
    assert calls == []


def test_notify_fire_sends_formatted_message(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _spy(text: str, *, bot_token: str, chat_id: str) -> bool:
        captured["text"] = text
        captured["bot_token"] = bot_token
        captured["chat_id"] = chat_id
        return True

    monkeypatch.setattr("plastiglom.apps.scheduler.__main__.send_text", _spy)
    _notify_fire(
        _entry(),
        _StubSettings(
            telegram_bot_token="TOKEN",
            telegram_chat_id="CHAT",
            web_base_url="http://plastiglom.local",
        ),
    )

    assert captured["bot_token"] == "TOKEN"
    assert captured["chat_id"] == "CHAT"
    assert "2026-05-14 - Evening review" in captured["text"]
    assert "What moment deserves a second look?" in captured["text"]
    assert "http://plastiglom.local/entry/2026-05-14-evening-review" in captured["text"]


def test_notify_fire_absorbs_send_failure(monkeypatch) -> None:
    """A returned False from send_text must not raise."""
    monkeypatch.setattr(
        "plastiglom.apps.scheduler.__main__.send_text", lambda *a, **k: False
    )
    _notify_fire(
        _entry(),
        _StubSettings(telegram_bot_token="T", telegram_chat_id="C"),
    )


def test_notify_fire_includes_followup_mention(monkeypatch) -> None:
    from plastiglom.apps.telegram_bot.notifier import FOLLOWUP_NOTE

    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "plastiglom.apps.scheduler.__main__.send_text",
        lambda text, **k: captured.update(text=text) or True,
    )
    _notify_fire(
        _entry(),
        _StubSettings(telegram_bot_token="T", telegram_chat_id="C"),
        has_followup=True,
    )
    assert FOLLOWUP_NOTE in captured["text"]


def test_notify_fire_omits_followup_by_default(monkeypatch) -> None:
    from plastiglom.apps.telegram_bot.notifier import FOLLOWUP_NOTE

    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "plastiglom.apps.scheduler.__main__.send_text",
        lambda text, **k: captured.update(text=text) or True,
    )
    _notify_fire(
        _entry(),
        _StubSettings(telegram_bot_token="T", telegram_chat_id="C"),
    )
    assert FOLLOWUP_NOTE not in captured["text"]
