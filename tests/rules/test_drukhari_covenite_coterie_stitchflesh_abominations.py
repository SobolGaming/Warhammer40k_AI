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
        faction_name: str = "Drukhari",
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
                "M": "7",
                "T": str(toughness),
                "Sv": "6",
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
    faction_name: str = "Drukhari",
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


class TestDrukhariCoveniteCoterieStitchfleshAbominations(unittest.TestCase):
    def test_stitchflesh_applies_to_haemonculus_covens_when_strength_gt_toughness(self):
        coterie_army = Army.with_detachment("Drukhari", "Covenite Coterie")
        coterie_army.faction_id = "DRU"
        enemy_army = Army.with_detachment("Enemy", "Other")
        enemy_army.faction_id = "EN"

        covens_defender = _make_unit(
            "Wracks",
            keywords=["DRUKHARI", "INFANTRY", "HAEMONCULUS COVENS"],
            faction_keywords=["DRUKHARI"],
            toughness="4",
        )
        non_covens_defender = _make_unit(
            "Kabalite Warriors",
            keywords=["DRUKHARI", "INFANTRY", "KABAL"],
            faction_keywords=["DRUKHARI"],
            toughness="4",
        )
        attacker = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness="4",
        )
        coterie_army.add_unit(covens_defender)
        coterie_army.add_unit(non_covens_defender)
        enemy_army.add_unit(attacker)
        attacker_model = attacker.models[0]

        ranged_strong = _make_profile(name="Strong Gun", weapon_type="ranged", strength="5")
        ranged_result = ranged_strong._wound_target_with_tracking(
            covens_defender,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Stitchflesh Abominations" in m for m in list(ranged_result.get("modifiers", []) or [])))

        melee_strong = _make_profile(name="Strong Blade", weapon_type="melee", strength="6")
        melee_result = melee_strong._wound_target_with_tracking(
            covens_defender,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Stitchflesh Abominations" in m for m in list(melee_result.get("modifiers", []) or [])))

        equal_strength = _make_profile(name="Equal Gun", weapon_type="ranged", strength="4")
        equal_result = equal_strength._wound_target_with_tracking(
            covens_defender,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Stitchflesh Abominations" in m for m in list(equal_result.get("modifiers", []) or [])))

        non_covens_result = ranged_strong._wound_target_with_tracking(
            non_covens_defender,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Stitchflesh Abominations" in m for m in list(non_covens_result.get("modifiers", []) or [])))

    def test_stitchflesh_does_not_apply_outside_covenite_coterie(self):
        non_coterie_army = Army.with_detachment("Drukhari", "Realspace Raiders")
        non_coterie_army.faction_id = "DRU"
        enemy_army = Army.with_detachment("Enemy", "Other")
        enemy_army.faction_id = "EN"

        covens_defender = _make_unit(
            "Wracks",
            keywords=["DRUKHARI", "INFANTRY", "HAEMONCULUS COVENS"],
            faction_keywords=["DRUKHARI"],
            toughness="4",
        )
        attacker = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness="4",
        )
        non_coterie_army.add_unit(covens_defender)
        enemy_army.add_unit(attacker)
        attacker_model = attacker.models[0]

        ranged_strong = _make_profile(name="Strong Gun", weapon_type="ranged", strength="5")
        result = ranged_strong._wound_target_with_tracking(
            covens_defender,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Stitchflesh Abominations" in m for m in list(result.get("modifiers", []) or [])))


if __name__ == "__main__":
    unittest.main()
