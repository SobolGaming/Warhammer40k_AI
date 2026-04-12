import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None):
        self.name = name
        self.faction_data = {"name": "Chaos Space Marines"}
        self.keywords = ["VEHICLE", "DAEMON", "HERETIC ASTARTES"]
        self.faction_keywords = ["HERETIC ASTARTES"]
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "12",
                "T": "11",
                "Sv": "3",
                "W": "18",
                "Ld": "6",
                "OC": "5",
                "base_size": "120mm x 92mm",
                "inv_sv": "5",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _defiler() -> Unit:
    ability = {
        "name": "Scuttling Walker",
        "description": (
            "Each time this unit makes a Normal, Advance or Fall Back move, it can move through models "
            "(excluding TITANIC models) and terrain features. When doing so, it can move within Engagement "
            "Range of enemy models, but cannot end that move within Engagement Range of them, and any "
            "Desperate Escape test is automatically passed."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    return Unit(_MockDatasheet("Defiler", abilities=[ability]))


def test_scuttling_walker_parses_current_defiler_wording():
    unit = _defiler()
    sr = dict(getattr(unit, "special_rules", {}) or {})

    assert set(sr.get("bearer_unit_phase_move_types", []) or []) >= {"move", "advance", "fall_back"}
    assert set(sr.get("bearer_unit_phase_move_block_titanic_types", []) or []) >= {"move", "advance", "fall_back"}
    assert set(sr.get("bearer_unit_phase_move_engagement_types", []) or []) >= {"move", "advance", "fall_back"}
    assert bool(sr.get("bearer_unit_auto_pass_desperate_escape", False)) is True


def test_scuttling_walker_feeds_current_movement_validation_rules():
    unit = _defiler()

    move_rules = get_validation_rules(MovementType.MOVE, moving_unit=unit)
    assert bool(move_rules.get("can_move_through_enemy_models", False)) is True
    assert bool(move_rules.get("can_move_through_friendly_models", False)) is True
    assert bool(move_rules.get("can_move_through_terrain", False)) is True
    assert bool(move_rules.get("block_titanic_models", False)) is True
    assert bool(move_rules.get("cannot_move_within_engagement_range", True)) is False
    assert bool(move_rules.get("cannot_end_in_engagement_range", False)) is True

    fall_back_rules = get_validation_rules(MovementType.FALL_BACK, moving_unit=unit)
    assert bool(fall_back_rules.get("can_move_through_enemy_models", False)) is True
    assert bool(fall_back_rules.get("can_move_through_friendly_models", False)) is True
    assert bool(fall_back_rules.get("can_move_through_terrain", False)) is True
    assert bool(fall_back_rules.get("block_titanic_models", False)) is True
    assert bool(fall_back_rules.get("check_desperate_escape", True)) is False


def test_scuttling_walker_auto_passes_desperate_escape_tests():
    unit = _defiler()

    assert unit.take_desperate_escape_test(reason="moved through enemy models") == 0
