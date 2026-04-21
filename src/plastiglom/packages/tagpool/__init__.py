"""Tag-pool management primitives."""

from plastiglom.packages.tagpool.io import append_history, load_pool, write_pool
from plastiglom.packages.tagpool.merge import merge_suggestions

__all__ = ["append_history", "load_pool", "merge_suggestions", "write_pool"]
