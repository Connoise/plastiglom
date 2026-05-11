"""Persistence for the LLM scheduler's last-run timestamps.

Stored under `<vault>/logs/llm_scheduler_state.json` as a flat
`{job_name: iso-8601-string}` map. The runner reads this at start, decides
which jobs are due, and writes it back after each successful firing.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

STATE_FILENAME = "llm_scheduler_state.json"


def state_path(logs_dir: Path) -> Path:
    return logs_dir / STATE_FILENAME


def load_state(logs_dir: Path) -> dict[str, datetime]:
    path = state_path(logs_dir)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, datetime] = {}
    for name, value in raw.items():
        if not isinstance(value, str):
            continue
        try:
            out[name] = datetime.fromisoformat(value)
        except ValueError:
            continue
    return out


def save_state(logs_dir: Path, state: dict[str, datetime]) -> None:
    path = state_path(logs_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {name: ts.isoformat() for name, ts in state.items()}
    # Atomic write: a partial state file would cause a job to re-fire or
    # never fire, both of which are worse than the cron retry.
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=path.parent,
        prefix=path.name,
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
    ) as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        tmp = Path(fh.name)
    os.replace(tmp, path)
