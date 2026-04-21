from plastiglom.packages.core.tags import TagPool, TagPoolEntry
from plastiglom.packages.tagpool.io import load_pool, write_pool
from plastiglom.packages.tagpool.merge import merge_suggestions


def test_pool_roundtrip(tmp_path):
    path = tmp_path / "pool.md"
    pool = TagPool(
        entries=[
            TagPoolEntry(tag="values", gloss="identity over time"),
            TagPoolEntry(
                tag="reflection",
                gloss="",
                representative_entries=["2026-05-14-evening-review"],
            ),
        ]
    )
    write_pool(path, pool)
    rehydrated = load_pool(path)
    assert {e.tag for e in rehydrated.entries} == {"values", "reflection"}
    values = rehydrated.get("values")
    assert values is not None
    assert values.gloss == "identity over time"


def test_merge_adds_unknown_and_records_existing():
    pool = TagPool(entries=[TagPoolEntry(tag="values", gloss="x")])
    new_pool, result = merge_suggestions(pool, ["values", "novelty"], entry_id="e1")
    assert set(new_pool.tag_names()) == {"values", "novelty"}
    assert [e.tag for e in result.added] == ["novelty"]
    assert result.existing == ["values"]
    values = new_pool.get("values")
    assert values and "e1" in values.representative_entries


def test_merge_caps_representatives():
    pool = TagPool(
        entries=[
            TagPoolEntry(
                tag="values",
                representative_entries=["a", "b", "c"],
            )
        ]
    )
    new_pool, _ = merge_suggestions(pool, ["values"], entry_id="d", max_representatives=3)
    values = new_pool.get("values")
    assert values is not None
    assert values.representative_entries == ["a", "b", "c"]
