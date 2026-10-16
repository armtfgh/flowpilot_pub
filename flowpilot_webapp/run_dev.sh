#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${FLOWPILOT_PYTHON:-python3}"
VENV="$ROOT/.venv-flowpilot"

if [[ ! -x "$VENV/bin/python" ]]; then
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install -e '.[web]'
npm --prefix flowpilot_webapp/frontend ci
npm --prefix flowpilot_webapp/frontend run build

exec "$VENV/bin/python" -m uvicorn flowpilot_webapp.backend.app:app \
  --host "${FLOWPILOT_HOST:-127.0.0.1}" \
  --port "${FLOWPILOT_PORT:-8510}" \
  --reload \
  --reload-dir flowpilot \
  --reload-dir flowpilot_translate \
  --reload-dir flowpilot_webapp/backend
