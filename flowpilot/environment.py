"""Load explicit local configuration before importing runtime settings.

Process environment variables always win. With FLOWPILOT_ENV_FILE set, only
that file is loaded. Otherwise, the current directory's .env is loaded first,
then $FLOWPILOT_HOME/.env (default ~/.flowpilot/.env) supplies missing values.
No parent directories are searched and no files or directories are created.
"""

from __future__ import annotations

import os
from pathlib import Path

_loaded = False


def load_environment() -> None:
    """Load configuration once, preserving values already in the environment."""
    global _loaded
    if _loaded:
        return
    from dotenv import load_dotenv

    explicit = os.environ.get("FLOWPILOT_ENV_FILE")
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"FLOWPILOT_ENV_FILE does not exist: {path}")
        load_dotenv(path, override=False)
    else:
        local = Path.cwd() / ".env"
        load_dotenv(local, override=False)
        home = Path(os.environ.get("FLOWPILOT_HOME", "~/.flowpilot")).expanduser().resolve()
        home_env = home / ".env"
        if home_env != local:
            load_dotenv(home_env, override=False)
    _loaded = True
