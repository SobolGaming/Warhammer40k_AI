import typing
from dataclasses import dataclass
from enum import Enum

from .dice import DiceCollection

class CountType(Enum):
    FLAT = 1
    DICE = 2

@dataclass
class Count:
    ctype: CountType = CountType.FLAT
    value: typing.Union[int, DiceCollection] = 0

    @classmethod
    def from_string(cls, dice_string: str) -> 'Count':
        if "D" in dice_string.upper():
            dc = DiceCollection.from_string(dice_string)
            return cls(CountType.DICE, dc)
        elif dice_string == "-":
            return cls(CountType.FLAT, 0)
        else:
            return cls(CountType.FLAT, int(dice_string))

    def resolve(self) -> int:
        return self.value if self.ctype is CountType.FLAT else self.value.roll()

    def min(self) -> int:
        return self.value if self.ctype is CountType.FLAT else self.value.min()

    def max(self) -> int:
        return self.value if self.ctype is CountType.FLAT else self.value.max()

    def stat_average(self) -> float:
        """Statistical Average

        Returns:
            float: The statistical average of this count (flat or dice)
        """
        return self.value if self.ctype is CountType.FLAT else self.value.stat_average()

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f"Count({self.ctype}, {self.value})"