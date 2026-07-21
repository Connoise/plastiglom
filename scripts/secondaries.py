#!/usr/bin/env python3
"""Cron entrypoint: fire any secondary exercise that has come due.

A secondary prompts the user 4 hours after its parent main exercise fired
(never at the same time as the parent). Install as two cron lines keyed to
PLASTIGLOM_MORNING_FIRE + 4h and PLASTIGLOM_EVENING_FIRE + 4h. The pass is
idempotent — each parent firing produces at most one secondary — so a more
frequent tick is also safe. Example crontab for 07:30 / 21:00 firings:

    30 11  * * *  /usr/bin/env PLASTIGLOM_VAULT_PATH=/home/vaults/Plastiglom \\
                    /path/to/scripts/secondaries.py
    0   1  * * *  /usr/bin/env PLASTIGLOM_VAULT_PATH=/home/vaults/Plastiglom \\
                    /path/to/scripts/secondaries.py
"""

from plastiglom.apps.scheduler.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(["--secondaries"]))
