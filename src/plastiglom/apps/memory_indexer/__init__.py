"""QMD integration for retrieval. See §7.8 of DESIGN.md.

The real QMD CLI interface is confirmed at implementation time (§10). This
module defines a thin retrieval API so the analyzer can be coded against a
stable surface today and wired to QMD later without churn.
"""

from plastiglom.apps.memory_indexer.indexer import (
    MemoryIndexer,
    QMDChunk,
    QMDCLIIndexer,
    StubIndexer,
)

__all__ = ["MemoryIndexer", "QMDCLIIndexer", "QMDChunk", "StubIndexer"]
