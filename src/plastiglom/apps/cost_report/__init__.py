"""LLM usage / cost reporting.

Reads `logs/llm_usage.jsonl` (one record per Anthropic call) and rolls it up
into totals + per-task / per-model / per-day breakdowns. The CLI in
`__main__.py` is the standard surface; the web app renders the same
`Report` on `/cost`.
"""

from plastiglom.apps.cost_report.report import (
    DEFAULT_PRICES,
    ModelPrice,
    Report,
    Totals,
    UsageRecord,
    build_report,
    load_usage,
    price_record,
)

__all__ = [
    "DEFAULT_PRICES",
    "ModelPrice",
    "Report",
    "Totals",
    "UsageRecord",
    "build_report",
    "load_usage",
    "price_record",
]
