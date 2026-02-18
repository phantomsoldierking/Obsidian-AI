#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m pip install -r requirements.txt -r requirements-dev.txt

echo "Installed backend runtime + dev dependencies."
echo "Next: ./scripts/run_tests.sh"
