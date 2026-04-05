import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestAuraToughnessAndStrengthBonus(unittest.TestCase):
    def test_toughness_aura_bonus_applies_once(self):
        from warhammer40k_ai.utility.aura_effects import get_aura_toughness_bonus
        from warhammer40k_ai.units.ability import Ability

        aura = Ability(
            name="Rotting Presence (Aura)",
            faction_id="",
            description='While a friendly NURGLE LEGIONES DAEMONICA unit is within 6" of this model, add 1 to the Toughness characteristic of models in that unit.',
            type="Datasheet",
            parameter="",
            legend=None,
        )

        class _Unit:
            def __init__(self, *, abilities=None, keywords=None):
                self.possible_abilities = list(abilities or [])
                self._army = None
                self._keywords = {str(k).strip().lower() for k in (keywords or [])}

            def get_parent_army(self):
                return self._army

            def has_any_keyword(self, kw: str) -> bool:
                return str(kw).strip().lower() in self._keywords

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        receiver = _Unit(keywords=["NURGLE LEGIONES DAEMONICA"])
        source1 = _Unit(abilities=[aura], keywords=["NURGLE LEGIONES DAEMONICA"])
        source2 = _Unit(abilities=[aura], keywords=["NURGLE LEGIONES DAEMONICA"])

        game_map = _Map([receiver, source1, source2])
        game = SimpleNamespace(map=game_map)
        player = SimpleNamespace(game=game, name="P1", id="P1")
        army = SimpleNamespace(player=player)
        receiver._army = army
        source1._army = army
        source2._army = army

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            bonus, reasons = get_aura_toughness_bonus(receiver, game_map=game_map)

        self.assertEqual(int(bonus), 1)
        self.assertEqual(len(reasons), 1)

    def test_strength_aura_bonus_applies_on_ranged_attack_phrase(self):
        from warhammer40k_ai.utility.aura_effects import get_aura_strength_bonus
        from warhammer40k_ai.units.ability import Ability
        from warhammer40k_ai.units.wargear import Wargear

        aura = Ability(
            name="Warpfire Guidance (Aura)",
            faction_id="",
            description='While a friendly TZEENTCH LEGIONES DAEMONICA unit is within 6" of this model, each time a model in that unit makes a ranged attack, add 1 to the Strength characteristic of that attack.',
            type="Datasheet",
            parameter="",
            legend=None,
        )

        class _Unit:
            def __init__(self, *, abilities=None, keywords=None):
                self.possible_abilities = list(abilities or [])
                self._army = None
                self._keywords = {str(k).strip().lower() for k in (keywords or [])}

            def get_parent_army(self):
                return self._army

            def has_any_keyword(self, kw: str) -> bool:
                return str(kw).strip().lower() in self._keywords

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        receiver = _Unit(keywords=["TZEENTCH LEGIONES DAEMONICA"])
        source = _Unit(abilities=[aura], keywords=["TZEENTCH LEGIONES DAEMONICA"])

        game_map = _Map([receiver, source])
        game = SimpleNamespace(map=game_map)
        player = SimpleNamespace(game=game, name="P1", id="P1")
        army = SimpleNamespace(player=player)
        receiver._army = army
        source._army = army

        parent = Wargear(
            {
                "name": "Test Gun",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = parent.profiles["default"]

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            bonus, reasons = get_aura_strength_bonus(receiver, profile, game_map=game_map)

        self.assertEqual(int(bonus), 1)
        self.assertTrue(any("Warpfire Guidance" in r for r in reasons))


if __name__ == "__main__":
    unittest.main()
