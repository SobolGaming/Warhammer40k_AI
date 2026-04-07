import unittest
from types import SimpleNamespace

from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


LOPING_SPEED_TEXT = (
    "Once per turn, when an enemy unit ends a Normal, Advance or Fall Back move within 9\" of this model's unit, "
    "if this model's unit is not within Engagement Range of one or more enemy units, it can make a Normal move of "
    "up to D6\"."
)
FIXED_REACTIVE_MOVE_TEXT = (
    "Once per turn, when an enemy unit ends a Normal, Advance or Fall Back move within 9\" of this unit, "
    "this unit can make a Normal move of up to 6\"."
)


class TestLopingSpeed(unittest.TestCase):
    def _make_unit(self, name, army, *, ability_text=None):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = getattr(army, "faction_id", "")
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models = []
        unit.keywords = []
        unit.faction_keywords = []
        unit.possible_abilities = []
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        if ability_text:
            unit.possible_abilities = [
                Ability("Trail Finding", unit.faction, ability_text, "")
            ]
        return unit

    def _make_model(self, name, unit, x, y):
        model = Model(
            name=name,
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = unit
        model.set_location(x, y, 0.0, 0.0)
        return model

    def _build_game(self, *, reacting_control=PlayerControl.LOCAL, moving_control=PlayerControl.LOCAL):
        army_move = Army.with_detachment("Moving Army", detachment_type="Other")
        army_move.faction_id = "MOVE"
        army_react = Army.with_detachment("Reactive Army", detachment_type="Other")
        army_react.faction_id = "REACT"

        moving_player = Player("Mover", moving_control, army=army_move)
        reacting_player = Player("Reactor", reacting_control, army=army_react)

        battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield, players=[moving_player, reacting_player])
        game.current_player_index = 0
        return game, moving_player, reacting_player, army_move, army_react

    def test_loping_speed_prompt_on_enemy_move(self):
        game, _moving_player, _reacting_player, army_move, army_react = self._build_game()

        moving_unit = self._make_unit("Enemy Movers", army_move)
        reacting_unit = self._make_unit("Trail Shaper", army_react, ability_text=LOPING_SPEED_TEXT)
        army_move.units = [moving_unit]
        army_react.units = [reacting_unit]

        moving_model = self._make_model("Enemy Model", moving_unit, 0.0, 0.0)
        reacting_model = self._make_model("Trail Model", reacting_unit, 8.0, 0.0)
        moving_unit.models = [moving_model]
        reacting_unit.models = [reacting_model]

        game.map.units = [moving_unit, reacting_unit]

        prompts = []

        def _capture(**kwargs):
            prompts.append(kwargs)

        game.event_system.subscribe("loping_speed_prompt", _capture)

        game.event_system.publish(
            "unit_move_ended",
            unit=moving_unit,
            action="move",
        )

        self.assertEqual(len(prompts), 1)
        self.assertIs(prompts[0].get("unit"), reacting_unit)
        self.assertIs(prompts[0].get("moving_unit"), moving_unit)
        rule = prompts[0].get("rule") or {}
        self.assertEqual(int(rule.get("range", 0) or 0), 9)

    def test_loping_speed_not_triggered_out_of_range(self):
        game, _moving_player, _reacting_player, army_move, army_react = self._build_game()

        moving_unit = self._make_unit("Enemy Movers", army_move)
        reacting_unit = self._make_unit("Trail Shaper", army_react, ability_text=LOPING_SPEED_TEXT)
        army_move.units = [moving_unit]
        army_react.units = [reacting_unit]

        moving_model = self._make_model("Enemy Model", moving_unit, 0.0, 0.0)
        reacting_model = self._make_model("Trail Model", reacting_unit, 20.0, 0.0)
        moving_unit.models = [moving_model]
        reacting_unit.models = [reacting_model]

        game.map.units = [moving_unit, reacting_unit]

        prompts = []

        def _capture(**kwargs):
            prompts.append(kwargs)

        game.event_system.subscribe("loping_speed_prompt", _capture)

        game.event_system.publish(
            "unit_move_ended",
            unit=moving_unit,
            action="move",
        )

        self.assertEqual(prompts, [])

    def test_loping_speed_once_per_turn_after_use(self):
        game, _moving_player, _reacting_player, army_move, army_react = self._build_game()

        moving_unit = self._make_unit("Enemy Movers", army_move)
        reacting_unit = self._make_unit("Trail Shaper", army_react, ability_text=LOPING_SPEED_TEXT)
        army_move.units = [moving_unit]
        army_react.units = [reacting_unit]

        moving_model = self._make_model("Enemy Model", moving_unit, 0.0, 0.0)
        reacting_model = self._make_model("Trail Model", reacting_unit, 8.0, 0.0)
        moving_unit.models = [moving_model]
        reacting_unit.models = [reacting_model]

        game.map.units = [moving_unit, reacting_unit]

        prompts = []

        def _capture(**kwargs):
            prompts.append(kwargs)

        game.event_system.subscribe("loping_speed_prompt", _capture)

        game.event_system.publish(
            "unit_move_ended",
            unit=moving_unit,
            action="move",
        )

        self.assertEqual(len(prompts), 1)

    def test_loping_speed_remote_queues_decision(self):
        game, _moving_player, reacting_player, army_move, army_react = self._build_game(
            reacting_control=PlayerControl.REMOTE,
        )

        moving_unit = self._make_unit("Enemy Movers", army_move)
        reacting_unit = self._make_unit("Trail Shaper", army_react, ability_text=LOPING_SPEED_TEXT)
        army_move.units = [moving_unit]
        army_react.units = [reacting_unit]

        moving_model = self._make_model("Enemy Model", moving_unit, 0.0, 0.0)
        reacting_model = self._make_model("Trail Model", reacting_unit, 8.0, 0.0)
        moving_unit.models = [moving_model]
        reacting_unit.models = [reacting_model]

        game.map.units = [moving_unit, reacting_unit]

        game.event_system.publish(
            "unit_move_ended",
            unit=moving_unit,
            action="move",
        )

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        self.assertEqual(request.player_id, reacting_player.id)
        ctx = request.context or {}
        self.assertEqual(ctx.get("reactive_move_kind"), "loping_speed")
        self.assertEqual(ctx.get("reactive_move_unit_id"), get_entity_id(reacting_unit))
        self.assertEqual(ctx.get("reactive_move_moving_unit_id"), get_entity_id(moving_unit))

    def test_loping_speed_remote_does_not_auto_confirm_with_decision_hook(self):
        game, _moving_player, reacting_player, army_move, army_react = self._build_game(
            reacting_control=PlayerControl.REMOTE,
        )

        reacting_player.decision_hook = lambda *_args, **_kwargs: True

        moving_unit = self._make_unit("Enemy Movers", army_move)
        reacting_unit = self._make_unit("Trail Shaper", army_react, ability_text=LOPING_SPEED_TEXT)
        army_move.units = [moving_unit]
        army_react.units = [reacting_unit]

        moving_model = self._make_model("Enemy Model", moving_unit, 0.0, 0.0)
        reacting_model = self._make_model("Trail Model", reacting_unit, 8.0, 0.0)
        moving_unit.models = [moving_model]
        reacting_unit.models = [reacting_model]

        game.map.units = [moving_unit, reacting_unit]

        game.event_system.publish(
            "unit_move_ended",
            unit=moving_unit,
            action="move",
        )

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].decision_type, DECISION_CONFIRM_YES_NO)

    def test_loping_speed_move_decision_not_auto_resolved_by_position_hook(self):
        game, _moving_player, reacting_player, army_move, army_react = self._build_game(
            reacting_control=PlayerControl.REMOTE,
        )

        moving_unit = self._make_unit("Enemy Movers", army_move)
        reacting_unit = self._make_unit("Trail Shaper", army_react, ability_text=LOPING_SPEED_TEXT)
        army_move.units = [moving_unit]
        army_react.units = [reacting_unit]

        moving_model = self._make_model("Enemy Model", moving_unit, 0.0, 0.0)
        reacting_model = self._make_model("Trail Model", reacting_unit, 8.0, 0.0)
        moving_unit.models = [moving_model]
        reacting_unit.models = [reacting_model]

        def _positions_hook(_player, _ctx):
            return [
                {
                    "model_id": get_entity_id(reacting_model),
                    "position": [8.0, 0.0, 0.0],
                    "facing": 0.0,
                }
            ]

        reacting_player.reactive_move_position_hook = _positions_hook

        game.map.units = [moving_unit, reacting_unit]

        game.event_system.publish(
            "unit_move_ended",
            unit=moving_unit,
            action="move",
        )

        request = game.decision_queue.peek()
        yes_option = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)):
                yes_option = opt
                break
        self.assertIsNotNone(yes_option)
        resolve_decision_command(game, request, yes_option.option_id, player_id=reacting_player.id)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].decision_type, DECISION_MOVE_UNIT)

    def test_loping_speed_confirm_yes_queues_move(self):
        game, _moving_player, reacting_player, army_move, army_react = self._build_game(
            reacting_control=PlayerControl.REMOTE,
        )

        moving_unit = self._make_unit("Enemy Movers", army_move)
        reacting_unit = self._make_unit("Trail Shaper", army_react, ability_text=LOPING_SPEED_TEXT)
        army_move.units = [moving_unit]
        army_react.units = [reacting_unit]

        moving_model = self._make_model("Enemy Model", moving_unit, 0.0, 0.0)
        reacting_model = self._make_model("Trail Model", reacting_unit, 8.0, 0.0)
        moving_unit.models = [moving_model]
        reacting_unit.models = [reacting_model]

        game.map.units = [moving_unit, reacting_unit]

        game.event_system.publish(
            "unit_move_ended",
            unit=moving_unit,
            action="move",
        )

        request = game.decision_queue.peek()
        yes_option = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)):
                yes_option = opt
                break
        self.assertIsNotNone(yes_option)
        resolve_decision_command(game, request, yes_option.option_id, player_id=reacting_player.id)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        move_request = pending[0]
        self.assertEqual(move_request.decision_type, DECISION_MOVE_UNIT)
        move_ctx = move_request.context or {}
        self.assertEqual(move_ctx.get("movement_type"), "loping_speed")
        self.assertGreater(int(move_ctx.get("max_distance") or 0), 0)

    def test_loping_speed_move_marks_used(self):
        game, _moving_player, reacting_player, army_move, army_react = self._build_game(
            reacting_control=PlayerControl.REMOTE,
        )

        moving_unit = self._make_unit("Enemy Movers", army_move)
        reacting_unit = self._make_unit("Trail Shaper", army_react, ability_text=LOPING_SPEED_TEXT)
        army_move.units = [moving_unit]
        army_react.units = [reacting_unit]

        moving_model = self._make_model("Enemy Model", moving_unit, 0.0, 0.0)
        reacting_model = self._make_model("Trail Model", reacting_unit, 8.0, 0.0)
        moving_unit.models = [moving_model]
        reacting_unit.models = [reacting_model]

        game.map.units = [moving_unit, reacting_unit]
        game.rebuild_entity_registry()

        game.event_system.publish(
            "unit_move_ended",
            unit=moving_unit,
            action="move",
        )

        request = game.decision_queue.peek()
        yes_option = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)):
                yes_option = opt
                break
        self.assertIsNotNone(yes_option)
        resolve_decision_command(game, request, yes_option.option_id, player_id=reacting_player.id)

        move_request = game.decision_queue.peek()
        confirm_option = None
        for opt in list(move_request.options or []):
            if str((opt.payload or {}).get("action", "") or "") == "confirm":
                confirm_option = opt
                break
        self.assertIsNotNone(confirm_option)
        model_positions = [
            {
                "model_id": get_entity_id(reacting_model),
                "position": [8.0, 0.0, 0.0],
                "facing": 0.0,
            }
        ]
        resolve_decision_command(
            game,
            move_request,
            confirm_option.option_id,
            result_payload={"model_positions": model_positions},
            player_id=reacting_player.id,
        )

        self.assertTrue(reacting_unit.loping_speed_used_this_turn(game))

    def test_fixed_reactive_move_rule_parses_distance(self):
        game, _moving_player, _reacting_player, _army_move, army_react = self._build_game()
        reacting_unit = self._make_unit("Skitterers", army_react, ability_text=FIXED_REACTIVE_MOVE_TEXT)
        rule = reacting_unit.get_loping_speed_rule()
        self.assertIsNotNone(rule)
        self.assertEqual(int(rule.get("max_distance") or 0), 6)

    def test_fixed_reactive_move_remote_queues_fixed_distance(self):
        game, _moving_player, reacting_player, army_move, army_react = self._build_game(
            reacting_control=PlayerControl.REMOTE,
        )

        moving_unit = self._make_unit("Enemy Movers", army_move)
        reacting_unit = self._make_unit("Skitterers", army_react, ability_text=FIXED_REACTIVE_MOVE_TEXT)
        army_move.units = [moving_unit]
        army_react.units = [reacting_unit]

        moving_model = self._make_model("Enemy Model", moving_unit, 0.0, 0.0)
        reacting_model = self._make_model("Skitterer", reacting_unit, 8.0, 0.0)
        moving_unit.models = [moving_model]
        reacting_unit.models = [reacting_model]

        game.map.units = [moving_unit, reacting_unit]

        game.event_system.publish(
            "unit_move_ended",
            unit=moving_unit,
            action="move",
        )

        request = game.decision_queue.peek()
        yes_option = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)):
                yes_option = opt
                break
        self.assertIsNotNone(yes_option)
        resolve_decision_command(game, request, yes_option.option_id, player_id=reacting_player.id)

        move_request = game.decision_queue.peek()
        move_ctx = move_request.context or {}
        self.assertEqual(int(move_ctx.get("max_distance") or 0), 6)


if __name__ == "__main__":
    unittest.main()
