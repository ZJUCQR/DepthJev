"""The text facts Jev reads at each step.

StepFacts holds what one step knows: whether the target is visible, its sector and distance bin, the free distance in each of the five sectors, whether each 0.25 m move would collide, the camera pitch, the search status and the last three actions with their outcome. to_state turns it into the JSON state sent to Jev, and to_text into a one-line summary for the reply. The summary has no apostrophes because EmbodiedBench replaces every ' with " before it parses the reply.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from depthjev.actions import MAX_EPISODE_STEPS
from depthjev.geometry import SECTOR_NAMES, distance_bin
from depthjev.prompt_parse import HistoryItem

DIRECTION_OPTIONS = {
    "left": "to the left of the current view; a rotate_left would bring it into view",
    "right": "to the right of the current view; a rotate_right would bring it into view",
    "behind": "behind the robot; two rotations are needed",
    "ahead": "straight ahead but too far or too small to be detected yet; moving forward helps",
    "above": "above the current view, for example on a high shelf while the camera looks down; look_up helps",
    "below": "below the current view, for example on the floor or a low surface while the camera is level; look_down helps",
}

CLEAR, BLOCKED, UNKNOWN = "clear", "blocked", "unknown"


@dataclass
class TargetObservation:
    visible: bool
    sector: str | None = None
    distance_m: float | None = None
    score: float | None = None
    box: tuple[float, float, float, float] | None = None


@dataclass
class StepFacts:
    instruction: str
    target_name: str | None  # human-readable target ("garbage can"); None if unresolved
    step_index: int  # 0-based index of the step about to be taken
    target: TargetObservation
    sector_free_m: dict = field(default_factory=dict)
    move_check: dict = field(default_factory=dict)
    camera_pitch_deg: int = 0
    recent: tuple[HistoryItem, ...] = ()
    last_seen: dict | None = None  # {"step": int, "sector": str, "distance": str}
    previous_direction_guess: str | None = None
    depth_available: bool = True
    detection_available: bool = True
    near_floor_visible: bool = False  # the corridor floor itself was in view (reliable move_ahead check)
    rotations_since_seen: int = 0  # successful rotations since the target was last seen (or since the start)
    headings_seen: int = 0  # distinct headings (of 4) visited since the target was last seen
    consecutive_rotation: tuple = ("none", 0)  # (direction, count) of the rotation streak ending the history
    sidestep_oscillation: bool = False  # the last four actions alternate move_left / move_right

    @property
    def steps_left(self) -> int:
        return max(MAX_EPISODE_STEPS - self.step_index, 0)

    def pitch_text(self) -> str:
        p = self.camera_pitch_deg
        if p == 0:
            return "level"
        return f"{abs(p)} degrees {'down' if p > 0 else 'up'}"

    def sector_bins(self) -> dict:
        return {name: distance_bin(self.sector_free_m.get(name)) for name in SECTOR_NAMES}

    def to_state(self) -> dict:
        target: dict = {"visible": self.target.visible}
        if self.target.visible:
            target["sector"] = self.target.sector
            target["distance"] = distance_bin(self.target.distance_m)
            if self.target.distance_m is None:
                target["distance"] = "unknown"
            elif self.target.distance_m < 1.0:
                # the episode ends automatically within 1 m, so a running episode means the estimate is short
                target["note"] = (
                    "the estimate reads under 1 m but the episode has not ended, so the true "
                    "distance is still over 1 m: keep closing in on the target"
                )
        else:
            target["last_seen"] = self.last_seen
            target["previous_direction_guess"] = self.previous_direction_guess
            target["search"] = {
                "rotations_since_target_seen": self.rotations_since_seen,
                "full_turn_done_without_seeing_it": self.headings_seen >= 4,
                "same_rotation_in_a_row": {
                    "direction": self.consecutive_rotation[0],
                    "count": self.consecutive_rotation[1],
                },
            }
        recent = [{"action": h.action.key, "result": "success" if h.success else "failed"} for h in self.recent]
        if self.sidestep_oscillation:
            recent.append({"note": "the robot has been alternating move_left and move_right without progress"})
        state = {
            "task": {
                "instruction": self.instruction,
                "target_object": self.target_name or "unknown",
                "success_rule": "the episode succeeds as soon as the robot stands within 1 m of the target object",
                "step": self.step_index + 1,
                "steps_left": self.steps_left,
            },
            "target": target,
            "free_distance_ahead_by_sector": self.sector_bins() if self.depth_available else "depth unavailable",
            "move_check": self.move_check,
            "move_ahead_check_saw_the_floor": self.near_floor_visible,
            "camera_pitch": self.pitch_text(),
            "recent_actions": recent,
        }
        if not self.detection_available:
            state["target"]["note"] = "detector unavailable this step"
        return state

    def to_text(self) -> str:
        parts = []
        if self.target.visible:
            parts.append(
                f"target {self.target_name} visible in the {self.target.sector} sector, {distance_bin(self.target.distance_m)}"
            )
        else:
            parts.append(f"target {self.target_name or 'unknown'} not visible")
        if self.depth_available:
            bins = self.sector_bins()
            parts.append("free ahead: " + ", ".join(f"{k} {v}" for k, v in bins.items()))
        else:
            parts.append("depth unavailable")
        parts.append("moves: " + ", ".join(f"{k} {v}" for k, v in self.move_check.items()))
        parts.append(f"camera {self.pitch_text()}")
        if self.recent:
            parts.append(
                "recent: " + ", ".join(f"{h.action.key} {'ok' if h.success else 'failed'}" for h in self.recent)
            )
        return "; ".join(parts).replace("'", "")


def search_status(history: tuple[HistoryItem, ...], last_seen_index: int | None) -> tuple[int, tuple, int]:
    """(rotations since the target was last seen, rotation streak ending the history, distinct headings visited).

    ``last_seen_index`` is the 0-based index of the step at which the target was last seen; the action
    taken at that step counts (it may be the rotation that made the target leave the view).
    """
    start = 0 if last_seen_index is None else last_seen_index
    rot, heading, visited = 0, 0, {0}
    for h in history[start:]:
        if h.success and h.action.key in ("rotate_left", "rotate_right"):
            rot += 1
            heading = (heading + (1 if h.action.key == "rotate_right" else -1)) % 4
            visited.add(heading)
    direction, count = "none", 0
    for h in reversed(history):
        if h.action.key in ("rotate_left", "rotate_right"):
            if count == 0:
                direction = "left" if h.action.key == "rotate_left" else "right"
            if ("left" if h.action.key == "rotate_left" else "right") != direction:
                break
            count += 1
        else:
            break
    return rot, (direction, count), len(visited)


def sidestep_oscillation(history: tuple[HistoryItem, ...]) -> bool:
    """True when the last four actions alternate between move_left and move_right."""
    keys = [h.action.key for h in history[-4:]]
    if len(keys) < 4 or not all(k in ("move_left", "move_right") for k in keys):
        return False
    return all(keys[i] != keys[i + 1] for i in range(3))


def move_checks(history: tuple[HistoryItem, ...], depth_available: bool, forward_blocked: bool) -> dict:
    """Would each 0.25 m move collide?

    * move_ahead comes from the depth corridor test, or from the feedback when MoveAhead failed at this pose.
    * move_back / move_left / move_right are outside the 100-degree front camera: they are ``blocked`` when
      that move failed at the current pose, move_back is ``clear`` right after a successful move_ahead (the
      robot came from there), otherwise ``unknown``. Reporting ``unknown`` instead of guessing keeps the facts honest.
    * "At the current pose" = since the last successful translation or rotation; LookUp/LookDown do not move
      the robot, so a move that failed before a camera tilt is still blocked after it.
    """
    failed_here: set[str] = set()
    last_pose_change = None
    for item in reversed(history):
        if item.success and item.action.key in (
            "move_ahead",
            "move_back",
            "move_left",
            "move_right",
            "rotate_left",
            "rotate_right",
        ):
            last_pose_change = item
            break
        if not item.success and item.action.key.startswith("move_"):
            failed_here.add(item.action.key)
    checks = {}
    if "move_ahead" in failed_here:
        checks["move_ahead"] = BLOCKED
    elif not depth_available:
        checks["move_ahead"] = UNKNOWN
    else:
        checks["move_ahead"] = BLOCKED if forward_blocked else CLEAR
    for key in ("move_back", "move_left", "move_right"):
        if key in failed_here:
            checks[key] = BLOCKED
        elif (
            key == "move_back"
            and last_pose_change is not None
            and last_pose_change.action.key == "move_ahead"
            and history
            and history[-1] is last_pose_change
        ):
            checks[key] = CLEAR
        else:
            checks[key] = UNKNOWN
    return checks
