from plastiglom.packages.hubs import Hub, list_hubs, load_hub, write_hub


def test_hub_roundtrip(tmp_path):
    hub = Hub(
        name="Identity",
        description="who-am-I family",
        tags=["values", "identity"],
        representative_entries=["2026-05-14-values-drift"],
        body="Notes go here.\n",
    )
    path = write_hub(tmp_path, hub)
    assert path.exists()

    loaded = load_hub(path)
    assert loaded.name == "Identity"
    assert loaded.tags == ["values", "identity"]
    assert loaded.representative_entries == ["2026-05-14-values-drift"]
    assert "Notes go here." in loaded.body


def test_list_hubs_returns_all(tmp_path):
    for name in ("Identity", "Relating", "Soma"):
        write_hub(tmp_path, Hub(name=name))
    hubs = list_hubs(tmp_path)
    assert {h.name for h in hubs} == {"Identity", "Relating", "Soma"}


def test_list_hubs_missing_dir_returns_empty(tmp_path):
    assert list_hubs(tmp_path) == []
