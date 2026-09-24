#!/usr/bin/env bash
# Evaluate DepthJev on EB-Navigation end to end: start the server, run EmbodiedBench (model_type=custom),
# stop the server and print the report.
#
#   bash scripts/run.sh [RUN_NAME] [--sets LIST] [--ratio R] [--gpus IDS] [--parallel]
#
#   RUN_NAME     default smoke. Requests are logged to logs/server/<run>.jsonl, EmbodiedBench writes its
#                results to repos/EmbodiedBench/running/eb_nav/depthjev_<run>/.
#   --sets LIST  comma-separated subsets (base, common_sense, complex_instruction, visual_appearance,
#                long_horizon) or all; default base.
#   --ratio R    EmbodiedBench down_sample_ratio: every round(1/R)-th task of each subset; default 0.05
#                (3 of the 60 tasks), 1 runs every task.
#   --gpus IDS   comma-separated CUDA devices for the servers; default the visible devices. Without
#                --parallel only the first one is used.
#   --parallel   one server and one evaluator per subset instead of one for all subsets. Subset i runs as
#                <run>-<subset> on GPU IDS[i mod n], port DEPTHJEV_PORT+i and X display :100+i. Several
#                subsets may share a card: a server needs < 4 GB and AI2-THOR renders on the CPU.
#
#   bash scripts/run.sh                                            # smoke test, 3 base episodes
#   bash scripts/run.sh full --sets all --ratio 1                  # all 300 episodes with one server
#   bash scripts/run.sh full --sets all --ratio 1 --parallel       # the same, one subset per GPU
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
CFG=$(cd "$REPO" && "${DEPTHJEV_PYTHON:-python3}" -m depthjev.config) || { echo "cannot read config.json; set DEPTHJEV_PYTHON to a Python 3 interpreter" >&2; exit 1; }
eval "$CFG"

ALL_SETS=(base common_sense complex_instruction visual_appearance long_horizon)
usage() { awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$0"; exit "${1:-0}"; }
RUN=smoke SETS=base RATIO=0.05 GPUS="" PARALLEL=0
while [ $# -gt 0 ]; do
    case $1 in
        --sets) SETS=${2:?--sets needs a value}; shift 2 ;;
        --ratio) RATIO=${2:?--ratio needs a value}; shift 2 ;;
        --gpus) GPUS=${2:?--gpus needs a value}; shift 2 ;;
        --parallel) PARALLEL=1; shift ;;
        -h | --help) usage ;;
        -*) echo "unknown option $1" >&2; usage 1 >&2 ;;
        *) RUN=$1; shift ;;
    esac
done
[ "$SETS" = all ] && SETS=$(IFS=,; echo "${ALL_SETS[*]}")
IFS=, read -r -a SUBSETS <<< "$SETS"
for s in "${SUBSETS[@]}"; do
    [[ " ${ALL_SETS[*]} " == *" $s "* ]] || { echo "unknown subset $s (expected one of: ${ALL_SETS[*]})" >&2; exit 1; }
done
if [ -z "$GPUS" ]; then
    GPUS=${CUDA_VISIBLE_DEVICES:-$(nvidia-smi --query-gpu=index --format=csv,noheader 2>/dev/null | paste -sd, - || true)}
fi
IFS=, read -r -a GPU_LIST <<< "${GPUS:-0}"
mkdir -p "$REPO/logs/server"

# One server and one evaluator: run_slot <run> <sets> <gpu> <port> <display>. Both get their own process
# group, so stop_slot also stops the AI2-THOR and Xvfb processes the evaluator started.
SERVER_PID="" EVAL_PID=""
stop_slot() {
    for p in $EVAL_PID $SERVER_PID; do kill -- -"$p" 2>/dev/null || true; done
    SERVER_PID="" EVAL_PID=""
}
run_slot() {
    local run=$1 sets=$2 gpu=$3 port=$4 display=$5
    local server_log="$REPO/logs/server/$run.server.log" eval_log="$REPO/logs/eval_$run.log"
    local jsonl="$REPO/logs/server/$run.jsonl" stall=0 last_n=-1 n
    say() { echo "[$run] $*"; }
    if ss -ltn 2>/dev/null | grep -qE "[:.]$port[[:space:]]"; then
        say "port $port is already in use (stale server?)"; return 1
    fi
    CUDA_VISIBLE_DEVICES=$gpu DEPTHJEV_RUN_NAME=$run setsid bash "$REPO/scripts/server.sh" --port "$port" > "$server_log" 2>&1 &
    SERVER_PID=$!
    say "server on GPU $gpu, port $port; loading models"
    for _ in $(seq 1 120); do
        kill -0 "$SERVER_PID" 2>/dev/null || { say "server died, see $server_log"; tail -20 "$server_log"; return 1; }
        curl -fsS "http://127.0.0.1:$port/health" > /dev/null 2>&1 && break
        sleep 5
    done
    curl -fsS "http://127.0.0.1:$port/health" > /dev/null 2>&1 || { say "server not ready after 10 minutes, see $server_log"; return 1; }
    SERVER_URL="http://127.0.0.1:$port/process" DISPLAY=$display setsid bash "$REPO/scripts/eval.sh" \
        exp_name="$run" eval_sets="[$sets]" down_sample_ratio="$RATIO" > "$eval_log" 2>&1 &
    EVAL_PID=$!
    say "evaluating [$sets], log $eval_log"
    # watchdog: the evaluator retries forever, so stop when the server dies or no step is logged for 10 minutes
    while kill -0 "$EVAL_PID" 2>/dev/null; do
        sleep 15 & wait $!
        kill -0 "$SERVER_PID" 2>/dev/null || { say "server died mid-run, see $server_log"; tail -20 "$server_log"; return 1; }
        n=$(wc -l < "$jsonl" 2>/dev/null || echo 0)
        if [ "$n" = "$last_n" ]; then stall=$((stall + 15)); else stall=0; last_n=$n; fi
        [ $stall -lt 600 ] || { say "no request logged for 10 minutes, aborting"; return 1; }
        curl -fsS "http://127.0.0.1:$port/health" 2>/dev/null | grep -q degraded && say "WARNING: server reports degraded"
    done
    wait "$EVAL_PID" || { say "evaluator failed, see $eval_log"; tail -20 "$eval_log"; return 1; }
    say "done, $(wc -l < "$jsonl") requests"
}

status=0
if [ $PARALLEL = 1 ]; then
    RUNS=() PIDS=()
    trap 'kill "${PIDS[@]}" 2>/dev/null || true; wait; exit 130' INT TERM
    for i in "${!SUBSETS[@]}"; do
        s=${SUBSETS[$i]}
        [ "$i" = 0 ] || sleep 30   # stagger model loading on the shared filesystem
        (
            trap stop_slot EXIT
            trap 'exit 143' TERM
            run_slot "$RUN-$s" "$s" "${GPU_LIST[$((i % ${#GPU_LIST[@]}))]}" $((DEPTHJEV_PORT + i)) ":$((100 + i))"
        ) &
        RUNS+=("$RUN-$s") PIDS+=($!)
    done
    for p in "${PIDS[@]}"; do wait "$p" || status=1; done
else
    RUNS=("$RUN")
    trap stop_slot EXIT
    trap 'exit 130' INT TERM
    run_slot "$RUN" "$SETS" "${GPU_LIST[0]}" "$DEPTHJEV_PORT" "${DISPLAY:-:99}" || status=1
    stop_slot
fi

echo "=== report ==="
(cd "$REPO" && "$DEPTHJEV_EVAL_ENV/bin/python" -m depthjev.report "${RUNS[@]}" --ratio "$RATIO")
exit $status
