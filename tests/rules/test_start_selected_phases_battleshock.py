import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestStartSelectedPhasesBattleshock(unittest.TestCase):
    def _make_unit(self, name, army, *, keywords=None, faction_keywords=None):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = getattr(army, "faction_id", "")
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models = []
        unit.models_lost = []
        unit.keywords = list(keywords or [])
        unit.faction_keywords = list(faction_keywords or [])
        unit.possible_abilities = []
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace(num_lost_models_this_round=0)
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.get_attached_unit_members = lambda: [unit]
        unit.is_in_reserves = lambda: False
        unit.has_any_keyword = lambda kw: any(
            str(kw or "").strip().upper() == str(k or "").strip().upper()
            for k in (unit.keywords + unit.faction_keywords)
        )
        return unit

    def _make_model(self, name, unit, *, x=0.0, y=0.0):
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
        model.set_location(float(x), float(y), 0.0, 0.0)
        return model

    def _build_game(self):
        army = Army.with_detachment("Necrons", detachment_type="Other")
        army.faction_id = "NEC"
        enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"

        player = Player("Necrons", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        return game, army, enemy_army, player, enemy_player

    def _harbinger_description(self):
        return (
            "Once per turn, at the start of your Command, Movement, Shooting, Charge or Fight phase, "
            "you can select one enemy unit within 18\" of this model. That unit must take a Battle-shock test, "
            "subtracting 1 from the test when it does so."
        )

    def test_parses_start_selected_phases_enemy_range_battleshock_spec(self):
        unit = self._make_unit("Psychomancer", Army.with_detachment("Necrons", detachment_type="Other"))
        model = self._make_model("Psychomancer", unit)
        ability = Ability("Harbinger of Despair", "NEC", self._harbinger_description(), "Datasheet", "")
        model.abilities = {"Harbinger of Despair": ability}
        unit.models = [model]

        specs = unit.model_start_selected_phases_enemy_range_battleshock_specs(model)
        self.assertEqual(len(specs), 1)
        spec = specs[0]
        self.assertEqual(int(spec.get("range", 0) or 0), 18)
        self.assertEqual(int(spec.get("test_penalty", 0) or 0), 1)
        self.assertEqual(
            list(spec.get("phase_names", []) or []),
            ["COMMAND_PHASE", "MOVEMENT_PHASE", "SHOOTING_PHASE", "CHARGE_PHASE", "FIGHT_PHASE"],
        )
        self.assertTrue(bool(spec.get("optional", False)))
        self.assertTrue(bool(spec.get("once_per_turn", False)))

    def test_queues_and_applies_battleshock_then_blocks_second_phase_same_turn(self):
        game, army, enemy_army, player, _enemy_player = self._build_game()
        game.turn = 2
        game.current_player_index = 0
        game.phase = BattleRoundPhases.COMMAND_PHASE

        ability = Ability("Harbinger of Despair", "NEC", self._harbinger_description(), "Datasheet", "")
        source = self._make_unit("Psychomancer", army, faction_keywords=["NECRONS"])
        source_model = self._make_model("Psychomancer", source, x=0.0, y=0.0)
        source_model.abilities = {"Harbinger of Despair": ability}
        source.models = [source_model]

        target = self._make_unit("Enemy Target", enemy_army, faction_keywords=["ENEMY"])
        target_model = self._make_model("Enemy", target, x=10.0, y=0.0)
        target.models = [target_model]
        target_calls = []
        target.take_battle_shock_test = lambda current_turn=1: target_calls.append(int(current_turn))

        army.units = [source]
        enemy_army.units = [target]
        game.rebuild_entity_registry()

        specs = source.model_start_selected_phases_enemy_range_battleshock_specs(source_model)
        self.assertEqual(len(specs), 1)
        ability_key = str(specs[0].get("ability_key", "") or "")

        game.event_system.publish("phase_start", player=player, phase=game.phase)

        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(str(request.decision_type), DECISION_CHOOSE_QUARRY)
        self.assertEqual(str((request.context or {}).get("ability", "")), "harbinger_of_despair_battleshock")
        self.assertTrue(any(str((opt.payload or {}).get("action", "")) == "skip" for opt in list(request.options or [])))

        target_option = next(
            opt for opt in list(request.options or []) if str((opt.payload or {}).get("target_unit_id", "")) == str(target._id)
        )
        outcome = resolve_decision_command(game, request, target_option.option_id, player_id=player.id)
        self.assertTrue(bool(getattr(outcome, "ok", False)))

        self.assertEqual(target_calls, [2])
        sr = dict(getattr(target, "special_rules", {}) or {})
        self.assertEqual(int(sr.get("battle_shock_test_modifier", 0) or 0), -1)
        self.assertIn("Harbinger of Despair: -1", list(sr.get("battle_shock_test_modifier_reasons", []) or []))
        self.assertTrue(source_model.has_used_once_per_battle_round(ability_key, battle_round=2))

        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.event_system.publish("phase_start", player=player, phase=game.phase)
        remaining = [
            req
            for req in list(game.decision_queue.list() or [])
            if str((getattr(req, "context", {}) or {}).get("ability", "")) == "harbinger_of_despair_battleshock"
        ]
        self.assertEqual(remaining, [])

    def test_skip_does_not_consume_and_can_be_used_in_later_phase_same_turn(self):
        game, army, enemy_army, player, _enemy_player = self._build_game()
        game.turn = 3
        game.current_player_index = 0
        game.phase = BattleRoundPhases.COMMAND_PHASE

        ability = Ability("Harbinger of Despair", "NEC", self._harbinger_description(), "Datasheet", "")
        source = self._make_unit("Psychomancer", army, faction_keywords=["NECRONS"])
        source_model = self._make_model("Psychomancer", source, x=0.0, y=0.0)
        source_model.abilities = {"Harbinger of Despair": ability}
        source.models = [source_model]

        target = self._make_unit("Enemy Target", enemy_army, faction_keywords=["ENEMY"])
        target_model = self._make_model("Enemy", target, x=10.0, y=0.0)
        target.models = [target_model]
        target.take_battle_shock_test = lambda current_turn=1: None

        army.units = [source]
        enemy_army.units = [target]
        game.rebuild_entity_registry()

        specs = source.model_start_selected_phases_enemy_range_battleshock_specs(source_model)
        self.assertEqual(len(specs), 1)
        ability_key = str(specs[0].get("ability_key", "") or "")

        game.event_system.publish("phase_start", player=player, phase=game.phase)
        request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str((getattr(req, "context", {}) or {}).get("ability", "")) == "harbinger_of_despair_battleshock"
        )
        skip_option = next(opt for opt in list(request.options or []) if str((opt.payload or {}).get("action", "")) == "skip")
        skip_result = resolve_decision_command(game, request, skip_option.option_id, player_id=player.id)
        self.assertTrue(bool(getattr(skip_result, "ok", False)))
        self.assertFalse(source_model.has_used_once_per_battle_round(ability_key, battle_round=3))

        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.event_system.publish("phase_start", player=player, phase=game.phase)
        pending_later = [
            req
            for req in list(game.decision_queue.list() or [])
            if str((getattr(req, "context", {}) or {}).get("ability", "")) == "harbinger_of_despair_battleshock"
        ]
        self.assertEqual(len(pending_later), 1)


if __name__ == "__main__":
    unittest.main()
