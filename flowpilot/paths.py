"""Writable user state, separate from immutable installed package assets."""

from __future__ import annotations

import os
from pathlib import Path

from .environment import load_environment

load_environment()

HOME = Path(os.environ.get("FLOWPILOT_HOME", "~/.flowpilot")).expanduser().resolve()
FLOWPILOT_HOME = HOME
DATA_DIR = HOME / "data"
RECORDS_DIR = DATA_DIR / "records"
CHROMA_DIR = DATA_DIR / "chroma_db"
OUTPUTS_DIR = HOME / "outputs"
INVENTORY_PROFILE_DIR = Path(
    os.environ.get("FLOWPILOT_INVENTORY_PROFILE_DIR", str(DATA_DIR / "inventory_profiles"))
).expanduser().resolve()
RULES_PATH = DATA_DIR / "rules.json"
EXTRACTION_DIR = HOME / "extraction_results"
PAPER_HISTORY_PATH = DATA_DIR / "paper_miner_history.json"


def ensure_runtime_dirs() -> None:
    """Create writable directories when an execution command needs them."""
    for directory in (DATA_DIR, RECORDS_DIR, CHROMA_DIR, OUTPUTS_DIR,
                      INVENTORY_PROFILE_DIR, EXTRACTION_DIR):
        directory.mkdir(parents=True, exist_ok=True)
