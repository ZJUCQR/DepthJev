"""The eight EB-Navigation actions.

Their order, ids and strings are copied from DISCRETE_SKILLSET and discrete_action_mapper in EmbodiedBench (embodiedbench/envs/eb_navigation/EBNavEnv.py). thor_action is the AI2-THOR action name that appears in the env feedback, as in "Last action MoveAhead executed successfully."
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Action:
    action_id: int
    key: str  # option name used in the Jev Choice question
    eb_name: str  # EmbodiedBench action string, returned in executable_plan.action_name
    thor_action: str  # AI2-THOR action name as it appears in EmbodiedBench env feedback
    description: str  # what Jev sees as the description of this option


ACTIONS: tuple[Action, ...] = (
    Action(
        0,
        "move_ahead",
        "Move forward by 0.25",
        "MoveAhead",
        "step 0.25 m forward in the facing direction; best when the target is ahead and the center sector is free",
    ),
    Action(
        1,
        "move_back",
        "Move backward by 0.25",
        "MoveBack",
        "step 0.25 m backward without turning; only useful to back away from an obstacle that blocks every other move",
    ),
    Action(
        2,
        "move_right",
        "Move rightward by 0.25",
        "MoveRight",
        "sidestep 0.25 m to the right without turning; use to line up with a target seen in a right sector or to get around an obstacle on the left",
    ),
    Action(
        3,
        "move_left",
        "Move leftward by 0.25",
        "MoveLeft",
        "sidestep 0.25 m to the left without turning; use to line up with a target seen in a left sector or to get around an obstacle on the right",
    ),
    Action(
        4,
        "rotate_right",
        "Rotate to the right by 90 degrees.",
        "RotateRight",
        "turn 90 degrees to the right in place; use when the target is not visible and is most likely to the right or behind",
    ),
    Action(
        5,
        "rotate_left",
        "Rotate to the left by 90 degrees.",
        "RotateLeft",
        "turn 90 degrees to the left in place; use when the target is not visible and is most likely to the left",
    ),
    Action(
        6,
        "look_up",
        "Tilt the camera upward by 30 degrees.",
        "LookUp",
        "tilt the camera 30 degrees up; only to undo an earlier look_down or when the target is likely above the current view",
    ),
    Action(
        7,
        "look_down",
        "Tilt the camera downward by 30 degrees.",
        "LookDown",
        "tilt the camera 30 degrees down; use when the target is likely below the current view, for example a small object on the floor or a low surface while the camera is level",
    ),
)

BY_ID = {a.action_id: a for a in ACTIONS}
BY_KEY = {a.key: a for a in ACTIONS}

# EmbodiedBench episode limit (EBNavEnv: _max_episode_steps = 20).
MAX_EPISODE_STEPS = 20
