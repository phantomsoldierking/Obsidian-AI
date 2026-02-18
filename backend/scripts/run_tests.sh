#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"

if command -v pytest >/dev/null 2>&1; then
  pytest -q
else
  echo "pytest not found. Install dev deps: pip install -r backend/requirements-dev.txt"
  echo "Running fallback syntax check..."
  python3 -m compileall app
fi
