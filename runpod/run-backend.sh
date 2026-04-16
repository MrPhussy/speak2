#!/bin/bash
set -euo pipefail
cd /opt/unmute
exec uv run --no-dev uvicorn unmute.main_websocket:app \
  --host 0.0.0.0 --port 8088 --ws-per-message-deflate=false
