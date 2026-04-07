import unittest
from types import SimpleNamespace

from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize, BattleRoundPhases
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_SELECT_SETUP_REACTIVE_TARGET,
    DECISION_CHOOSE_SETUP_REACTIVE_ACTION,
    DECISION_DECLARE_SHOTS,
)
from warhammer40k_ai.roster.player import Player, PlayerControl
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


class TestSetupReactiveShootCharge(unittest.TestCase):
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
                Ability("Unleash Wrath", unit.faction, ability_text, "")
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


if __name__ == "__main__":
    unittest.main()
