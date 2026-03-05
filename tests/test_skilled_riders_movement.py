import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "12",
                "T": "5",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "2",
                "base_size": "60mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"


def _skilled_riders_unit() -> Unit:
    ability = {
        "name": "Skilled Riders",
        "description": (
            "Each time a model in this model's unit makes a Normal, Advance, Fall Back or Charge move, "
            "it can move horizontally through terrain features."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    return Unit(_MockDatasheet("Skilled Riders Unit", abilities=[ability]))


def test_skilled_riders_parses_and_sets_phase_terrain_traversal_rules():
    unit = _skilled_riders_unit()
    sr = dict(getattr(unit, "special_rules", {}) or {})

    assert set(sr.get("bearer_unit_phase_move_terrain_only_types", []) or []) >= {
        "move",
        "advance",
        "fall_back",
        "charge",
    }

    for movement_type in (MovementType.MOVE, MovementType.ADVANCE, MovementType.FALL_BACK, MovementType.CHARGE):
        rules = get_validation_rules(movement_type, moving_unit=unit)
        assert bool(rules.get("can_move_through_terrain")) is True

    move_rules = get_validation_rules(MovementType.MOVE, moving_unit=unit)
    charge_rules = get_validation_rules(MovementType.CHARGE, moving_unit=unit)
    assert bool(move_rules.get("can_move_through_enemy_models", False)) is False
    assert bool(charge_rules.get("can_move_through_enemy_models", False)) is False
