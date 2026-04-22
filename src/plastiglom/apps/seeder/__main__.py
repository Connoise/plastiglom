"""CLI: seed the tag pool and hubs from a YAML file.

Usage:
    python -m plastiglom.apps.seeder seed-tagpool path/to/seed.yaml
    python -m plastiglom.apps.seeder seed-tagpool path/to/seed.yaml --replace
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from plastiglom.apps.seeder.seed_tagpool import seed_tagpool_from_yaml
from plastiglom.packages.config import load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plastiglom vault seeders.")
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed-tagpool", help="Seed tag pool + hubs from YAML.")
    seed.add_argument("yaml_path", type=Path)
    seed.add_argument(
        "--replace",
        action="store_true",
        help="Replace the existing pool instead of merging.",
    )

    args = parser.parse_args(argv)
    settings = load_settings()

    if args.command == "seed-tagpool":
        pool, hubs = seed_tagpool_from_yaml(
            settings.vault_path, args.yaml_path, replace=args.replace
        )
        print(f"pool: {len(pool.entries)} tags  hubs: {len(hubs)} written")
        return 0

    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
