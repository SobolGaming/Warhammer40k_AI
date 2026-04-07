import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, model_count: int = 1):
        count = max(1, int(model_count or 1))
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "12",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "2",
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_model_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_game(*, size: BattlefieldSize = BattlefieldSize.STRIKE_FORCE):
    sm_army = Army.with_detachment("Space Marines", "The Angelic Host")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("SM", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(size), players=[sm_player, enemy_player])
    return game, sm_army, enemy_army, sm_player, enemy_player


def _upon_wings_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_REALM_OF_CHAOS_UNITS
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "").strip().lower()
        == "upon_wings_of_fire_end_of_opponent_turn"
    ]


class TestSpaceMarinesTheAngelicHost(unittest.TestCase):
    def test_upon_wings_queues_single_multiselect_request_with_eligibility_filtering(self):
        game, sm_army, enemy_army, _sm_player, enemy_player = _build_game(size=BattlefieldSize.STRIKE_FORCE)
        jump_a = _make_unit(
            "Jump A",
            keywords=["INFANTRY", "JUMP PACK"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        jump_b = _make_unit(
            "Jump B",
            keywords=["INFANTRY", "JUMP PACK"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        non_jump = _make_unit(
            "Non Jump",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        engaged_jump = _make_unit(
            "Engaged Jump",
            keywords=["INFANTRY", "JUMP PACK"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

        _set_model_location(jump_a, x=4.0, y=4.0)
        _set_model_location(jump_b, x=10.0, y=4.0)
        _set_model_location(non_jump, x=16.0, y=4.0)
        _set_model_location(engaged_jump, x=22.0, y=4.0)
        _set_model_location(enemy, x=22.0, y=4.0)

        for unit in (jump_a, jump_b, non_jump, engaged_jump):
            sm_army.add_unit(unit)
        enemy_army.add_unit(enemy)
        game.map.units = [jump_a, jump_b, non_jump, engaged_jump, enemy]
        game.rebuild_entity_registry()

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)

        requests = _upon_wings_requests(game)
        self.assertEqual(len(requests), 1)
        req = requests[0]
        ctx = dict(getattr(req, "context", {}) or {})
        allowed_ids = set(str(v) for v in list(ctx.get("allowed_unit_ids") or []))
        self.assertEqual(int(ctx.get("max_units", 0) or 0), 2)
        self.assertIn(str(get_entity_id(jump_a)), allowed_ids)
        self.assertIn(str(get_entity_id(jump_b)), allowed_ids)
        self.assertNotIn(str(get_entity_id(non_jump)), allowed_ids)
        self.assertNotIn(str(get_entity_id(engaged_jump)), allowed_ids)
        self.assertEqual(str(ctx.get("skip_label", "")), "None (do not use this ability)")

    def test_upon_wings_selection_moves_units_sets_arrival_window_and_prevents_repeat_prompt(self):
        game, sm_army, enemy_army, sm_player, enemy_player = _build_game()
        jump_a = _make_unit(
            "Jump A",
            keywords=["INFANTRY", "JUMP PACK"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        jump_b = _make_unit(
            "Jump B",
            keywords=["INFANTRY", "JUMP PACK"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        _set_model_location(jump_a, x=6.0, y=6.0)
        _set_model_location(jump_b, x=12.0, y=6.0)
        _set_model_location(enemy, x=30.0, y=30.0)

        sm_army.add_unit(jump_a)
        sm_army.add_unit(jump_b)
        enemy_army.add_unit(enemy)
        game.map.units = [jump_a, jump_b, enemy]
        game.rebuild_entity_registry()

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
        request = _upon_wings_requests(game)[0]
        confirm_option = next(
            opt for opt in list(request.options or []) if str((opt.payload or {}).get("action", "")) == "confirm"
        )
        resolve_decision_command(
            game,
            request,
            confirm_option.option_id,
            result_payload={"unit_ids": [str(get_entity_id(jump_a))]},
            player_id=sm_player.id,
        )

        self.assertTrue(jump_a.is_in_strategic_reserves())
        self.assertFalse(jump_b.is_in_strategic_reserves())
        sr = getattr(jump_a, "special_rules", None) or {}
        self.assertTrue(bool(sr.get("umbralefic_crystal_temp_deep_strike")))
        self.assertEqual(str(sr.get("umbralefic_crystal_must_arrive_turn_owner", "") or ""), str(sm_player.id))
        self.assertEqual(int(sr.get("umbralefic_crystal_must_arrive_turn", 0) or 0), int(game.turn) + 1)

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
        self.assertEqual(len(_upon_wings_requests(game)), 0)

    def test_upon_wings_skip_marks_phase_resolved(self):
        game, sm_army, enemy_army, sm_player, enemy_player = _build_game()
        jump = _make_unit(
            "Jump Unit",
            keywords=["INFANTRY", "JUMP PACK"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        _set_model_location(jump, x=8.0, y=8.0)
        _set_model_location(enemy, x=30.0, y=30.0)

        sm_army.add_unit(jump)
        enemy_army.add_unit(enemy)
        game.map.units = [jump, enemy]
        game.rebuild_entity_registry()

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
        request = _upon_wings_requests(game)[0]
        skip_option = next(
            opt for opt in list(request.options or []) if str((opt.payload or {}).get("action", "")) == "skip"
        )
        resolve_decision_command(
            game,
            request,
            skip_option.option_id,
            result_payload={"skipped": True},
            player_id=sm_player.id,
        )

        self.assertFalse(jump.is_in_strategic_reserves())
        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
        self.assertEqual(len(_upon_wings_requests(game)), 0)


if __name__ == "__main__":
    unittest.main()
