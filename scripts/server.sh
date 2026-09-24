#!/usr/bin/env bash
# Start the DepthJev server (GPU box). Settings come from config.json.
#   bash scripts/server.sh [extra args for python -m depthjev.server]
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd); cd "$REPO"
CFG=$(cd "$REPO" && "${DEPTHJEV_PYTHON:-python3}" -m depthjev.config) || { echo "cannot read config.json; set DEPTHJEV_PYTHON to a Python 3 interpreter" >&2; exit 1; }
eval "$CFG"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export DEPTHJEV_RUN_NAME=${DEPTHJEV_RUN_NAME:-$(date -u +%Y%m%dT%H%M%SZ)}
exec "$DEPTHJEV_SERVER_ENV/bin/python" -m depthjev.server --log-dir "$REPO/logs/server" "$@"
