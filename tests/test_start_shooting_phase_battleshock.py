import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestStartShootingPhaseBattleshock(unittest.TestCase):
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

    def _make_model(self, name, unit):
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
        model.set_location(0.0, 0.0, 0.0, 0.0)
        return model

    def test_start_shooting_phase_visible_battleshock_queues_and_applies(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 2

        ability_desc = (
            "At the start of your Shooting phase, select one enemy unit within 24\" of and visible to this model. "
            "That enemy unit must take a Battle-shock test."
        )
        ability = Ability("Bale Gaze", "AE", ability_desc, "Datasheet", "")

        unit = self._make_unit("Seer", army, faction_keywords=["AELDARI"])
        model = self._make_model("Seer", unit)
        model.abilities = {"Bale Gaze": ability}
        unit.models = [model]
        unit._has_line_of_sight_to_target = lambda _model, _target, _map: True

        target_unit = self._make_unit("Target", enemy_army)
        target_model = self._make_model("Target", target_unit)
        target_model.set_location(10.0, 0.0, 0.0, 0.0)
        target_unit.models = [target_model]
        target_unit.battleshock_turns = []

        def _take_battleshock(turn):
            target_unit.battleshock_turns.append(int(turn))

        target_unit.take_battle_shock_test = _take_battleshock

        army.units = [unit]
        enemy_army.units = [target_unit]
        game.rebuild_entity_registry()

        game._on_phase_start_shooting_phase_visible_battleshock(player=player, phase=game.phase)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "start_shooting_phase_visible_battleshock")

        resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)

        self.assertEqual(target_unit.battleshock_turns, [2])
