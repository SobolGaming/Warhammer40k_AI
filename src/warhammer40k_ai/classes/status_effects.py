from typing import Callable, TYPE_CHECKING
from enum import Enum, auto
if TYPE_CHECKING:
    from .unit import Unit
    from .game import Game

class StatusEffect:
    def __init__(self, name: str, turn_duration: int, phase_duration: int, apply_effect: Callable, remove_effect: Callable):
        self.name = name
        self.turn = turn_duration
        self.phase = phase_duration
        self.apply_effect = apply_effect  # Function to apply effect
        self.remove_effect = remove_effect  # Function to remove effect
    
    def check_expiration(self, unit: 'Unit'):
        if Game.current_turn >= self.turn and Game.current_phase >= self.phase:
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
            name = "Battle-shock",
            # Lasts until the next Command Phase
            turn_duration = Game.current_turn + 1,
            phase_duration = Game.BattleRoundPhases.COMMAND_PHASE,
            apply_effect = self.apply_battle_shock,
            remove_effect = self.remove_battle_shock
        )

    def apply_battle_shock(self, unit):
        unit.stats['objective_control'] = (UnitStatsModifier.OVERRIDE, 0)  # Unit cannot control objectives
        unit.special_rules['cannot_use_stratagems'] = True  # Cannot use Stratagems

    def remove_battle_shock(self, unit):
        # Restore objective control and allow Stratagems again
        unit.stats['objective_control'] = (UnitStatsModifier.NONE, 0)
        unit.special_rules['cannot_use_stratagems'] = False