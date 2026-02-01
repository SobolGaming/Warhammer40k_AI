import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules


class _MockDatasheet:
    def __init__(self, name, *, unit_comp="1 Test Model", abilities=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "TEST"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": unit_comp}]
        self.datasheets_models_cost = [{"description": unit_comp, "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_unit(name, *, ability_desc=None, ability_name=None, model_count=1):
    abilities = []
    if ability_desc:
        abilities.append(
            {
                "name": ability_name or name,
                "description": ability_desc,
                "type": "Datasheet",
                "parameter": "",
            }
        )
    datasheet = _MockDatasheet(name, unit_comp=f"{model_count} Test Models", abilities=abilities)
    return Unit(datasheet)


def test_consolidate_distance_override_from_unit_ability():
    ability_text = (
        "Each time this model's unit Consolidates, it can move up to 6\" instead of up to 3\"."
    )
    unit = _make_unit("Test Unit", ability_desc=ability_text, model_count=5)

    consolidate_rules = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=unit)
    assert consolidate_rules.get("max_distance_override") == 6.0

    pile_in_rules = get_validation_rules(MovementType.PILE_IN, moving_unit=unit)
    assert pile_in_rules.get("max_distance_override") == 3.0


def test_pile_in_and_consolidate_override_from_leading_ability():
    ability_text = (
        "While this model is leading a unit, each time that unit Piles In or Consolidates, "
        "each model in that unit can move up to 6\" instead of up to 3\"."
    )
    bodyguard = _make_unit("Bodyguard", model_count=5)
    leader = _make_unit("Leader", ability_desc=ability_text, model_count=1)

    leader.can_be_attached_to = ["INFANTRY"]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]

    bodyguard._refresh_bearer_unit_common_modifiers()

    pile_in_rules = get_validation_rules(MovementType.PILE_IN, moving_unit=bodyguard)
    assert pile_in_rules.get("max_distance_override") == 6.0

    consolidate_rules = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=bodyguard)
    assert consolidate_rules.get("max_distance_override") == 6.0
