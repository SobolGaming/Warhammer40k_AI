import re
from dataclasses import dataclass
from typing import Union

# Utility Library for Dice Roll random values
from . import RNG
from .game_context import get_active_game, get_roll_context

# get result of a random dice roll, defaults to D6


def get_dice_roll(size: int = 6) -> int:
    game = get_active_game()
    if game is not None:
        event_log = getattr(game, "event_log", None)
        if event_log is not None:
            if getattr(event_log, "mode", "record") == "replay":
                event = event_log.consume("dice_roll")
                value = int(event.payload.get("value", 0) or 0)
                return value
            roll_context = get_roll_context()
            value = int(getattr(game, "random_source").randint(1, size))
            event_log.record(
                "dice_roll",
                payload={
                    "die_faces": int(size),
                    "value": int(value),
                    "context": roll_context,
                },
            )
            return value
        return int(getattr(game, "random_source").randint(1, size))
    return RNG.randint(1, size)

@dataclass
class DiceCollection:
    number: int = 0
    die_faces: int = 0
    modifier: int = 0

    @classmethod
    def from_string(cls, dice_string: str) -> 'DiceCollection':
        d_collection = cls()

        patterns = [
            r"(\d+)?D(\d+)(?:\s*\+\s*(\d+))?",
            r"(\d+)\s*\+\s*(\d+)?D(\d+)"
        ]

        for pattern in patterns:
            match = re.match(pattern, dice_string, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    d_collection.number = int(groups[0] or 1)
                    d_collection.die_faces = int(groups[1])
                    d_collection.modifier = int(groups[2] or 0)
                else:
                    d_collection.number = int(groups[1] or 1)
                    d_collection.die_faces = int(groups[2])
                    d_collection.modifier = int(groups[0] or 0)
                return d_collection

        raise ValueError(f"Invalid dice string: {dice_string}")

    def roll(self) -> int:
        roll_value = sum(get_dice_roll(self.die_faces) for _ in range(self.number)) + self.modifier
        #print(f"Roll of {self}: {roll_value}")
        return roll_value

    def roll_detailed(self) -> tuple[int, list[int]]:
        """Roll dice and return both total and individual dice results"""
        individual_rolls = [get_dice_roll(self.die_faces) for _ in range(self.number)]
        total = sum(individual_rolls) + self.modifier
        return total, individual_rolls

    def min(self) -> int:
        return self.number + self.modifier

    def max(self) -> int:
        return self.number * self.die_faces + self.modifier

    def stat_average(self) -> float:
        return (self.number * (self.die_faces + 1) / 2) + self.modifier

    def __str__(self) -> str:
        return f"{self.number}D{self.die_faces}{'+' + str(self.modifier) if self.modifier > 0 else ''}"

    def __repr__(self) -> str:
        return f"DiceCollection({self.number}, {self.die_faces}, {self.modifier})"

def get_roll(data: str) -> Union[int, None]:
    try:
        dice = DiceCollection.from_string(data)
        return dice.roll()
    except ValueError as e:
        print(f"ERROR: {e}")
        return None

if __name__ == "__main__":
    test_rolls = ["D6", "2D6", "D6+5", "2D6+5"]
    for roll in test_rolls:
        value = get_roll(roll)
        print(f"Roll of {roll}: {value}")
