#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v ruff >/dev/null 2>&1; then
  echo "ruff not found. Install dev deps: pip install -r backend/requirements-dev.txt"
  exit 1
fi

ruff check app tests
