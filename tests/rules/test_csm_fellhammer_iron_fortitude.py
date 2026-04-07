from __future__ import annotations

import unittest

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        toughness: str = "4",
        wounds: str = "3",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    toughness: str = "4",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_profile(*, name: str, weapon_type: str, strength: str):
    weapon = Wargear(
        {
            "name": str(name),
            "type": "Melee" if str(weapon_type).lower() == "melee" else "Ranged",
            "range": "Melee" if str(weapon_type).lower() == "melee" else "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


class TestCsmFellhammerIronFortitude(unittest.TestCase):
    def test_iron_fortitude_applies_only_to_eligible_ranged_strength_gt_toughness_attacks(self):
        fellhammer_army = Army.with_detachment("Chaos Space Marines", "Fellhammer Siege-host")
        fellhammer_army.faction_id = "CSM"
        enemy_army = Army.with_detachment("Enemy", "Other")
        enemy_army.faction_id = "EN"

        defender = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
            toughness="4",
        )
        damned_defender = _make_unit(
            "Accursed Cultists",
            keywords=["HERETIC ASTARTES", "INFANTRY", "DAMNED"],
            faction_keywords=["HERETIC ASTARTES"],
            toughness="4",
        )
        attacker = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness="4",
        )
        fellhammer_army.add_unit(defender)
        fellhammer_army.add_unit(damned_defender)
        enemy_army.add_unit(attacker)
        attacker_model = attacker.models[0]

        ranged_strong = _make_profile(name="Strong Gun", weapon_type="ranged", strength="5")
        strong_result = ranged_strong._wound_target_with_tracking(
            defender,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Iron Fortitude" in m for m in list(strong_result.get("modifiers", []) or [])))

        ranged_equal = _make_profile(name="Equal Gun", weapon_type="ranged", strength="4")
        equal_result = ranged_equal._wound_target_with_tracking(
            defender,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Iron Fortitude" in m for m in list(equal_result.get("modifiers", []) or [])))

        melee_strong = _make_profile(name="Melee Weapon", weapon_type="melee", strength="6")
        melee_result = melee_strong._wound_target_with_tracking(
            defender,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Iron Fortitude" in m for m in list(melee_result.get("modifiers", []) or [])))

        damned_result = ranged_strong._wound_target_with_tracking(
            damned_defender,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Iron Fortitude" in m for m in list(damned_result.get("modifiers", []) or [])))

    def test_iron_fortitude_does_not_apply_outside_fellhammer(self):
        non_fellhammer_army = Army.with_detachment("Chaos Space Marines", "Renegade Raiders")
        non_fellhammer_army.faction_id = "CSM"
        enemy_army = Army.with_detachment("Enemy", "Other")
        enemy_army.faction_id = "EN"

        defender = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
            toughness="4",
        )
        attacker = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness="4",
        )
        non_fellhammer_army.add_unit(defender)
        enemy_army.add_unit(attacker)
        attacker_model = attacker.models[0]

        ranged_strong = _make_profile(name="Strong Gun", weapon_type="ranged", strength="5")
        result = ranged_strong._wound_target_with_tracking(
            defender,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Iron Fortitude" in m for m in list(result.get("modifiers", []) or [])))


if __name__ == "__main__":
    unittest.main()
