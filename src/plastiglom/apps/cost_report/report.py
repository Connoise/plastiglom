"""Roll up `logs/llm_usage.jsonl` into a cost / usage report.

The router writes one JSON line per Anthropic call with token counts, task,
model, latency, and timestamp. This module is the only consumer — both the
CLI and the web app build their views from `build_report()`.

Pricing is intentionally a small static table (`DEFAULT_PRICES`) keyed by
model name. The user can override via `PLASTIGLOM_LLM_PRICES_JSON` (a path
to a JSON file with the same shape) when prices change or for non-default
models. We never reach out to the API to fetch prices — that adds latency
and a network dependency for a CLI that should be instant.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class ModelPrice:
    """USD per 1K tokens. Mirrors Anthropic's published billing units."""

    input_per_1k: float
    output_per_1k: float
    cache_read_per_1k: float
    cache_creation_per_1k: float


# Public list prices for the Claude 4 family in USD per 1K tokens.
# Numbers come from Anthropic's pricing page; override via the env hook below
# if the user has a different contract.
DEFAULT_PRICES: dict[str, ModelPrice] = {
    "claude-opus-4-8": ModelPrice(
        input_per_1k=0.015,
        output_per_1k=0.075,
        cache_read_per_1k=0.0015,
        cache_creation_per_1k=0.01875,
    ),
    "claude-opus-4-7": ModelPrice(
        input_per_1k=0.015,
        output_per_1k=0.075,
        cache_read_per_1k=0.0015,
        cache_creation_per_1k=0.01875,
    ),
    "claude-opus-4-6": ModelPrice(
        input_per_1k=0.015,
        output_per_1k=0.075,
        cache_read_per_1k=0.0015,
        cache_creation_per_1k=0.01875,
    ),
    "claude-sonnet-4-6": ModelPrice(
        input_per_1k=0.003,
        output_per_1k=0.015,
        cache_read_per_1k=0.0003,
        cache_creation_per_1k=0.00375,
    ),
    "claude-haiku-4-5-20251001": ModelPrice(
        input_per_1k=0.001,
        output_per_1k=0.005,
        cache_read_per_1k=0.0001,
        cache_creation_per_1k=0.00125,
    ),
}


def load_price_overrides() -> dict[str, ModelPrice]:
    """Optional user-supplied price overrides via `PLASTIGLOM_LLM_PRICES_JSON`.

    File schema: `{"model-id": {"input_per_1k": 0.0, "output_per_1k": 0.0,
    "cache_read_per_1k": 0.0, "cache_creation_per_1k": 0.0}, ...}`.
    """
    path = os.environ.get("PLASTIGLOM_LLM_PRICES_JSON")
    if not path:
        return {}
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        model: ModelPrice(**fields)
        for model, fields in raw.items()
        if isinstance(fields, dict)
    }


def resolve_prices() -> dict[str, ModelPrice]:
    """Return the effective price table: defaults overlaid with overrides."""
    table = dict(DEFAULT_PRICES)
    table.update(load_price_overrides())
    return table


@dataclass(frozen=True)
class UsageRecord:
    timestamp: datetime | None
    task: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    latency_ms: int

    @classmethod
    def from_jsonline(cls, payload: dict[str, object]) -> UsageRecord:
        ts_raw = payload.get("timestamp")
        ts: datetime | None = None
        if isinstance(ts_raw, str):
            try:
                ts = datetime.fromisoformat(ts_raw)
            except ValueError:
                ts = None
        return cls(
            timestamp=ts,
            task=str(payload.get("task", "unknown")),
            model=str(payload.get("model", "unknown")),
            input_tokens=int(payload.get("input_tokens") or 0),
            output_tokens=int(payload.get("output_tokens") or 0),
            cache_read_tokens=int(payload.get("cache_read_tokens") or 0),
            cache_creation_tokens=int(payload.get("cache_creation_tokens") or 0),
            latency_ms=int(payload.get("latency_ms") or 0),
        )


def price_record(rec: UsageRecord, prices: dict[str, ModelPrice]) -> float:
    """USD cost of a single call. Unknown models price at 0 (and are flagged)."""
    p = prices.get(rec.model)
    if p is None:
        return 0.0
    return (
        rec.input_tokens / 1000 * p.input_per_1k
        + rec.output_tokens / 1000 * p.output_per_1k
        + rec.cache_read_tokens / 1000 * p.cache_read_per_1k
        + rec.cache_creation_tokens / 1000 * p.cache_creation_per_1k
    )


