"""Sonnet-driven tagger. See §7.5 of DESIGN.md.

Runs per-submission (or nightly in batch). Reads `tags/pool.md`, assigns
relevant tags, and emits a `suggested_tags` list for Opus pool updates.
"""

from plastiglom.apps.tagger.tagger import TagAssignment, Tagger

__all__ = ["TagAssignment", "Tagger"]
