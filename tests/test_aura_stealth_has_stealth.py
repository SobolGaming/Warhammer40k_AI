import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(self, name: str, *, keywords=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [{
            "M": "6",
            "T": "4",
            "Sv": "3",
            "W": "2",
            "Ld": "7",
            "OC": "1",
            "base_size": "32mm",
            "inv_sv": "7",
            "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name: str, *, keywords=None, abilities=None):
    unit = Unit(MockDatasheet(name, keywords=keywords))
    unit.deployed = True
    for ab in list(abilities or []):
        unit.possible_abilities.append(ab)
    return unit


class TestAuraStealthHasStealth(unittest.TestCase):
    def test_stealth_aura_grants_stealth(self):
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE))
        p1 = Player("P1", PlayerControl.LOCAL, Army("Army A", "Detachment A"))
        game.add_player(p1)

        aura = Ability(
            name="Prince of Darkness (Aura)",
            faction_id="",
            description=(
                'While a friendly Legiones Daemonica unit is within 6" of this model, '
                "models in that unit have the Stealth ability."
            ),
            type="Datasheet",
            parameter="",
        )

        source = _make_unit("Source", keywords=["Legiones Daemonica"], abilities=[aura])
        target = _make_unit("Target", keywords=["Legiones Daemonica"])

        p1.army.add_unit(source)
        p1.army.add_unit(target)
        game.map.units = [source, target]

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            self.assertTrue(target.has_stealth())


if __name__ == "__main__":
    unittest.main()
