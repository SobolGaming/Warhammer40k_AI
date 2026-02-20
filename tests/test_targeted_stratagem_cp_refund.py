import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
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
        self.transport = ""


def _make_unit(name, *, abilities=None, keywords=None, faction_keywords=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities, keywords=keywords, faction_keywords=faction_keywords)
    return Unit(datasheet)


class TestTargetedStratagemCpRefund(unittest.TestCase):
    def _make_player(self, unit, *, extra_units=None):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army("Test", "Test")
        all_units = [unit]
        all_units.extend(list(extra_units or []))
        army.units = all_units
        for u in all_units:
            u.set_parent_army(army)
        player = Player("P1", control=PlayerControl.LOCAL, army=army)
        player.set_game(SimpleNamespace(turn=1))
        return player

    def test_parses_targeted_stratagem_cp_refund(self):
        ability = {
            "name": "Broad Spectrum Data-tether",
            "description": "Each time you target this unit with a Stratagem, roll one D6: on a 5+, you gain 1CP.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Ballistarii", abilities=[ability])
        specs = list(unit.special_rules.get("stratagem_target_cp_refund_specs", []) or [])
        self.assertTrue(specs)
        self.assertEqual(int(specs[0].get("roll_min", 0) or 0), 5)
        self.assertEqual(int(specs[0].get("cp_gain", 0) or 0), 1)

    def test_refund_applies_after_stratagem_targeting(self):
        ability = {
            "name": "Broad Spectrum Data-tether",
            "description": "Each time you target this unit with a Stratagem, roll one D6: on a 5+, you gain 1CP.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Ballistarii", abilities=[ability])
        player = self._make_player(unit)

        player.command_points = 2
        player._pending_stratagem_target_unit_id = str(get_entity_id(unit) or "")
        player._pending_stratagem_name = "Rapid Fire"

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=6):
            ok = bool(player.spend_command_points(1, reason="Stratagem: Rapid Fire", source="stratagem"))

        self.assertTrue(ok)
        self.assertEqual(int(player.command_points or 0), 2)

    def test_parses_select_target_variant(self):
        ability = {
            "name": "Command Uplink",
            "description": "Each time you select the bearer's unit as the target of a Stratagem, roll one D6: on a 5+, you gain 1CP.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Archaeopter", abilities=[ability])
        specs = list(unit.special_rules.get("stratagem_target_cp_refund_specs", []) or [])
        self.assertTrue(specs)
        self.assertEqual(int(specs[0].get("roll_min", 0) or 0), 5)
        self.assertEqual(int(specs[0].get("cp_gain", 0) or 0), 1)

    def test_bearer_loses_smoke_and_still_gets_refund_rule(self):
        ability = {
            "name": "Broad spectrum data-tether",
            "description": (
                "The bearer loses the SMOKE keyword, but each time you target the bearer with a Stratagem, "
                "roll one D6: on a 5+, you gain 1CP."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Onager Dunecrawler", abilities=[ability], keywords=["Smoke"])
        specs = list(unit.special_rules.get("stratagem_target_cp_refund_specs", []) or [])

        self.assertFalse(unit.has_keyword("SMOKE"))
        self.assertTrue(specs)
        self.assertEqual(int(specs[0].get("roll_min", 0) or 0), 5)
        self.assertEqual(int(specs[0].get("cp_gain", 0) or 0), 1)

    def test_parses_vox_caster_officer_bonus_refund(self):
        ability = {
            "name": "Vox-caster",
            "description": (
                "Each time you target the bearer's unit with a Stratagem, roll one D6, adding 1 to the result if "
                "there are one or more friendly Officer models within 6\": on a 5+, you gain 1CP."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Infantry Squad", abilities=[ability])
        specs = list(unit.special_rules.get("stratagem_target_cp_refund_specs", []) or [])

        self.assertTrue(specs)
        self.assertEqual(int(specs[0].get("roll_min", 0) or 0), 5)
        self.assertEqual(int(specs[0].get("cp_gain", 0) or 0), 1)
        self.assertEqual(int(specs[0].get("roll_bonus", 0) or 0), 1)
        self.assertEqual(str(specs[0].get("roll_bonus_keyword", "") or "").upper(), "OFFICER")
        self.assertEqual(int(specs[0].get("roll_bonus_range", 0) or 0), 6)

    def test_vox_caster_bonus_applies_when_officer_within_6(self):
        ability = {
            "name": "Vox-caster",
            "description": (
                "Each time you target the bearer's unit with a Stratagem, roll one D6, adding 1 to the result if "
                "there are one or more friendly Officer models within 6\": on a 5+, you gain 1CP."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Infantry Squad", abilities=[ability])
        officer_unit = _make_unit("Command Squad", keywords=["Officer"])
        unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        officer_unit.models[0].set_location(5.0, 0.0, 0.0, 0.0)
        player = self._make_player(unit, extra_units=[officer_unit])

        player.command_points = 2
        player._pending_stratagem_target_unit_id = str(get_entity_id(unit) or "")
        player._pending_stratagem_name = "Rapid Fire"

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
            ok = bool(player.spend_command_points(1, reason="Stratagem: Rapid Fire", source="stratagem"))

        self.assertTrue(ok)
        self.assertEqual(int(player.command_points or 0), 2)

    def test_vox_caster_bonus_not_applied_when_officer_outside_6(self):
        ability = {
            "name": "Vox-caster",
            "description": (
                "Each time you target the bearer's unit with a Stratagem, roll one D6, adding 1 to the result if "
                "there are one or more friendly Officer models within 6\": on a 5+, you gain 1CP."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Infantry Squad", abilities=[ability])
        officer_unit = _make_unit("Command Squad", keywords=["Officer"])
        unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        officer_unit.models[0].set_location(24.0, 0.0, 0.0, 0.0)
        player = self._make_player(unit, extra_units=[officer_unit])

        player.command_points = 2
        player._pending_stratagem_target_unit_id = str(get_entity_id(unit) or "")
        player._pending_stratagem_name = "Rapid Fire"

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
            ok = bool(player.spend_command_points(1, reason="Stratagem: Rapid Fire", source="stratagem"))

        self.assertTrue(ok)
        self.assertEqual(int(player.command_points or 0), 1)


if __name__ == "__main__":
    unittest.main()
