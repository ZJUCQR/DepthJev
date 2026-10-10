"""The HTTP server that EmbodiedBench talks to with model_type=custom.

It follows third_party/EmbodiedBench/server.py: POST /process takes a multipart image file and a sentence form field and answers {"response": text}. Unlike the template, it always answers with HTTP 200 and a valid single-action plan, because the evaluator would otherwise retry an error forever. It also answers a repeated identical request from a cache, reports its state on GET /health, and writes one JSON line per request with the time spent in each stage.

Every command-line flag can also be set through an environment variable: --jev-model through DEPTHJEV_JEV_MODEL, --port through DEPTHJEV_PORT, and so on. A flag given on the command line wins.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import time
from pathlib import Path

from flask import Flask, jsonify, request
from PIL import Image

from depthjev.decision.jev import DEFAULT_MODEL
from depthjev.decision.policy import FALLBACK_ROTATE, Policy, build_response

log = logging.getLogger("depthjev.server")
REPO = Path(__file__).resolve().parents[1]


def create_app(policy: Policy, log_path: str | None) -> Flask:
    app = Flask("depthjev")
    log_file = open(log_path, "a", buffering=1, encoding="utf-8") if log_path else None
    counter = {"n": 0}
    last = {"key": None, "response": None, "record": None}
    health = {"consecutive_fallbacks": 0, "last_error": None}

    def write_record(record: dict):
        if log_file is not None:
            log_file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    @app.get("/health")
    def health_view():
        degraded = health["consecutive_fallbacks"] >= 5
        return jsonify(
            {
                "status": "degraded" if degraded else "ok",
                "requests": counter["n"],
                "consecutive_fallbacks": health["consecutive_fallbacks"],
                "last_error": health["last_error"],
            }
        )

    @app.post("/process")
    def process():
        t0 = time.perf_counter()
        counter["n"] += 1
        record: dict = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "request_index": counter["n"]}
        response_text = None
        try:
            if "image" not in request.files or "sentence" not in request.form:
                # a wiring bug on the client side; still answer a valid plan (the evaluator retries any error forever)
                raise ValueError("missing image or sentence field")
            upload = request.files["image"]
            sentence = request.form["sentence"]
            data = upload.read()
            key = (upload.filename, hashlib.sha1(data).hexdigest(), hashlib.sha1(sentence.encode("utf-8")).hexdigest())
            if key == last["key"] and last["response"] is not None:
                # the evaluator re-sends the identical step after an AI2-THOR/transport hiccup: answer from cache
                record.update({k: v for k, v in last["record"].items() if k != "ts"})
                record["repeat"] = True
                response_text = last["response"]
            else:
                image = Image.open(io.BytesIO(data))
                image.load()
                result = policy.step(image, sentence, image_name=upload.filename)
                record.update(result.record)
                response_text = result.response_text
                last.update({"key": key, "response": response_text, "record": dict(result.record)})
        except Exception as exc:  # noqa: BLE001 - last line of defence: never let the evaluator see an error
            error = f"step failed ({type(exc).__name__})"
            log.error("%s; answering with the emergency action", error)
            record.update({"fallback": True, "error": error, "action": FALLBACK_ROTATE.key})
            response_text = build_response(FALLBACK_ROTATE, "server error", "fallback: server error")
        health["consecutive_fallbacks"] = health["consecutive_fallbacks"] + 1 if record.get("fallback") else 0
        if record.get("fallback"):
            health["last_error"] = record.get("error") or "; ".join(record.get("notes", []))[:300]
        record["server_latency_s"] = time.perf_counter() - t0
        try:
            write_record(record)
            log.info(
                "req %d step %s action=%s total=%.2fs depth=%.2fs detect=%.2fs jev=%.2fs fallback=%s%s",
                counter["n"],
                record.get("step_index"),
                record.get("action"),
                record["server_latency_s"],
                record.get("timings_s", {}).get("depth", 0.0),
                record.get("timings_s", {}).get("detect", 0.0),
                record.get("timings_s", {}).get("jev", 0.0),
                record.get("fallback"),
                " repeat" if record.get("repeat") else "",
            )
        except Exception as exc:  # noqa: BLE001 - logging must never turn a valid answer into an HTTP error
            log.error("could not write the request log (%s)", type(exc).__name__)
        return jsonify({"response": response_text})

    return app


def build_policy(args) -> Policy:
    from depthjev.decision.jev import JevClient
    from depthjev.perception.depth import DepthEstimator
    from depthjev.perception.detection import TargetDetector

    depth = DepthEstimator(args.da3_dir, device=args.device)
    detector = TargetDetector(args.owlv2_dir, device=args.device, threshold=args.detection_threshold)
    jev = JevClient(model=args.jev_model, timeout_s=args.jev_timeout)
    return Policy(depth, detector, jev)


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="python -m depthjev.server",
        description="DepthJev server for EmbodiedBench model_type=custom. "
        "Each flag can also be set as an environment variable, e.g. --jev-model as DEPTHJEV_JEV_MODEL.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    def flag(name: str, default, **kwargs):
        env = "DEPTHJEV_" + name.upper().replace("-", "_")
        p.add_argument(f"--{name}", default=os.environ.get(env, default), **kwargs)

    flag("host", "127.0.0.1", help="bind address; use 0.0.0.0 for an evaluator on another machine")
    flag("port", 23333, type=int, help="HTTP port; scripts/run.sh --parallel uses port + subset index")
    flag("device", "cuda", help="torch device for Depth Anything 3 and OWLv2")
    flag("da3-dir", str(REPO / "checkpoints/DA3METRIC-LARGE"), help="local copy of depth-anything/DA3METRIC-LARGE")
    flag(
        "owlv2-dir",
        str(REPO / "checkpoints/owlv2-base-patch16-ensemble"),
        help="local copy of google/owlv2-base-patch16-ensemble",
    )
    flag("detection-threshold", 0.1, type=float, help="OWLv2 score threshold")
    flag("jev-model", DEFAULT_MODEL, help="Jev model name")
    flag("jev-timeout", 20.0, type=float, help="seconds per Jev request; the SDK retries twice on top")
    flag("log-dir", str(REPO / "logs"), help="one JSON line per request goes to <log-dir>/<run-name>.jsonl")
    flag("run-name", time.strftime("%Y%m%d_%H%M%S"), help="names the request log")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    for name, path in (("--da3-dir", args.da3_dir), ("--owlv2-dir", args.owlv2_dir)):
        if not Path(path).is_dir():
            raise SystemExit(f"{name}: no checkpoint at {path}; download it as described in README.md")
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s][%(levelname)s] %(message)s")
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{args.run_name}.jsonl"
    policy = build_policy(args)
    app = create_app(policy, str(log_path))
    log.info("DepthJev server on %s:%d, log %s", args.host, args.port, log_path)
    # threaded=False: one GPU pipeline at a time; the evaluator is a single sequential client anyway
    app.run(host=args.host, port=args.port, threaded=False)


if __name__ == "__main__":
    main()
