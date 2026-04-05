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

    def test_foul_spores_stealth_aura_excludes_monsters(self):
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE))
        p1 = Player("P1", PlayerControl.LOCAL, Army("Army A", "Detachment A"))
        game.add_player(p1)

        aura = Ability(
            name="Foul Spores (Aura)",
            faction_id="",
            description=(
                'While a friendly TYRANIDS unit is within 6" of this unit, each time a ranged attack targets that unit, '
                "models in that unit have the Benefit of Cover against that attack. In addition, while a friendly TYRANIDS "
                'unit (excluding Monsters) is within 6" of this unit, models in that unit have the Stealth ability.'
            ),
            type="Datasheet",
            parameter="",
        )

        source = _make_unit("Venomthropes", keywords=["TYRANIDS"], abilities=[aura])
        infantry_target = _make_unit("Termagants", keywords=["TYRANIDS", "INFANTRY"])
        monster_target = _make_unit("Carnifexes", keywords=["TYRANIDS", "MONSTER"])

        p1.army.add_unit(source)
        p1.army.add_unit(infantry_target)
        p1.army.add_unit(monster_target)
        game.map.units = [source, infantry_target, monster_target]

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            self.assertTrue(infantry_target.has_stealth())
            self.assertFalse(monster_target.has_stealth())

    def test_foul_spores_attached_hive_tyrant_tyrant_guard_unit_has_no_stealth(self):
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE))
        p1 = Player("P1", PlayerControl.LOCAL, Army("Army A", "Detachment A"))
        game.add_player(p1)

        aura = Ability(
            name="Foul Spores (Aura)",
            faction_id="",
            description=(
                'While a friendly TYRANIDS unit is within 6" of this unit, each time a ranged attack targets that unit, '
                "models in that unit have the Benefit of Cover against that attack. In addition, while a friendly TYRANIDS "
                'unit (excluding Monsters) is within 6" of this unit, models in that unit have the Stealth ability.'
            ),
            type="Datasheet",
            parameter="",
        )

        source = _make_unit("Venomthropes", keywords=["TYRANIDS"], abilities=[aura])
        bodyguard = _make_unit("Tyrant Guard", keywords=["TYRANIDS", "INFANTRY"])
        leader = _make_unit("Hive Tyrant", keywords=["TYRANIDS", "MONSTER", "CHARACTER"])
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard

        p1.army.add_unit(source)
        p1.army.add_unit(bodyguard)
        game.map.units = [source, bodyguard]

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            self.assertTrue(bodyguard.has_any_keyword("MONSTER"))
            self.assertFalse(bodyguard.has_stealth())


if __name__ == "__main__":
    unittest.main()
