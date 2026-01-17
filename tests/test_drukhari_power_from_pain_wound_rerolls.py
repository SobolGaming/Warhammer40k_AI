import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.units.wargear import WargearProfile


class _GameStub:
    def __init__(self, *, objective_in_range: bool):
        self._objective_in_range = objective_in_range
        self.map = None

    def _unit_within_range_of_objective(self, _unit):
        if self._objective_in_range:
            return object()
        return None


class _PlayerStub:
    def __init__(self, game):
        self.name = "P1"
        self.control = SimpleNamespace(name="REMOTE")
        self.has_control = lambda: False
        self.game = game


class _ArmyStub:
    def __init__(self, player):
        self.player = player
        self.faction_id = "DRU"


class _UnitStub:
    def __init__(self, name, army, *, toughness=4):
        self.name = name
        self._id = name
        self.toughness = toughness
        self.models = [SimpleNamespace(is_alive=True)]
        self.special_rules = {}
        self.round_state = SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False)
        self._army = army

    def get_parent_army(self):
        return self._army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_members(self):
        return [self]

    def get_models_for_wound_allocation(self):
        return list(self.models)

    def is_alive(self):
        return True

    def has_keyword(self, _k: str) -> bool:
        return False


def _make_melee_profile():
    parent = SimpleNamespace(name="Test Melee", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


class TestPowerFromPainWoundRerolls(unittest.TestCase):
    def test_sadistic_raiders_reroll_wound_ones(self):
        game = _GameStub(objective_in_range=False)
        player = _PlayerStub(game)
        army = _ArmyStub(player)
        attacker_unit = _UnitStub("Kabalites", army)
        attacker_unit.special_rules["pain_reroll_wound_ones"] = True
        attacker = SimpleNamespace(name="Attacker", parent_unit=attacker_unit, is_character=False)
        target = _UnitStub("Target", army)

        profile = _make_melee_profile()
        attack_instance = {"_aura_attack_mods": _aura_stub()}

        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[1, 4]):
            res = profile._wound_target_with_tracking(target, attacker, attack_instance)

        self.assertEqual(res.get("reroll"), 4)
        self.assertIn("Power from Pain: re-roll Wound roll of 1", res.get("special_effects", []))

    def test_sadistic_raiders_objective_full_reroll(self):
        game = _GameStub(objective_in_range=True)
        player = _PlayerStub(game)
        army = _ArmyStub(player)
        attacker_unit = _UnitStub("Kabalites", army)
        attacker_unit.special_rules["pain_reroll_wound_ones"] = True
        attacker_unit.special_rules["pain_reroll_wound_full_if_objective"] = True
        attacker = SimpleNamespace(name="Attacker", parent_unit=attacker_unit, is_character=False)
        target = _UnitStub("Target", army)

        profile = _make_melee_profile()
        attack_instance = {"_aura_attack_mods": _aura_stub()}

        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2, 5]):
            res = profile._wound_target_with_tracking(target, attacker, attack_instance)

        self.assertEqual(res.get("reroll"), 5)
        self.assertIn("Power from Pain: re-roll Wound roll (objective)", res.get("special_effects", []))

    def test_goaded_savagery_beast_reroll_wound(self):
        game = _GameStub(objective_in_range=False)
        player = _PlayerStub(game)
        army = _ArmyStub(player)
        attacker_unit = _UnitStub("Beast", army)
        attacker_unit.special_rules["pain_beast_reroll_wound"] = True
        attacker = SimpleNamespace(name="Attacker", parent_unit=attacker_unit, is_character=False)
        target = _UnitStub("Target", army)

        profile = _make_melee_profile()
        attack_instance = {"_aura_attack_mods": _aura_stub()}

        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2, 6]):
            res = profile._wound_target_with_tracking(target, attacker, attack_instance)

        self.assertEqual(res.get("reroll"), 6)
        self.assertIn("Power from Pain: re-roll Wound roll (beast melee)", res.get("special_effects", []))


if __name__ == "__main__":
    unittest.main()
