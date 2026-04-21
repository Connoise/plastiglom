"""CLI entrypoint: finalize prior entries and rebuild today's daily index."""

from __future__ import annotations

import argparse
from datetime import datetime

from plastiglom.apps.archiver.archiver import Archiver
from plastiglom.packages.config import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Plastiglom archiver maintenance.")
    parser.add_argument(
        "--finalize",
        action="store_true",
        help="Finalize any entry whose lock_at has passed.",
    )
    args = parser.parse_args()

    settings = load_settings()
    archiver = Archiver(settings.vault_path)

    if args.finalize:
        now = datetime.now(tz=settings.timezone)
        touched = archiver.finalize_prior(now)
        print(f"finalized {len(touched)} entries")


if __name__ == "__main__":
    main()
