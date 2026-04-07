import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_value
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


HYPERSPACE_HUNTERS_TEXT = (
    "Once per turn, in the Reinforcements step of your opponent's Movement phase, when an enemy unit is set up on the "
    "battlefield from Reserves within 18\" of and visible to this unit, this unit can shoot as if it were your Shooting "
    "phase, but must only target that enemy unit when doing so, and can only do so if that enemy unit is an eligible target."
)


class TestNecronsHyperspaceHunters(unittest.TestCase):
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
                Ability("Hyperspace Hunters", unit.faction, ability_text, "")
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

    def _build_game(self):
        army_move = Army.with_detachment("Moving Army", detachment_type="Other")
        army_move.faction_id = "MOVE"
        army_react = Army.with_detachment("Necrons", detachment_type="Other")
        army_react.faction_id = "NEC"

        moving_player = Player("Mover", PlayerControl.LOCAL, army=army_move)
        reacting_player = Player("Reactor", PlayerControl.REMOTE, army=army_react)

        battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield, players=[moving_player, reacting_player])
        game.current_player_index = 0
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        return game, moving_player, reacting_player, army_move, army_react

    def _arrange_units(self):
        game, moving_player, reacting_player, army_move, army_react = self._build_game()
        moving_unit = self._make_unit("Enemy", army_move)
        reacting_unit = self._make_unit(
            "Deathmarks",
            army_react,
            ability_text=HYPERSPACE_HUNTERS_TEXT,
        )
        moving_unit.models = [self._make_model("Enemy Model", moving_unit, 0.0, 0.0)]
        reacting_unit.models = [self._make_model("Deathmark", reacting_unit, 8.0, 0.0)]
        army_move.units = [moving_unit]
        army_react.units = [reacting_unit]
        game.map.units = [moving_unit, reacting_unit]
        game.rebuild_entity_registry()
        game._setup_reactive_can_shoot_target = lambda _u, _t: True
        game._model_can_see_unit = lambda _m, _u, game_map=None: True
        return game, moving_player, reacting_player, moving_unit, reacting_unit

    def test_hyperspace_hunters_queues_choose_quarry_on_enemy_reinforcement_setup(self):
        game, moving_player, _reacting_player, moving_unit, _reacting_unit = self._arrange_units()

        game.event_system.publish("unit_set_up", unit=moving_unit, set_up_as_reinforcements=True)
        game.event_system.publish("phase_end", player=moving_player, phase=BattleRoundPhases.MOVEMENT_PHASE)

        pending = [
            req
            for req in game.decision_queue.list()
            if req.decision_type == DECISION_CHOOSE_QUARRY
            and str((req.context or {}).get("ability", "") or "") == "hyperspace_hunters"
        ]
        self.assertEqual(len(pending), 1)
        labels = [str(getattr(opt, "label", "") or "") for opt in list(getattr(pending[0], "options", []) or [])]
        self.assertIn("None", labels)

    def test_hyperspace_hunters_choice_queues_out_of_phase_shooting_and_marks_used(self):
        game, moving_player, reacting_player, moving_unit, reacting_unit = self._arrange_units()

        game.event_system.publish("unit_set_up", unit=moving_unit, set_up_as_reinforcements=True)
        game.event_system.publish("phase_end", player=moving_player, phase=BattleRoundPhases.MOVEMENT_PHASE)

        request = next(
            req
            for req in game.decision_queue.list()
            if req.decision_type == DECISION_CHOOSE_QUARRY
            and str((req.context or {}).get("ability", "") or "") == "hyperspace_hunters"
        )
        target_option = next(
            opt
            for opt in list(getattr(request, "options", []) or [])
            if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
            == str(get_entity_id(moving_unit) or "")
        )
        _value, apply_result = resolve_decision_value(
            game,
            request,
            target_option.option_id,
            player_id=reacting_player.id,
        )
        self.assertTrue(bool(getattr(apply_result, "ok", False)))
        self.assertTrue(bool(reacting_unit.hyperspace_hunters_used_this_turn(game)))

        shoot_requests = [req for req in game.decision_queue.list() if req.decision_type == DECISION_DECLARE_SHOTS]
        self.assertEqual(len(shoot_requests), 1)
        ctx = dict(getattr(shoot_requests[0], "context", {}) or {})
        self.assertTrue(bool(ctx.get("out_of_phase", False)))
        self.assertEqual(str(ctx.get("force_target_unit_id", "") or ""), str(get_entity_id(moving_unit) or ""))

        game.event_system.publish("unit_set_up", unit=moving_unit, set_up_as_reinforcements=True)
        game.event_system.publish("phase_end", player=moving_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
        additional = [
            req
            for req in game.decision_queue.list()
            if req.decision_type == DECISION_CHOOSE_QUARRY
            and str((req.context or {}).get("ability", "") or "") == "hyperspace_hunters"
        ]
        self.assertEqual(len(additional), 0)

    def test_hyperspace_hunters_does_not_trigger_without_reinforcements_setup(self):
        game, moving_player, _reacting_player, moving_unit, _reacting_unit = self._arrange_units()

        game.event_system.publish("unit_set_up", unit=moving_unit, set_up_as_reinforcements=False)
        game.event_system.publish("phase_end", player=moving_player, phase=BattleRoundPhases.MOVEMENT_PHASE)

        pending = [
            req
            for req in game.decision_queue.list()
            if req.decision_type == DECISION_CHOOSE_QUARRY
            and str((req.context or {}).get("ability", "") or "") == "hyperspace_hunters"
        ]
        self.assertEqual(len(pending), 0)


if __name__ == "__main__":
    unittest.main()
