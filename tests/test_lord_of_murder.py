import unittest
from unittest.mock import patch
from types import SimpleNamespace


class TestLordOfMurder(unittest.TestCase):
    def test_grants_lone_operative_within_3_of_friendly_world_eaters_infantry(self):
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.units.ability import Ability

        lom = Ability(
            name="Lord of Murder",
            faction_id="",
            description='While this model is within 3" of one or more friendly WORLD EATERS INFANTRY units, this model has the Lone Operative ability.',
            type="Datasheet",
            parameter="",
            legend=None,
        )

        class _U:
            def __init__(self, *, abilities=None, we=False, inf=False):
                self.possible_abilities = list(abilities or [])
                self._ability_cache = {}
                self._army = None
                self._we = we
                self._inf = inf

            def get_parent_army(self):
                return self._army

            def is_alive(self):
                return True

            def has_any_keyword(self, k: str) -> bool:
                return self._we and str(k).strip().lower() == "world eaters"

            def has_keyword(self, k: str) -> bool:
                return self._inf and str(k).strip().lower() == "infantry"

            def _find_ability_with_patterns(self, _patterns, *_a, **_k):
                # No base Lone Operative; only from Lord of Murder
                return False, None

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        # Unit with Lord of Murder
        u = _U(abilities=[lom], we=True, inf=False)
        # Nearby friendly WORLD EATERS INFANTRY
        friend = _U(abilities=[], we=True, inf=True)

        game_map = _Map([u, friend])
        game = SimpleNamespace(map=game_map)
        player = SimpleNamespace(game=game)
        army = SimpleNamespace(player=player)
        u._army = army
        friend._army = army

        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            res = Unit.has_lone_operative(u)
        self.assertTrue(res)

    def test_does_not_grant_lone_operative_when_no_friendly_infantry_in_range(self):
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.units.ability import Ability

        lom = Ability(
            name="Lord of Murder",
            faction_id="",
            description='While this model is within 3" of one or more friendly WORLD EATERS INFANTRY units, this model has the Lone Operative ability.',
            type="Datasheet",
            parameter="",
            legend=None,
        )

        class _U:
            def __init__(self, *, abilities=None):
                self.possible_abilities = list(abilities or [])
                self._ability_cache = {}
                self._army = None

            def get_parent_army(self):
                return self._army

            def is_alive(self):
                return True

            def has_any_keyword(self, _k: str) -> bool:
                return False

            def has_keyword(self, _k: str) -> bool:
                return False

            def _find_ability_with_patterns(self, _patterns, *_a, **_k):
                return False, None

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        u = _U(abilities=[lom])
        friend = _U(abilities=[])
        game_map = _Map([u, friend])
        game = SimpleNamespace(map=game_map)
        player = SimpleNamespace(game=game)
        army = SimpleNamespace(player=player)
        u._army = army
        friend._army = army

        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=False):
            res = Unit.has_lone_operative(u)
        self.assertFalse(res)


if __name__ == "__main__":
    unittest.main()


