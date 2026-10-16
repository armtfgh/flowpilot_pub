"""Portability and persisted-data compatibility for the publication package."""

from pathlib import Path

import chromadb

from flowpilot_translate.vector_store import VectorStore


def test_existing_legacy_index_remains_visible_after_package_rename(tmp_path):
    client = chromadb.PersistentClient(path=str(tmp_path / "index"))
    records = client.create_collection("flora_records")
    records.add(ids=["legacy-record"], embeddings=[[0.1, 0.2, 0.3]], documents=["Example record"])
    pairs = client.create_collection("flora_pairs")
    pairs.add(ids=["legacy-pair"], embeddings=[[0.3, 0.2, 0.1]], documents=["Example pair"])

    store = VectorStore(tmp_path / "index")

    assert store.count == 1
    assert store.pairs_count == 1
    assert store.collection.get()["ids"] == ["legacy-record"]
    assert store.pairs_collection.get()["ids"] == ["legacy-pair"]
    assert {collection.name for collection in client.list_collections()} == {"flora_records", "flora_pairs"}


def test_fresh_index_uses_flowpilot_names_without_creating_legacy_collections(tmp_path):
    store = VectorStore(tmp_path / "index")
    assert store.collection.name == "flowpilot_records"
    assert store.pairs_collection.name == "flowpilot_pairs"
    assert store.count == store.pairs_count == 0


def test_explicit_custom_collection_does_not_read_legacy_data(tmp_path):
    store = VectorStore(tmp_path / "index")
    store.chroma.create_collection("flora_records")
    custom = store._open_collection("my_corpus", "flora_records")
    assert custom.name == "my_corpus"


def test_bundled_prompts_icons_and_generic_inventory_exist():
    from flowpilot_translate.config import LAB_INVENTORY_PATH, PROMPTS_DIR
    from flowpilot_design.visualizer import flowsheet_builder

    assert LAB_INVENTORY_PATH.is_file()
    assert (PROMPTS_DIR / "translate_system.txt").is_file()
    assert list((Path(flowsheet_builder.__file__).parent / "icons").glob("*.png"))


def test_diagram_cache_fingerprint_supports_frozen_modules_without_source(tmp_path):
    from types import SimpleNamespace
    from flowpilot_translate.diagram_views import _module_content

    frozen = SimpleNamespace(__name__="frozen_renderer", __file__=str(tmp_path / "missing.py"),
                             __loader__=SimpleNamespace(get_code=lambda name: compile("value = 1", name, "exec")))
    assert _module_content(frozen)
    assert _module_content(frozen) == _module_content(frozen)
