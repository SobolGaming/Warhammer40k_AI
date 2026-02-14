import unittest
from unittest.mock import patch
from types import SimpleNamespace


class TestAuraExtendedShapes(unittest.TestCase):
    def _make_profile(self, *, melee: bool, strength: int = 4):
        from warhammer40k_ai.units.wargear import Wargear

        data = {
            "range": "Melee" if melee else "24",
            "A": "1",
            "BS_WS": "3",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        }
        parent = Wargear({"name": "Test Weapon", "type": "Melee" if melee else "Ranged", **data})
        return parent.profiles["default"]

    def test_reroll_hit_rolls_of_one_aura(self):
        from warhammer40k_ai.units.ability import Ability

        profile = self._make_profile(melee=True)

        aura = Ability(
            name="Test Reroll Hits (Aura)",
            faction_id="",
            description='While a friendly WORLD EATERS unit is within 6" of this unit, you can re-roll Hit rolls of 1.',
            type="Datasheet",
            parameter="",
            legend=None,
        )

        class _Unit:
            def __init__(self, *, abilities=None):
                self.possible_abilities = list(abilities or [])
                self.round_state = SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False)
                self._army = None

            def get_parent_army(self):
                return self._army

            def has_any_keyword(self, kw: str) -> bool:
                return str(kw).strip().lower() == "world eaters"

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        attacker_unit = _Unit(abilities=[])
        aura_source = _Unit(abilities=[aura])
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda _k: False,
            has_stealth=lambda: False,
        )

        game_map = _Map([attacker_unit, aura_source])
        game = SimpleNamespace(map=game_map, event_system=SimpleNamespace(publish=lambda *_a, **_k: None), turn=1)
        player = SimpleNamespace(game=game, name="P1", id="P1")
        army = SimpleNamespace(player=player)
        attacker_unit._army = army
        aura_source._army = army

        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)

        # Hit roll 1, then reroll into 4 => should resolve as a hit (need 3+)
        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[1, 4]):
                res = profile._hit_target_with_tracking(target, attacker_model, {})

        self.assertTrue(res["hit"])
        self.assertEqual(res["roll"], 4)
        self.assertIn("Aura: re-roll Hit rolls of 1", res["special_effects"])

    def test_enhancement_aura_reroll_hit_and_wound_ones_excludes_titanic(self):
        from warhammer40k_ai.rules.enhancement import Enhancement

        profile = self._make_profile(melee=True)

        enhancement = Enhancement(
            id="dread",
            name="Dread Majesty (Aura)",
            faction_id="NEC",
            detachment="Starshatter Arsenal",
            description=(
                "Overlord or Catacomb Command Barge model only. While a friendly NECRONS unit "
                "(excluding Titanic units) is within 6\" of the bearer, each time a model in that unit "
                "makes an attack, re-roll a Hit roll of 1 and re-roll a Wound roll of 1."
            ),
        )

        class _Unit:
            def __init__(self, *, keywords=None, enhancement=None):
                self.possible_abilities = []
                self.enhancement = enhancement
                self.round_state = SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False)
                self._army = None
                self._keywords = [str(k or "") for k in (keywords or [])]

            def get_parent_army(self):
                return self._army

            def has_any_keyword(self, kw: str) -> bool:
                key = str(kw or "").strip().lower()
                return key in [k.lower() for k in self._keywords]

            def has_keyword(self, kw: str) -> bool:
                return self.has_any_keyword(kw)

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        attacker_unit = _Unit(keywords=["NECRONS"])
        aura_source = _Unit(keywords=["NECRONS"], enhancement=enhancement)
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda _k: False,
            has_stealth=lambda: False,
        )

        game_map = _Map([attacker_unit, aura_source])
        game = SimpleNamespace(map=game_map, event_system=SimpleNamespace(publish=lambda *_a, **_k: None), turn=1)
        player = SimpleNamespace(game=game, name="P1", id="P1")
        army = SimpleNamespace(player=player)
        attacker_unit._army = army
        aura_source._army = army

        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[1, 4]):
                hit_res = profile._hit_target_with_tracking(target, attacker_model, {})
        self.assertTrue(hit_res["hit"])
        self.assertIn("Aura: re-roll Hit rolls of 1", hit_res["special_effects"])

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[1, 4]):
                wound_res = profile._wound_target_with_tracking(target, attacker_model, {})
        self.assertTrue(any("Aura: re-roll Wound rolls of 1" in s for s in wound_res.get("special_effects", [])))

        titanic_attacker = _Unit(keywords=["NECRONS", "TITANIC"])
        titanic_attacker._army = army
        titanic_model = SimpleNamespace(name="Titanic", parent_unit=titanic_attacker)
        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[1]):
                miss_res = profile._hit_target_with_tracking(target, titanic_model, {})
        self.assertNotIn("Aura: re-roll Hit rolls of 1", miss_res.get("special_effects", []))

    def test_objective_control_aura_bonus(self):
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.units.ability import Ability

        aura = Ability(
            name="OC Aura (Aura)",
            faction_id="",
            description='While a friendly ADEPTUS ASTARTES unit is within 6" of this model, add 1 to the Objective Control characteristic of models in that unit.',
            type="Datasheet",
            parameter="",
            legend=None,
        )

        class _Unit:
            def __init__(self, *, abilities=None, oc=2):
                self.possible_abilities = list(abilities or [])
                self.models = [SimpleNamespace(objective_control=oc)]
                self._army = None

            def get_parent_army(self):
                return self._army

            def has_any_keyword(self, kw: str) -> bool:
                return str(kw).strip().lower() == "adeptus astartes"

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        receiver = _Unit(abilities=[], oc=2)
        source = _Unit(abilities=[aura], oc=2)
        game_map = _Map([receiver, source])
        game = SimpleNamespace(map=game_map, event_system=SimpleNamespace(publish=lambda *_a, **_k: None), turn=1)
        player = SimpleNamespace(game=game, name="P1", id="P1")
        army = SimpleNamespace(player=player)
        receiver._army = army
        source._army = army

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            oc = Unit.objective_control.fget(receiver)
        self.assertEqual(int(oc), 3)

    def test_objective_control_aura_bonus_excludes_battleshocked_and_damned(self):
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.units.ability import Ability

        aura = Ability(
            name="Lord of Badab (Aura)",
            faction_id="",
            description=(
                'While a friendly Heretic Astartes Infantry unit (excluding Battle-shocked units and Damned units) '
                'is within 6" of this model, add 1 to the Objective Control characteristic of models in that unit.'
            ),
            type="Datasheet",
            parameter="",
            legend=None,
        )

        class _Unit:
            def __init__(self, *, abilities=None, oc=2, keywords=None, battle_shocked=False):
                self.possible_abilities = list(abilities or [])
                self.models = [SimpleNamespace(objective_control=oc)]
                self._army = None
                self._keywords = {str(k).strip().lower() for k in (keywords or []) if str(k).strip()}
                self._battle_shocked = bool(battle_shocked)

            def get_parent_army(self):
                return self._army

            def has_any_keyword(self, kw: str) -> bool:
                parts = [p for p in str(kw).strip().lower().split() if p]
                return all(p in self._keywords for p in parts)

            def has_keyword(self, kw: str) -> bool:
                return str(kw).strip().lower() in self._keywords

            def is_battle_shocked(self) -> bool:
                return self._battle_shocked

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        source = _Unit(abilities=[aura], oc=2, keywords=["heretic", "astartes", "infantry"])
        game_map = _Map([source])
        game = SimpleNamespace(map=game_map, event_system=SimpleNamespace(publish=lambda *_a, **_k: None), turn=1)
        player = SimpleNamespace(game=game, name="P1", id="P1")
        army = SimpleNamespace(player=player)
        source._army = army

        eligible = _Unit(abilities=[], oc=2, keywords=["heretic", "astartes", "infantry"])
        eligible._army = army
        battle_shocked = _Unit(abilities=[], oc=2, keywords=["heretic", "astartes", "infantry"], battle_shocked=True)
        battle_shocked._army = army
        damned = _Unit(abilities=[], oc=2, keywords=["heretic", "astartes", "infantry", "damned"])
        damned._army = army

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            self.assertEqual(int(Unit.objective_control.fget(eligible)), 3)
            self.assertEqual(int(Unit.objective_control.fget(battle_shocked)), 2)
            self.assertEqual(int(Unit.objective_control.fget(damned)), 2)

    def test_battleshock_aura_penalty_applies(self):
        from warhammer40k_ai.units.ability import Ability
        from warhammer40k_ai.utility.aura_effects import get_aura_battleshock_test_modifiers

        aura = Ability(
            name="Dread Aura (Aura)",
            faction_id="",
            description='While an enemy unit is within 6" of this model, each time that unit takes a Battle-shock test, subtract 1 from that test.',
            type="Datasheet",
            parameter="",
            legend=None,
        )

        class _Unit:
            def __init__(self, *, abilities=None):
                self.possible_abilities = list(abilities or [])

        class _Map:
            def __init__(self, enemies):
                self._enemies = list(enemies)

            def get_enemy_units(self, _unit):
                return list(self._enemies)

        receiver = _Unit()
        source = _Unit(abilities=[aura])
        game_map = _Map([source])

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            mods = get_aura_battleshock_test_modifiers(receiver, game_map=game_map)

        self.assertEqual(mods, [(-1, "Aura: Dread Aura (Aura)")])

    def test_same_oc_aura_name_does_not_double_apply_from_two_sources(self):
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.units.ability import Ability

        aura = Ability(
            name="OC Aura (Aura)",
            faction_id="",
            description='While a friendly ADEPTUS ASTARTES unit is within 6" of this model, add 1 to the Objective Control characteristic of models in that unit.',
            type="Datasheet",
            parameter="",
            legend=None,
        )

        class _Unit:
            def __init__(self, *, abilities=None, oc=2):
                self.possible_abilities = list(abilities or [])
                self.models = [SimpleNamespace(objective_control=oc)]
                self._army = None

            def get_parent_army(self):
                return self._army

            def has_any_keyword(self, kw: str) -> bool:
                return str(kw).strip().lower() == "adeptus astartes"

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        receiver = _Unit(abilities=[], oc=2)
        source1 = _Unit(abilities=[aura], oc=2)
        source2 = _Unit(abilities=[aura], oc=2)
        game_map = _Map([receiver, source1, source2])
        game = SimpleNamespace(map=game_map, event_system=SimpleNamespace(publish=lambda *_a, **_k: None), turn=1)
        player = SimpleNamespace(game=game, name="P1", id="P1")
        army = SimpleNamespace(player=player)
        receiver._army = army
        source1._army = army
        source2._army = army

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            oc = Unit.objective_control.fget(receiver)
        # Base 2 + 1 once (NOT +2)
        self.assertEqual(int(oc), 3)

    def test_nurgles_gift_debuff_reduces_target_toughness_for_wound(self):
        from warhammer40k_ai.units.ability import Ability

        profile = self._make_profile(melee=True, strength=4)

        aura = Ability(
            name="Nurgle's Gift (Aura)",
            faction_id="",
            description="While an enemy unit is within Contagion Range of this unit, subtract 1 from the Toughness characteristic of models in that unit.",
            type="Faction",
            parameter="",
            legend=None,
        )

        class _Unit:
            def __init__(self, *, abilities=None):
                self.possible_abilities = list(abilities or [])
                self.round_state = SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False)
                self._army = None

            def get_parent_army(self):
                return self._army

            def has_any_keyword(self, _kw: str) -> bool:
                return False

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        attacker_unit = _Unit(abilities=[])
        aura_source = _Unit(abilities=[aura])

        class _Target:
            toughness = 4
            models = [SimpleNamespace(is_alive=True)]

            def has_keyword(self, _k: str) -> bool:
                return False

        target = _Target()

        game_map = _Map([attacker_unit, aura_source])
        game = SimpleNamespace(map=game_map, event_system=SimpleNamespace(publish=lambda *_a, **_k: None), turn=1)
        player = SimpleNamespace(game=game, name="P1", id="P1")
        army = SimpleNamespace(player=player)
        attacker_unit._army = army
        aura_source._army = army

        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)

        # With BR1 Contagion Range=3". Apply -1T => T3 so S4 > T3 => needs 3+.
        # Roll 3 should wound only if debuff is applied.
        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            with patch("warhammer40k_ai.units.wargear.get_roll", return_value=3):
                res = profile._wound_target_with_tracking(target, attacker_model, {})

        self.assertTrue(res["wound"])
        self.assertEqual(int(res["target_toughness"]), 3)
        self.assertTrue(any("Nurgle" in m for m in (res.get("modifiers") or [])))

    def test_same_nurgles_gift_aura_name_does_not_stack_from_two_sources(self):
        from warhammer40k_ai.units.ability import Ability

        profile = self._make_profile(melee=True, strength=4)

        aura = Ability(
            name="Nurgle's Gift (Aura)",
            faction_id="",
            description="While an enemy unit is within Contagion Range of this unit, subtract 1 from the Toughness characteristic of models in that unit.",
            type="Faction",
            parameter="",
            legend=None,
        )

        class _Unit:
            def __init__(self, *, abilities=None):
                self.possible_abilities = list(abilities or [])
                self.round_state = SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False)
                self._army = None

            def get_parent_army(self):
                return self._army

            def has_any_keyword(self, _kw: str) -> bool:
                return False

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        attacker_unit = _Unit(abilities=[])
        aura_source1 = _Unit(abilities=[aura])
        aura_source2 = _Unit(abilities=[aura])

        class _Target:
            toughness = 4
            models = [SimpleNamespace(is_alive=True)]

            def has_keyword(self, _k: str) -> bool:
                return False

        target = _Target()

        game_map = _Map([attacker_unit, aura_source1, aura_source2])
        game = SimpleNamespace(map=game_map, event_system=SimpleNamespace(publish=lambda *_a, **_k: None), turn=1)
        player = SimpleNamespace(game=game, name="P1", id="P1")
        army = SimpleNamespace(player=player)
        attacker_unit._army = army
        aura_source1._army = army
        aura_source2._army = army

        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            with patch("warhammer40k_ai.units.wargear.get_roll", return_value=3):
                res = profile._wound_target_with_tracking(target, attacker_model, {})

        # Should be -1T once (4 -> 3), not 2 (4 -> 2)
        self.assertEqual(int(res["target_toughness"]), 3)


if __name__ == "__main__":
    unittest.main()
