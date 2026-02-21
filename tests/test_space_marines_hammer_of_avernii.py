import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        save: str = "3",
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
                "T": str(int(toughness)),
                "Sv": str(save),
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4, save: str = "3"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        save=save,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Hammer of Avernii"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1

    army_sm = Army("Space Marines", detachment_type)
    army_sm.faction_id = "SM"
    army_enemy = Army("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army_sm)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)

    return game, army_sm, army_enemy


def _make_ranged_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "-1",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesHammerOfAvernii(unittest.TestCase):
    def test_calculated_annihilation_applies_reroll_ones_vs_oath_target(self):
        _game, army_sm, army_enemy = _build_game("Hammer of Avernii")
        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        army_sm.oath_of_moment.set_target(target)

        profile = _make_ranged_profile()
        wound = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 18.0},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertIn(1, list(wound.get("reroll_values", []) or []))
        self.assertTrue(
            any("Calculated Annihilation" in reason for reason in list(wound.get("reroll_value_reasons", []) or []))
        )

    def test_calculated_annihilation_requires_oath_target(self):
        _game, army_sm, army_enemy = _build_game("Hammer of Avernii")
        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        oath_target = _make_unit(
            "Enemy A",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        non_oath_target = _make_unit(
            "Enemy B",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(oath_target)
        army_enemy.add_unit(non_oath_target)
        army_sm.oath_of_moment.set_target(oath_target)

        profile = _make_ranged_profile()
        wound = profile._wound_target_with_tracking(
            non_oath_target,
            attacker.models[0],
            {"distance_to_target": 18.0},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertNotIn(1, list(wound.get("reroll_values", []) or []))
        self.assertFalse(
            any("Calculated Annihilation" in reason for reason in list(wound.get("reroll_value_reasons", []) or []))
        )

    def test_calculated_annihilation_does_not_apply_outside_hammer_of_avernii(self):
        _game, army_sm, army_enemy = _build_game("Gladius Task Force")
        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        army_sm.oath_of_moment.set_target(target)

        profile = _make_ranged_profile()
        wound = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 18.0},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertNotIn(1, list(wound.get("reroll_values", []) or []))
        self.assertFalse(
            any("Calculated Annihilation" in reason for reason in list(wound.get("reroll_value_reasons", []) or []))
        )

    def test_recalculating_queues_and_applies_new_oath_target(self):
        from warhammer40k_ai.engine.decisions import DecisionResult

        game, army_sm, army_enemy = _build_game("Hammer of Avernii")
        caanok = _make_unit(
            "Caanok Var",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        oath_target = _make_unit(
            "Enemy A",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        next_target = _make_unit(
            "Enemy B",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(caanok)
        army_enemy.add_unit(oath_target)
        army_enemy.add_unit(next_target)
        army_sm.oath_of_moment.set_target(oath_target)

        caanok._has_line_of_sight_to_target = lambda _model, _target, _game_map: True

        game._on_unit_destroyed_recalculating(unit=oath_target)
        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(str(request.context.get("ability", "")), "oath_of_moment")
        self.assertEqual(str(request.context.get("ability_name", "")), "Recalculating")

        target_option = None
        for option in list(request.options or []):
            target_id = str((option.payload or {}).get("target_unit_id", "") or "")
            if target_id == str(getattr(next_target, "_id", "")):
                target_option = option
                break
        self.assertIsNotNone(target_option)

        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=request.player_id,
            option_id=target_option.option_id,
            payload=dict(target_option.payload or {}),
        )
        apply_result = game.resolve_decision(result)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))
        self.assertTrue(army_sm.oath_of_moment.is_oath_target(next_target))

    def test_recalculating_is_limited_to_once_per_battle_round(self):
        from warhammer40k_ai.engine.decisions import DecisionResult

        game, army_sm, army_enemy = _build_game("Hammer of Avernii")
        caanok = _make_unit(
            "Caanok Var",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        first_target = _make_unit(
            "Enemy A",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        second_target = _make_unit(
            "Enemy B",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        third_target = _make_unit(
            "Enemy C",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(caanok)
        army_enemy.add_unit(first_target)
        army_enemy.add_unit(second_target)
        army_enemy.add_unit(third_target)
        army_sm.oath_of_moment.set_target(first_target)

        caanok._has_line_of_sight_to_target = lambda _model, _target, _game_map: True

        game._on_unit_destroyed_recalculating(unit=first_target)
        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        request = pending[0]
        option = list(request.options or [])[0]
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=request.player_id,
            option_id=option.option_id,
            payload=dict(option.payload or {}),
        )
        apply_result = game.resolve_decision(result)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))
        self.assertEqual(int(getattr(army_sm.oath_of_moment, "recalculatingUsedBattleRound", 0)), int(game.turn))

        # Same battle round: no second Recalculating prompt.
        current_queue_size = len(list(game.decision_queue.list() or []))
        game._on_unit_destroyed_recalculating(unit=second_target)
        self.assertEqual(len(list(game.decision_queue.list() or [])), current_queue_size)


if __name__ == "__main__":
    unittest.main()
