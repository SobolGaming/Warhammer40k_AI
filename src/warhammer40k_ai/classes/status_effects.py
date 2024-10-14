from typing import Callable, TYPE_CHECKING
from enum import Enum, auto
if TYPE_CHECKING:
    from .unit import Unit

class StatusEffect:
    def __init__(self, name: str, duration: int, apply_effect: Callable, remove_effect: Callable):
        self.name = name
        self.duration = duration
        self.remaining_duration = duration
        self.apply_effect = apply_effect  # Function to apply effect
        self.remove_effect = remove_effect  # Function to remove effect
    
    def tick(self, unit: 'Unit'):
        self.remaining_duration -= 1
        if self.remaining_duration <= 0:
            self.remove_effect(unit)
            return False  # Effect has ended
        return True  # Effect is still active


class UnitStatsModifier(Enum):
    NONE = auto()
    OVERRIDE = auto()
    ADDITIVE = auto()


class BattleShockEffect(StatusEffect):
    def __init__(self):
        super().__init__(
            name="Battle-shock",
            duration=1,  # Lasts until the next Command Phase
            apply_effect=self.apply_battle_shock,
            remove_effect=self.remove_battle_shock
        )

    def apply_battle_shock(self, unit):
        unit.stats['objective_control'] = (UnitStatsModifier.OVERRIDE, 0)  # Unit cannot control objectives
        unit.special_rules['cannot_use_stratagems'] = True  # Cannot use Stratagems

    def remove_battle_shock(self, unit):
        # Restore objective control and allow Stratagems again
        unit.stats['objective_control'] = (UnitStatsModifier.NONE, 0)
        unit.special_rules['cannot_use_stratagems'] = False