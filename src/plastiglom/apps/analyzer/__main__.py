"""CLI entrypoint for weekly/monthly/ad-hoc analysis runs."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta

from plastiglom.apps.analyzer.analyzer import (
    AnalysisRequest,
    Analyzer,
    Cadence,
    week_bounds,
)
from plastiglom.packages.config import load_settings
from plastiglom.packages.llm.router import LLMRouter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Plastiglom analysis.")
    parser.add_argument("cadence", choices=[c.value for c in Cadence])
    parser.add_argument("--query", default=None)
    parser.add_argument("--slug", default=None)
    args = parser.parse_args(argv)

    settings = load_settings()
    router = LLMRouter(
        sonnet_model=settings.model_sonnet,
        opus_model=settings.model_opus,
        api_key=settings.anthropic_api_key,
        usage_log_path=settings.logs_dir / "llm_usage.jsonl",
    )
    analyzer = Analyzer(vault_path=settings.vault_path, router=router)

    today = date.today()
    cadence = Cadence(args.cadence)
    if cadence is Cadence.WEEKLY:
        start, end = week_bounds(today - timedelta(days=1))
    elif cadence is Cadence.MONTHLY:
        first = today.replace(day=1)
        previous_end = datetime.combine(first, datetime.min.time())
        month_start = (first - timedelta(days=1)).replace(day=1)
        start = datetime.combine(month_start, datetime.min.time())
        end = previous_end
    else:
        end = datetime.combine(today + timedelta(days=1), datetime.min.time())
        start = end - timedelta(days=7)

    report_path = analyzer.run(
        AnalysisRequest(
            cadence=cadence,
            window_start=start,
            window_end=end,
            query=args.query,
            slug=args.slug,
        )
    )
    print(f"wrote {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
