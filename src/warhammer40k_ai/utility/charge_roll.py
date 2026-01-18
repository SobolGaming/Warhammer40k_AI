from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Sequence, Tuple


class ChargeRerollPolicy(Enum):
    NONE = "none"
    REROLL_ALL = "reroll_all"
    REROLL_ONE = "reroll_one"
    REROLL_SPECIFIC = "reroll_specific"


@dataclass
class ChargeRollSpec:
    dice_count: int = 2
    keep_highest: int = 2
    reroll_policy: ChargeRerollPolicy = ChargeRerollPolicy.NONE
    reroll_specific: Optional[List[int]] = None
    modifiers: List[Tuple[int, str]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class ChargeRollResult:
    spec: ChargeRollSpec
    dice: List[int]
    kept_indices: List[int]
    dropped_indices: List[int]
    total: int

    @classmethod
    def from_dice(cls, spec: ChargeRollSpec, dice: Sequence[int]) -> "ChargeRollResult":
        dice_list = [int(d or 0) for d in list(dice)]
        keep = max(0, int(spec.keep_highest or 0))
        if keep >= len(dice_list):
            kept_indices = list(range(len(dice_list)))
            dropped_indices = []
        else:
            pairs = list(enumerate(dice_list))
            pairs.sort(key=lambda item: (item[1], item[0]))
            drop_count = max(0, len(dice_list) - keep)
            dropped_indices = sorted([idx for idx, _val in pairs[:drop_count]])
            kept_indices = sorted([idx for idx, _val in pairs[drop_count:]])
        total = sum(dice_list[i] for i in kept_indices)
        return cls(
            spec=spec,
            dice=dice_list,
            kept_indices=kept_indices,
            dropped_indices=dropped_indices,
            total=int(total),
        )

    def reroll_all(self, roller: Callable[[], int]) -> "ChargeRollResult":
        dice = [int(roller() or 0) for _ in range(int(self.spec.dice_count or 0))]
        return ChargeRollResult.from_dice(self.spec, dice)

    def reroll_one(self, index: int, roller: Callable[[], int]) -> "ChargeRollResult":
        dice = list(self.dice)
        if 0 <= index < len(dice):
            dice[index] = int(roller() or 0)
        return ChargeRollResult.from_dice(self.spec, dice)

    def reroll_indices(self, indices: Sequence[int], roller: Callable[[], int]) -> "ChargeRollResult":
        dice = list(self.dice)
        for idx in indices:
            if 0 <= idx < len(dice):
                dice[idx] = int(roller() or 0)
        return ChargeRollResult.from_dice(self.spec, dice)

    def kept_values(self) -> List[int]:
        return [self.dice[i] for i in self.kept_indices]

    def dropped_values(self) -> List[int]:
        return [self.dice[i] for i in self.dropped_indices]
