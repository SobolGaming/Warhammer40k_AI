import unittest
from unittest.mock import patch
from types import SimpleNamespace


class TestBeaconsOfRageAura(unittest.TestCase):
    def _make_profile(self, *, melee: bool):
        from warhammer40k_ai.units.wargear import Wargear

        data = {
            "range": "Melee" if melee else "24",
            "A": "1",
            "BS_WS": "3",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
        parent = Wargear({"name": "Test Weapon", "type": "Melee" if melee else "Ranged", **data})
        return parent.profiles["default"]

    def _mk_stack(
        self,
        *,
        in_range: bool,
        attacker_is_world_eaters: bool = True,
        target_is_monster: bool = False,
        target_is_vehicle: bool = False,
        target_below_half: bool = False,
    ):
        from warhammer40k_ai.units.ability import Ability

        aura = Ability(
            name="Beacons of Rage (Aura)",
            faction_id="",
            description=(
                'While a friendly WORLD EATERS unit is within 6" of this unit, each time a model in that unit '
                "makes a melee attack that targets a unit (excluding MONSTERS and VEHICLES), add 1 to the Hit roll. "
                "If that attack targets a unit (excluding MONSTERS and VEHICLES) that is Below Half-strength, "
                "add 1 to the Wound roll as well."
            ),
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
                if not attacker_is_world_eaters:
                    return False
                return str(kw).strip().lower() == "world eaters"

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        attacker_unit = _Unit(abilities=[])
        aura_source = _Unit(abilities=[aura])

        # Target unit stub
        class _Target:
            toughness = 4
            is_monster = target_is_monster
            is_vehicle = target_is_vehicle
            models = [SimpleNamespace(is_alive=True)]

            def is_below_half_strength(self) -> bool:
                return bool(target_below_half)

            def has_keyword(self, k: str) -> bool:
                kk = str(k).strip().lower()
                if target_is_monster and kk == "monster":
                    return True
                if target_is_vehicle and kk == "vehicle":
                    return True
                return False

        target_unit = _Target()

        game_map = _Map([attacker_unit, aura_source])
        game = SimpleNamespace(map=game_map, event_system=SimpleNamespace(publish=lambda *_a, **_k: None))
        player = SimpleNamespace(game=game, name="P1", id="P1")
        army = SimpleNamespace(player=player)
        attacker_unit._army = army
        aura_source._army = army

        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)
        return attacker_model, attacker_unit, aura_source, target_unit, game_map

    def test_in_range_melee_applies_plus_one_to_hit(self):
        profile = self._make_profile(melee=True)
        attacker_model, attacker_unit, aura_source, target, _game_map = self._mk_stack(in_range=True)

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            # Roll 2: without aura (WS3+) would miss, with aura (+1) should hit (need 2+)
            with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
                res = profile._hit_target_with_tracking(target, attacker_model, {})

        self.assertTrue(res["hit"])
        self.assertIn("+1 from Beacons of Rage (Aura)", res["modifiers"])

    def test_out_of_range_does_not_apply(self):
        profile = self._make_profile(melee=True)
        attacker_model, attacker_unit, aura_source, target, _game_map = self._mk_stack(in_range=False)

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=False):
            with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
                res = profile._hit_target_with_tracking(target, attacker_model, {})

        self.assertFalse(res["hit"])
        self.assertNotIn("+1 from Beacons of Rage (Aura)", res["modifiers"])

    def test_ranged_attack_does_not_apply(self):
        profile = self._make_profile(melee=False)
        attacker_model, attacker_unit, aura_source, target, _game_map = self._mk_stack(in_range=True)

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
                res = profile._hit_target_with_tracking(target, attacker_model, {})

        self.assertFalse(res["hit"])
        self.assertNotIn("+1 from Beacons of Rage (Aura)", res["modifiers"])

    def test_excluded_monster_target_does_not_apply(self):
        profile = self._make_profile(melee=True)
        attacker_model, attacker_unit, aura_source, target, _game_map = self._mk_stack(in_range=True, target_is_monster=True)

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
                res = profile._hit_target_with_tracking(target, attacker_model, {})

        self.assertFalse(res["hit"])
        self.assertNotIn("+1 from Beacons of Rage (Aura)", res["modifiers"])

    def test_excluded_vehicle_target_does_not_apply(self):
        profile = self._make_profile(melee=True)
        attacker_model, attacker_unit, aura_source, target, _game_map = self._mk_stack(in_range=True, target_is_vehicle=True)

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
                res = profile._hit_target_with_tracking(target, attacker_model, {})

        self.assertFalse(res["hit"])
        self.assertNotIn("+1 from Beacons of Rage (Aura)", res["modifiers"])

    def test_non_world_eaters_does_not_apply(self):
        profile = self._make_profile(melee=True)
        attacker_model, attacker_unit, aura_source, target, _game_map = self._mk_stack(in_range=True, attacker_is_world_eaters=False)

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
                res = profile._hit_target_with_tracking(target, attacker_model, {})

        self.assertFalse(res["hit"])
        self.assertNotIn("+1 from Beacons of Rage (Aura)", res["modifiers"])

    def test_below_half_strength_grants_plus_one_to_wound(self):
        profile = self._make_profile(melee=True)
        attacker_model, attacker_unit, aura_source, target, _game_map = self._mk_stack(in_range=True, target_below_half=True)

        attack_instance = {}
        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            # Ensure hit succeeds first; store aura cache on attack_instance
            with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2, 3]):
                hit = profile._hit_target_with_tracking(target, attacker_model, attack_instance)
                self.assertTrue(hit["hit"])
                wound = profile._wound_target_with_tracking(target, attacker_model, attack_instance)

        self.assertTrue(wound["wound"])
        self.assertIn("+1 to wound from Beacons of Rage (Aura) vs Below Half-strength", wound["modifiers"])


if __name__ == "__main__":
    unittest.main()

