#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

echo "[1/4] Health check"
curl -sS "$BASE_URL/health"
echo -e "\n\n[2/4] Classify"
curl -sS -X POST "$BASE_URL/classify" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Summarize my sprint notes"}'
echo -e "\n\n[3/4] Semantic search"
curl -sS -X POST "$BASE_URL/semantic-search" \
  -H 'Content-Type: application/json' \
  -d '{"query":"What notes mention roadmap?","top_k":3}'
echo -e "\n\n[4/4] Query"
curl -sS -X POST "$BASE_URL/query" \
  -H 'Content-Type: application/json' \
  -d '{"query":"Give me key tasks from recent notes","top_k":4}'
echo
