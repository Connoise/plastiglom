"""Runner dispatch + state-file behaviour for the LLM scheduler.

Real job callables hit LLMRouter; here we register stub jobs through the
public `Job` dataclass and let the runner orchestrate them. The default
registry (`build_default_jobs`) is exercised only for shape, not execution.
"""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from plastiglom.apps.llm_scheduler.cadence import Weekly
from plastiglom.apps.llm_scheduler.runner import (
    Job,
    JobContext,
    build_default_jobs,
    force_run,
    is_due,
    run_due,
)
from plastiglom.apps.llm_scheduler.state import load_state, save_state

UTC = ZoneInfo("UTC")


def _stub_settings(vault: Path) -> object:
    class _S:
        vault_path = vault
        logs_dir = vault / "logs"
        timezone = UTC

    return _S()


def _stub_job(name: str, tracker: list[str], *, weekday: int = 6) -> Job:
    def _action(_ctx: JobContext) -> None:
        tracker.append(name)

    return Job(
        name=name,
        description=name,
        cadence=Weekly(weekday=weekday, at=time(22, 0), tz=UTC),
        run=_action,
    )


def test_is_due_when_no_prior_run() -> None:
    job = _stub_job("a", [])
    now = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)  # Monday
    assert is_due(job, now=now, last_run=None) is True


def test_is_due_false_when_last_run_is_after_previous_tick() -> None:
    job = _stub_job("a", [])
    now = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)  # Monday
    last = datetime(2026, 5, 10, 22, 5, tzinfo=UTC)  # just after Sunday tick
    assert is_due(job, now=now, last_run=last) is False


def test_is_due_true_when_new_tick_has_passed() -> None:
    job = _stub_job("a", [])
    now = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)  # Monday
    last = datetime(2026, 5, 3, 22, 5, tzinfo=UTC)  # previous week
    assert is_due(job, now=now, last_run=last) is True


def test_run_due_fires_only_due_jobs_and_persists_state(tmp_path: Path) -> None:
    settings = _stub_settings(tmp_path)
    tracker: list[str] = []
    due_job = _stub_job("digest_weekly", tracker)
    not_due = _stub_job("blind_spots", tracker, weekday=2)  # Wednesday tick
    now = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)  # Monday morning
    # Pre-seed only `blind_spots` as recently run so it stays not-due.
    save_state(tmp_path / "logs", {"blind_spots": now - timedelta(days=1)})

    report = run_due(
        [due_job, not_due], settings=settings, router=object(), now=now
    )

    fired = {r.name for r in report.fired}
    assert fired == {"digest_weekly"}
    assert tracker == ["digest_weekly"]
    state = load_state(tmp_path / "logs")
    assert state["digest_weekly"] == now


def test_run_due_does_not_persist_state_on_failure(tmp_path: Path) -> None:
    settings = _stub_settings(tmp_path)

    def _boom(_ctx: JobContext) -> None:
        raise RuntimeError("anthropic exploded")

    job = Job(
        name="digest_weekly",
        description="x",
        cadence=Weekly(weekday=6, at=time(22, 0), tz=UTC),
        run=_boom,
    )
    now = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)

    report = run_due([job], settings=settings, router=object(), now=now)
    assert report.errors and report.errors[0].error == "anthropic exploded"
    assert load_state(tmp_path / "logs") == {}


def test_run_due_only_filter_skips_others(tmp_path: Path) -> None:
    settings = _stub_settings(tmp_path)
    tracker: list[str] = []
    a = _stub_job("digest_weekly", tracker)
    b = _stub_job("analyzer_weekly", tracker)
    now = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)

    report = run_due(
        [a, b], settings=settings, router=object(), now=now, only={"digest_weekly"}
    )

    assert tracker == ["digest_weekly"]
    names = {r.name for r in report.results}
    assert names == {"digest_weekly"}


def test_force_run_executes_regardless_of_cadence(tmp_path: Path) -> None:
    settings = _stub_settings(tmp_path)
    tracker: list[str] = []
    job = _stub_job("digest_weekly", tracker)
    # Last run is *just past* the previous tick, so the job would be skipped
    # by run_due. force_run should still fire it.
    save_state(
        tmp_path / "logs",
        {"digest_weekly": datetime(2026, 5, 10, 22, 5, tzinfo=UTC)},
    )
    now = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)

    result = force_run([job], "digest_weekly", settings=settings, router=object(), now=now)

    assert result.fired
    assert tracker == ["digest_weekly"]
    assert load_state(tmp_path / "logs")["digest_weekly"] == now


def test_force_run_raises_on_unknown_job(tmp_path: Path) -> None:
    settings = _stub_settings(tmp_path)
    with pytest.raises(KeyError):
        force_run([], "missing", settings=settings, router=object(), now=datetime.now(tz=UTC))


def test_state_round_trip_is_lossless(tmp_path: Path) -> None:
    payload = {
        "digest_weekly": datetime(2026, 5, 10, 22, 0, tzinfo=UTC),
        "analyzer_monthly": datetime(2026, 4, 30, 23, 0, tzinfo=UTC),
    }
    save_state(tmp_path / "logs", payload)
    assert load_state(tmp_path / "logs") == payload


def test_state_load_ignores_malformed_entries(tmp_path: Path) -> None:
    target = tmp_path / "logs" / "llm_scheduler_state.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(
            {
                "good": "2026-05-10T22:00:00+00:00",
                "bad_value": 12,
                "bad_iso": "nope",
            }
        ),
        encoding="utf-8",
    )
    state = load_state(tmp_path / "logs")
    assert set(state) == {"good"}


def test_default_registry_names_match_design_docs() -> None:
    """Smoke check: the default registry exposes the four scheduled jobs the
    DESIGN doc names. Cadence details are validated by the cadence tests."""

    class _Settings:
        timezone = UTC
        digest_weekly_at = time(22, 0)
        analyzer_weekly_at = time(22, 30)
        analyzer_monthly_at = time(23, 0)
        meta_blind_spots_at = time(4, 0)

    jobs = build_default_jobs(_Settings())  # type: ignore[arg-type]
    assert {j.name for j in jobs} == {
        "digest_weekly",
        "analyzer_weekly",
        "analyzer_monthly",
        "meta_blind_spots",
    }
