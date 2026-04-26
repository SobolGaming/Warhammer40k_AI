import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize, BattleRoundPhases
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_SELECT_SETUP_REACTIVE_TARGET,
    DECISION_CHOOSE_SETUP_REACTIVE_ACTION,
    DECISION_DECLARE_SHOTS,
    DECISION_DECLARE_CHARGE,
    DECISION_MOVE_UNIT,
)
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.selectable_section_abilities import KEY_COUNTERSTRATEGIST, set_active_section_ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


SETUP_REACTIVE_TEXT = (
    "At the end of your opponent's Movement phase, you can select one enemy unit that was set up on the battlefield "
    "within 12\" of this model; this model can then either: - Shoot at that unit, but only if it is an eligible target. "
    "- Declare a charge against that unit (note that even if this charge is successful, this model does not receive any "
    "Charge bonus this turn)."
)

COUNTERSTRATEGIST_TEXT = (
    "At the end of your opponent's Movement phase, you can select one enemy unit that was set up or ended a move "
    "within 12\" of this model's unit, and one friendly Regiment unit within 6\" of and visible to this model. "
    "That REGIMENT unit can then either: - Make a Normal move of up to D6\". - Shoot at that enemy unit, but only "
    "if it is an eligible target. - Declare a charge against that enemy unit, but only if it is within 12\" of that "
    "REGIMENT unit (note that even if this charge is successful, the charging unit does not receive any Charge Bonus "
    "this turn)."
)


