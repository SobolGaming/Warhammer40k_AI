import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "3",
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


def _make_unit(name, *, abilities=None, keywords=None):
    return Unit(_MockDatasheet(name, abilities=abilities, keywords=keywords))


class TestChaosDaemonsPsychicAuras(unittest.TestCase):
    def _make_game(self, attacker_unit, defender_unit):
        attacker_army = Army("Attacker", detachment_type="Other")
        attacker_army.faction_id = "ATK"
        defender_army = Army("Defender", detachment_type="Other")
        defender_army.faction_id = "DEF"
        attacker = Player("Attacker", PlayerControl.REMOTE, army=attacker_army)
        defender = Player("Defender", PlayerControl.REMOTE, army=defender_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[attacker, defender])
        attacker_army.add_unit(attacker_unit)
        defender_army.add_unit(defender_unit)
        game.map.units = [attacker_unit, defender_unit]
        return game

    def test_discordant_disruption_makes_psychic_hazardous(self):
        ability = {
            "name": "Discordant Disruption (Aura)",
            "description": (
                'While an enemy PSYKER unit is within 12" of this model, Psychic weapons equipped by models in that '
                'unit have the [HAZARDOUS] ability.'
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        source_unit = _make_unit("Infernal Enrapturess", abilities=[ability])
        attacker_unit = _make_unit("Psyker", keywords=["PSYKER"])

        game = self._make_game(attacker_unit, source_unit)

        # Keep models within 12" (same point).
        attacker_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        source_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)

        parent = SimpleNamespace(name="Psychic Blade", is_melee=lambda: True, is_ranged=lambda: False)
        profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "psychic",
            },
            parent_wargear=parent,
        )

        with patch("warhammer40k_ai.units.wargear.get_roll", lambda _expr: 1):
            result = profile.attack(source_unit, attacker_unit.models[0], game_map=game.map)

        self.assertIsNotNone(result)
        self.assertEqual(result.hazardous_roll, 1)
        self.assertEqual(result.hazardous_damage, 3)

    def test_ptarix_sorcerous_syphon_wound_penalty(self):
        ability = {
            "name": "P\u2019tarix\u2019s Sorcerous Syphon (Aura)",
            "description": (
                'While an enemy unit is within 12" of this model, each time a model in that unit makes a '
                "Psychic Attack, subtract 1 from the Wound roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        source_unit = _make_unit("The Blue Scribes", abilities=[ability])
        attacker_unit = _make_unit("Attacker")

        game = self._make_game(attacker_unit, source_unit)

        attacker_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        source_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)

        parent = SimpleNamespace(name="Psychic Bolt", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "psychic",
            },
            parent_wargear=parent,
        )

        wound = profile._wound_target_with_tracking(
            source_unit,
            attacker_unit.models[0],
            {},
            roll_value=4,
        )

        self.assertIn("-1 to wound from Aura: P\u2019tarix\u2019s Sorcerous Syphon (Aura)", wound.get("modifiers", []))
        self.assertEqual(wound.get("needed"), 4)
        self.assertEqual(wound.get("final_needed"), 5)


if __name__ == "__main__":
    unittest.main()
