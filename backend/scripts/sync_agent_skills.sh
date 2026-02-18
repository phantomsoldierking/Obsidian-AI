#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT_DIR/scripts/sync_agent_skills.py"

if [[ ! -f "$SCRIPT" ]]; then
  echo "sync script not found: $SCRIPT"
  exit 1
fi

python3 "$SCRIPT" "$@"
