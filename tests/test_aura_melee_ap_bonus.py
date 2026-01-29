import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestAuraMeleeApBonus(unittest.TestCase):
    def test_melee_ap_aura_applies_in_get_effective_ap(self):
        from warhammer40k_ai.units.ability import Ability
        from warhammer40k_ai.units.wargear import Wargear

        aura = Ability(
            name="Cruel Fervor (Aura)",
            faction_id="",
            description='While a friendly LEGIONS OF EXCESS unit is within 6" of this model, improve the Armour Penetration characteristic of melee weapons equipped by models in that unit by 1.',
            type="Datasheet",
            parameter="",
            legend=None,
        )

        class _Unit:
            def __init__(self, *, abilities=None, keywords=None, charged=False):
                self.possible_abilities = list(abilities or [])
                self._army = None
                self._keywords = {str(k).strip().lower() for k in (keywords or [])}
                self.round_state = SimpleNamespace(charged_this_round=charged)

            def get_parent_army(self):
                return self._army

            def has_any_keyword(self, kw: str) -> bool:
                return str(kw).strip().lower() in self._keywords

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        attacker_unit = _Unit(keywords=["LEGIONS OF EXCESS"])
        source = _Unit(abilities=[aura], keywords=["LEGIONS OF EXCESS"])
        game_map = _Map([attacker_unit, source])
        game = SimpleNamespace(map=game_map)
        player = SimpleNamespace(game=game, name="P1", id="P1")
        army = SimpleNamespace(player=player)
        attacker_unit._army = army
        source._army = army

        parent = Wargear(
            {
                "name": "Test Blade",
                "type": "Melee",
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = parent.profiles["default"]
        attacker_model = SimpleNamespace(parent_unit=attacker_unit)
        target_unit = SimpleNamespace()

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            ap_val = profile.get_effective_ap(attacker_model, target_unit)

        self.assertEqual(ap_val, -1)

    def test_melee_ap_aura_requires_charge(self):
        from warhammer40k_ai.utility.aura_effects import get_aura_melee_ap_bonus
        from warhammer40k_ai.units.ability import Ability
        from warhammer40k_ai.units.wargear import Wargear

        aura = Ability(
            name="Hypnotic Lunge (Aura)",
            faction_id="",
            description='While a friendly SLAANESH unit is within 6" of this model, if that unit made a Charge move this turn, improve the Armour Penetration characteristic of melee weapons equipped by models in that unit by 1.',
            type="Datasheet",
            parameter="",
            legend=None,
        )

        class _Unit:
            def __init__(self, *, abilities=None, keywords=None, charged=False):
                self.possible_abilities = list(abilities or [])
                self._army = None
                self._keywords = {str(k).strip().lower() for k in (keywords or [])}
                self.round_state = SimpleNamespace(charged_this_round=charged)

            def get_parent_army(self):
                return self._army

            def has_any_keyword(self, kw: str) -> bool:
                return str(kw).strip().lower() in self._keywords

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        attacker_unit = _Unit(keywords=["SLAANESH"], charged=False)
        source = _Unit(abilities=[aura], keywords=["SLAANESH"])
        game_map = _Map([attacker_unit, source])
        game = SimpleNamespace(map=game_map)
        player = SimpleNamespace(game=game, name="P1", id="P1")
        army = SimpleNamespace(player=player)
        attacker_unit._army = army
        source._army = army

        parent = Wargear(
            {
                "name": "Test Blade",
                "type": "Melee",
                "range": "Melee",
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
            bonus, _ = get_aura_melee_ap_bonus(attacker_unit, profile, game_map=game_map)
        self.assertEqual(int(bonus), 0)

        attacker_unit.round_state.charged_this_round = True
        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            bonus, _ = get_aura_melee_ap_bonus(attacker_unit, profile, game_map=game_map)
        self.assertEqual(int(bonus), 1)

    def test_melee_ap_aura_parses_short_phrase(self):
        from warhammer40k_ai.utility.aura_effects import get_aura_melee_ap_bonus
        from warhammer40k_ai.units.ability import Ability
        from warhammer40k_ai.units.wargear import Wargear

        aura = Ability(
            name="Lethal Exuberance (Aura)",
            faction_id="",
            description='While a friendly SLAANESH unit is within 6" of this model, improve the Armour Penetration of melee weapons in that unit by 1.',
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

        attacker_unit = _Unit(keywords=["SLAANESH"])
        source = _Unit(abilities=[aura], keywords=["SLAANESH"])
        game_map = _Map([attacker_unit, source])
        game = SimpleNamespace(map=game_map)
        player = SimpleNamespace(game=game, name="P1", id="P1")
        army = SimpleNamespace(player=player)
        attacker_unit._army = army
        source._army = army

        parent = Wargear(
            {
                "name": "Test Blade",
                "type": "Melee",
                "range": "Melee",
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
            bonus, _ = get_aura_melee_ap_bonus(attacker_unit, profile, game_map=game_map)
        self.assertEqual(int(bonus), 1)


if __name__ == "__main__":
    unittest.main()
