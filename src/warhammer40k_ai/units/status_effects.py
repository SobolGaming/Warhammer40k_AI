from typing import Callable, TYPE_CHECKING
import uuid
from enum import Enum, auto
if TYPE_CHECKING:
    from .unit import Unit
    from ..engine.game import Game

class StatusEffect:
    def __init__(self, name: str, turn_duration: int, phase_duration: int, apply_effect: Callable, remove_effect: Callable):
        self._id = str(uuid.uuid4())
        self.name = name
        self.turn = turn_duration
        self.phase = phase_duration
        self.apply_effect = apply_effect  # Function to apply effect
        self.remove_effect = remove_effect  # Function to remove effect

    @property
    def id(self) -> str:
        return self._id
    
    def check_expiration(self, unit: 'Unit', current_turn: int = None, current_phase: int = None):
        # If no current turn/phase provided, assume effect is still active
        if current_turn is None or current_phase is None:
            return True
        
        if current_turn >= self.turn and current_phase >= self.phase:
            self.remove_effect(unit)
            return False  # Effect has ended
        return True  # Effect is still active


class UnitStatsModifier(Enum):
    NONE = auto()
    OVERRIDE = auto()
    ADDITIVE = auto()


class BattleShockEffect(StatusEffect):
    def __init__(self, current_turn: int = 1):
        super().__init__(
            name = "Battle-shock",
            # Lasts until the next Command Phase
            turn_duration = current_turn + 1,
            phase_duration = 0,  # Command phase is phase 0
            apply_effect = self.apply_battle_shock,
            remove_effect = self.remove_battle_shock
        )

    def apply_battle_shock(self, unit):
        # Core Rules: Battle-shock changes OC characteristic to 0 (replacement) before other modifiers.
        from ..utility.modifiers import Modifier, ModifierOp
        unit.add_characteristic_modifier("objective_control", Modifier(ModifierOp.SET, 0, source="status:Battle-shock"))
        unit.special_rules['cannot_use_stratagems'] = True  # Cannot use Stratagems

    def remove_battle_shock(self, unit):
        # Restore objective control and allow Stratagems again
        unit.remove_characteristic_modifiers_by_source("status:Battle-shock")
        unit.special_rules['cannot_use_stratagems'] = False
