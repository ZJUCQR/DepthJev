"""The names of things: the 125 iTHOR object types, how the facts spell them, and how OWLv2 is asked for them.

The target type is one of OBJECT_TYPES (Jev picks it from the instruction once per episode). display_name turns it into the words the facts and the detector use, and detector_queries adds everyday phrasings for the open-vocabulary detector.
"""

from __future__ import annotations

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
