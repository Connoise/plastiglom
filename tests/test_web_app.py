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


def _seed_followup_secondary(vault):
    """Write an active secondary connected to main-evening-review."""
    from plastiglom.packages.core.exercise import (
        Exercise,
        ExerciseCategory,
        Schedule,
        ScheduleWindow,
        WeightFactors,
    )
    from plastiglom.packages.vault.markdown import write_markdown_file
    from plastiglom.packages.vault.serializers import exercise_to_document

    now = datetime(2026, 5, 1, tzinfo=UTC)
    sec = Exercise(
        id="secondary-evening-review-deepen",
        title="Evening review — deepen",
        category=ExerciseCategory.SECONDARY,
        parent_id="main-evening-review",
        version=1,
        schedule=Schedule(window=ScheduleWindow.CONTEXTUAL, weight_factors=WeightFactors()),
        prompts=["Say it again with fewer hedges."],
        tags=[],
        created_at=now,
        created_by="seed",
        updated_at=now,
        updated_by="seed",
    )
    write_markdown_file(
        vault / "exercises" / "secondary" / f"{sec.id}.md", exercise_to_document(sec)
    )


def _fire_morning(vault, main_exercise):
    """Fire main_exercise in the morning so it locks later the *same* day."""
    archiver = Archiver(vault)
    fired = datetime(2026, 5, 14, 7, 30, tzinfo=UTC)
    lock_at = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    archiver.on_fire(FireEvent(exercise=main_exercise, fired_at=fired, lock_at=lock_at))
    return fired, lock_at


def test_followup_surfaced_when_connected_secondary_exists(vault, main_exercise):
    fired, _ = _fire_morning(vault, main_exercise)
    _seed_followup_secondary(vault)
    client = _client(vault, fired + timedelta(minutes=5))

    # HTML home page mentions the coming follow-up.
    r = client.get("/")
    assert "follow-up" in r.text.lower()

    # API exposes the flag for the mobile UI.
    payload = client.get("/api/today").json()["entry"]
    assert payload["has_followup"] is True


def test_no_followup_when_no_connected_secondary(vault, main_exercise):
    fired, _ = _fire_morning(vault, main_exercise)
    client = _client(vault, fired + timedelta(minutes=5))
    payload = client.get("/api/today").json()["entry"]
    assert payload["has_followup"] is False


def test_no_followup_for_evening_entry_that_locks_next_day(vault, main_exercise, fired_fixture):
    # Evening firing locks next morning, so even with a connected secondary
    # there is no follow-up "later today".
    fired, _ = fired_fixture
    _seed_followup_secondary(vault)
    client = _client(vault, fired + timedelta(minutes=5))
    payload = client.get("/api/today").json()["entry"]
    assert payload["has_followup"] is False
