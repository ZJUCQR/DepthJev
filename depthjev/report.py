"""Report one or more DepthJev runs: per-step latency from the server JSONL, per-subset success from the EmbodiedBench results, and a per-episode table with the target type Jev resolved from the instruction. From the repo root:

    python3 -m depthjev.report <run_name> [<run_name> ...] [--ratio r]

For each run it reads logs/server/<run_name>.jsonl and repos/EmbodiedBench/running/eb_nav/depthjev_<run_name>/; several runs (e.g. one per GPU card, each covering different subsets) are merged. It uses only the standard library and stays Python 3.9-compatible, because scripts/run.sh runs it in the evaluation environment.
"""

import glob
import json
import os
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SETS = ["base", "common_sense", "complex_instruction", "visual_appearance", "long_horizon"]


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    return xs[max(0, min(len(xs) - 1, int(round(p / 100.0 * (len(xs) - 1)))))]


def load_rows(runs):
    rows = []
    for run in runs:
        path = REPO / "logs/server" / f"{run}.jsonl"
        if path.exists():
            rows += [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    return rows


def result_files(run, subset):
    pattern = (
        REPO
        / "repos/EmbodiedBench/running/eb_nav"
        / f"depthjev_{run}"
        / subset
        / "results"
        / "episode_*_final_res.json"
    )
    return sorted(glob.glob(str(pattern)), key=lambda p: int(os.path.basename(p).split("_")[1]))


def load_results(runs):
    out = {s: [] for s in SETS}
    for run in runs:
        for s in SETS:
            out[s] += [json.load(open(f)) for f in result_files(run, s)]
    return out


def latency_table(rows):
    print(
        f"{len(rows)} requests, fallback={sum(bool(r.get('fallback')) for r in rows)}, repeats={sum(bool(r.get('repeat')) for r in rows)}"
    )
    print(f"{'stage':18s}{'n':>6s}{'mean':>9s}{'p50':>9s}{'p90':>9s}{'max':>9s}")
    for k in ["total", "depth", "detect", "jev", "target_resolution"]:
        xs = [r["timings_s"][k] for r in rows if k in r.get("timings_s", {})]
        if xs:
            print(f"{k:18s}{len(xs):6d}{statistics.mean(xs):9.3f}{pct(xs, 50):9.3f}{pct(xs, 90):9.3f}{max(xs):9.3f}")
    xs = [r["server_latency_s"] for r in rows if "server_latency_s" in r]
    if xs:
        print(
            f"{'server (http)':18s}{len(xs):6d}{statistics.mean(xs):9.3f}{pct(xs, 50):9.3f}{pct(xs, 90):9.3f}{max(xs):9.3f}"
        )
    vis = [bool(r.get("target", {}).get("visible")) for r in rows if "target" in r]
    if vis:
        print(f"target visible in {sum(vis)}/{len(vis)} steps")
    acts = {}
    for r in rows:
        acts[r.get("action")] = acts.get(r.get("action"), 0) + 1
    print("actions:", dict(sorted(acts.items(), key=lambda kv: -kv[1])))


def subset_table(results):
    print(f"\n{'subset':20s}{'episodes':>9s}{'success':>9s}{'steps/ep':>9s}{'sec/ep':>8s}{'sec/step':>9s}")
    tot_n = tot_s = 0
    for s in SETS:
        eps = results.get(s, [])
        if not eps:
            continue
        succ = [float(e.get("task_success", 0)) for e in eps]
        steps = [e.get("num_steps", 0) for e in eps]
        secs = [e.get("episode_elapsed_seconds", 0.0) for e in eps]
        tot_n += len(eps)
        tot_s += sum(succ)
        print(
            f"{s:20s}{len(eps):9d}{sum(succ) / len(succ):9.3f}{statistics.mean(steps):9.1f}{statistics.mean(secs):8.1f}{sum(secs) / max(sum(steps), 1):9.2f}"
        )
    if tot_n:
        print(f"{'all':20s}{tot_n:9d}{tot_s / tot_n:9.3f}")


def episode_table(rows, results, ratio):
    episodes, cur = [], None
    for r in rows:
        if r.get("repeat"):
            continue
        if r.get("step_index") == 0:
            cur = {"instruction": r.get("instruction"), "steps": []}
            episodes.append(cur)
        if cur is not None:
            cur["steps"].append(r)
    every = round(1 / ratio) if 0 < ratio < 1 else 1
    truth = []
    for s in SETS:
        if not results.get(s):
            continue
        tasks = json.load(open(REPO / "repos/EmbodiedBench/embodiedbench/envs/eb_navigation/datasets" / f"{s}.json"))[
            "tasks"
        ]
        truth += [(s, t) for t in tasks[::every]]
    print(
        f"\n{'subset':20s}{'true':15s}{'resolved':15s}{'conf':>5s} {'ok':>2s} {'succ':>4s} {'steps':>5s} {'vis%':>5s} {'s/step':>6s}  instruction"
    )
    n = n_ok = 0
    counters = {s: 0 for s in SETS}
    pointer = 0
    for ep in episodes:
        # align on the instruction text: the next dataset task (in evaluation order) with this instruction
        j = next(
            (k for k in range(pointer, len(truth)) if truth[k][1]["instruction"].rstrip(".") == ep["instruction"]), None
        )
        if j is None:
            s, task = "?", {}
        else:
            s, task = truth[j]
            pointer = j + 1
        res = results.get(s, [])[counters[s]] if s in counters and counters[s] < len(results.get(s, [])) else {}
        if s in counters:
            counters[s] += 1
        tr = next((x["target_resolution"] for x in ep["steps"] if "target_resolution" in x), {})
        vis = sum(1 for x in ep["steps"] if x.get("target", {}).get("visible")) / max(len(ep["steps"]), 1)
        lat = sum(x.get("server_latency_s", 0) for x in ep["steps"]) / max(len(ep["steps"]), 1)
        true = task.get("targetObjectType", "?")
        ok = tr.get("type") == true
        n += 1
        n_ok += ok
        print(
            f"{s:20s}{true:15s}{str(tr.get('type')):15s}{tr.get('confidence', 0):5.2f} {str(ok)[:1]:>2s} {str(res.get('task_success')):>4s} "
            f"{str(res.get('num_steps')):>5s} {vis * 100:5.0f} {lat:6.2f}  {ep['instruction'][:60]}"
        )
    print(f"target type resolved correctly: {n_ok}/{n}")


if __name__ == "__main__":
    args = sys.argv[1:]
    ratio = 1.0
    if "--ratio" in args:
        i = args.index("--ratio")
        ratio = float(args[i + 1])
        del args[i : i + 2]
    runs = args or ["full"]
    rows = load_rows(runs)
    results = load_results(runs)
    latency_table(rows)
    subset_table(results)
    episode_table(rows, results, ratio)
