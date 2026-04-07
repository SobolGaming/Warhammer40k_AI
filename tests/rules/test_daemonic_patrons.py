import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE, DECISION_CONFIRM_YES_NO
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestDaemonicPatrons(unittest.TestCase):
    def _make_unit(self, name, army, *, abilities=None):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = getattr(army, "faction_id", "")
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models = []
        unit.models_lost = []
        unit.keywords = []
        unit.faction_keywords = []
        unit.possible_abilities = list(abilities or [])
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        unit.is_alive = lambda: True
        unit.is_in_reserves = lambda: False
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_members = lambda: [unit]
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.has_any_keyword = lambda kw: False
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

    def _resolve_yes(self, game, request, player):
        option_id = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)):
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)
        resolve_decision_command(game, request, option_id, player_id=player.id)

    def test_daemonic_patrons_prompt_and_apply(self):
        army = Army.with_detachment("Chaos", detachment_type="Other")
        army.faction_id = "CSM"
        enemy_army = Army.with_detachment("Enemies", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Chaos", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        ability_desc = (
            "Each time this unit is selected to fight, it can call upon daemonic patrons. "
            "If it does, until the end of the phase, each time a model in this unit makes an attack, "
            "an unmodified Wound roll of 3+ scores a Critical Wound. At the end of the Fight phase, "
            "if this unit called upon daemonic patrons this phase and no enemy models were destroyed "
            "by attacks made by models in this unit this phase, one model in this unit is destroyed."
        )
        ability = Ability("Daemonic Patrons", "CSM", ability_desc, "Datasheet", "")
        unit = self._make_unit("Daemonic Patrons Unit", army, abilities=[ability])
        model = self._make_model("Daemonic Model", unit)
        unit.models = [model]
        army.units = [unit]
        game.rebuild_entity_registry()

        game._on_fight_unit_selected_daemonic_patrons(unit=unit)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        self.assertEqual((request.context or {}).get("ability"), "daemonic_patrons")

        self._resolve_yes(game, request, player)

        sr = unit.special_rules
        self.assertTrue(sr.get("daemonic_patrons_active"))
        self.assertEqual(int(sr.get("daemonic_patrons_crit_wound_threshold", 0)), 3)

    def test_daemonic_patrons_end_phase_loss(self):
        army = Army.with_detachment("Chaos", detachment_type="Other")
        army.faction_id = "CSM"
        enemy_army = Army.with_detachment("Enemies", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Chaos", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        unit = self._make_unit("Daemonic Patrons Unit", army)
        model_a = self._make_model("Model A", unit)
        model_b = self._make_model("Model B", unit)
        unit.models = [model_a, model_b]
        unit.special_rules = {
            "daemonic_patrons_active": True,
            "daemonic_patrons_called": True,
            "daemonic_patrons_expires_phase": "FIGHT_PHASE",
            "daemonic_patrons_source": "Daemonic Patrons",
        }
        army.units = [unit]
        game.rebuild_entity_registry()

        game._on_phase_end_daemonic_patrons(phase=game.phase)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_ALLOCATE_DAMAGE)
        self.assertEqual((request.context or {}).get("selection_kind"), "daemonic_patrons_loss")

        died = {"called": False}

        def _die(game_map=None):
            died["called"] = True

        model_a.die = _die
        model_b.die = _die

        option_id = request.options[0].option_id
        resolve_decision_command(game, request, option_id, player_id=player.id)
        self.assertTrue(died["called"])

    def test_daemonic_patrons_no_loss_when_kill_recorded(self):
        army = Army.with_detachment("Chaos", detachment_type="Other")
        army.faction_id = "CSM"
        enemy_army = Army.with_detachment("Enemies", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Chaos", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        unit = self._make_unit("Daemonic Patrons Unit", army)
        model = self._make_model("Model", unit)
        unit.models = [model]
        unit.special_rules = {
            "daemonic_patrons_active": True,
            "daemonic_patrons_called": True,
            "daemonic_patrons_expires_phase": "FIGHT_PHASE",
            "daemonic_patrons_source": "Daemonic Patrons",
        }
        army.units = [unit]
        game.rebuild_entity_registry()

        unit_id = get_entity_id(unit)
        game._phase_enemy_model_destroyers["FIGHT_PHASE"] = {unit_id}

        game._on_phase_end_daemonic_patrons(phase=game.phase)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 0)
