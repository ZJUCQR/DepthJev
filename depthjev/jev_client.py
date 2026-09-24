"""Client for Jev, the System One decision model from TypeSafe (https://docs.typesafe.ai).

Jev reads a state and answers typed questions with probabilities instead of text. Three Choice questions are used here. The action question picks one of the eight actions at every step. The target_direction question asks where the target probably is; it goes into the same request whenever the target is not visible. The target_type question asks once per episode which iTHOR object type the instruction is about, because the detector needs a name before any facts exist.

Proxy configuration is inherited from the process environment.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from depthjev.actions import ACTIONS
from depthjev.facts import DIRECTION_OPTIONS

DEFAULT_MODEL = "jev-latest"

ACTION_INSTRUCTIONS = (
    "You control a robot in a house. Pick exactly one next action that brings the robot within 1 m of the "
    "target object as fast as possible. Read the state: target sector and distance, free distance ahead in "
    "each of the five sectors (far_left, left, center, right, far_right), move_check for the four 0.25 m "
    "moves, camera pitch, recent actions and the search status. Rules: "
    "(1) never pick a move whose move_check is blocked, and never pick an option whose description says it is not useful now; "
    "(2) when the target is visible in the center sector and move_ahead is clear, pick move_ahead; "
    "(3) when the target is visible in the left or right sector and its distance is 1 to 2 m or over 2 m, pick move_ahead "
    "if it is clear (going forward also closes the distance); sidestep toward it with move_left or move_right when it is "
    "under 1 m away or when move_ahead is blocked; when the target is in the far_left or far_right sector it would leave "
    "the view if the robot moved ahead, so pick move_left or move_right toward it, or rotate toward it if that sidestep is blocked; "
    "(4) when the target is not visible and the camera is level, turn toward where it most likely is with rotate_left or "
    "rotate_right and keep turning in the same direction until a full turn of 4 rotations is done; "
    "(5) when a full turn was done without seeing the target, do not rotate again: pick move_ahead toward the sector "
    "with the most free distance, or move_left / move_right if move_ahead is blocked, to look from a new place; "
    "(6) pick look_down only when the camera is level and the target is likely below the view; when the camera already "
    "looks down and the target is not visible, pick look_up to bring it back to level before turning; "
    "(7) when move_ahead is blocked and the target is visible, sidestep with move_left or move_right toward the sector with more free distance; "
    "(8) when the previous action failed, do not repeat it; "
    "(9) never sidestep away from the side the target is on, and when the robot has been stepping left and right without "
    "getting closer, turn to face the target and go forward instead; "
    "(10) when two or more moves are blocked at the current position, do not alternate between them: pick move_back if it "
    "is not blocked, otherwise rotate toward the side with more free distance, to go around the obstacle; "
    "(11) when the target note says the true distance is still over 1 m, keep approaching: move_ahead if the target is in "
    "the center sector, otherwise sidestep toward it; "
    "(12) move_ahead_check_saw_the_floor false means the camera could not see low obstacles within 0.45 m, so a clear "
    "move_ahead may still fail once; after such a failure prefer look_down over guessing."
)

DIRECTION_INSTRUCTIONS = (
    "The target object is not visible in the current camera view. Where is it most likely relative to the "
    "robot right now? Use the instruction, the recent actions (rotations change what is in view), where the "
    "target was last seen and the previous guess."
)

TARGET_TYPE_INSTRUCTIONS = (
    "The instruction asks a robot to navigate to one object in a house. Which object type from the options is "
    "that object? Pick the single best match. When the instruction describes the object indirectly, by its "
    "use, its appearance, or inside a story, choose the type that fits the description."
)


# The 125 iTHOR object types, the options of the target_type question. This is the public type list from
# https://ai2thor.allenai.org/ithor/documentation/objects/object-types, not the benchmark's answers.
OBJECT_TYPES = tuple(
    """
    AlarmClock AluminumFoil Apple AppleSliced ArmChair BaseballBat BasketBall Bathtub BathtubBasin Bed Blinds
    Book Boots Bottle Bowl Box Bread BreadSliced ButterKnife Cabinet Candle CD CellPhone Chair Cloth
    CoffeeMachine CoffeeTable CounterTop CreditCard Cup Curtains Desk DeskLamp Desktop DiningTable DishSponge
    DogBed Drawer Dresser Dumbbell Egg EggCracked Faucet Floor FloorLamp Footstool Fork Fridge GarbageBag
    GarbageCan HandTowel HandTowelHolder HousePlant Kettle KeyChain Knife Ladle Laptop LaundryHamper Lettuce
    LettuceSliced LightSwitch Microwave Mirror Mug Newspaper Ottoman Painting Pan PaperTowelRoll Pen Pencil
    PepperShaker Pillow Plate Plunger Poster Pot Potato PotatoSliced RemoteControl RoomDecor Safe SaltShaker
    ScrubBrush Shelf ShelvingUnit ShowerCurtain ShowerDoor ShowerGlass ShowerHead SideTable Sink SinkBasin
    SoapBar SoapBottle Sofa Spatula Spoon SprayBottle Statue Stool StoveBurner StoveKnob TableTopDecor
    TargetCircle TeddyBear Television TennisRacket TissueBox Toaster Toilet ToiletPaper ToiletPaperHanger Tomato
    TomatoSliced Towel TowelHolder TVStand VacuumCleaner Vase Watch WateringCan Window WineBottle
    """.split()
)


def display_name(object_type: str) -> str:
    """'GarbageCan' -> 'garbage can' (what the detector query and the facts use)."""
    out = []
    for i, ch in enumerate(object_type):
        if ch.isupper() and i and not object_type[i - 1].isupper():
            out.append(" ")
        out.append(ch)
    return "".join(out).lower()


# Extra everyday phrasings for the open-vocabulary detector; the iTHOR type name alone is sometimes
# an unusual phrase for OWLv2 ("garbage can" scored below 0.1 on most frames of the 15-episode smoke).
DETECTOR_ALIASES = {
    "GarbageCan": ["trash can", "bin"],
    "CellPhone": ["smartphone", "mobile phone"],
    "Laptop": ["laptop computer", "notebook computer"],
    "DeskLamp": ["lamp", "table lamp"],
    "FloorLamp": ["lamp"],
    "AlarmClock": ["clock"],
    "Television": ["tv"],
    "RemoteControl": ["tv remote"],
    "HousePlant": ["potted plant", "plant"],
    "CoffeeMachine": ["coffee maker"],
    "Fridge": ["refrigerator"],
    "StoveBurner": ["stove"],
    "SoapBottle": ["soap dispenser"],
    "TissueBox": ["box of tissues"],
    "SprayBottle": ["spray bottle"],
    "Kettle": ["tea kettle"],
    "Bread": ["loaf of bread"],
    "Mug": ["coffee mug"],
    "Cup": ["cup"],
    "Bowl": ["bowl"],
}


def detector_queries(object_type: str) -> list[str]:
    """Names handed to OWLv2 for one iTHOR type: the spaced type name plus its aliases."""
    return [display_name(object_type)] + DETECTOR_ALIASES.get(object_type, [])


class JevError(RuntimeError):
    pass


@dataclass
class ChoiceResult:
    choice: str
    probabilities: dict
    confidence: float | None


@dataclass
class JevResponse:
    answers: dict = field(default_factory=dict)  # question key -> ChoiceResult
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_s: float = 0.0


def _key_from_dotenv() -> str | None:
    """TYPESAFE_API_KEY from the .env file at the repository root, see .env.example."""
    path = Path(__file__).resolve().parents[1] / ".env"
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        name, sep, value = line.strip().partition("=")
        if sep and name.removeprefix("export ").strip() == "TYPESAFE_API_KEY":
            return value.strip().strip("'\"") or None
    return None


class JevClient:
    def __init__(
        self, api_key: str | None = None, model: str = DEFAULT_MODEL, timeout_s: float = 20.0, max_retries: int = 2
    ):
        from typesafe_sdk import (
            RetryPolicy,
            TypeSafeClient,
        )  # imported here so the rest of the module works without typesafe-sdk

        key = api_key or os.environ.get("TYPESAFE_API_KEY") or _key_from_dotenv()
        if not key:
            raise JevError("no Jev API key: export TYPESAFE_API_KEY or set it in .env at the repository root")
        self.model = model
        self._client = TypeSafeClient(
            api_key=key, model=model, timeout=timeout_s, retry=RetryPolicy(max_retries=max_retries)
        )

    # ---- question builders -------------------------------------------------------------------
    @staticmethod
    def action_question(facts=None):
        """The eight-action Choice. Option descriptions carry the step's own constraints (blocked moves,
        camera pitch, rotation streak) because Jev reads literally and does not do the arithmetic itself."""
        from typesafe_sdk import Choice

        criteria = {a.key: a.description for a in ACTIONS}
        if facts is not None:
            pitch = facts.camera_pitch_deg
            for key, status in facts.move_check.items():
                if status == "blocked":
                    criteria[key] += "; NOT USEFUL NOW: this move is blocked"
            if pitch >= 30:
                criteria["look_down"] += f"; NOT USEFUL NOW: the camera already looks {pitch} degrees down"
                criteria["look_up"] += "; useful now: brings the camera back toward level"
            elif pitch <= -30:
                criteria["look_up"] += f"; NOT USEFUL NOW: the camera already looks {-pitch} degrees up"
            elif pitch == 0 and not facts.target.visible:
                criteria["look_up"] += (
                    "; NOT USEFUL NOW: the camera is level and nothing suggests the target is above eye level"
                )
            if facts.target.visible and facts.target.sector in ("far_left", "far_right", "left", "right"):
                side = "left" if facts.target.sector.endswith("left") else "right"
                other = "right" if side == "left" else "left"
                if facts.move_check.get(f"move_{side}") == "blocked":
                    criteria[f"rotate_{side}"] += (
                        f"; USEFUL NOW: the target is in the {facts.target.sector} sector and "
                        f"move_{side} is blocked, so turning {side} faces the target"
                    )
                    criteria["move_ahead"] += "; NOT USEFUL NOW: it would carry the robot past the target on its side"
                criteria[f"move_{other}"] += f"; NOT USEFUL NOW: it moves away from the target, which is on the {side}"
            if facts.sidestep_oscillation:
                criteria["move_left"] += "; NOT USEFUL NOW: the robot has been stepping left and right without progress"
                criteria["move_right"] += (
                    "; NOT USEFUL NOW: the robot has been stepping left and right without progress"
                )
            direction, count = facts.consecutive_rotation
            if count >= 1:
                criteria[f"rotate_{direction}"] += f"; you already turned {direction} {count} time(s) in a row"
            if facts.headings_seen >= 4 and not facts.target.visible:
                criteria["rotate_left"] += "; NOT USEFUL NOW: a full turn was already done without seeing the target"
                criteria["rotate_right"] += "; NOT USEFUL NOW: a full turn was already done without seeing the target"
        return Choice(instructions=ACTION_INSTRUCTIONS, criteria=criteria)

    @staticmethod
    def direction_question():
        from typesafe_sdk import Choice

        return Choice(instructions=DIRECTION_INSTRUCTIONS, criteria=dict(DIRECTION_OPTIONS))

    def target_type_question(self):
        from typesafe_sdk import Choice

        return Choice(instructions=TARGET_TYPE_INSTRUCTIONS, criteria={t: display_name(t) for t in OBJECT_TYPES})

    # ---- calls ---------------------------------------------------------------------------------
    def ask(self, state, questions: dict) -> JevResponse:
        t0 = time.perf_counter()
        try:
            res = self._client.system_one(state=state, questions=questions)
        except Exception as exc:  # network, 4xx/5xx after retries, validation
            # SDK errors may include credentials or response bodies; keep only the error category.
            raise JevError(f"request failed ({type(exc).__name__})") from None
        out = JevResponse(latency_s=time.perf_counter() - t0, model=getattr(res, "model", None))
        usage = getattr(res, "usage", None)
        if usage is not None:
            out.input_tokens = getattr(usage, "input_tokens", None)
            out.output_tokens = getattr(usage, "output_tokens", None)
        try:
            for key, ans in res.answers.items():
                out.answers[key] = ChoiceResult(
                    choice=str(ans.choice),
                    probabilities={str(k): float(v) for k, v in dict(ans.probabilities).items()},
                    confidence=float(ans.confidence) if getattr(ans, "confidence", None) is not None else None,
                )
        except Exception as exc:  # answers of an unexpected shape
            raise JevError(f"unexpected answer shape ({type(exc).__name__})") from None
        return out

    def resolve_target_type(self, instruction: str) -> tuple[str, JevResponse]:
        resp = self.ask({"instruction": instruction}, {"target_type": self.target_type_question()})
        ans = resp.answers.get("target_type")
        if ans is None:
            raise JevError("no target_type answer in the response")
        choice = ans.choice
        if choice not in OBJECT_TYPES:
            raise JevError("unexpected target_type answer")
        return choice, resp

    def decide(self, state: dict, ask_direction: bool, facts=None) -> JevResponse:
        questions = {"action": self.action_question(facts)}
        if ask_direction:
            questions["target_direction"] = self.direction_question()
        return self.ask(state, questions)