class TestSetupReactiveShootCharge(unittest.TestCase):
    def _make_unit(
        self,
        name,
        army,
        *,
        ability_text=None,
        ability_name="Unleash Wrath",
        keywords=None,
        faction_keywords=None,
    ):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = getattr(army, "faction_id", "")
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models = []
        unit.keywords = list(keywords or [])
        unit.faction_keywords = list(faction_keywords or [])
        unit.possible_abilities = []
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace(
            remained_stationary_this_round=True,
            advanced_this_round=False,
            shot_this_round=False,
            fell_back_this_round=False,
            reinforced_this_round=False,
            attempted_charge_this_round=False,
            charged_this_round=False,
            action_locked_until_turn_end=False,
            disembarked_cannot_charge=False,
            disembarked_from_destroyed_transport=False,
        )
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        if ability_text:
            unit.possible_abilities = [
                Ability(ability_name, unit.faction, ability_text, "")
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

    def _build_game(self, *, reacting_control=PlayerControl.REMOTE):
        army_move = Army.with_detachment("Moving Army", detachment_type="Other")
        army_move.faction_id = "MOVE"
        army_react = Army.with_detachment("Reactive Army", detachment_type="Other")
        army_react.faction_id = "REACT"

        moving_player = Player("Mover", PlayerControl.LOCAL, army=army_move)
        reacting_player = Player("Reactor", reacting_control, army=army_react)

        battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield, players=[moving_player, reacting_player])
        game.current_player_index = 0
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        return game, moving_player, reacting_player, army_move, army_react

    def _arrange_units(self):
        game, moving_player, reacting_player, army_move, army_react = self._build_game()

        moving_unit = self._make_unit("Enemy", army_move)
        reacting_unit = self._make_unit("Defiler", army_react, ability_text=SETUP_REACTIVE_TEXT)
        moving_unit.models = [self._make_model("Enemy Model", moving_unit, 0.0, 0.0)]
        reacting_unit.models = [self._make_model("Defiler Model", reacting_unit, 8.0, 0.0)]

        army_move.units = [moving_unit]
        army_react.units = [reacting_unit]
        game.map.units = [moving_unit, reacting_unit]
        game.rebuild_entity_registry()
        return game, moving_player, reacting_player, moving_unit, reacting_unit

    def _trigger_setup_reactive_prompt(self, game, moving_player, moving_unit):
        game.event_system.publish("unit_set_up", unit=moving_unit)
        game.event_system.publish("phase_end", player=moving_player, phase=BattleRoundPhases.MOVEMENT_PHASE)

    def _arrange_counterstrategist_units(self, *, active=True):
        game, moving_player, reacting_player, army_move, army_react = self._build_game()

        moving_unit = self._make_unit("Enemy", army_move)
        yarrick = self._make_unit(
            "Commissar Yarrick",
            army_react,
            ability_text=COUNTERSTRATEGIST_TEXT,
            ability_name="Counterstrategist",
        )
        yarrick.possible_abilities.append(
            Ability(
                "Hero of Hades Hive",
                yarrick.faction,
                "In your Command phase, select one of the abilities in the Hero of Hades Hive section.",
                "",
            )
        )
        regiment = self._make_unit(
            "Cadian Shock Troops",
            army_react,
            keywords=["INFANTRY"],
            faction_keywords=["ASTRA MILITARUM", "REGIMENT"],
        )
        moving_unit.models = [self._make_model("Enemy Model", moving_unit, 0.0, 0.0)]
        yarrick.models = [self._make_model("Yarrick", yarrick, 6.0, 0.0)]
        regiment.models = [self._make_model("Cadian", regiment, 8.0, 0.0)]
        regiment.can_declare_charge_against = lambda _target, _game, out_of_turn=False: True

        army_move.units = [moving_unit]
        army_react.units = [yarrick, regiment]
        game.map.units = [moving_unit, yarrick, regiment]
        game.rebuild_entity_registry()
        if active:
            set_active_section_ability(yarrick, KEY_COUNTERSTRATEGIST, start_round=1, expires_round=2)
        game._model_can_see_unit = lambda _model, _unit, game_map=None: True
        game._setup_reactive_can_shoot_target = lambda unit, target: unit is regiment and target is moving_unit
        return game, moving_player, reacting_player, moving_unit, yarrick, regiment

    def _trigger_counterstrategist_prompt(self, game, moving_player, moving_unit, *, trigger="move"):
        if trigger == "set_up":
            game.event_system.publish("unit_set_up", unit=moving_unit)
        else:
            game.event_system.publish("unit_move_ended", unit=moving_unit, action=trigger)
        game.event_system.publish("phase_end", player=moving_player, phase=BattleRoundPhases.MOVEMENT_PHASE)

    def test_setup_reactive_phase_end_queues_target_decision_remote(self):
        game, moving_player, reacting_player, moving_unit, _reacting_unit = self._arrange_units()
        game._setup_reactive_available_actions = lambda _u, _t: ["charge"]

        self._trigger_setup_reactive_prompt(game, moving_player, moving_unit)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_SELECT_SETUP_REACTIVE_TARGET]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.player_id, reacting_player.id)
        ctx = request.context or {}
        self.assertTrue(bool(ctx.get("setup_reactive_flow")))

    def test_setup_reactive_target_selection_queues_action_decision(self):
        game, moving_player, reacting_player, moving_unit, _reacting_unit = self._arrange_units()
        game._setup_reactive_available_actions = lambda _u, _t: ["charge"]

        self._trigger_setup_reactive_prompt(game, moving_player, moving_unit)

        request = next(req for req in game.decision_queue.list() if req.decision_type == DECISION_SELECT_SETUP_REACTIVE_TARGET)
        target_option = None
        target_id = get_entity_id(moving_unit)
        for opt in list(request.options or []):
            if str((opt.payload or {}).get("unit_id", "")) == target_id:
                target_option = opt
                break
        self.assertIsNotNone(target_option)
        resolve_decision_command(game, request, target_option.option_id, player_id=reacting_player.id)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CHOOSE_SETUP_REACTIVE_ACTION]
        self.assertEqual(len(pending), 1)

    def test_setup_reactive_action_charge_defers_to_ui(self):
        game, moving_player, reacting_player, moving_unit, reacting_unit = self._arrange_units()
        game._setup_reactive_available_actions = lambda _u, _t: ["charge"]
        reacting_unit.can_declare_charge_against = lambda _t, _g, out_of_turn=False: True

        called = {}

        def _attempt_charge(unit, target, *, out_of_turn=False, count_as_charged=True):
            called["unit"] = unit
            called["target"] = target
            called["out_of_turn"] = out_of_turn
            called["count_as_charged"] = count_as_charged
            return True

        game.attempt_charge = _attempt_charge

        self._trigger_setup_reactive_prompt(game, moving_player, moving_unit)

        target_req = next(req for req in game.decision_queue.list() if req.decision_type == DECISION_SELECT_SETUP_REACTIVE_TARGET)
        target_option = next(opt for opt in target_req.options if str((opt.payload or {}).get("unit_id", "")) == get_entity_id(moving_unit))
        resolve_decision_command(game, target_req, target_option.option_id, player_id=reacting_player.id)

        action_req = next(req for req in game.decision_queue.list() if req.decision_type == DECISION_CHOOSE_SETUP_REACTIVE_ACTION)
        action_option = next(opt for opt in action_req.options if (opt.payload or {}).get("action") == "charge")
        resolve_decision_command(game, action_req, action_option.option_id, player_id=reacting_player.id)

        self.assertFalse(bool(called), "Setup reactive charge should defer to UI/decision flow (no auto attempt).")

    def test_setup_reactive_action_shoot_queues_declare_shots(self):
        game, moving_player, reacting_player, moving_unit, _reacting_unit = self._arrange_units()
        game._setup_reactive_available_actions = lambda _u, _t: ["shoot"]
        game._setup_reactive_can_shoot_target = lambda _u, _t: True

        self._trigger_setup_reactive_prompt(game, moving_player, moving_unit)

        target_req = next(req for req in game.decision_queue.list() if req.decision_type == DECISION_SELECT_SETUP_REACTIVE_TARGET)
        target_option = next(opt for opt in target_req.options if str((opt.payload or {}).get("unit_id", "")) == get_entity_id(moving_unit))
        resolve_decision_command(game, target_req, target_option.option_id, player_id=reacting_player.id)

        action_req = next(req for req in game.decision_queue.list() if req.decision_type == DECISION_CHOOSE_SETUP_REACTIVE_ACTION)
        action_option = next(opt for opt in action_req.options if (opt.payload or {}).get("action") == "shoot")
        resolve_decision_command(game, action_req, action_option.option_id, player_id=reacting_player.id)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_DECLARE_SHOTS]
        self.assertEqual(len(pending), 1)
        ctx = pending[0].context or {}
        self.assertTrue(bool(ctx.get("out_of_phase")))
        self.assertEqual(ctx.get("force_target_unit_id"), get_entity_id(moving_unit))

    def test_counterstrategist_queues_enemy_and_regiment_pair_after_enemy_move(self):
        game, moving_player, reacting_player, moving_unit, _yarrick, regiment = self._arrange_counterstrategist_units()

        self._trigger_counterstrategist_prompt(game, moving_player, moving_unit, trigger="move")

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_SELECT_SETUP_REACTIVE_TARGET]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.player_id, reacting_player.id)
        ctx = request.context or {}
        self.assertTrue(bool(ctx.get("setup_reactive_counterstrategist")))
        option = next(
            opt
            for opt in request.options
            if (opt.payload or {}).get("target_unit_id") == get_entity_id(moving_unit)
        )
        self.assertEqual((option.payload or {}).get("reactive_unit_id"), get_entity_id(regiment))
        self.assertEqual((option.payload or {}).get("actions"), ["move", "shoot", "charge"])

    def test_counterstrategist_inactive_section_does_not_queue(self):
        game, moving_player, _reacting_player, moving_unit, _yarrick, _regiment = self._arrange_counterstrategist_units(
            active=False
        )

        self._trigger_counterstrategist_prompt(game, moving_player, moving_unit, trigger="move")

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_SELECT_SETUP_REACTIVE_TARGET]
        self.assertEqual(pending, [])

    def test_counterstrategist_move_choice_queues_d6_normal_move_for_regiment(self):
        game, moving_player, reacting_player, moving_unit, yarrick, regiment = self._arrange_counterstrategist_units()

        self._trigger_counterstrategist_prompt(game, moving_player, moving_unit, trigger="move")
        target_req = next(req for req in game.decision_queue.list() if req.decision_type == DECISION_SELECT_SETUP_REACTIVE_TARGET)
        target_option = next(
            opt
            for opt in target_req.options
            if (opt.payload or {}).get("target_unit_id") == get_entity_id(moving_unit)
        )
        resolve_decision_command(game, target_req, target_option.option_id, player_id=reacting_player.id)
        action_req = next(req for req in game.decision_queue.list() if req.decision_type == DECISION_CHOOSE_SETUP_REACTIVE_ACTION)
        move_option = next(opt for opt in action_req.options if (opt.payload or {}).get("action") == "move")

        with patch("warhammer40k_ai.engine.game_mixins.reactive_decisions_mixin.get_roll", return_value=4):
            resolve_decision_command(game, action_req, move_option.option_id, player_id=reacting_player.id)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_MOVE_UNIT]
        self.assertEqual(len(pending), 1)
        ctx = pending[0].context or {}
        self.assertEqual(ctx.get("unit_id"), get_entity_id(regiment))
        self.assertEqual(ctx.get("max_distance"), 4)
        self.assertEqual(ctx.get("reactive_move_kind"), "counterstrategist")
        self.assertTrue(yarrick.setup_reactive_shoot_or_charge_used_this_phase(game))

    def test_counterstrategist_charge_choice_queues_no_bonus_charge_declaration(self):
        game, moving_player, reacting_player, moving_unit, _yarrick, _regiment = self._arrange_counterstrategist_units()

        self._trigger_counterstrategist_prompt(game, moving_player, moving_unit, trigger="set_up")
        target_req = next(req for req in game.decision_queue.list() if req.decision_type == DECISION_SELECT_SETUP_REACTIVE_TARGET)
        target_option = next(
            opt
            for opt in target_req.options
            if (opt.payload or {}).get("target_unit_id") == get_entity_id(moving_unit)
        )
        resolve_decision_command(game, target_req, target_option.option_id, player_id=reacting_player.id)
        action_req = next(req for req in game.decision_queue.list() if req.decision_type == DECISION_CHOOSE_SETUP_REACTIVE_ACTION)
        charge_option = next(opt for opt in action_req.options if (opt.payload or {}).get("action") == "charge")
        resolve_decision_command(game, action_req, charge_option.option_id, player_id=reacting_player.id)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_DECLARE_CHARGE]
        self.assertEqual(len(pending), 1)
        ctx = pending[0].context or {}
        self.assertTrue(bool(ctx.get("out_of_turn")))
        self.assertFalse(bool(ctx.get("count_as_charged")))
        self.assertEqual(ctx.get("charge_retarget_reason"), "counterstrategist")


if __name__ == "__main__":
    unittest.main()
