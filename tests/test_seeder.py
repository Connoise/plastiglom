import textwrap

from plastiglom.apps.seeder import seed_tagpool_from_yaml
from plastiglom.packages.core.tags import TagPool, TagPoolEntry
from plastiglom.packages.tagpool import load_pool, write_pool


def _write_yaml(path, body: str):
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_seed_creates_pool_and_hubs(tmp_path):
    yaml_path = _write_yaml(
        tmp_path / "seed.yaml",
        """
        tags:
          - tag: values
            gloss: "what the user cares about"
          - tag: body
            gloss: ""
        hubs:
          - name: Identity
            description: "who am I"
            tags: [values, identity]
        """,
    )
    pool, hubs = seed_tagpool_from_yaml(tmp_path, yaml_path)
    assert {e.tag for e in pool.entries} == {"values", "body"}
    assert pool.get("values").gloss == "what the user cares about"
    assert [h.name for h in hubs] == ["Identity"]
    assert (tmp_path / "hubs" / "identity.md").exists()
    assert (tmp_path / "tags" / "pool.md").exists()


def test_seed_preserves_existing_gloss(tmp_path):
    pool_path = tmp_path / "tags" / "pool.md"
    write_pool(
        pool_path,
        TagPool(entries=[TagPoolEntry(tag="values", gloss="original gloss")]),
    )

    yaml_path = _write_yaml(
        tmp_path / "seed.yaml",
        """
        tags:
          - tag: values
            gloss: "new gloss"
          - tag: reflection
            gloss: "first time added"
        """,
    )
    pool, _ = seed_tagpool_from_yaml(tmp_path, yaml_path)
    values = pool.get("values")
    assert values.gloss == "original gloss"
    assert pool.get("reflection").gloss == "first time added"


def test_seed_replace_flag_replaces_pool(tmp_path):
    pool_path = tmp_path / "tags" / "pool.md"
    write_pool(pool_path, TagPool(entries=[TagPoolEntry(tag="old")]))

    yaml_path = _write_yaml(
        tmp_path / "seed.yaml",
        """
        tags:
          - tag: new
        """,
    )
    pool, _ = seed_tagpool_from_yaml(tmp_path, yaml_path, replace=True)
    assert [e.tag for e in pool.entries] == ["new"]
    # And the on-disk pool matches.
    reloaded = load_pool(pool_path)
    assert [e.tag for e in reloaded.entries] == ["new"]
