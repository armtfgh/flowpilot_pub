#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${FLOWPILOT_PYTHON:-python3}"
VENV="$ROOT/.venv-flowpilot"

if [[ ! -x "$VENV/bin/python" ]]; then
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install -e '.[legacy-ui]'
exec "$VENV/bin/python" -m streamlit run "$ROOT/app.py" \
  --server.address "${FLOWPILOT_HOST:-127.0.0.1}" \
  --server.port "${FLOWPILOT_STREAMLIT_PORT:-8501}"
