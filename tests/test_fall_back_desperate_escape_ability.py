import unittest
import sys
import os
import types

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, model_count=1, keywords=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, abilities=None, model_count=1, keywords=None):
    datasheet = _MockDatasheet(name, abilities=abilities, model_count=model_count, keywords=keywords)
    return Unit(datasheet)


class TestFallBackDesperateEscapeAbility(unittest.TestCase):
    def _setup_units(self, *, battleshocked=False):
        ability = {
            "name": "Punishing Withdrawal",
            "description": (
                "Each time an enemy unit (excluding MONSTERS and VEHICLES) within Engagement Range of one or more "
                "units from your army with this ability Falls Back, models in that enemy unit must take Desperate "
                "Escape tests. When doing so, if that enemy unit is also Battle-shocked, subtract 1 from each of "
                "those Desperate Escape tests."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        trapper = _make_unit("Trapper", abilities=[ability])
        runner = _make_unit("Runner", model_count=1)

        trapper.parent_army = object()
        runner.parent_army = object()
        trapper.deployed = True
        runner.deployed = True

        # Place in engagement range (within 1")
        runner.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        trapper.models[0].set_location(10.5, 10.0, 0.0, 0.0)

        if battleshocked:
            runner.apply_status_effect(BattleShockEffect(1))

        game_map = Map(60, 44)
        game_map.units = [runner, trapper]
        return runner, trapper, game_map

    def test_parses_fall_back_desperate_escape_ability(self):
        ability = {
            "name": "Punishing Withdrawal",
            "description": (
                "Each time an enemy unit (excluding MONSTERS and VEHICLES) within Engagement Range of one or more "
                "units from your army with this ability Falls Back, models in that enemy unit must take Desperate "
                "Escape tests. When doing so, if that enemy unit is also Battle-shocked, subtract 1 from each of "
                "those Desperate Escape tests."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Trapper", abilities=[ability])
        sr = unit.special_rules
        self.assertTrue(sr.get("enemy_fallback_desperate_escape"))
        self.assertTrue(sr.get("enemy_fallback_desperate_escape_exclude_monster_vehicle"))
        self.assertEqual(int(sr.get("enemy_fallback_desperate_escape_bs_penalty", 0)), 1)

    def test_fall_back_triggers_desperate_escape(self):
        runner, _trapper, game_map = self._setup_units(battleshocked=False)

        called = {"count": 0, "modifier": None}

        def _fake(self, game_map=None, *, roll_modifier=0, reason=None):
            called["count"] += 1
            called["modifier"] = roll_modifier
            return 0

        runner.take_desperate_escape_test = types.MethodType(_fake, runner)
        result = runner.fall_back((14.0, 10.0, 0.0), [], game_map)
        self.assertTrue(result)
        self.assertEqual(called["count"], 1)
        self.assertEqual(int(called["modifier"] or 0), 0)

    def test_battleshock_penalty_applies(self):
        runner, _trapper, game_map = self._setup_units(battleshocked=True)

        called = {"count": 0, "modifier": None}

        def _fake(self, game_map=None, *, roll_modifier=0, reason=None):
            called["count"] += 1
            called["modifier"] = roll_modifier
            return 0

        runner.take_desperate_escape_test = types.MethodType(_fake, runner)
        result = runner.fall_back((14.0, 10.0, 0.0), [], game_map)
        self.assertTrue(result)
        self.assertEqual(called["count"], 1)
        self.assertEqual(int(called["modifier"] or 0), -1)

    def test_targeted_desperate_escape_ignores_non_matching_enemy_id(self):
        runner, trapper, game_map = self._setup_units(battleshocked=False)
        trapper.special_rules["enemy_fallback_desperate_escape_target_enemy_id"] = "non-matching-enemy-id"
        self.assertNotEqual(str(get_entity_id(runner) or ""), "non-matching-enemy-id")

        called = {"count": 0}

        def _fake(self, game_map=None, *, roll_modifier=0, reason=None):
            called["count"] += 1
            return 0

        runner.take_desperate_escape_test = types.MethodType(_fake, runner)
        result = runner.fall_back((14.0, 10.0, 0.0), [], game_map)
        self.assertTrue(result)
        self.assertEqual(called["count"], 0)

    def test_battleshocked_fall_back_exempt_when_only_fortification(self):
        runner = _make_unit("Runner", model_count=1)
        fort = _make_unit("Fortification", keywords=["Fortification"])

        runner.parent_army = object()
        fort.parent_army = object()
        runner.deployed = True
        fort.deployed = True

        runner.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        fort.models[0].set_location(10.5, 10.0, 0.0, 0.0)

        runner.apply_status_effect(BattleShockEffect(1))

        game_map = Map(60, 44)
        game_map.units = [runner, fort]

        called = {"count": 0}

        def _fake(self, game_map=None, *, roll_modifier=0, reason=None):
            called["count"] += 1
            return 0

        runner.take_desperate_escape_test = types.MethodType(_fake, runner)
        result = runner.fall_back((14.0, 10.0, 0.0), [], game_map)
        self.assertTrue(result)
        self.assertEqual(called["count"], 0)


if __name__ == "__main__":
    unittest.main()
