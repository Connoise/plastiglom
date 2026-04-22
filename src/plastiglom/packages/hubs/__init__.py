"""Hub notes: lightweight organizing structure over the tag pool.

Hubs are markdown files living at `hubs/<name>.md` in the vault. Each hub
gathers a set of related tags and points at representative entries. Opus
maintains them during analysis; the tag pool stays the primary classifier,
hubs are just a second-level view.
"""

from plastiglom.packages.hubs.hub import Hub
from plastiglom.packages.hubs.io import (
    hub_path,
    list_hubs,
    load_hub,
    write_hub,
)

__all__ = ["Hub", "hub_path", "list_hubs", "load_hub", "write_hub"]
