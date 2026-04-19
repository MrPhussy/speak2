#!/usr/bin/env bash
# Optional smoke: curl Traefik on a deployed Unmute RunPod URL.
# Set RUNPOD_UNMUTE_URL (e.g. http://IP:DIRECT_PORT/) — see docs/runpod-testing.md.
set -euo pipefail

URL="${RUNPOD_UNMUTE_URL:-}"
if [[ -z "$URL" ]]; then
  echo "SKIP: set RUNPOD_UNMUTE_URL to the Pod TCP URL (port 80 mapped)."
  exit 0
fi

echo "GET $URL"
curl -fsS --max-time 30 "${URL}" | head -c 200 || true
echo
echo "OK"
