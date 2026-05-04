"""Memory files: one markdown file per subject. See §6.4 of DESIGN.md.

Opus appends observations and reorganizes within a file during routine
analysis. Memory is never silently overwritten — corrections go through the
logged channel in `analysis_history/`. Day-to-day reorganization is fine
because the vault's private git repo is the source of truth for diffs.
"""

from plastiglom.packages.memory.io import (
    append_observation,
    list_subjects,
    load_memory,
    memory_path,
    reorganize,
    write_memory,
)
from plastiglom.packages.memory.model import MemoryFile

__all__ = [
    "MemoryFile",
    "append_observation",
    "list_subjects",
    "load_memory",
    "memory_path",
    "reorganize",
    "write_memory",
]
