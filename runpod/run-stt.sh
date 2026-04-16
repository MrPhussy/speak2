#!/bin/bash
set -euo pipefail
cd /opt/moshi
export UV_LINK_MODE="${UV_LINK_MODE:-copy}"
export LD_LIBRARY_PATH="$(uv run python -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))'):${LD_LIBRARY_PATH:-}"
exec /usr/local/bin/moshi-server worker --config /opt/moshi/configs/stt.toml --port 8091
