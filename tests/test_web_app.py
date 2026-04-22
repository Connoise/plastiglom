from datetime import UTC, datetime, timedelta
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


def test_home_shows_open_entry(vault, fired_fixture):
    fired, _ = fired_fixture
    client = _client(vault, fired + timedelta(minutes=5))
    r = client.get("/")
    assert r.status_code == 200
    assert "Evening review" in r.text
    assert "What moment deserves a second look?" in r.text
    assert "<textarea" in r.text


def test_submit_persists_and_redirects(vault, fired_fixture):
    fired, _ = fired_fixture
    now = fired + timedelta(minutes=30)
    client = _client(vault, now)
    r = client.post(
        "/entry/2026-05-14-evening-review",
        data={"response": "A real response."},
        follow_redirects=False,
    )
    assert r.status_code == 303
    # On re-view the response is displayed and editable (still unlocked).
    r2 = client.get("/entry/2026-05-14-evening-review")
    assert "A real response." in r2.text
    assert "<textarea" in r2.text


def test_submit_after_lock_returns_409(vault, fired_fixture):
    fired, lock_at = fired_fixture
    client = _client(vault, lock_at + timedelta(minutes=1))
    r = client.post(
        "/entry/2026-05-14-evening-review",
        data={"response": "Too late."},
        follow_redirects=False,
    )
    assert r.status_code == 409


def test_view_after_lock_is_read_only(vault, fired_fixture):
    _, lock_at = fired_fixture
    client = _client(vault, lock_at + timedelta(minutes=1))
    r = client.get("/entry/2026-05-14-evening-review")
    assert r.status_code == 200
    assert "<textarea" not in r.text
    assert "locked" in r.text


def test_day_lists_entries(vault, fired_fixture):
    fired, _ = fired_fixture
    client = _client(vault, fired + timedelta(minutes=5))
    r = client.get("/day/2026-05-14")
    assert r.status_code == 200
    assert "Evening review" in r.text


def test_bad_entry_id_404(vault):
    client = _client(vault, datetime(2026, 1, 1, tzinfo=UTC))
    r = client.get("/entry/not-a-valid-id")
    assert r.status_code == 404
