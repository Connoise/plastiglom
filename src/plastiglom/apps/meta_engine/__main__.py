"""CLI for the meta-engine. See §7.7 of DESIGN.md.

Two subcommands:
  - `blind-spots`: scan a recent window for coverage gaps and ask Opus for
    proposals that target them.
  - `generate`: feed an arbitrary analysis excerpt (and optional memory
    excerpt) to the generator. Useful when the user wants to drive a pass
    off a specific weekly/monthly report or hand-written prompt.

Both flows are advisory only: proposals land in the queue as `pending` and
must be approved through the web app per §11. `--dry-run` skips persistence
so the user can preview what would be filed.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from plastiglom.apps.meta_engine.blind_spots import detect_blind_spots
from plastiglom.apps.meta_engine.generator import Generator, GeneratorInput
from plastiglom.apps.meta_engine.proposals import load_active_pool
from plastiglom.apps.meta_engine.queue import ProposalRecord
from plastiglom.packages.config import Settings, load_settings
from plastiglom.packages.llm.router import LLMRouter

logger = logging.getLogger(__name__)

DEFAULT_BLIND_SPOTS_DAYS = 30


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the meta-engine generator and persist proposals."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Invoke Opus but do not save proposals to the queue.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    bs = sub.add_parser(
        "blind-spots",
        help="Detect coverage gaps in the recent window and propose new exercises.",
    )
    bs.add_argument(
        "--days",
        type=int,
        default=DEFAULT_BLIND_SPOTS_DAYS,
        help=f"How many days back to scan (default: {DEFAULT_BLIND_SPOTS_DAYS}).",
    )

    gen = sub.add_parser(
        "generate",
        help="Run the generator with an explicit analysis excerpt file.",
    )
    gen.add_argument(
        "--analysis",
        required=True,
        type=Path,
        help="Path to a text/markdown file used as the analysis excerpt.",
    )
    gen.add_argument(
        "--memory",
        type=Path,
        default=None,
        help="Optional path to a text file used as the memory excerpt.",
    )

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = load_settings()
    router = _build_router(settings)
    generator = Generator(router=router, vault_path=settings.vault_path)

    if args.command == "blind-spots":
        return _run_blind_spots(args, settings, generator)
    if args.command == "generate":
        return _run_generate(args, settings, generator)
    parser.error(f"unknown command {args.command!r}")
    return 2


def _build_router(settings: Settings) -> LLMRouter:
    return LLMRouter(
        sonnet_model=settings.model_sonnet,
        opus_model=settings.model_opus,
        api_key=settings.anthropic_api_key,
        usage_log_path=settings.logs_dir / "llm_usage.jsonl",
        thinking_budget_tokens=settings.thinking_budget_tokens,
    )


def _run_blind_spots(
    args: argparse.Namespace, settings: Settings, generator: Generator
) -> int:
    pool = load_active_pool(settings.exercises_dir)
    if not pool:
        logger.error("no active exercises in %s", settings.exercises_dir)
        return 2
    end = datetime.now(tz=UTC)
    start = end - timedelta(days=args.days)
    logger.info(
        "blind-spots window=%s..%s pool_size=%d dry_run=%s",
        start.isoformat(),
        end.isoformat(),
        len(pool),
        args.dry_run,
    )
    records = detect_blind_spots(
        generator=generator,
        vault_path=settings.vault_path,
        pool=pool,
        window_start=start,
        window_end=end,
        dry_run=args.dry_run,
    )
    _report(records, dry_run=args.dry_run)
    return 0


def _run_generate(
    args: argparse.Namespace, settings: Settings, generator: Generator
) -> int:
    pool = load_active_pool(settings.exercises_dir)
    if not pool:
        logger.error("no active exercises in %s", settings.exercises_dir)
        return 2
    analysis_text = args.analysis.read_text(encoding="utf-8")
    memory_text = args.memory.read_text(encoding="utf-8") if args.memory else ""
    payload = GeneratorInput(
        pool=pool,
        analysis_excerpt=analysis_text,
        memory_excerpt=memory_text,
    )
    logger.info(
        "generate analysis=%s pool_size=%d dry_run=%s",
        args.analysis,
        len(pool),
        args.dry_run,
    )
    records = generator.generate(payload, dry_run=args.dry_run)
    _report(records, dry_run=args.dry_run)
    return 0


def _report(records: list[ProposalRecord], *, dry_run: bool) -> None:
    """Print a one-line summary plus a JSON manifest of proposed actions."""
    verb = "would propose" if dry_run else "filed"
    print(f"{verb} {len(records)} proposal(s)")
    summary = [
        {
            "id": r.id,
            "action": r.proposal.action.value,
            "exercise_id": r.proposal.exercise.id,
            "new_version": r.proposal.exercise.version,
            "rationale": r.proposal.rationale[:120],
        }
        for r in records
    ]
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    sys.exit(main())
