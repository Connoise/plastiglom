#!/usr/bin/env python3
"""Cron entrypoint: finalize any entry whose lock_at has passed.

Safe to run frequently; idempotent. In Phase 1 this is also invoked inline by
the scheduler at each firing, but an independent heartbeat helps when the
scheduler misses a tick.
"""

from plastiglom.apps.archiver.__main__ import main

if __name__ == "__main__":
    import sys

    sys.argv.append("--finalize")
    main()
