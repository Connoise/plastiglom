"""Retrieval surface for the analyzer.

Two implementations:
  - `QMDCLIIndexer`: subprocesses the user's installed QMD CLI.
  - `StubIndexer`: returns an empty result set; used until QMD is wired.

`reindex` is called after each archive write / memory edit / analysis write.
Rate-limiting and batching are a QMD concern and out of scope here.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class QMDChunk:
    path: Path
    score: float
    text: str


class MemoryIndexer(Protocol):
    def reindex(self) -> None: ...

    def query(self, text: str, *, k: int = 8) -> list[QMDChunk]: ...


class StubIndexer:
    def reindex(self) -> None:
        return None

    def query(self, text: str, *, k: int = 8) -> list[QMDChunk]:  # noqa: ARG002
        return []


@dataclass
class QMDCLIIndexer:
    qmd_bin: str
    vault_path: Path

    def reindex(self) -> None:
        subprocess.run(
            [self.qmd_bin, "index", str(self.vault_path)],
            check=True,
        )

    def query(self, text: str, *, k: int = 8) -> list[QMDChunk]:
        result = subprocess.run(
            [self.qmd_bin, "query", "--json", "-k", str(k), "--root", str(self.vault_path), text],
            check=True,
            capture_output=True,
            text=True,
        )
        raw = json.loads(result.stdout or "[]")
        return [
            QMDChunk(
                path=Path(item["path"]),
                score=float(item.get("score", 0.0)),
                text=item.get("text", ""),
            )
            for item in raw
        ]
