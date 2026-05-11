"""Vault integrity validator.

Walks `exercises/` and `entries/` looking for the most likely sources of
silent corruption: malformed frontmatter, orphan entries, broken parent_id
links on secondaries, missing lock_at, prompt-snapshot drift, etc. All
checks are read-only.
"""

from plastiglom.apps.vault_check.checks import (
    Finding,
    Severity,
    ValidationReport,
    run_checks,
)

__all__ = ["Finding", "Severity", "ValidationReport", "run_checks"]
