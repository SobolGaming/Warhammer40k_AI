import unittest
from types import SimpleNamespace

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(self, name, *, abilities=None):
        self.name = name
        self.faction_data = {"name": "Imperial Knights"}
        self.keywords = ["VEHICLE", "ARMIGER"]
        self.faction_keywords = ["IMPERIAL KNIGHTS"]
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 140}]
        self.datasheets_models = [
            {
                "M": "12",
                "T": "10",
                "Sv": "3",
                "W": "12",
                "Ld": "7",
                "OC": "8",
                "base_size": "100mm",
                "inv_sv": "5",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, abilities=None):
    datasheet = _MockDatasheet(name, abilities=abilities)
    return Unit(datasheet)


def _impetuous_glory_ability():
    return {
        "name": "Impetuous Glory",
        "description": (
            "Each time this model makes a Charge move, until the end of the turn, add 1 to the Attacks "
            "characteristic of this model's reaper chain-cleaver - strike profile, and add 2 to the Attacks "
            "characteristic of this model's reaper chain-cleaver - sweep profile."
        ),
        "type": "Datasheet",
        "parameter": "",
    }


class TestImpetuousGlory(unittest.TestCase):
    def _build_chain_cleaver(self):
        chain_cleaver = Wargear(
            {
                "name": "reaper chain-cleaver - strike",
                "type": "Melee",
                "range": "Melee",
                "A": "4",
                "BS_WS": "3+",
                "S": "12",
                "AP": "-3",
                "D": "D6+1",
                "description": "",
            }
        )
        chain_cleaver.add_profile(
            "sweep",
            {
                "name": "reaper chain-cleaver - sweep",
                "type": "Melee",
                "range": "Melee",
                "A": "8",
                "BS_WS": "3+",
                "S": "6",
                "AP": "-2",
                "D": "2",
                "description": "",
            },
        )
        return chain_cleaver

    def test_impetuous_glory_applies_profile_specific_attacks_bonuses(self):
        unit = _make_unit("Armiger Warglaive", abilities=[_impetuous_glory_ability()])
        attacker = unit.models[0]
        attacker.set_location(0.0, 0.0, 0.0, 0.0)

        target = _make_unit("Target")
        target.models[0].set_location(1.0, 0.0, 0.0, 0.0)

        chain_cleaver = self._build_chain_cleaver()
        strike = chain_cleaver.profiles["strike"]
        sweep = chain_cleaver.profiles["sweep"]

        applied = unit._apply_charge_move_model_weapon_profile_attacks_bonuses()
        self.assertTrue(applied)

        strike_info = strike.preview_attack_count(target, attacker, publish_roll_event=False)
        sweep_info = sweep.preview_attack_count(target, attacker, publish_roll_event=False)

        self.assertEqual(int(strike_info.num_attacks), 5)
        self.assertEqual(int(sweep_info.num_attacks), 10)

    def test_impetuous_glory_expires_at_end_of_fight_phase(self):
        unit = _make_unit("Armiger Warglaive", abilities=[_impetuous_glory_ability()])
        model = unit.models[0]

        applied = unit._apply_charge_move_model_weapon_profile_attacks_bonuses()
        self.assertTrue(applied)
        self.assertEqual(model.get_temporary_weapon_attacks_bonus("reaper chain-cleaver - strike")[0], 1)
        self.assertEqual(model.get_temporary_weapon_attacks_bonus("reaper chain-cleaver - sweep")[0], 2)

        model.on_phase_end(SimpleNamespace(name="FIGHT_PHASE"))
        self.assertEqual(model.get_temporary_weapon_attacks_bonus("reaper chain-cleaver - strike")[0], 0)
        self.assertEqual(model.get_temporary_weapon_attacks_bonus("reaper chain-cleaver - sweep")[0], 0)


if __name__ == "__main__":
    unittest.main()
