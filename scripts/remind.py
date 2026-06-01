#!/usr/bin/env python3
"""Cron entrypoint: send follow-up reminders for still-open entries.

Run frequently (hourly is plenty); the pass is idempotent and pings each
entry at most once, when its lock_at (the next main firing) is within the
reminder window. Example crontab:

    15 * * * *  /usr/bin/env PLASTIGLOM_VAULT_PATH=/home/vaults/Plastiglom \\
                  /path/to/scripts/remind.py
"""

from plastiglom.apps.scheduler.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(["--remind"]))
