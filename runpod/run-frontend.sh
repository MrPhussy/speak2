#!/bin/bash
set -euo pipefail
cd /opt/frontend
export NODE_ENV=production
export PORT=3000
export HOSTNAME=0.0.0.0
exec node server.js
