#!/usr/bin/env python3
"""Cron entrypoint: fire any LLM jobs whose cadence has ticked.

Safe to run frequently; the runner is idempotent (state file gates each job
to one fire per canonical tick). Recommended cron line — hourly is plenty
since every default job ticks at most once per day:

    0   *   * * *  PLASTIGLOM_VAULT_PATH=/home/vaults/Plastiglom \\
                    /path/to/scripts/llm_schedule.py

To run a single job off-schedule:

    PLASTIGLOM_VAULT_PATH=... \\
        /path/to/scripts/llm_schedule.py force digest_weekly

See `python -m plastiglom.apps.llm_scheduler --help` for the full surface.
"""

import sys

from plastiglom.apps.llm_scheduler.__main__ import main

if __name__ == "__main__":
    argv = sys.argv[1:] or ["run"]
    sys.exit(main(argv))
