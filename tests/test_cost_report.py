"""LLM cost / usage report aggregation."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from plastiglom.apps.cost_report import (
    DEFAULT_PRICES,
    ModelPrice,
    UsageRecord,
    build_report,
    load_usage,
    price_record,
)
from plastiglom.apps.cost_report.report import parse_window


def _line(**fields) -> str:
    base = {
        "timestamp": "2026-05-10T12:00:00+00:00",
        "task": "weekly_analysis",
        "model": "claude-opus-4-7",
        "input_tokens": 1000,
        "output_tokens": 500,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "latency_ms": 1200,
    }
    base.update(fields)
    return json.dumps(base)


def test_load_usage_skips_blank_and_malformed(tmp_path: Path) -> None:
    log = tmp_path / "llm_usage.jsonl"
    log.write_text(
        "\n".join(
            [
                _line(),
                "",
                "{not-json",
                "[1, 2, 3]",  # not a dict
                _line(model="claude-sonnet-4-6", input_tokens=100, output_tokens=50),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    records = load_usage(log)
    assert len(records) == 2
    assert {r.model for r in records} == {"claude-opus-4-7", "claude-sonnet-4-6"}


def test_load_usage_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_usage(tmp_path / "absent.jsonl") == []


def test_price_record_uses_default_table() -> None:
    rec = UsageRecord(
        timestamp=None,
        task="weekly_analysis",
        model="claude-opus-4-7",
        input_tokens=1000,
        output_tokens=1000,
        cache_read_tokens=0,
        cache_creation_tokens=0,
        latency_ms=0,
    )
    expected = (1000 / 1000) * 0.015 + (1000 / 1000) * 0.075
    assert abs(price_record(rec, DEFAULT_PRICES) - expected) < 1e-9


def test_price_record_zero_for_unknown_model() -> None:
    rec = UsageRecord(
        timestamp=None,
        task="x",
        model="claude-unknown",
        input_tokens=1000,
        output_tokens=1000,
        cache_read_tokens=0,
        cache_creation_tokens=0,
        latency_ms=0,
    )
    assert price_record(rec, DEFAULT_PRICES) == 0.0


def test_build_report_overall_breakdowns(tmp_path: Path) -> None:
    log = tmp_path / "llm_usage.jsonl"
    log.write_text(
        "\n".join(
            [
                _line(
                    timestamp="2026-05-10T12:00:00+00:00",
                    task="weekly_analysis",
                    model="claude-opus-4-7",
                    input_tokens=1000,
                    output_tokens=500,
                ),
                _line(
                    timestamp="2026-05-10T15:00:00+00:00",
                    task="tag_assignment",
                    model="claude-sonnet-4-6",
                    input_tokens=200,
                    output_tokens=100,
                ),
                _line(
                    timestamp="2026-05-11T09:00:00+00:00",
                    task="weekly_analysis",
                    model="claude-opus-4-7",
                    input_tokens=2000,
                    output_tokens=1000,
                ),
            ]
        ),
        encoding="utf-8",
    )
    report = build_report(load_usage(log))
    assert report.overall.calls == 3
    assert report.overall.input_tokens == 3200
    assert set(report.by_task) == {"weekly_analysis", "tag_assignment"}
    assert set(report.by_model) == {"claude-opus-4-7", "claude-sonnet-4-6"}
    assert len(report.by_day) == 2
    assert report.unknown_models == set()


def test_build_report_filters_by_window(tmp_path: Path) -> None:
    log = tmp_path / "llm_usage.jsonl"
    log.write_text(
        "\n".join(
            [
                _line(timestamp="2026-05-01T12:00:00+00:00"),
                _line(timestamp="2026-05-10T12:00:00+00:00"),
                _line(timestamp="2026-05-20T12:00:00+00:00"),
            ]
        ),
        encoding="utf-8",
    )
    report = build_report(
        load_usage(log),
        window_start=datetime(2026, 5, 5, tzinfo=UTC),
        window_end=datetime(2026, 5, 15, tzinfo=UTC),
    )
    assert report.overall.calls == 1


def test_build_report_counts_undated_records_in_overall_only(tmp_path: Path) -> None:
    log = tmp_path / "llm_usage.jsonl"
    log.write_text(_line(timestamp=None) + "\n" + _line(), encoding="utf-8")
    report = build_report(load_usage(log))
    assert report.overall.calls == 2
    # Only the dated record makes it into by_day.
    assert sum(t.calls for t in report.by_day.values()) == 1
    assert report.skipped_undated == 1


def test_cache_hit_rate_and_avg_latency() -> None:
    rec = UsageRecord(
        timestamp=datetime(2026, 5, 10, tzinfo=UTC),
        task="weekly_analysis",
        model="claude-opus-4-7",
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=900,
        cache_creation_tokens=0,
        latency_ms=2000,
    )
    report = build_report([rec])
    # 900 / (100 + 900 + 0) = 0.9
    assert abs(report.overall.cache_hit_rate - 0.9) < 1e-9
    assert report.overall.avg_latency_ms == 2000.0


def test_unknown_model_is_flagged() -> None:
    rec = UsageRecord(
        timestamp=datetime(2026, 5, 10, tzinfo=UTC),
        task="weekly_analysis",
        model="claude-future-9",
        input_tokens=100,
        output_tokens=100,
        cache_read_tokens=0,
        cache_creation_tokens=0,
        latency_ms=10,
    )
    report = build_report([rec])
    assert "claude-future-9" in report.unknown_models
    assert report.overall.cost_usd == 0.0


def test_price_overrides(monkeypatch, tmp_path: Path) -> None:
    overrides_path = tmp_path / "prices.json"
    overrides_path.write_text(
        json.dumps(
            {
                "claude-future-9": {
                    "input_per_1k": 0.5,
                    "output_per_1k": 1.0,
                    "cache_read_per_1k": 0.05,
                    "cache_creation_per_1k": 0.25,
                }
            }
        )
    )
    monkeypatch.setenv("PLASTIGLOM_LLM_PRICES_JSON", str(overrides_path))
    rec = UsageRecord(
        timestamp=datetime(2026, 5, 10, tzinfo=UTC),
        task="weekly_analysis",
        model="claude-future-9",
        input_tokens=1000,
        output_tokens=1000,
        cache_read_tokens=0,
        cache_creation_tokens=0,
        latency_ms=0,
    )
    report = build_report([rec])
    assert report.overall.cost_usd == 1.5  # 1k * 0.5 + 1k * 1.0
    assert report.unknown_models == set()


def test_parse_window_since_days() -> None:
    now = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
    start, end = parse_window(since_days=7, since=None, until=None, now=now)
    assert end == now
    assert start == now - timedelta(days=7)


def test_parse_window_iso_strings() -> None:
    start, end = parse_window(
        since_days=None,
        since="2026-05-01T00:00:00",
        until="2026-05-08T00:00:00",
        now=None,
    )
    assert start == datetime(2026, 5, 1, tzinfo=UTC)
    assert end == datetime(2026, 5, 8, tzinfo=UTC)


def test_default_prices_table_has_known_models() -> None:
    # Smoke check: defaults stay populated with at least the two production models.
    assert "claude-opus-4-7" in DEFAULT_PRICES
    assert "claude-sonnet-4-6" in DEFAULT_PRICES
    assert isinstance(DEFAULT_PRICES["claude-opus-4-7"], ModelPrice)
