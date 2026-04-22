"""CLI entrypoints for analysis: Opus reports + the Phase 2 Sonnet digest."""

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
from plastiglom.apps.analyzer.digest import WeeklyDigest
from plastiglom.apps.analyzer.digest import week_bounds as digest_week_bounds
from plastiglom.packages.config import load_settings
from plastiglom.packages.llm.router import LLMRouter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Plastiglom analysis.")
    sub = parser.add_subparsers(dest="command", required=True)

    opus = sub.add_parser("opus", help="Opus weekly / monthly / ad-hoc report (§7.6).")
    opus.add_argument("cadence", choices=[c.value for c in Cadence])
    opus.add_argument("--query", default=None)
    opus.add_argument("--slug", default=None)

    digest = sub.add_parser("digest", help="Phase 2 Sonnet weekly digest (§9 Phase 2).")
    digest.add_argument("--no-themes", action="store_true", help="Skip the LLM themes pass.")

    args = parser.parse_args(argv)
    settings = load_settings()
    router = LLMRouter(
        sonnet_model=settings.model_sonnet,
        opus_model=settings.model_opus,
        api_key=settings.anthropic_api_key,
        usage_log_path=settings.logs_dir / "llm_usage.jsonl",
    )

    if args.command == "opus":
        return _run_opus(args, settings, router)
    if args.command == "digest":
        return _run_digest(args, settings, router)

    parser.error(f"unknown command {args.command!r}")
    return 2


def _run_opus(args: argparse.Namespace, settings, router: LLMRouter) -> int:
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


def _run_digest(args: argparse.Namespace, settings, router: LLMRouter) -> int:
    today = date.today()
    start, end = digest_week_bounds(today - timedelta(days=1))
    digest = WeeklyDigest(
        vault_path=settings.vault_path,
        router=None if args.no_themes else router,
    )
    out = digest.run(start, end)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
