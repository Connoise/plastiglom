"""CLI entrypoint for the tagger. Intended to run per-submission or nightly."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from plastiglom.apps.tagger.tagger import Tagger
from plastiglom.packages.config import load_settings
from plastiglom.packages.llm.router import LLMRouter
from plastiglom.packages.tagpool import load_pool
from plastiglom.packages.vault.markdown import read_markdown_file, write_markdown_file
from plastiglom.packages.vault.serializers import entry_to_document, parse_entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tag an entry via Sonnet.")
    parser.add_argument("entry_path", type=Path)
    args = parser.parse_args(argv)

    settings = load_settings()
    pool = load_pool(settings.tags_dir / "pool.md")
    router = LLMRouter(
        sonnet_model=settings.model_sonnet,
        opus_model=settings.model_opus,
        api_key=settings.anthropic_api_key,
        usage_log_path=settings.logs_dir / "llm_usage.jsonl",
    )
    tagger = Tagger(router=router)

    doc = read_markdown_file(args.entry_path)
    entry = parse_entry(doc)
    result = tagger.tag(entry, pool)
    # Union applied tags onto the entry without duplicating.
    merged = list(dict.fromkeys([*entry.tags, *result.applied_tags]))
    entry.tags = merged
    write_markdown_file(args.entry_path, entry_to_document(entry))
    print(f"applied={result.applied_tags} suggested={result.suggested_tags}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