@dataclass
class Totals:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms_total: int = 0

    @property
    def cache_hit_rate(self) -> float:
        """Fraction of input tokens served from cache (0.0 if no input)."""
        denom = self.input_tokens + self.cache_read_tokens + self.cache_creation_tokens
        if denom <= 0:
            return 0.0
        return self.cache_read_tokens / denom

    @property
    def avg_latency_ms(self) -> float:
        if self.calls == 0:
            return 0.0
        return self.latency_ms_total / self.calls

    def add(self, rec: UsageRecord, cost: float) -> None:
        self.calls += 1
        self.input_tokens += rec.input_tokens
        self.output_tokens += rec.output_tokens
        self.cache_read_tokens += rec.cache_read_tokens
        self.cache_creation_tokens += rec.cache_creation_tokens
        self.cost_usd += cost
        self.latency_ms_total += rec.latency_ms


@dataclass
class Report:
    window_start: datetime | None
    window_end: datetime | None
    overall: Totals = field(default_factory=Totals)
    by_task: dict[str, Totals] = field(default_factory=dict)
    by_model: dict[str, Totals] = field(default_factory=dict)
    by_day: dict[date, Totals] = field(default_factory=dict)
    unknown_models: set[str] = field(default_factory=set)
    record_count: int = 0
    skipped_undated: int = 0

    @property
    def top_tasks(self) -> list[tuple[str, Totals]]:
        return sorted(self.by_task.items(), key=lambda kv: kv[1].cost_usd, reverse=True)


def load_usage(path: Path) -> list[UsageRecord]:
    """Read every JSONL record from `path`. Malformed lines are dropped."""
    if not path.exists():
        return []
    records: list[UsageRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        records.append(UsageRecord.from_jsonline(payload))
    return records


def build_report(
    records: list[UsageRecord],
    *,
    prices: dict[str, ModelPrice] | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> Report:
    """Aggregate `records` into a `Report`.

    `window_start`/`window_end` (UTC) filter records by timestamp; records
    without a parseable timestamp are counted under `skipped_undated` and
    excluded from `by_day` but still flow into the overall totals so the
    report doesn't lie about historical files written before the timestamp
    field existed.
    """
    pricing = prices if prices is not None else resolve_prices()
    by_task: dict[str, Totals] = defaultdict(Totals)
    by_model: dict[str, Totals] = defaultdict(Totals)
    by_day: dict[date, Totals] = defaultdict(Totals)
    unknown: Counter[str] = Counter()
    overall = Totals()
    skipped_undated = 0
    counted = 0

    for rec in records:
        if rec.timestamp is None:
            skipped_undated += 1
        else:
            if window_start is not None and rec.timestamp < window_start:
                continue
            if window_end is not None and rec.timestamp >= window_end:
                continue
        cost = price_record(rec, pricing)
        if rec.model not in pricing:
            unknown[rec.model] += 1
        overall.add(rec, cost)
        by_task[rec.task].add(rec, cost)
        by_model[rec.model].add(rec, cost)
        if rec.timestamp is not None:
            by_day[rec.timestamp.astimezone(UTC).date()].add(rec, cost)
        counted += 1

    return Report(
        window_start=window_start,
        window_end=window_end,
        overall=overall,
        by_task=dict(by_task),
        by_model=dict(by_model),
        by_day=dict(sorted(by_day.items())),
        unknown_models=set(unknown),
        record_count=counted,
        skipped_undated=skipped_undated,
    )


def parse_window(
    *,
    since_days: int | None,
    since: str | None,
    until: str | None,
    now: datetime | None = None,
) -> tuple[datetime | None, datetime | None]:
    """Translate CLI `--since-days` / `--since` / `--until` into a UTC window."""
    end = _parse_iso_or_none(until)
    start = _parse_iso_or_none(since)
    if since_days is not None:
        anchor = now or datetime.now(tz=UTC)
        if end is None:
            end = anchor
        start = end - timedelta(days=since_days)
    return start, end


def _parse_iso_or_none(value: str | None) -> datetime | None:
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
