import unittest
from unittest.mock import patch
from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestYesNoOptionalAbilityDecisions(unittest.TestCase):
    def _make_unit(self, name, army, *, keywords=None, faction_keywords=None, abilities=None):
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
        unit.possible_abilities = list(abilities or [])
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace(num_lost_models_this_round=0)
        unit.models_lost = []
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.has_any_keyword = lambda kw: any(
            str(kw or "").strip().upper() == str(k or "").strip().upper()
            for k in (unit.keywords + unit.faction_keywords)
        )
        return unit

    def _make_model(self, name, unit, *, wounds: int = 2):
        model = Model(
            name=name,
            movement=6,
            toughness=4,
            save=3,
            wounds=int(wounds),
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

    def test_shadow_in_the_warp_queues_and_applies(self):
        tyr_army = Army("Tyranids", detachment_type="Other")
        tyr_army.faction_id = "TYR"
        enemy_army = Army("Enemies", detachment_type="Other")
        enemy_army.faction_id = "SM"

        tyr_player = Player("Tyr", PlayerControl.REMOTE, army=tyr_army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield, players=[tyr_player, enemy_player])
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0

        synapse = self._make_unit(
            "Synapse",
            tyr_army,
            faction_keywords=["TYRANIDS"],
            abilities=[Ability("Shadow in the Warp", "TYR", "", "")],
        )
        tyr_army.units = [synapse]

        game._maybe_prompt_shadow_in_the_warp()

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "shadow_in_the_warp")

        self._resolve_yes(game, request, tyr_player)

        self.assertTrue(tyr_army.shadow_in_the_warp.used_this_battle)

    def test_waaagh_queues_and_applies(self):
        ork_army = Army("Orks", detachment_type="Other")
        ork_army.faction_id = "ORK"
        enemy_army = Army("Enemies", detachment_type="Other")
        enemy_army.faction_id = "SM"

        ork_player = Player("Ork", PlayerControl.REMOTE, army=ork_army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield, players=[ork_player, enemy_player])
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0

        mgr = ork_army.waaagh
        if mgr is not None:
            mgr._army_has_waaagh = lambda: True

        game._maybe_prompt_waaagh()

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "waaagh")

        self._resolve_yes(game, request, ork_player)

        self.assertTrue(mgr.used_this_battle)
        self.assertTrue(mgr.active)
        self.assertIs(mgr.called_player, ork_player)

    def test_possessed_lord_queues_and_applies(self):
        army = Army("Chaos", detachment_type="Other")
        army.faction_id = "CSM"
        player = Player("Chaos", PlayerControl.REMOTE, army=army)
        other_army = Army("Enemies", detachment_type="Other")
        other_player = Player("Enemy", PlayerControl.REMOTE, army=other_army)

        battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield, players=[player, other_player])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        unit = self._make_unit(
            "Possessed Lord Unit",
            army,
            abilities=[Ability("Possessed Lord", "CSM", "", "")],
        )
        model = self._make_model("Possessed Lord", unit)
        unit.models = [model]
        army.units = [unit]
        game.rebuild_entity_registry()

        game._on_phase_start_optional_abilities(player=player, phase=game.phase)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "possessed_lord")
        self.assertEqual(ctx.get("model_id"), get_entity_id(model))

        self._resolve_yes(game, request, player)

        self.assertTrue(model.has_used_once_per_battle("possessed_lord"))

    def test_fight_phase_melee_ap_boost_queues_and_applies(self):
        army = Army("Test", detachment_type="Other")
        army.faction_id = "TEST"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        ability_desc = (
            "Once per battle, at the start of the Fight phase, this model can use this ability. If it does, until the "
            "end of the phase, add 3 to the Attacks characteristic of melee weapons equipped by this model and improve "
            "the Armour Penetration characteristic of those weapons by 1."
        )
        ability = Ability("Ruinous Assault", "TEST", ability_desc, "Datasheet", "")
        unit = self._make_unit("Ruinous Assault Unit", army, abilities=[ability])
        model = self._make_model("Ruinous Assault Model", unit)
        unit.models = [model]
        army.units = [unit]
        game.rebuild_entity_registry()

        game._on_phase_start_optional_abilities(player=player, phase=game.phase)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "fight_phase_melee_ap_boost")
        self.assertEqual(ctx.get("model_id"), get_entity_id(model))

        self._resolve_yes(game, request, player)

        self.assertEqual(int(model.get_temporary_melee_attacks_bonus()), 3)
        self.assertEqual(int(model.get_temporary_melee_ap_bonus()), 1)

    def test_movement_phase_normal_move_weapon_attacks_bonus_queues_and_applies(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0

        ability_desc = (
            "Once per battle, in your Movement phase, before this model makes a Normal move, it can use this ability. "
            "If it does, until the end of the turn, add 2D6\" to this model's Move characteristic and add 3 to the "
            "Attacks characteristic of this model's Solitaire weapons."
        )
        ability = Ability("Blitz", "AE", ability_desc, "Datasheet", "")
        unit = self._make_unit("Solitaire Unit", army, abilities=[ability])
        model = self._make_model("Solitaire", unit)
        unit.models = [model]
        army.units = [unit]
        game.rebuild_entity_registry()

        game._queue_movement_phase_normal_move_weapon_attacks_bonus(player=player, unit=unit)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "movement_phase_move_weapon_bonus")
        self.assertEqual(ctx.get("model_id"), get_entity_id(model))

        self._resolve_yes(game, request, player)

        bonus = int(model.get_temporary_movement_bonus() or 0)
        self.assertGreaterEqual(bonus, 2)
        self.assertLessEqual(bonus, 12)
        weapon_bonus, _reasons = model.get_temporary_weapon_attacks_bonus("Solitaire weapons")
        self.assertEqual(int(weapon_bonus), 3)
        buff_key = str(ctx.get("buff_key") or "")
        if buff_key:
            self.assertTrue(model.has_used_once_per_battle(buff_key))

    def test_flickerjump_queues_and_applies(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0

        ability_desc = (
            "In your Movement phase, each time this unit is selected to make a Normal move, it can use this ability. "
            "If it does, until the end of the turn, this unit is not eligible to declare a charge and models in it have "
            "a Move characteristic of 24\". Each time this unit uses this ability, at the end of the phase, roll one D6 "
            "for each model in this unit: for each 1, this unit suffers 1 mortal wound."
        )
        ability = Ability("Flickerjump", "AE", ability_desc, "Datasheet", "")
        unit = self._make_unit("Warp Spiders", army, abilities=[ability])
        model_a = self._make_model("Spider A", unit, wounds=1)
        model_b = self._make_model("Spider B", unit, wounds=1)
        unit.models = [model_a, model_b]
        army.units = [unit]
        game.rebuild_entity_registry()

        game._queue_movement_phase_flickerjump(player=player, unit=unit)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "flickerjump")
        self.assertEqual(ctx.get("unit_id"), get_entity_id(unit))

        self._resolve_yes(game, request, player)

        self.assertEqual(int(model_a.movement), 24)
        sr = getattr(unit, "special_rules", {}) or {}
        self.assertEqual(int(sr.get("flickerjump_move_set_value", 0) or 0), 24)
        self.assertEqual(int(sr.get("flickerjump_pending_uses", 0) or 0), 1)

        game.is_authoritative = False
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=1):
            game._on_phase_end_flickerjump_mortal_wounds(player=player, phase=game.phase)

        alive = [m for m in unit.models if m.is_alive]
        self.assertEqual(len(alive), 0)

    def test_power_from_pain_command_phase_queues_and_applies(self):
        army = Army("Drukhari", detachment_type="Other")
        army.faction_id = "DRU"
        enemy_army = Army("Enemies", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Drukhari", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0

        mgr = army.power_from_pain
        if mgr is None:
            self.skipTest("Power from Pain manager unavailable")
        mgr.has_command_phase_action = lambda **_kw: True
        mgr._resolved = False

        def _resolve_action(**_kw):
            mgr._resolved = True

        mgr.resolve_command_phase_action = _resolve_action

        game._maybe_prompt_power_from_pain_command_phase()

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "power_from_pain_command")

        self._resolve_yes(game, request, player)
        self.assertTrue(mgr._resolved)

    def test_enhancement_fight_first_queues_and_applies(self):
        army = Army("Test", detachment_type="Other")
        army.faction_id = "SM"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "CSM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        unit = self._make_unit("Enhanced", army)
        unit.enhancement = SimpleNamespace(name="Test Enhancement")
        unit.has_enhancement_fight_first_once_per_battle = lambda: True
        unit.can_use_enhancement_fight_first = lambda: True
        unit._activated = False
        unit.activate_enhancement_fight_first = lambda: setattr(unit, "_activated", True)
        army.units = [unit]
        game.rebuild_entity_registry()

        game._on_phase_start_optional_abilities(player=player, phase=game.phase)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "enhancement_fight_first")
        self.assertEqual(ctx.get("unit_id"), get_entity_id(unit))

        self._resolve_yes(game, request, player)
        self.assertTrue(unit._activated)

    def test_opponent_turn_strategic_reserves_queues_and_applies(self):
        army = Army("Owner", detachment_type="Other")
        army.faction_id = "SM"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "CSM"

        owner = Player("Owner", PlayerControl.REMOTE, army=army)
        enemy = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[owner, enemy])
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0

        unit = self._make_unit("Reserves Unit", army)
        unit.get_end_of_opponent_turn_strategic_reserves_ability = lambda: {"name": "Strategic Reserves"}
        unit.enter_strategic_reserves_midgame = lambda **_kw: setattr(unit, "_entered", True) or True
        unit._entered = False

        enemy_unit = self._make_unit("Enemy Unit", enemy_army)
        unit.models = [self._make_model("Model", unit)]
        enemy_unit.models = [self._make_model("Enemy Model", enemy_unit)]
        enemy_unit.models[0].set_location(40.0, 0.0, 0.0, 0.0)

        army.units = [unit]
        enemy_army.units = [enemy_unit]
        game.map.units = [unit, enemy_unit]
        game.rebuild_entity_registry()

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "opponent_turn_strategic_reserves")
        self.assertEqual(ctx.get("unit_id"), get_entity_id(unit))

        self._resolve_yes(game, request, owner)
        self.assertTrue(unit._entered)

    def test_seductive_gambit_queues_and_applies(self):
        army = Army("Daemons", detachment_type="Other")
        army.faction_id = "DAE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Daemons", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.CHARGE_PHASE
        game.current_player_index = 0

        unit = self._make_unit("Slaanesh Unit", army, faction_keywords=["SLAANESH"])
        army.units = [unit]
        game.rebuild_entity_registry()

        army.chaos_daemons_detachments = SimpleNamespace(seductive_gambit_applies=lambda _u: True)

        game._on_unit_move_ended_detachment_rules(unit=unit, action="charge")

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "seductive_gambit")
        self.assertEqual(ctx.get("unit_id"), get_entity_id(unit))

        self._resolve_yes(game, request, player)
        self.assertTrue(unit.special_rules.get("seductive_gambit_active"))

    def test_sensational_performance_queues_and_applies(self):
        army = Army("Emperors Children", detachment_type="Other")
        army.faction_id = "EC"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("EC", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        unit = self._make_unit("EC Unit", army)
        unit.round_state.charged_this_round = True
        army.units = [unit]
        game.rebuild_entity_registry()

        army.emperors_children_detachments = SimpleNamespace(sensational_performance_applies=lambda _u: True)

        game._on_fight_unit_selected_emperors_children(unit=unit)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "sensational_performance")
        self.assertEqual(ctx.get("unit_id"), get_entity_id(unit))

        self._resolve_yes(game, request, player)
        self.assertTrue(unit.special_rules.get("sensational_performance_active"))

    def test_cult_ambush_queues_and_applies(self):
        army = Army("GSC", detachment_type="Other")
        army.faction_id = "GC"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("GSC", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        unit = self._make_unit("Cult Unit", army)
        army.units = [unit]
        game.rebuild_entity_registry()

        mgr = SimpleNamespace(
            can_spend_for_unit=lambda _u: True,
            resurgence_cost_for_unit=lambda _u: 2,
            resurgence_points=4,
            handle_unit_destroyed=lambda _u, **_kw: setattr(unit, "_ambush_used", True),
        )
        army.cult_ambush = mgr
        unit._ambush_used = False

        game._on_unit_destroyed_cult_ambush(unit=unit)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "cult_ambush")
        self.assertEqual(ctx.get("unit_id"), get_entity_id(unit))

        self._resolve_yes(game, request, player)
        self.assertTrue(unit._ambush_used)

    def test_battle_focus_sudden_strike_queues_and_applies(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Aeldari", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        unit = self._make_unit("Aspect", army, keywords=["ASURYANI"])
        army.units = [unit]
        game.rebuild_entity_registry()

        mgr = army.battle_focus
        if mgr is None:
            self.skipTest("Battle Focus manager unavailable")
        mgr.tokens = 1
        mgr._army_has_battle_focus = lambda: True
        mgr._unit_has_battle_focus = lambda _u: True
        mgr._can_use_unit_this_phase = lambda _u: True
        mgr._maneuver_used_this_phase = lambda _m: False

        mgr.maybe_trigger_sudden_strike(unit, game)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "battle_focus_sudden_strike")
        self.assertEqual(ctx.get("unit_id"), get_entity_id(unit))

        self._resolve_yes(game, request, player)
        self.assertEqual(unit.special_rules.get("battle_focus_sudden_strike_expires_phase"), "FIGHT_PHASE")


if __name__ == "__main__":
    unittest.main()
