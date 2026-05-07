"""Smoke tests for the mobile UI shell + JSON API."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from plastiglom.apps.archiver.archiver import Archiver, FireEvent
from plastiglom.apps.web_app.app import create_app

TZ = ZoneInfo("UTC")


@pytest.fixture
def fired_fixture(vault, main_exercise):
    archiver = Archiver(vault)
    fired = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    lock_at = fired + timedelta(hours=10)
    archiver.on_fire(FireEvent(exercise=main_exercise, fired_at=fired, lock_at=lock_at))
    return fired, lock_at


def _client(vault, fake_now: datetime):
    app = create_app(vault_path=vault, tz=TZ, now=lambda: fake_now)
    return TestClient(app)


def test_mobile_shell_serves_html(vault):
    client = _client(vault, datetime(2026, 5, 14, 21, 5, tzinfo=UTC))
    r = client.get("/mobile")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Plastiglom" in r.text
    assert 'id="root"' in r.text


def test_static_jsx_served(vault):
    client = _client(vault, datetime(2026, 5, 14, 21, 5, tzinfo=UTC))
    r = client.get("/static/mobile/pg-app.jsx")
    assert r.status_code == 200
    assert "ReactDOM.createRoot" in r.text


def test_mobile_shell_injects_cache_bust(vault):
    """The /mobile shell must rewrite JSX <script src> to include ?v=<build>
    so browsers cannot serve a stale Babel-compiled cache after a deploy."""
    client = _client(vault, datetime(2026, 5, 14, 21, 5, tzinfo=UTC))
    r = client.get("/mobile")
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-cache"
    text = r.text
    # Every JSX include must carry a versioned query string.
    import re as _re
    jsx_includes = _re.findall(r'src="(/static/mobile/[^"]+\.jsx[^"]*)"', text)
    assert jsx_includes, "no JSX includes found in mobile shell"
    for src in jsx_includes:
        assert "?v=" in src, f"missing cache-bust on {src}"


def test_api_today_returns_open_entry(vault, fired_fixture):
    fired, _ = fired_fixture
    client = _client(vault, fired + timedelta(minutes=5))
    r = client.get("/api/today")
    assert r.status_code == 200
    j = r.json()
    assert j["entry"] is not None
    assert "Evening review" in j["entry"]["title"]
    assert j["entry"]["is_locked"] is False
    assert j["entry"]["prompt_snapshot"] == ["What moment deserves a second look?"]


def test_api_today_returns_null_when_locked(vault, fired_fixture):
    _, lock_at = fired_fixture
    client = _client(vault, lock_at + timedelta(minutes=1))
    r = client.get("/api/today")
    assert r.status_code == 200
    assert r.json()["entry"] is None


def test_api_entry_get_and_submit(vault, fired_fixture):
    fired, _ = fired_fixture
    client = _client(vault, fired + timedelta(minutes=10))
    entry_id = "2026-05-14-evening-review"

    r = client.get(f"/api/entry/{entry_id}")
    assert r.status_code == 200
    assert r.json()["entry"]["response"] == ""

    r = client.post(f"/api/entry/{entry_id}", json={"response": "Looked at the meeting again."})
    assert r.status_code == 200
    assert r.json()["entry"]["response"].strip() == "Looked at the meeting again."

    r = client.get(f"/api/entry/{entry_id}")
    assert r.json()["entry"]["response"].strip() == "Looked at the meeting again."


def test_api_entry_submit_after_lock_returns_409(vault, fired_fixture):
    _, lock_at = fired_fixture
    client = _client(vault, lock_at + timedelta(minutes=1))
    r = client.post(
        "/api/entry/2026-05-14-evening-review",
        json={"response": "Too late."},
    )
    assert r.status_code == 409


def test_api_archive_lists_entries(vault, fired_fixture):
    fired, _ = fired_fixture
    client = _client(vault, fired + timedelta(minutes=5))
    r = client.get("/api/archive")
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert len(entries) >= 1
    assert "Evening review" in entries[0]["title"]


def test_api_info(vault, fired_fixture):
    fired, _ = fired_fixture
    app = create_app(
        vault_path=vault,
        tz=TZ,
        now=lambda: fired + timedelta(minutes=5),
        morning_fire=time(7, 30),
        evening_fire=time(21, 0),
        telegram_configured=True,
    )
    client = TestClient(app)
    r = client.get("/api/info")
    assert r.status_code == 200
    j = r.json()
    assert j["timezone"] == "UTC"
    assert j["morning_fire"] == "07:30"
    assert j["evening_fire"] == "21:00"
    assert j["telegram_configured"] is True
    assert j["entries_count"] >= 1
    assert j["analysis_count"] == 0
    assert j["proposals_pending"] == 0
    assert j["version"]


def test_api_info_defaults_when_unconfigured(vault):
    client = _client(vault, datetime(2026, 5, 14, 21, 5, tzinfo=UTC))
    r = client.get("/api/info")
    assert r.status_code == 200
    j = r.json()
    assert j["morning_fire"] is None
    assert j["evening_fire"] is None
    assert j["telegram_configured"] is False


def test_api_analysis_empty_vault(vault):
    client = _client(vault, datetime(2026, 5, 14, 21, 5, tzinfo=UTC))
    r = client.get("/api/analysis")
    assert r.status_code == 200
    assert r.json() == {"groups": []}
