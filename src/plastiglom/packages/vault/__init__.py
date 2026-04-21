"""Obsidian-markdown read/write helpers for the private vault."""

from plastiglom.packages.vault.markdown import (
    FrontmatterDocument,
    dump_markdown,
    load_markdown,
    read_markdown_file,
    write_markdown_file,
)
from plastiglom.packages.vault.paths import (
    daily_index_path,
    entry_path,
    exercise_path,
)
from plastiglom.packages.vault.serializers import (
    entry_to_document,
    exercise_from_document,
    exercise_to_document,
    parse_entry,
)

__all__ = [
    "FrontmatterDocument",
    "daily_index_path",
    "dump_markdown",
    "entry_path",
    "entry_to_document",
    "exercise_from_document",
    "exercise_path",
    "exercise_to_document",
    "load_markdown",
    "parse_entry",
    "read_markdown_file",
    "write_markdown_file",
]
