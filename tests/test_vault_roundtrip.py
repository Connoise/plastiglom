from datetime import UTC, datetime

from plastiglom.packages.core.entry import Entry, EntryStatus
from plastiglom.packages.vault.markdown import (
    FrontmatterDocument,
    dump_markdown,
    load_markdown,
    read_markdown_file,
    write_markdown_file,
)
from plastiglom.packages.vault.serializers import (
    entry_to_document,
    exercise_from_document,
    exercise_to_document,
    parse_entry,
)


def test_frontmatter_roundtrip():
    doc = FrontmatterDocument(metadata={"a": 1, "b": "x"}, content="hello\n")
    rehydrated = load_markdown(dump_markdown(doc))
    assert rehydrated.metadata == {"a": 1, "b": "x"}
    assert rehydrated.content.strip() == "hello"


def test_no_frontmatter_passthrough():
    doc = load_markdown("just a body\n")
    assert doc.metadata == {}
    assert doc.content == "just a body\n"


def test_exercise_serializer_roundtrip(main_exercise, vault):
    doc = exercise_to_document(main_exercise)
    path = vault / "exercises" / "main" / f"{main_exercise.id}.md"
    write_markdown_file(path, doc)
    rehydrated = exercise_from_document(read_markdown_file(path))
    assert rehydrated.id == main_exercise.id
    assert rehydrated.prompts == main_exercise.prompts
    assert rehydrated.schedule.window == main_exercise.schedule.window


def test_entry_serializer_roundtrip(vault):
    fired = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)
    lock = datetime(2026, 5, 15, 7, 30, tzinfo=UTC)
    entry = Entry(
        id="2026-05-14-evening-review",
        exercise_id="main-evening-review",
        exercise_version=1,
        title="2026-05-14 - Evening review",
        timestamp_fired=fired,
        timestamp_submitted=fired,
        timestamp_last_edited=fired,
        lock_at=lock,
        status=EntryStatus.SUBMITTED,
        tags=["reflection"],
        prompt_snapshot=["What moment deserves a second look?"],
        response="Today, the silence after the call.",
    )
    path = vault / "entries" / "2026" / "05" / "14-evening-review.md"
    write_markdown_file(path, entry_to_document(entry))
    rehydrated = parse_entry(read_markdown_file(path))
    assert rehydrated.response.strip() == "Today, the silence after the call."
    assert rehydrated.prompt_snapshot == entry.prompt_snapshot
    assert rehydrated.status == EntryStatus.SUBMITTED
