import unittest
from unittest.mock import patch
from types import SimpleNamespace


class TestAuraMeleeAttacksBonus(unittest.TestCase):
    def test_melee_attacks_aura_parses_and_applies_once(self):
        from warhammer40k_ai.utility.aura_effects import get_aura_melee_attacks_bonus
        from warhammer40k_ai.units.ability import Ability
        from warhammer40k_ai.units.wargear import Wargear

        aura = Ability(
            name="Rage Embodied (Aura)",
            faction_id="",
            description='While a friendly KHORNE LEGIONES DAEMONICA unit is within 6" of this model, add 1 to the Attacks characteristic of melee weapons equipped by models in that unit.',
            type="Datasheet",
            parameter="",
            legend=None,
        )

        class _Unit:
            def __init__(self, *, abilities=None, is_khorne=False):
                self.possible_abilities = list(abilities or [])
                self._army = None
                self._is_khorne = is_khorne

            def get_parent_army(self):
                return self._army

            def has_any_keyword(self, kw: str) -> bool:
                return self._is_khorne and str(kw).strip().lower() == "khorne legiones daemonica"

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        attacker_unit = _Unit(abilities=[], is_khorne=True)
        source1 = _Unit(abilities=[aura], is_khorne=True)
        source2 = _Unit(abilities=[aura], is_khorne=True)  # same aura name; should not stack

        game_map = _Map([attacker_unit, source1, source2])
        game = SimpleNamespace(map=game_map)
        player = SimpleNamespace(game=game, name="P1", id="P1")
        army = SimpleNamespace(player=player)
        attacker_unit._army = army
        source1._army = army
        source2._army = army

        parent = Wargear({"name": "Test Weapon", "type": "Melee", "range": "Melee", "A": "1", "BS_WS": "3", "S": "4", "AP": "0", "D": "1", "description": ""})
        profile = parent.profiles["default"]

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            bonus, reasons = get_aura_melee_attacks_bonus(attacker_unit, profile, game_map=game_map)

        self.assertEqual(int(bonus), 1)
        self.assertEqual(len(reasons), 1)


if __name__ == "__main__":
    unittest.main()

