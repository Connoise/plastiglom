"""One-shot seeders: tag pool, hubs, memory files.

These run during initial vault setup (Phase 0 closing) and again when the
user wants to re-seed from a known good YAML. They never run automatically
during the daily loop.
"""

from plastiglom.apps.seeder.seed_tagpool import seed_tagpool_from_yaml

__all__ = ["seed_tagpool_from_yaml"]
