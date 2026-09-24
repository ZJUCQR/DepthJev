"""One step of the agent: a frame and the EmbodiedBench prompt in, one action out.

A step parses the prompt, resolves the target type on the first step of an episode, runs Depth Anything 3 and OWLv2 on the frame, builds the facts, asks Jev, and answers in EmbodiedBench's JSON format with a single action in executable_plan. The evaluator retries a failed step forever, so no failure is allowed to escape: a model error marks that part of the facts as unavailable, a Jev error falls back to a fixed rule, and an unreadable prompt gets a default rotation.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from PIL import Image

from depthjev.actions import BY_KEY, Action
from depthjev.facts import CLEAR, StepFacts, TargetObservation, move_checks, search_status, sidestep_oscillation
from depthjev.geometry import FOV_DEG, analyze_depth, distance_bin, sector_of_column
from depthjev.jev_client import JevClient, JevError, detector_queries, display_name
from depthjev.prompt_parse import ParsedPrompt, PromptParseError, parse_prompt

FALLBACK_ROTATE = BY_KEY["rotate_right"]


@dataclass
class EpisodeMemory:
    instruction: str
    target_type: str | None = None  # iTHOR type, e.g. "GarbageCan"
    target_name: str | None = None  # "garbage can"
    resolve_attempts: int = 0
    last_seen: dict | None = None
    last_seen_index: int | None = None  # 0-based step index of the last sighting
    previous_direction_guess: str | None = None


@dataclass
class StepResult:
    action: Action
    response_text: str
    record: dict


def sanitize(text: str) -> str:
    """Make a string safe for EmbodiedBench's post-processing of our JSON.

    ``act_custom`` rewrites every ' into ", strips ```json fences and turns '"s ' into "'s " before
    json.loads (planner/nav_planner.py), so values must contain no quotes, no backticks and must not
    start with "s ".
    """
    out = text.replace("'", "").replace('"', "").replace("`", "")
    out = out.encode("ascii", "ignore").decode("ascii")
    if out.startswith("s "):
        out = "- " + out
    return out


def build_response(action: Action, visual_state: str, reasoning: str) -> str:
    obj = {
        "visual_state_description": sanitize(visual_state),
        "reasoning_and_reflection": sanitize(reasoning),
        "language_plan": sanitize(f"1. {action.eb_name}"),
        "executable_plan": [{"action_id": action.action_id, "action_name": action.eb_name}],
    }
    return json.dumps(obj, ensure_ascii=True)


def fallback_action(facts: StepFacts | None) -> Action:
    """Deterministic emergency choice when Jev cannot answer: keep approaching a visible target
    if the way is clear, otherwise turn right to search."""
    if facts is not None and facts.target.visible:
        if facts.move_check.get("move_ahead") == CLEAR:
            return BY_KEY["move_ahead"]
        if facts.target.sector in ("left", "far_left") and facts.move_check.get("move_left") != "blocked":
            return BY_KEY["move_left"]
        if facts.target.sector in ("right", "far_right") and facts.move_check.get("move_right") != "blocked":
            return BY_KEY["move_right"]
    return FALLBACK_ROTATE


class Policy:
    def __init__(self, depth, detector, jev: JevClient, fov_deg: float = FOV_DEG):
        self.depth = depth  # DepthEstimator
        self.detector = detector  # TargetDetector
        self.jev = jev
        self.fov_deg = fov_deg
        self.memory: EpisodeMemory | None = None

    # ---- episode memory ---------------------------------------------------------------------------
    def _memory_for(self, parsed: ParsedPrompt) -> EpisodeMemory:
        if parsed.is_first_step or self.memory is None or self.memory.instruction != parsed.instruction:
            self.memory = EpisodeMemory(instruction=parsed.instruction)
        return self.memory

    # ---- main entry -------------------------------------------------------------------------------
    def step(self, image: Image.Image, sentence: str, image_name: str | None = None) -> StepResult:
        t_start = time.perf_counter()
        # Keep the frame identifier without any client-side directory information.
        image_name = image_name.replace("\\", "/").rsplit("/", 1)[-1] if image_name else None
        record: dict = {"image_name": image_name, "timings_s": {}, "notes": [], "fallback": False}
        notes = record["notes"]

        try:
            parsed = parse_prompt(sentence)
        except PromptParseError as exc:
            notes.append(f"prompt parse failed ({type(exc).__name__})")
            record["fallback"] = True
            record["action"] = FALLBACK_ROTATE.key
            record["timings_s"]["total"] = time.perf_counter() - t_start
            return StepResult(
                FALLBACK_ROTATE,
                build_response(FALLBACK_ROTATE, "prompt not understood", "fallback: prompt parse failed"),
                record,
            )

        record["instruction"] = parsed.instruction
        record["step_index"] = parsed.step_index
        mem = self._memory_for(parsed)

        # target type (once per episode; retried on later steps if the first attempt failed)
        if mem.target_type is None and mem.resolve_attempts < 3:
            mem.resolve_attempts += 1
            t0 = time.perf_counter()
            try:
                mem.target_type, resp = self.jev.resolve_target_type(parsed.instruction)
                mem.target_name = display_name(mem.target_type)
                probs = resp.answers["target_type"].probabilities
                record["target_resolution"] = {
                    "type": mem.target_type,
                    "confidence": resp.answers["target_type"].confidence,
                    "top5": sorted(probs.items(), key=lambda kv: -kv[1])[:5],
                    "input_tokens": resp.input_tokens,
                    "latency_s": resp.latency_s,
                }
            except JevError as exc:
                notes.append(f"target resolution failed ({type(exc).__name__})")
            record["timings_s"]["target_resolution"] = time.perf_counter() - t0
        record["target_type"] = mem.target_type

        pitch = parsed.camera_pitch_deg()

        # depth
        geom = None
        t0 = time.perf_counter()
        try:
            metric = self.depth.predict(image)
            geom = analyze_depth(metric, pitch, self.fov_deg)
        except Exception as exc:  # noqa: BLE001 - any model failure degrades to "depth unavailable"
            notes.append(f"depth failed ({type(exc).__name__})")
        record["timings_s"]["depth"] = time.perf_counter() - t0

        # detection
        target = TargetObservation(visible=False)
        detection_available = mem.target_name is not None
        t0 = time.perf_counter()
        if detection_available:
            try:
                dets = self.detector.detect(image, detector_queries(mem.target_type))
                record["detections"] = [
                    {"box": [round(v, 1) for v in d.box], "score": round(d.score, 4), "query": d.query}
                    for d in dets[:5]
                ]
                if dets:
                    best = dets[0]
                    cx = (best.box[0] + best.box[2]) / 2.0
                    target = TargetObservation(
                        visible=True,
                        sector=sector_of_column(cx, image.size[0]),
                        distance_m=geom.target_range_m(best.box) if geom is not None else None,
                        score=best.score,
                        box=best.box,
                    )
            except Exception as exc:  # noqa: BLE001
                detection_available = False
                notes.append(f"detection failed ({type(exc).__name__})")
        else:
            notes.append("no target name: detection skipped")
        record["timings_s"]["detect"] = time.perf_counter() - t0

        # facts
        facts = StepFacts(
            instruction=parsed.instruction,
            target_name=mem.target_name,
            step_index=parsed.step_index,
            target=target,
            sector_free_m=geom.sector_free_m if geom is not None else {},
            move_check=move_checks(
                parsed.history, geom is not None, geom.forward_blocked if geom is not None else False
            ),
            camera_pitch_deg=pitch,
            recent=parsed.last(3),
            last_seen=mem.last_seen,
            previous_direction_guess=mem.previous_direction_guess,
            depth_available=geom is not None,
            detection_available=detection_available,
        )
        facts.rotations_since_seen, facts.consecutive_rotation, facts.headings_seen = search_status(
            parsed.history, mem.last_seen_index
        )
        facts.near_floor_visible = geom.near_floor_visible if geom is not None else False
        facts.sidestep_oscillation = sidestep_oscillation(parsed.history)
        state = facts.to_state()
        record["facts"] = state
        record["target"] = {
            "visible": target.visible,
            "sector": target.sector,
            "distance_m": target.distance_m,
            "score": target.score,
            "box": target.box,
        }
        if geom is not None:
            record["geometry"] = {
                "floor_depth_m": geom.floor_depth_m,
                "floor_from_data": geom.floor_from_data,
                "sector_free_m": {
                    k: (None if v == float("inf") else round(v, 3)) for k, v in geom.sector_free_m.items()
                },
                "forward_blocking_pixels": geom.forward_blocking_pixels,
            }

        # decision
        t0 = time.perf_counter()
        action = None
        reasoning = ""
        try:
            resp = self.jev.decide(state, ask_direction=not target.visible, facts=facts)
            ans = resp.answers.get("action")
            if ans is None or ans.choice not in BY_KEY:
                raise JevError("no usable action answer")
            action = BY_KEY[ans.choice]
            record["jev"] = {
                "model": resp.model,
                "latency_s": resp.latency_s,
                "input_tokens": resp.input_tokens,
                "output_tokens": resp.output_tokens,
                "action": ans.choice,
                "confidence": ans.confidence,
                "probabilities": {k: round(v, 4) for k, v in ans.probabilities.items()},
            }
            reasoning = (
                f"jev {resp.model} chose {ans.choice} with probability {ans.probabilities.get(ans.choice, 0):.2f}"
            )
            if "target_direction" in resp.answers:
                d = resp.answers["target_direction"]
                mem.previous_direction_guess = d.choice
                record["jev"]["target_direction"] = d.choice
                record["jev"]["target_direction_probabilities"] = {k: round(v, 4) for k, v in d.probabilities.items()}
                reasoning += f"; target most likely {d.choice} (p={d.probabilities.get(d.choice, 0):.2f})"
        except JevError as exc:
            notes.append(f"jev failed ({type(exc).__name__})")
        record["timings_s"]["jev"] = time.perf_counter() - t0
        if action is None:
            action = fallback_action(facts)
            record["fallback"] = True
            reasoning = f"fallback rule chose {action.key} because the decision model was unavailable"

        # memory and response
        if target.visible:
            mem.last_seen = {
                "step": parsed.step_index + 1,
                "sector": target.sector,
                "distance": distance_bin(target.distance_m),
            }
            mem.last_seen_index = parsed.step_index
        record["action"] = action.key
        record["action_id"] = action.action_id
        record["timings_s"]["total"] = time.perf_counter() - t_start
        return StepResult(action, build_response(action, facts.to_text(), reasoning), record)
