"""Telegram notification wiring for the LLM scheduler.

Two layers:
  - `send_text` posts to the Bot API and tolerates transport / shape failures
  - the runner invokes a configurable notifier on every executed job and
    treats notifier exceptions as non-fatal (a bad notify can't poison state)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest

from plastiglom.apps.llm_scheduler.cadence import Weekly
from plastiglom.apps.llm_scheduler.runner import (
    Job,
    JobContext,
    JobResult,
    build_telegram_notifier,
    force_run,
    format_job_message,
    run_due,
)
from plastiglom.apps.llm_scheduler.state import save_state
from plastiglom.apps.telegram_bot.notifier import send_text

UTC = ZoneInfo("UTC")


# ---------------------------------------------------------------------------
# send_text
# ---------------------------------------------------------------------------


def _client_with_handler(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler)


def test_send_text_posts_to_correct_url_and_payload() -> None:
    captured: dict[str, Any] = {}

    def _handle(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = httpx.Response(200).json if False else None
        captured["body"] = request.read().decode()
        return httpx.Response(200, json={"ok": True})

    client = _client_with_handler(httpx.MockTransport(_handle))
    ok = send_text(
        "hello",
        bot_token="TOKEN",
        chat_id="42",
        api_base="https://example.test",
        client=client,
    )
    assert ok is True
    import json as _json

    assert captured["url"] == "https://example.test/botTOKEN/sendMessage"
    body = _json.loads(captured["body"])
    assert body == {
        "chat_id": "42",
        "text": "hello",
        "disable_web_page_preview": True,
    }


def test_send_text_returns_false_on_http_error_status() -> None:
    def _handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="bad")

    client = _client_with_handler(httpx.MockTransport(_handle))
    assert (
        send_text("x", bot_token="t", chat_id="c", api_base="https://x.test", client=client)
        is False
    )


def test_send_text_returns_false_on_ok_false_body() -> None:
    def _handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "description": "blocked"})

    client = _client_with_handler(httpx.MockTransport(_handle))
    assert (
        send_text("x", bot_token="t", chat_id="c", api_base="https://x.test", client=client)
        is False
    )


def test_send_text_returns_false_on_transport_error() -> None:
    def _handle(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope")

    client = _client_with_handler(httpx.MockTransport(_handle))
    assert (
        send_text("x", bot_token="t", chat_id="c", api_base="https://x.test", client=client)
        is False
    )


# ---------------------------------------------------------------------------
# Notifier integration
# ---------------------------------------------------------------------------


@dataclass
class _StubSettings:
    vault_path: Path
    logs_dir: Path
    timezone: ZoneInfo = UTC
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


def _stub_settings(tmp_path: Path, **kw: Any) -> _StubSettings:
    return _StubSettings(vault_path=tmp_path, logs_dir=tmp_path / "logs", **kw)


@dataclass
class _Capture:
    results: list[JobResult] = field(default_factory=list)

    def __call__(self, result: JobResult) -> None:
        self.results.append(result)


def _job(name: str, returning: str | None = None) -> Job:
    def _run(_ctx: JobContext) -> str | None:
        return returning

    return Job(
        name=name,
        description=name,
        cadence=Weekly(weekday=6, at=time(22, 0), tz=UTC),
        run=_run,
    )


def _boom(name: str) -> Job:
    def _run(_ctx: JobContext) -> str | None:
        raise RuntimeError("nope")

    return Job(
        name=name,
        description=name,
        cadence=Weekly(weekday=6, at=time(22, 0), tz=UTC),
        run=_run,
    )


def test_run_due_invokes_notifier_for_each_fired_job(tmp_path: Path) -> None:
    capture = _Capture()
    settings = _stub_settings(tmp_path)
    now = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)

    run_due(
        [_job("digest_weekly", returning="wrote /x"), _job("analyzer_weekly")],
        settings=settings,
        router=object(),
        now=now,
        notifier=capture,
    )

    assert [r.name for r in capture.results] == ["digest_weekly", "analyzer_weekly"]
    assert capture.results[0].summary == "wrote /x"
    assert capture.results[1].summary is None
    assert all(r.fired for r in capture.results)


def test_run_due_notifier_receives_failures(tmp_path: Path) -> None:
    capture = _Capture()
    settings = _stub_settings(tmp_path)
    now = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)

    run_due([_boom("digest_weekly")], settings=settings, router=object(), now=now, notifier=capture)

    assert len(capture.results) == 1
    assert capture.results[0].fired is False
    assert capture.results[0].error == "nope"


def test_run_due_skips_notifier_for_not_due_jobs(tmp_path: Path) -> None:
    capture = _Capture()
    settings = _stub_settings(tmp_path)
    now = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)
    # Pre-seed the job as having run after the previous Sunday tick.
    save_state(tmp_path / "logs", {"digest_weekly": datetime(2026, 5, 10, 22, 5, tzinfo=UTC)})

    run_due(
        [_job("digest_weekly", returning="x")],
        settings=settings,
        router=object(),
        now=now,
        notifier=capture,
    )

    assert capture.results == []


def test_run_due_swallows_notifier_exceptions(tmp_path: Path) -> None:
    """A flaky notifier must not affect the job's fired status."""
    settings = _stub_settings(tmp_path)
    now = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)

    def _raise(_result: JobResult) -> None:
        raise RuntimeError("telegram down")

    report = run_due(
        [_job("digest_weekly", returning="ok")],
        settings=settings,
        router=object(),
        now=now,
        notifier=_raise,
    )
    assert [r.fired for r in report.results] == [True]


