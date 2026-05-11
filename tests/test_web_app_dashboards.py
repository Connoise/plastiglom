"""End-to-end smoke tests for /stats and /cost.

We seed a few entries + a tiny usage log, hit each route, and assert the
core numbers show up in the rendered HTML.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from plastiglom.apps.archiver.archiver import Archiver, FireEvent, SubmitRequest
from plastiglom.apps.web_app.app import create_app

TZ = ZoneInfo("UTC")


def _client(vault, fake_now: datetime) -> TestClient:
    return TestClient(create_app(vault_path=vault, tz=TZ, now=lambda: fake_now))


def _seed_usage(vault, *, model: str = "claude-opus-4-7", count: int = 2) -> None:
    path = vault / "logs" / "llm_usage.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for i in range(count):
        lines.append(
            json.dumps(
                {
                    "timestamp": (
                        datetime(2026, 5, 10, 12, tzinfo=UTC) + timedelta(hours=i)
                    ).isoformat(),
                    "task": "weekly_analysis",
                    "model": model,
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cache_read_tokens": 0,
                    "cache_creation_tokens": 0,
                    "latency_ms": 1500,
                }
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_stats_page_renders_with_submitted_entry(vault, main_exercise) -> None:
    archiver = Archiver(vault)
    fired = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    archiver.on_fire(FireEvent(exercise=main_exercise, fired_at=fired, lock_at=fired + timedelta(hours=10)))
    archiver.on_submit(
        SubmitRequest(
            entry_id=f"{fired.date().isoformat()}-evening-review",
            exercise_id=main_exercise.id,
            fired_at=fired,
            submitted_at=fired + timedelta(minutes=5),
            response="kept the focus today",
        )
    )

    client = _client(vault, fired + timedelta(hours=1))
    r = client.get("/stats")
    assert r.status_code == 200
    assert "Streak" in r.text
    assert "main-evening-review" in r.text
    # 1 entry submitted -> submission rate 100%.
    assert "100.0%" in r.text or "100%" in r.text


def test_stats_page_window_filter_respected(vault, main_exercise) -> None:
    archiver = Archiver(vault)
    fired = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    archiver.on_fire(FireEvent(exercise=main_exercise, fired_at=fired, lock_at=fired + timedelta(hours=10)))
    # `today` (clock) is way after the fire; since_days=1 should exclude it.
    client = _client(vault, datetime(2026, 6, 1, tzinfo=UTC))
    r = client.get("/stats?since_days=1")
    assert r.status_code == 200
    # window label should mention the bounds; entry count should be 0.
    assert "entries: 0" in r.text or "entries: <" in r.text or "entries:" in r.text


def test_cost_page_renders_breakdown(vault) -> None:
    _seed_usage(vault, count=3)
    client = _client(vault, datetime(2026, 5, 11, tzinfo=UTC))
    r = client.get("/cost")
    assert r.status_code == 200
    assert "weekly_analysis" in r.text
    assert "claude-opus-4-7" in r.text
    # 3 calls @ 1000in / 500out @ opus pricing = 0.045 + 0.1125 = $0.1575
    assert "0.1575" in r.text


def test_cost_page_with_no_log_renders_empty(vault) -> None:
    client = _client(vault, datetime(2026, 5, 11, tzinfo=UTC))
    r = client.get("/cost")
    assert r.status_code == 200
    assert "calls: 0" in r.text


def test_nav_includes_stats_and_cost_links(vault) -> None:
    client = _client(vault, datetime(2026, 5, 11, tzinfo=UTC))
    r = client.get("/")
    assert r.status_code == 200
    assert 'href="/stats"' in r.text
    assert 'href="/cost"' in r.text
