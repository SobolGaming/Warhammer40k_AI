import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(self, name, *, abilities=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
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


def _make_unit(name, *, abilities=None, enhancement=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities)
    return Unit(datasheet, enhancement=enhancement)


class TestOpponentCpGainReactions(unittest.TestCase):
    def _make_players(self, reaction_unit, enemy_unit):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army1 = Army("Army1", "Detachment1")
        army2 = Army("Army2", "Detachment2")
        army1.units = [reaction_unit]
        army2.units = [enemy_unit]
        reaction_unit.set_parent_army(army1)
        enemy_unit.set_parent_army(army2)

        player1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
        player2 = Player("P2", control=PlayerControl.LOCAL, army=army2)
        game = SimpleNamespace(turn=1, players=[player1, player2], event_system=None)
        player1.game = game
        player2.game = game
        return player1, player2

    def test_parses_opponent_cp_gain_reaction_from_datasheet_ability(self):
        ability = {
            "name": "Spy Network",
            "description": "Each time your opponent gains a CP as the result of an ability, roll one D6: on a 2+, you also gain 1CP.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Inquisitor Coteaz", abilities=[ability])

        specs = list(unit.special_rules.get("opponent_ability_cp_gain_reaction_specs", []) or [])
        self.assertTrue(specs)
        self.assertEqual(int(specs[0].get("roll_min", 0) or 0), 2)
        self.assertEqual(int(specs[0].get("cp_gain", 0) or 0), 1)

    def test_parses_opponent_cp_gain_reaction_from_enhancement_text(self):
        enhancement = SimpleNamespace(
            name="Autodivinator",
            description=(
                "CRYPTEK model only. Each time your opponent gains a CP as the result of an ability, "
                "roll one D6: on a 2+, you also gain 1CP."
            ),
        )
        unit = _make_unit("Technomancer", enhancement=enhancement)

        specs = list(unit.special_rules.get("opponent_ability_cp_gain_reaction_specs", []) or [])
        self.assertTrue(specs)
        self.assertEqual(int(specs[0].get("roll_min", 0) or 0), 2)
        self.assertEqual(int(specs[0].get("cp_gain", 0) or 0), 1)
        self.assertTrue(str(specs[0].get("source_model_id", "") or "").strip())

    def test_reacts_when_opponent_gains_cp_from_ability(self):
        ability = {
            "name": "Spy Network",
            "description": "Each time your opponent gains a CP as the result of an ability, roll one D6: on a 2+, you also gain 1CP.",
            "type": "Datasheet",
            "parameter": "",
        }
        reaction_unit = _make_unit("Inquisitor Coteaz", abilities=[ability])
        enemy_unit = _make_unit("Enemy Unit")
        player1, player2 = self._make_players(reaction_unit, enemy_unit)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=6):
            gained = int(player2.gain_command_points(1, reason="Enemy Ability", source="ability") or 0)

        self.assertEqual(gained, 1)
        self.assertEqual(int(player2.command_points or 0), 1)
        self.assertEqual(int(player1.command_points or 0), 1)

    def test_does_not_react_to_normal_command_phase_cp(self):
        ability = {
            "name": "Spy Network",
            "description": "Each time your opponent gains a CP as the result of an ability, roll one D6: on a 2+, you also gain 1CP.",
            "type": "Datasheet",
            "parameter": "",
        }
        reaction_unit = _make_unit("Inquisitor Coteaz", abilities=[ability])
        enemy_unit = _make_unit("Enemy Unit")
        player1, player2 = self._make_players(reaction_unit, enemy_unit)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=6) as patched_roll:
            gained = int(
                player2.gain_command_points(
                    1,
                    is_normal_command_phase_gain=True,
                    reason="Normal Command phase CP",
                )
                or 0
            )

        self.assertEqual(gained, 1)
        self.assertEqual(int(player2.command_points or 0), 1)
        self.assertEqual(int(player1.command_points or 0), 0)
        patched_roll.assert_not_called()

    def test_chain_stops_with_guardrail_when_both_players_have_reaction(self):
        ability = {
            "name": "Spy Network",
            "description": "Each time your opponent gains a CP as the result of an ability, roll one D6: on a 2+, you also gain 1CP.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit1 = _make_unit("Inquisitor Coteaz", abilities=[ability])
        unit2 = _make_unit("Inquisitor Coteaz", abilities=[ability])
        player1, player2 = self._make_players(unit1, unit2)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=6):
            gained = int(player2.gain_command_points(1, reason="Enemy Ability", source="ability") or 0)

        self.assertEqual(gained, 1)
        self.assertEqual(int(player1.command_points or 0), 1)
        self.assertEqual(int(player2.command_points or 0), 1)


if __name__ == "__main__":
    unittest.main()