def test_force_run_invokes_notifier_too(tmp_path: Path) -> None:
    capture = _Capture()
    settings = _stub_settings(tmp_path)
    now = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)

    force_run(
        [_job("digest_weekly", returning="forced run")],
        "digest_weekly",
        settings=settings,
        router=object(),
        now=now,
        notifier=capture,
    )

    assert [r.name for r in capture.results] == ["digest_weekly"]
    assert capture.results[0].summary == "forced run"


# ---------------------------------------------------------------------------
# format_job_message + factory
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "result, expected",
    [
        (
            JobResult(name="digest_weekly", fired=True, summary="wrote /v/analysis/x.md"),
            "Plastiglom: wrote /v/analysis/x.md",
        ),
        (
            JobResult(name="analyzer_weekly", fired=True),
            "Plastiglom: analyzer_weekly completed",
        ),
        (
            JobResult(name="digest_weekly", fired=False, error="api 429"),
            "Plastiglom: digest_weekly failed — api 429",
        ),
    ],
)
def test_format_job_message_shapes(result: JobResult, expected: str) -> None:
    assert format_job_message(result) == expected


def test_build_telegram_notifier_returns_none_when_unconfigured(tmp_path: Path) -> None:
    assert build_telegram_notifier(_stub_settings(tmp_path)) is None
    assert (
        build_telegram_notifier(_stub_settings(tmp_path, telegram_bot_token="t"))
        is None
    )
    assert (
        build_telegram_notifier(_stub_settings(tmp_path, telegram_chat_id="c"))
        is None
    )


def test_build_telegram_notifier_sends_when_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def _fake_send_text(text: str, **kwargs: Any) -> bool:
        captured["text"] = text
        captured["kwargs"] = kwargs
        return True

    # Patch the symbol where the runner imported it.
    monkeypatch.setattr(
        "plastiglom.apps.llm_scheduler.runner.send_text", _fake_send_text
    )
    notifier = build_telegram_notifier(
        _stub_settings(tmp_path, telegram_bot_token="TOKEN", telegram_chat_id="CHAT")
    )
    assert notifier is not None

    notifier(JobResult(name="digest_weekly", fired=True, summary="wrote it"))

    assert captured["text"] == "Plastiglom: wrote it"
    assert captured["kwargs"]["bot_token"] == "TOKEN"
    assert captured["kwargs"]["chat_id"] == "CHAT"
