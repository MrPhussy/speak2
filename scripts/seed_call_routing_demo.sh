#!/usr/bin/env bash
# Call published `call-routing-core` reducers to seed Fjord demo DIDs (requires spacetime CLI + server).
# Run from speak2 repo root or set SPEAK2_ROOT.
set -euo pipefail
ROOT="${SPEAK2_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DB="${CALL_ROUTING_DB:-call-routing}"
URL="${SPACETIME_URL:-http://127.0.0.1:3000}"

echo "Calling seed_fjord_demo_routes on database ${DB} (${URL}) …"
spacetime call "${DB}" seed_fjord_demo_routes -s "${URL}" -y
