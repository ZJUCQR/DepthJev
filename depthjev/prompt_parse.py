"""Read the instruction and the action history out of the prompt that EmbodiedBench sends.

With model_type=custom, EmbodiedBench posts the whole planner prompt as the sentence form field (planner/custom_model.py); the prompt is built by EBNavigationPlanner.process_prompt in planner/nav_planner.py. The instruction follows "## Now the human instruction is: " (or "## The human instruction is: " when chat_history is on) and ends with a period. From the second step on, the prompt lists every executed action on its own line, such as "Step 0, action id 0, Move forward by 0.25, env feedback: Last action MoveAhead executed successfully." A failed action has "Last action <name> is invalid." followed by the simulator's error message.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from depthjev.actions import BY_ID, Action

_INSTRUCTION_RE = re.compile(
    r"## (?:Now the|The) human instruction is: (?P<instruction>.*?)\.(?=To achieve the task|\s*\n|\s*$)",
    re.DOTALL,
)
_HISTORY_LINE_RE = re.compile(
    r"^\s*Step (?P<step>\d+), action id (?P<action_id>\d+), (?P<name>.*?), env feedback: (?P<feedback>.*?)\s*$",
    re.MULTILINE,
)
_SUCCESS_MARK = "executed successfully"


class PromptParseError(ValueError):
    """The sentence does not look like an EmbodiedBench EB-Navigation prompt."""


@dataclass(frozen=True)
class HistoryItem:
    action: Action
    success: bool


@dataclass(frozen=True)
class ParsedPrompt:
    instruction: str
    history: tuple[HistoryItem, ...] = field(default_factory=tuple)

    @property
    def step_index(self) -> int:
        """0-based index of the step about to be executed."""
        return len(self.history)

    @property
    def is_first_step(self) -> bool:
        return not self.history

    def last(self, n: int = 3) -> tuple[HistoryItem, ...]:
        return self.history[-n:]

    def camera_pitch_deg(self) -> int:
        """Camera pitch accumulated from successful LookDown (+30) / LookUp (-30) actions.

        Every EB-Navigation episode starts at horizon 0 (all 300 tasks in
        repos/EmbodiedBench/embodiedbench/envs/eb_navigation/datasets/*.json have agentPose.horizon = 0).
        Positive means looking down, matching AI2-THOR's ``cameraHorizon`` sign.
        """
        pitch = 0
        for item in self.history:
            if not item.success:
                continue
            if item.action.thor_action == "LookDown":
                pitch += 30
            elif item.action.thor_action == "LookUp":
                pitch -= 30
        return pitch


def parse_prompt(sentence: str) -> ParsedPrompt:
    m = _INSTRUCTION_RE.search(sentence)
    if m is None:
        raise PromptParseError("no '## ... human instruction is:' line found")
    instruction = " ".join(m.group("instruction").split())
    history = []
    tail = sentence[m.end() :]
    for hm in _HISTORY_LINE_RE.finditer(tail):
        action_id = int(hm.group("action_id"))
        if action_id not in BY_ID:
            raise PromptParseError(f"history references unknown action id {action_id}")
        feedback = hm.group("feedback").strip()
        history.append(HistoryItem(action=BY_ID[action_id], success=_SUCCESS_MARK in feedback))
    return ParsedPrompt(instruction=instruction, history=tuple(history))
