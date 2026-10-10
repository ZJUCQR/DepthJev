#!/usr/bin/env bash
# Start the DepthJev server. Arguments go to `python -m depthjev.server`; see --help for the flags.
#
#   bash scripts/server.sh                      # 127.0.0.1:23333, models from checkpoints/
#   bash scripts/server.sh --host 0.0.0.0       # for an evaluator on another machine
#
#   DEPTHJEV_SERVER_ENV  Python environment of the server, default envs/depthjev
#   DEPTHJEV_RUN_NAME    names the request log logs/<run>.jsonl, default a UTC timestamp
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export DEPTHJEV_RUN_NAME=${DEPTHJEV_RUN_NAME:-$(date -u +%Y%m%dT%H%M%SZ)}
exec "${DEPTHJEV_SERVER_ENV:-$REPO/envs/depthjev}/bin/python" -m depthjev.server "$@"
