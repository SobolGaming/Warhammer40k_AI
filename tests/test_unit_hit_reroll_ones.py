import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
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


def _make_unit(name, *, abilities=None):
    from warhammer40k_ai.classes.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities)
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.classes.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.classes.army import Army
    from warhammer40k_ai.classes.player import Player, PlayerType

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Orks", "Det")
    army1.faction_id = "ORK"
    army2 = Army("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("P1", player_type=PlayerType.HUMAN, army=army1)
    p2 = Player("P2", player_type=PlayerType.AI, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    return game, army1, army2, p1


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


class TestUnitHitRerollOnes(unittest.TestCase):
    def test_ranged_hit_reroll_ones(self):
        from warhammer40k_ai.classes.wargear import WargearProfile
        from warhammer40k_ai.classes import wargear as wargear_mod

        ability = {
            "name": "Dat's Our Loot!",
            "description": "Each time a model in this unit makes a ranged attack, you can re-roll a Hit roll of 1.",
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1 = _build_game()
        attacker = _make_unit("Lootas", abilities=[ability])
        target = _make_unit("Target")
        army1.add_unit(attacker)
        army2.add_unit(target)

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )

        rolls = iter([1, 5])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls)
        try:
            result = profile._hit_target_with_tracking(target, attacker.models[0], {"_aura_attack_mods": _aura_stub()})
        finally:
            wargear_mod.get_roll = original_roll

        self.assertEqual(int(result["roll"]), 5)
        self.assertEqual(int(result.get("reroll_of_one", 0)), 1)

    def test_melee_hit_reroll_ones(self):
        from warhammer40k_ai.classes.wargear import WargearProfile
        from warhammer40k_ai.classes import wargear as wargear_mod

        ability = {
            "name": "Choppa Skill",
            "description": "Each time a model in this unit makes a melee attack, re-roll a Hit roll of 1.",
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1 = _build_game()
        attacker = _make_unit("Boyz", abilities=[ability])
        target = _make_unit("Target")
        army1.add_unit(attacker)
        army2.add_unit(target)

        parent = SimpleNamespace(name="Choppa", is_melee=lambda: True, is_ranged=lambda: False)
        profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )

        rolls = iter([1, 6])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls)
        try:
            result = profile._hit_target_with_tracking(target, attacker.models[0], {"_aura_attack_mods": _aura_stub()})
        finally:
            wargear_mod.get_roll = original_roll

        self.assertEqual(int(result["roll"]), 6)
        self.assertEqual(int(result.get("reroll_of_one", 0)), 1)

    def test_any_attack_hit_reroll_ones(self):
        from warhammer40k_ai.classes.wargear import WargearProfile
        from warhammer40k_ai.classes import wargear as wargear_mod

        ability = {
            "name": "Scrap Savvy",
            "description": "Each time a model in this unit makes an attack, re-roll a Hit roll of 1.",
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1 = _build_game()
        attacker = _make_unit("Lootas", abilities=[ability])
        target = _make_unit("Target")
        army1.add_unit(attacker)
        army2.add_unit(target)

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )

        rolls = iter([1, 4])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls)
        try:
            result = profile._hit_target_with_tracking(target, attacker.models[0], {"_aura_attack_mods": _aura_stub()})
        finally:
            wargear_mod.get_roll = original_roll

        self.assertEqual(int(result["roll"]), 4)
        self.assertEqual(int(result.get("reroll_of_one", 0)), 1)

    def test_objective_full_hit_reroll(self):
        from warhammer40k_ai.classes.wargear import WargearProfile
        from warhammer40k_ai.classes.map import Objective, ObjectiveCategory, ObjectivePoint
        from warhammer40k_ai.classes import wargear as wargear_mod

        ability = {
            "name": "Dat's Our Loot!",
            "description": "Each time a model in this unit makes an attack, re-roll a Hit roll of 1. If that attack targets a unit that is within range of an objective marker, you can re-roll the Hit roll instead.",
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1 = _build_game()
        attacker = _make_unit("Lootas", abilities=[ability])
        target = _make_unit("Target")
        army1.add_unit(attacker)
        army2.add_unit(target)

        target.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        objective_point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Test Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=objective_point,
        )
        game.map.add_objective(objective)

        called = {}
        def _provider(**kwargs):
            called["reason"] = kwargs.get("reason")
            return True

        game.map.roll_reroll_provider = _provider

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )

        rolls = iter([2, 6])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls)
        try:
            result = profile._hit_target_with_tracking(target, attacker.models[0], {"_aura_attack_mods": _aura_stub()})
        finally:
            wargear_mod.get_roll = original_roll

        self.assertEqual(int(result["roll"]), 6)
        self.assertIn("objective", str(called.get("reason", "")).lower())

    def test_conditional_target_hit_reroll_not_applied(self):
        from warhammer40k_ai.classes.wargear import WargearProfile
        from warhammer40k_ai.classes import wargear as wargear_mod

        ability = {
            "name": "Conditional Reroll",
            "description": "Each time a model in this unit makes a ranged attack that targets a unit within 9\", re-roll a Hit roll of 1.",
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1 = _build_game()
        attacker = _make_unit("Lootas", abilities=[ability])
        target = _make_unit("Target")
        army1.add_unit(attacker)
        army2.add_unit(target)

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )

        rolls = iter([1, 6])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls)
        try:
            result = profile._hit_target_with_tracking(target, attacker.models[0], {"_aura_attack_mods": _aura_stub()})
        finally:
            wargear_mod.get_roll = original_roll

        self.assertEqual(int(result["roll"]), 1)
        self.assertEqual(int(result.get("reroll_of_one", 0)), 0)
        self.assertIsNone(result.get("reroll"))

    def test_extra_clause_does_not_trigger_objective_full_reroll(self):
        from warhammer40k_ai.classes.wargear import WargearProfile
        from warhammer40k_ai.classes.map import Objective, ObjectiveCategory, ObjectivePoint
        from warhammer40k_ai.classes import wargear as wargear_mod

        ability = {
            "name": "Swift Demise",
            "description": "Each time a model in this unit makes a ranged attack, re-roll a Hit roll of 1. If the target of that attack is the closest eligible target, you can re-roll the Hit roll instead.",
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1 = _build_game()
        attacker = _make_unit("Windriders", abilities=[ability])
        target = _make_unit("Target")
        army1.add_unit(attacker)
        army2.add_unit(target)

        target.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        objective_point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Test Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=objective_point,
        )
        game.map.add_objective(objective)

        called = {}
        def _provider(**kwargs):
            called["called"] = True
            return True

        game.map.roll_reroll_provider = _provider

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )

        rolls = iter([2, 6])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls)
        try:
            result = profile._hit_target_with_tracking(target, attacker.models[0], {"_aura_attack_mods": _aura_stub()})
        finally:
            wargear_mod.get_roll = original_roll

        self.assertEqual(int(result["roll"]), 2)
        self.assertFalse(called)


if __name__ == "__main__":
    unittest.main()
