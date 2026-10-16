"""Offline checks for the publication package's filesystem boundary."""

import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from flowpilot.cli import _import_records, main


def test_import_conflict_is_detected_before_any_copy(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "state"
    source.mkdir()
    destination.mkdir()
    (source / "a.json").write_text('{"record_id":"a"}')
    (source / "z.json").write_text('{"record_id":"new"}')
    (destination / "z.json").write_text('{"record_id":"old"}')
    with pytest.raises(ValueError, match="different record"):
        _import_records(source, destination)
    assert not (destination / "a.json").exists()
    assert json.loads((destination / "z.json").read_text()) == {"record_id": "old"}


def test_index_retains_originals_and_uses_user_corpus(tmp_path, monkeypatch):
    import flowpilot.paths as paths
    source, destination = tmp_path / "source", tmp_path / "state"
    source.mkdir()
    record = source / "example.json"
    content = '{"record_id":"example"}'
    record.write_text(content)
    indexed = []
    monkeypatch.setattr(paths, "RECORDS_DIR", destination)
    monkeypatch.setattr(paths, "ensure_runtime_dirs", lambda: None)
    monkeypatch.setitem(sys.modules, "flowpilot_translate.main", SimpleNamespace(
        index_records=lambda folder: indexed.append(folder) or 1))
    assert main(["index", str(source)]) == 0
    assert indexed == [str(destination.resolve())]
    assert record.read_text() == content
    assert (destination / "example.json").read_text() == content
    assert _import_records(source, destination) == destination.resolve()


def test_invalid_record_creates_no_state(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "state"
    source.mkdir()
    (source / "invalid.json").write_text("[]")
    with pytest.raises(ValueError, match="JSON object"):
        _import_records(source, destination)
    assert not destination.exists()


def test_environment_is_loaded_before_paths_without_creating_state(tmp_path, monkeypatch):
    package_root = Path(__file__).resolve().parents[2]
    state = tmp_path / "state"
    (tmp_path / ".env").write_text(f"FLOWPILOT_HOME={state}\nFLOWPILOT_TEST_VALUE=file\n")
    monkeypatch.delenv("FLOWPILOT_ENV_FILE", raising=False)
    monkeypatch.delenv("FLOWPILOT_HOME", raising=False)
    monkeypatch.setenv("FLOWPILOT_TEST_VALUE", "environment")
    monkeypatch.setenv("PYTHONPATH", str(package_root))
    code = """
import os
from flowpilot.paths import HOME, RECORDS_DIR
from flowpilot_translate.config import LAB_INVENTORY_PATH
assert HOME == __import__('pathlib').Path(os.environ['FLOWPILOT_HOME'])
assert RECORDS_DIR == HOME / 'data' / 'records'
assert os.environ['FLOWPILOT_TEST_VALUE'] == 'environment'
assert LAB_INVENTORY_PATH.is_file()
assert not HOME.exists()
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert not state.exists()


def test_explicit_environment_file_excludes_cwd_configuration(tmp_path, monkeypatch):
    package_root = Path(__file__).resolve().parents[2]
    (tmp_path / ".env").write_text("FLOWPILOT_TEST_VALUE=wrong\n")
    explicit = tmp_path / "selected.env"
    explicit.write_text("FLOWPILOT_TEST_VALUE=selected\n")
    monkeypatch.setenv("FLOWPILOT_ENV_FILE", str(explicit))
    monkeypatch.delenv("FLOWPILOT_TEST_VALUE", raising=False)
    monkeypatch.setenv("PYTHONPATH", str(package_root))
    code = "from flowpilot.environment import load_environment; import os; load_environment(); assert os.environ['FLOWPILOT_TEST_VALUE'] == 'selected'"
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
