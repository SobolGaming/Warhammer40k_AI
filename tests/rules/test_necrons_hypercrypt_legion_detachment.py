import unittest
from types import SimpleNamespace

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
                "M": "6",
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
    necron_army = Army.with_detachment("Necrons", "Hypercrypt Legion")
    necron_army.faction_id = "NEC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    necron_player = Player("Necrons", control=PlayerControl.REMOTE, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(size), players=[necron_player, enemy_player])
    return game, necron_army, enemy_army, necron_player, enemy_player


def _hyperphasing_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_REALM_OF_CHAOS_UNITS
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "").strip().lower()
        == "hyperphasing_end_of_opponent_turn"
    ]


class TestNecronsHypercryptLegionDetachment(unittest.TestCase):
    def test_hyperphasing_queues_single_multiselect_request_with_correct_filters(self):
        game, necron_army, enemy_army, _necron_player, enemy_player = _build_game(size=BattlefieldSize.STRIKE_FORCE)
        eligible_a = _make_unit("Eligible A", keywords=["INFANTRY"], faction_keywords=["NECRONS"])
        eligible_b = _make_unit("Eligible B", keywords=["INFANTRY"], faction_keywords=["NECRONS"])
        allied = _make_unit("Allied Unit", keywords=["INFANTRY"], faction_keywords=["AELDARI"])
        engaged = _make_unit("Engaged Unit", keywords=["INFANTRY"], faction_keywords=["NECRONS"])
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

        _set_model_location(eligible_a, x=4.0, y=4.0)
        _set_model_location(eligible_b, x=10.0, y=4.0)
        _set_model_location(allied, x=16.0, y=4.0)
        _set_model_location(engaged, x=22.0, y=4.0)
        _set_model_location(enemy, x=22.0, y=4.0)

        for unit in (eligible_a, eligible_b, allied, engaged):
            necron_army.add_unit(unit)
        enemy_army.add_unit(enemy)
        game.map.units = [eligible_a, eligible_b, allied, engaged, enemy]
        game.rebuild_entity_registry()

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)

        requests = _hyperphasing_requests(game)
        self.assertEqual(len(requests), 1)
        req = requests[0]
        ctx = dict(getattr(req, "context", {}) or {})
        allowed_ids = set(str(v) for v in list(ctx.get("allowed_unit_ids") or []))

        self.assertEqual(int(ctx.get("max_units", 0) or 0), 2)
        self.assertIn(str(get_entity_id(eligible_a)), allowed_ids)
        self.assertIn(str(get_entity_id(eligible_b)), allowed_ids)
        self.assertNotIn(str(get_entity_id(allied)), allowed_ids)
        self.assertNotIn(str(get_entity_id(engaged)), allowed_ids)
        self.assertEqual(str(ctx.get("skip_label", "")), "None (do not use this ability)")

    def test_hyperphasing_selection_moves_units_and_prevents_repeat_prompt_same_turn(self):
        game, necron_army, enemy_army, necron_player, enemy_player = _build_game()
        eligible_a = _make_unit("Eligible A", keywords=["INFANTRY"], faction_keywords=["NECRONS"])
        eligible_b = _make_unit("Eligible B", keywords=["INFANTRY"], faction_keywords=["NECRONS"])
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        _set_model_location(eligible_a, x=6.0, y=6.0)
        _set_model_location(eligible_b, x=12.0, y=6.0)
        _set_model_location(enemy, x=30.0, y=30.0)

        necron_army.add_unit(eligible_a)
        necron_army.add_unit(eligible_b)
        enemy_army.add_unit(enemy)
        game.map.units = [eligible_a, eligible_b, enemy]
        game.rebuild_entity_registry()

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
        request = _hyperphasing_requests(game)[0]
        confirm_option = next(
            opt for opt in list(request.options or []) if str((opt.payload or {}).get("action", "")) == "confirm"
        )
        resolve_decision_command(
            game,
            request,
            confirm_option.option_id,
            result_payload={"unit_ids": [str(get_entity_id(eligible_a))]},
            player_id=necron_player.id,
        )

        self.assertTrue(eligible_a.is_in_strategic_reserves())
        self.assertFalse(eligible_b.is_in_strategic_reserves())
        self.assertTrue(bool(eligible_a.special_rules.get("hyperphasing_arrival_pending", False)))
        self.assertEqual(
            str(eligible_a.special_rules.get("hyperphasing_arrival_turn_owner", "") or ""),
            str(necron_player.id),
        )

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
        self.assertEqual(len(_hyperphasing_requests(game)), 0)

    def test_hyperphasing_skip_marks_phase_resolved(self):
        game, necron_army, enemy_army, necron_player, enemy_player = _build_game()
        eligible = _make_unit("Eligible Unit", keywords=["INFANTRY"], faction_keywords=["NECRONS"])
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        _set_model_location(eligible, x=8.0, y=8.0)
        _set_model_location(enemy, x=30.0, y=30.0)

        necron_army.add_unit(eligible)
        enemy_army.add_unit(enemy)
        game.map.units = [eligible, enemy]
        game.rebuild_entity_registry()

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
        request = _hyperphasing_requests(game)[0]
        skip_option = next(
            opt for opt in list(request.options or []) if str((opt.payload or {}).get("action", "")) == "skip"
        )
        resolve_decision_command(
            game,
            request,
            skip_option.option_id,
            result_payload={"skipped": True},
            player_id=necron_player.id,
        )

        self.assertFalse(eligible.is_in_strategic_reserves())
        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
        self.assertEqual(len(_hyperphasing_requests(game)), 0)

    def test_hyperphasing_deep_strike_unit_can_arrive_round_one_when_owner_turn_begins(self):
        game, necron_army, _enemy_army, necron_player, _enemy_player = _build_game()
        reserve_unit = _make_unit("Hyperphased Immortals", keywords=["INFANTRY"], faction_keywords=["NECRONS"])
        reserve_unit.deployed = True
        reserve_unit.reserve_status = "strategic_reserves"
        reserve_unit.special_rules["bearer_unit_deep_strike"] = True
        reserve_unit.special_rules["hyperphasing_arrival_pending"] = True
        reserve_unit.special_rules["hyperphasing_arrival_turn_owner"] = str(necron_player.id)
        reserve_unit.special_rules["hyperphasing_arrival_turn"] = 1
        necron_army.add_unit(reserve_unit)

        game.turn = 1
        game.current_player_index = 0
        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")

        self.assertTrue(reserve_unit.can_arrive_from_reserves(1))


if __name__ == "__main__":
    unittest.main()
