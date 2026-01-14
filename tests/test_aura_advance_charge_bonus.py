import unittest
from unittest.mock import patch
from types import SimpleNamespace


class TestAuraAdvanceChargeBonus(unittest.TestCase):
    def test_advance_and_charge_aura_applies_once(self):
        from warhammer40k_ai.utility.aura_effects import get_aura_advance_charge_roll_modifiers
        from warhammer40k_ai.classes.ability import Ability

        aura = Ability(
            name="Swift Wind (Aura)",
            faction_id="",
            description='While a friendly AELDARI unit is within 6" of this model, add 1 to Advance and Charge rolls made for that unit.',
            type="Datasheet",
            parameter="",
            legend=None,
        )

        class _Unit:
            def __init__(self, *, abilities=None, is_aeldari=False):
                self.possible_abilities = list(abilities or [])
                self._army = None
                self._is_aeldari = is_aeldari

            def get_parent_army(self):
                return self._army

            def has_any_keyword(self, kw: str) -> bool:
                return self._is_aeldari and str(kw).strip().lower() == "aeldari"

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        receiver = _Unit(abilities=[], is_aeldari=True)
        source1 = _Unit(abilities=[aura], is_aeldari=True)
        source2 = _Unit(abilities=[aura], is_aeldari=True)  # same aura name; should not stack

        game_map = _Map([receiver, source1, source2])
        game = SimpleNamespace(map=game_map)
        player = SimpleNamespace(game=game)
        army = SimpleNamespace(player=player)
        receiver._army = army
        source1._army = army
        source2._army = army

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            advance_mods, charge_mods = get_aura_advance_charge_roll_modifiers(receiver, game_map=game_map)

        self.assertEqual(len(advance_mods), 1)
        self.assertEqual(len(charge_mods), 1)
        self.assertEqual(int(advance_mods[0][0]), 1)
        self.assertEqual(int(charge_mods[0][0]), 1)


if __name__ == "__main__":
    unittest.main()
