#!/usr/bin/env bash
# Start the GeoLingo server. Arguments go to `python -m geolingo.server`; see --help for the flags.
#
#   bash scripts/server.sh                      # 127.0.0.1:23333, models from checkpoints/
#   bash scripts/server.sh --host 0.0.0.0       # for an evaluator on another machine
#
#   GEOLINGO_SERVER_ENV  Python environment of the server, default envs/geolingo
#   GEOLINGO_RUN_NAME    names the request log logs/<run>.jsonl, default a UTC timestamp
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export GEOLINGO_RUN_NAME=${GEOLINGO_RUN_NAME:-$(date -u +%Y%m%dT%H%M%SZ)}
exec "${GEOLINGO_SERVER_ENV:-$REPO/envs/geolingo}/bin/python" -m geolingo.server "$@"
