#!/usr/bin/env bash
# Run the EB-Navigation evaluation against a running DepthJev server (GPU box).
#   SERVER_URL=http://127.0.0.1:23333/process bash scripts/eval.sh exp_name=smoke eval_sets=[base] down_sample_ratio=0.05
#   THOR_PLATFORM=Linux64 (default; Xvfb + Mesa) or CloudRendering (needs a Vulkan driver).
# Results land in repos/EmbodiedBench/running/eb_nav/depthjev_<exp_name>/<eval_set>/.
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
CFG=$(cd "$REPO" && "${DEPTHJEV_PYTHON:-python3}" -m depthjev.config) || { echo "cannot read config.json; set DEPTHJEV_PYTHON to a Python 3 interpreter" >&2; exit 1; }
eval "$CFG"
SERVER_URL=${SERVER_URL:-http://127.0.0.1:$DEPTHJEV_PORT/process}
# ai2thor maps CUDA_VISIBLE_DEVICES to a Vulkan device (controller.py, unity_command) and fails without an
# NVIDIA Vulkan driver; the evaluator renders on the CPU, so it must not see the variable.
unset CUDA_VISIBLE_DEVICES
THOR_PLATFORM=${THOR_PLATFORM:-Linux64}
if [ "$THOR_PLATFORM" = Linux64 ]; then
    export DISPLAY=${DISPLAY:-:99}
    if ! xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
        mkdir -p "$REPO/logs"
        # software GL: Xvfb + Mesa llvmpipe (packages listed under Install, Rendering in README.md)
        nohup Xvfb "$DISPLAY" -screen 0 1280x1024x24 +extension GLX +render -noreset > "$REPO/logs/xvfb_${DISPLAY#:}.log" 2>&1 &
        for _ in $(seq 1 30); do xdpyinfo -display "$DISPLAY" >/dev/null 2>&1 && break; sleep 1; done
    fi
    export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=${GALLIUM_DRIVER:-llvmpipe}
fi
curl -fsS "${SERVER_URL%/process}/health" >/dev/null || { echo "DepthJev server not reachable at $SERVER_URL"; exit 1; }
cd "$REPO"
exec "$DEPTHJEV_EVAL_ENV/bin/python" -m depthjev.eb_launch --server-url "$SERVER_URL" --platform "$THOR_PLATFORM" \
    env=eb-nav model_name=depthjev model_type=custom "$@"
