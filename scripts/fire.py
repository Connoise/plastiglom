#!/usr/bin/env python3
"""Cron entrypoint: fire the next main exercise.

Install as two cron lines keyed to PLASTIGLOM_MORNING_FIRE and
PLASTIGLOM_EVENING_FIRE (or use systemd timers). Example crontab:

    30  7  * * *  /usr/bin/env PLASTIGLOM_VAULT_PATH=/home/vaults/Plastiglom \\
                    /path/to/scripts/fire.py
    0  21  * * *  /usr/bin/env PLASTIGLOM_VAULT_PATH=/home/vaults/Plastiglom \\
                    /path/to/scripts/fire.py
"""

from plastiglom.apps.scheduler.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
