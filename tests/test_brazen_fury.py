import unittest
from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize, BattleRoundPhases
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestBrazenFury(unittest.TestCase):
    def _make_unit(self, name, army, *, possessed=False, faction="A"):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = faction
        unit.deployed = True
        unit.models = []
        unit.keywords = ["POSSESSED"] if possessed else []
        unit.faction_keywords = ["WORLD EATERS"] if possessed else []
        unit.possible_abilities = []
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit._ability_cache = {}
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

    def _build_game(self, *, target_control=PlayerControl.REMOTE):
        army_attacker = Army("Other", detachment_type="Other")
        army_attacker.faction_id = "OT"
        army_target = Army("World Eaters", detachment_type="Possessed Slaughterband")
        army_target.faction_id = "WE"

        p1 = Player("P1", PlayerControl.LOCAL, army=army_attacker)
        p2 = Player("P2", target_control, army=army_target)

        bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(bf, players=[p1, p2])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        return game, p1, p2, army_attacker, army_target

    def test_brazen_fury_prompt_published_on_casualties(self):
        game, p1, p2, army_attacker, army_target = self._build_game(target_control=PlayerControl.LOCAL)

        attacker = self._make_unit("Shooter", army_attacker, possessed=False, faction="A")
        target = self._make_unit("Possessed", army_target, possessed=True, faction="B")
        army_attacker.units = [attacker]
        army_target.units = [target]

        attacker_model = self._make_model("Shooter", attacker, 0.0, 0.0)
        target_model_a = self._make_model("Target A", target, 10.0, 0.0)
        target_model_b = self._make_model("Target B", target, 12.0, 0.0)
        attacker.models = [attacker_model]
        target.models = [target_model_a, target_model_b]
        game.map.units = [attacker, target]

        prompts = []

        def _capture(**kwargs):
            prompts.append(kwargs)

        game.event_system.subscribe("brazen_fury_prompt", _capture)

        game.event_system.publish(
            "shooting_targets_selected",
            attacking_unit=attacker,
            target_units=[target],
        )
        target_model_a.wounds = 0
        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=attacker,
            hits_by_target={target: 1},
        )

        self.assertEqual(len(prompts), 1)
        self.assertIs(prompts[0].get("unit"), target)
        self.assertIs(prompts[0].get("attacker_unit"), attacker)

    def test_brazen_fury_remote_queues_decision(self):
        game, _p1, p2, army_attacker, army_target = self._build_game()

        attacker = self._make_unit("Shooter", army_attacker, possessed=False, faction="A")
        target = self._make_unit("Possessed", army_target, possessed=True, faction="B")
        army_attacker.units = [attacker]
        army_target.units = [target]

        attacker_model = self._make_model("Shooter", attacker, 0.0, 0.0)
        target_model_a = self._make_model("Target A", target, 10.0, 0.0)
        target_model_b = self._make_model("Target B", target, 12.0, 0.0)
        attacker.models = [attacker_model]
        target.models = [target_model_a, target_model_b]
        game.map.units = [attacker, target]

        game.event_system.publish(
            "shooting_targets_selected",
            attacking_unit=attacker,
            target_units=[target],
        )
        target_model_a.wounds = 0
        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=attacker,
            hits_by_target={target: 1},
        )

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        self.assertEqual(request.player_id, p2.id)
        ctx = request.context or {}
        self.assertEqual(ctx.get("reactive_move_kind"), "brazen_fury")
        self.assertEqual(ctx.get("reactive_move_unit_id"), get_entity_id(target))
        self.assertEqual(ctx.get("reactive_move_attacker_unit_id"), get_entity_id(attacker))

    def test_brazen_fury_confirm_yes_queues_move(self):
        game, _p1, p2, army_attacker, army_target = self._build_game()

        attacker = self._make_unit("Shooter", army_attacker, possessed=False, faction="A")
        target = self._make_unit("Possessed", army_target, possessed=True, faction="B")
        army_attacker.units = [attacker]
        army_target.units = [target]

        attacker_model = self._make_model("Shooter", attacker, 0.0, 0.0)
        target_model_a = self._make_model("Target A", target, 10.0, 0.0)
        target_model_b = self._make_model("Target B", target, 12.0, 0.0)
        attacker.models = [attacker_model]
        target.models = [target_model_a, target_model_b]
        game.map.units = [attacker, target]

        game.event_system.publish(
            "shooting_targets_selected",
            attacking_unit=attacker,
            target_units=[target],
        )
        target_model_a.wounds = 0
        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=attacker,
            hits_by_target={target: 1},
        )

        request = game.decision_queue.peek()
        yes_option = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)):
                yes_option = opt
                break
        self.assertIsNotNone(yes_option)
        resolve_decision_command(game, request, yes_option.option_id, player_id=p2.id)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        move_request = pending[0]
        self.assertEqual(move_request.decision_type, DECISION_MOVE_UNIT)
        move_ctx = move_request.context or {}
        self.assertEqual(move_ctx.get("movement_type"), "brazen_fury")
        self.assertGreater(int(move_ctx.get("max_distance") or 0), 0)

    def test_brazen_fury_move_marks_used(self):
        game, _p1, p2, army_attacker, army_target = self._build_game()

        attacker = self._make_unit("Shooter", army_attacker, possessed=False, faction="A")
        target = self._make_unit("Possessed", army_target, possessed=True, faction="B")
        army_attacker.units = [attacker]
        army_target.units = [target]

        attacker_model = self._make_model("Shooter", attacker, 0.0, 0.0)
        target_model_a = self._make_model("Target A", target, 10.0, 0.0)
        target_model_b = self._make_model("Target B", target, 12.0, 0.0)
        attacker.models = [attacker_model]
        target.models = [target_model_a, target_model_b]
        game.map.units = [attacker, target]
        game.rebuild_entity_registry()

        game.event_system.publish(
            "shooting_targets_selected",
            attacking_unit=attacker,
            target_units=[target],
        )
        target_model_a.wounds = 0
        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=attacker,
            hits_by_target={target: 1},
        )

        request = game.decision_queue.peek()
        yes_option = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)):
                yes_option = opt
                break
        self.assertIsNotNone(yes_option)
        resolve_decision_command(game, request, yes_option.option_id, player_id=p2.id)

        move_request = game.decision_queue.peek()
        confirm_option = None
        for opt in list(move_request.options or []):
            if str((opt.payload or {}).get("action", "") or "") == "confirm":
                confirm_option = opt
                break
        self.assertIsNotNone(confirm_option)
        model_positions = [
            {
                "model_id": get_entity_id(target_model_a),
                "position": [10.0, 0.0, 0.0],
                "facing": 0.0,
            },
            {
                "model_id": get_entity_id(target_model_b),
                "position": [12.0, 0.0, 0.0],
                "facing": 0.0,
            },
        ]
        resolve_decision_command(
            game,
            move_request,
            confirm_option.option_id,
            result_payload={"model_positions": model_positions},
            player_id=p2.id,
        )

        self.assertTrue(target.brazen_fury_used_this_phase(game))


if __name__ == "__main__":
    unittest.main()
