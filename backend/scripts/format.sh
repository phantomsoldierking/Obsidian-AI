#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v black >/dev/null 2>&1; then
  echo "black not found. Install dev deps: pip install -r backend/requirements-dev.txt"
  exit 1
fi

black app tests scripts
