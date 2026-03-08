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


class TestFightPhaseSelectEngagementBattleshock(unittest.TestCase):
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
        army = Army("Tyranids", detachment_type="Other")
        army.faction_id = "TYR"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"

        player = Player("Tyranids", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        return game, army, enemy_army, player, enemy_player

    @staticmethod
    def _mandatory_description():
        return (
            "At the start of the Fight phase, select one enemy unit within Engagement Range of this model. "
            "That enemy unit must take a Battle-shock test."
        )

    @staticmethod
    def _optional_description():
        return (
            "At the start of the Fight phase, you can select one enemy unit within Engagement Range of this model. "
            "That enemy unit must take a Battle-shock test."
        )

    @staticmethod
    def _find_engagement_request(game):
        for req in list(game.decision_queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") == "fight_phase_select_engagement_battleshock":
                return req
        return None

    def test_parses_fight_phase_select_engagement_battleshock_spec(self):
        unit = self._make_unit("Parasite", Army("Tyranids", detachment_type="Other"))
        model = self._make_model("Parasite of Mortrex", unit)
        ability = Ability("Terror Aura", "TYR", self._mandatory_description(), "Datasheet", "")
        model.abilities = {"Terror Aura": ability}
        unit.models = [model]

        specs = unit.model_start_fight_phase_select_engagement_battleshock_specs(model)
        self.assertEqual(len(specs), 1)
        spec = specs[0]
        self.assertTrue(bool(spec.get("engagement_only", False)))
        self.assertFalse(bool(spec.get("optional", True)))
        self.assertEqual(int(spec.get("test_penalty", 0) or 0), 0)
        self.assertEqual(str(spec.get("context_ability", "") or ""), "fight_phase_select_engagement_battleshock")

    def test_queues_and_applies_mandatory_fight_phase_selection(self):
        game, army, enemy_army, player, _enemy_player = self._build_game()
        game.turn = 2
        game.current_player_index = 0
        game.phase = BattleRoundPhases.FIGHT_PHASE

        ability = Ability("Terror Aura", "TYR", self._mandatory_description(), "Datasheet", "")
        source = self._make_unit("Parasite", army, faction_keywords=["TYRANIDS"])
        source_model = self._make_model("Parasite of Mortrex", source, x=0.0, y=0.0)
        source_model.abilities = {"Terror Aura": ability}
        source.models = [source_model]

        target = self._make_unit("Enemy Target", enemy_army, faction_keywords=["ENEMY"])
        target_model = self._make_model("Enemy", target, x=2.5, y=0.0)
        target.models = [target_model]
        target_calls = []
        target.take_battle_shock_test = lambda current_turn=1: target_calls.append(int(current_turn))

        army.units = [source]
        enemy_army.units = [target]
        game.rebuild_entity_registry()

        game.event_system.publish("phase_start", player=player, phase=game.phase)
        request = self._find_engagement_request(game)
        self.assertIsNotNone(request)
        self.assertFalse(
            any(str((opt.payload or {}).get("action", "")) == "skip" for opt in list(request.options or []))
        )

        target_option = next(
            opt for opt in list(request.options or []) if str((opt.payload or {}).get("target_unit_id", "")) == str(target._id)
        )
        outcome = resolve_decision_command(game, request, target_option.option_id, player_id=player.id)
        self.assertTrue(bool(getattr(outcome, "ok", False)))
        self.assertEqual(target_calls, [2])
        self.assertNotIn("battle_shock_test_modifier", dict(getattr(target, "special_rules", {}) or {}))

    def test_invalid_when_target_is_no_longer_in_engagement_range(self):
        game, army, enemy_army, player, _enemy_player = self._build_game()
        game.turn = 3
        game.current_player_index = 0
        game.phase = BattleRoundPhases.FIGHT_PHASE

        ability = Ability("Terror Aura", "TYR", self._mandatory_description(), "Datasheet", "")
        source = self._make_unit("Parasite", army, faction_keywords=["TYRANIDS"])
        source_model = self._make_model("Parasite of Mortrex", source, x=0.0, y=0.0)
        source_model.abilities = {"Terror Aura": ability}
        source.models = [source_model]

        target = self._make_unit("Enemy Target", enemy_army, faction_keywords=["ENEMY"])
        target_model = self._make_model("Enemy", target, x=2.5, y=0.0)
        target.models = [target_model]
        target_calls = []
        target.take_battle_shock_test = lambda current_turn=1: target_calls.append(int(current_turn))

        army.units = [source]
        enemy_army.units = [target]
        game.rebuild_entity_registry()

        game.event_system.publish("phase_start", player=player, phase=game.phase)
        request = self._find_engagement_request(game)
        self.assertIsNotNone(request)
        target_option = next(
            opt for opt in list(request.options or []) if str((opt.payload or {}).get("target_unit_id", "")) == str(target._id)
        )

        target_model.set_location(20.0, 0.0, 0.0, 0.0)
        outcome = resolve_decision_command(game, request, target_option.option_id, player_id=player.id)
        self.assertFalse(bool(getattr(outcome, "ok", False)))
        errors = [str(e or "") for e in list(getattr(outcome, "errors", []) or [])]
        self.assertTrue(any("Engagement Range" in err for err in errors))
        self.assertEqual(target_calls, [])

        still_pending = self._find_engagement_request(game)
        self.assertIsNotNone(still_pending)

    def test_optional_wording_includes_none_option(self):
        game, army, enemy_army, player, _enemy_player = self._build_game()
        game.turn = 1
        game.current_player_index = 0
        game.phase = BattleRoundPhases.FIGHT_PHASE

        ability = Ability("Terror Aura", "TYR", self._optional_description(), "Datasheet", "")
        source = self._make_unit("Parasite", army, faction_keywords=["TYRANIDS"])
        source_model = self._make_model("Parasite of Mortrex", source, x=0.0, y=0.0)
        source_model.abilities = {"Terror Aura": ability}
        source.models = [source_model]

        target = self._make_unit("Enemy Target", enemy_army, faction_keywords=["ENEMY"])
        target_model = self._make_model("Enemy", target, x=2.5, y=0.0)
        target.models = [target_model]
        target.take_battle_shock_test = lambda current_turn=1: None

        army.units = [source]
        enemy_army.units = [target]
        game.rebuild_entity_registry()

        game.event_system.publish("phase_start", player=player, phase=game.phase)
        request = self._find_engagement_request(game)
        self.assertIsNotNone(request)
        self.assertTrue(any(str((opt.payload or {}).get("action", "")) == "skip" for opt in list(request.options or [])))

    def test_queues_for_non_active_player_owner(self):
        game, army, enemy_army, player, enemy_player = self._build_game()
        game.turn = 4
        game.current_player_index = 0
        game.phase = BattleRoundPhases.FIGHT_PHASE

        source = self._make_unit("Player Unit", army, faction_keywords=["TYRANIDS"])
        source_model = self._make_model("Player Model", source, x=0.0, y=0.0)
        source.models = [source_model]

        ability = Ability("Terror Aura", "EN", self._mandatory_description(), "Datasheet", "")
        enemy_source = self._make_unit("Enemy Parasite", enemy_army, faction_keywords=["ENEMY"])
        enemy_model = self._make_model("Enemy Parasite", enemy_source, x=2.5, y=0.0)
        enemy_model.abilities = {"Terror Aura": ability}
        enemy_source.models = [enemy_model]

        army.units = [source]
        enemy_army.units = [enemy_source]
        game.rebuild_entity_registry()

        game.event_system.publish("phase_start", player=player, phase=game.phase)
        request = self._find_engagement_request(game)
        self.assertIsNotNone(request)
        self.assertEqual(str(getattr(request, "player_id", "") or ""), str(enemy_player.id))


if __name__ == "__main__":
    unittest.main()
