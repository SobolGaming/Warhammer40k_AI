import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
    DECISION_MOVE_UNIT,
    DECISION_USE_MODEL_UNMODIFIED_SIX,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, faction_keywords=None, model_count=1):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Leagues of Votann"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["LEAGUES OF VOTANN"])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name, *, abilities=None, keywords=None, faction_keywords=None, model_count=1):
    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
    )
    return Unit(datasheet)


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army.with_detachment("Leagues of Votann", "Detachment")
    army1.faction_id = "LOV"
    army2 = Army.with_detachment("Enemy", "Detachment")
    army2.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


def _first_option_with(request, predicate):
    for opt in list(request.options or []):
        if predicate(getattr(opt, "payload", {}) or {}):
            return opt
    return None


class TestVotannBatch3Abilities(unittest.TestCase):
    def test_ancestral_fortune_spends_yp_to_set_hit_roll_to_unmodified_six(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability = {
            "name": "Ancestral Fortune",
            "description": (
                "Once per turn, you can spend 1 YP to change the result of one hit roll, "
                "one wound roll or one saving throw made for this model to an unmodified 6."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Kahl", abilities=[ability])
        target = _make_unit("Enemy Unit")
        army.add_unit(attacker)
        enemy_army.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, target]

        pe = getattr(army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)
        pe.add_yield_points(2, game=game)
        player.set_next_optional_selection("MODEL_UNMODIFIED_SIX", "use")

        parent = SimpleNamespace(name="Autoch-pattern bolter", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="default",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )
        hit = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )

        self.assertEqual(int(hit.get("roll", 0) or 0), 6)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 1)
        specs = list(attacker.model_once_per_battle_unmodified_six_specs(attacker.models[0]) or [])
        self.assertTrue(specs)
        self.assertTrue(attacker.models[0].has_used_once_per_battle_round(specs[0]["key"]))

    def test_ancestral_fortune_reuses_immediately_resolved_decision_request(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability = {
            "name": "Ancestral Fortune",
            "description": (
                "Once per turn, you can spend 1 YP to change the result of one hit roll, "
                "one wound roll or one saving throw made for this model to an unmodified 6."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Kahl", abilities=[ability])
        target = _make_unit("Enemy Unit")
        army.add_unit(attacker)
        enemy_army.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, target]

        pe = getattr(army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)
        pe.add_yield_points(2, game=game)

        seen_decisions = []
        original_request_decision = game.request_decision

        def _auto_resolve(request):
            seen_decisions.append(str(getattr(request, "decision_type", "") or ""))
            original_request_decision(request)
            use_option = next(
                opt
                for opt in list(request.options or [])
                if str((getattr(opt, "payload", {}) or {}).get("choice", "") or "") == "use"
            )
            resolve_decision_command(game, request, use_option.option_id, player_id=player.id)

        game.request_decision = _auto_resolve

        parent = SimpleNamespace(name="Autoch-pattern bolter", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="default",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )
        hit = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )

        self.assertIn(DECISION_USE_MODEL_UNMODIFIED_SIX, seen_decisions)
        self.assertEqual(int(hit.get("roll", 0) or 0), 6)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 1)

    def test_ancestral_fortune_local_provider_still_emits_decision(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        player.control = PlayerControl.LOCAL
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability = {
            "name": "Ancestral Fortune",
            "description": (
                "Once per turn, you can spend 1 YP to change the result of one hit roll, "
                "one wound roll or one saving throw made for this model to an unmodified 6."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Kahl", abilities=[ability])
        target = _make_unit("Enemy Unit")
        army.add_unit(attacker)
        enemy_army.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, target]
        game.rebuild_entity_registry()

        pe = getattr(army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)
        pe.add_yield_points(2, game=game)

        seen_decisions = []

        def _capture(request):
            seen_decisions.append(str(getattr(request, "decision_type", "") or ""))
            game.decision_queue.add(request)

        def _apply(command):
            payload = dict(getattr(command, "payload", {}) or {})
            request = game.decision_queue.get(str(payload.get("decision_id", "") or ""))
            option_id = str(payload.get("option_id", "") or "")
            option = next(
                opt for opt in list(getattr(request, "options", []) or []) if str(getattr(opt, "option_id", "") or "") == option_id
            )
            resolved_payload = dict(getattr(option, "payload", {}) or {})
            apply_result = SimpleNamespace(ok=True, value=resolved_payload)
            setattr(request, "_resolved_decision_value", resolved_payload)
            setattr(request, "_resolved_decision_apply_result", apply_result)
            game.decision_queue.pop(request.decision_id)
            return SimpleNamespace(value=apply_result)

        game.request_decision = _capture
        game.apply_command = _apply
        game.map.model_unmodified_six_provider = lambda **_kwargs: "use"

        parent = SimpleNamespace(name="Autoch-pattern bolter", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="default",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )
        hit = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )

        self.assertIn(DECISION_USE_MODEL_UNMODIFIED_SIX, seen_decisions)
        self.assertEqual(int(hit.get("roll", 0) or 0), 6)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 1)

    def test_computational_mastermind_can_spend_yp_before_mode_update(self):
        game, army, _enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0
        game.turn = 2

        ability = {
            "name": "Computational Mastermind",
            "description": "Command phase objective marker YP adjustment.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Kahl", abilities=[ability])
        army.add_unit(unit)
        unit.deployed = True
        unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        game.map.units = [unit]

        objective_point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
        objective = Objective(
            "Home Objective",
            ObjectiveCategory.PRIMARY,
            0,
            "",
            lambda _game: False,
            location=objective_point,
        )
        game.map.objectives = [objective]

        pe = getattr(army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)
        pe.add_yield_points(1, game=game)
        player.set_next_optional_selection("computational_mastermind", {str(get_entity_id(objective)): "spend"})

        delta = int(game._resolve_computational_mastermind_before_mode(player) or 0)
        self.assertEqual(delta, -1)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 0)

    def test_forgewrought_expertise_repairs_target_and_marks_once_per_turn(self):
        game, army, _enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0
        game.turn = 3

        ability = {
            "name": "Forgewrought Expertise",
            "description": (
                "At the end of your Movement phase, this unit can repair one friendly Leagues of Votann Vehicle, "
                "Exoframe or Ironkin Steeljacks unit within 3\". If it does, that unit regains up to D3 lost wounds. "
                "If this unit contains an Ironkin Assistant model, that unit regains up to 3 lost wounds instead. "
                "Each unit can only be repaired once per turn."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        source = _make_unit("Brôkhyr Iron-master", abilities=[ability])
        source.models[0].name = "Ironkin Assistant"
        target = _make_unit("Hekaton Land Fortress", keywords=["VEHICLE"])
        army.add_unit(source)
        army.add_unit(target)

        source.deployed = True
        target.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(2.0, 0.0, 0.0, 0.0)
        target.models[0].wounds = 1
        game.map.units = [source, target]

        game._on_phase_end_forgewrought_expertise(player=player, phase=BattleRoundPhases.MOVEMENT_PHASE)

        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if req.decision_type == DECISION_CHOOSE_QUARRY
            and str((req.context or {}).get("ability", "")) == "forgewrought_expertise"
        ]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        target_option = _first_option_with(request, lambda payload: str(payload.get("target_unit_id", "")) == str(get_entity_id(target)))
        self.assertIsNotNone(target_option)

        resolve_decision_command(game, request, target_option.option_id, player_id=player.id)

        self.assertEqual(int(target.models[0].wounds or 0), int(target.models[0]._base_wounds or 0))
        tsr = dict(getattr(target, "special_rules", {}) or {})
        self.assertEqual(str(tsr.get("forgewrought_expertise_repaired_turn_owner", "")), str(player.id))
        self.assertEqual(int(tsr.get("forgewrought_expertise_repaired_turn", 0) or 0), int(game.turn))

    def test_geomantic_hunters_applies_breacher_ordnance_wound_reroll(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability = {
            "name": "Geomantic Hunters",
            "description": (
                "Twice per battle, in your Shooting phase, when this unit is selected to shoot, it can use this ability. "
                "If it does, each time a model in this unit makes an attack with a Breacher ordnance weapon, "
                "you can re-roll the Wound roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Brôkhyr Thunderkyn", abilities=[ability])
        target = _make_unit("Enemy Unit")
        army.add_unit(attacker)
        enemy_army.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, target]

        game._on_shooting_targets_selected_geomantic_hunters(attacking_unit=attacker, target_units=[target])
        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if req.decision_type == DECISION_CONFIRM_YES_NO
            and str((req.context or {}).get("ability", "")) == "geomantic_hunters"
        ]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        yes_opt = _first_option_with(request, lambda payload: bool(payload.get("choice", False)))
        self.assertIsNotNone(yes_opt)

        resolve_decision_command(game, request, yes_opt.option_id, player_id=player.id)
        self.assertEqual(int(attacker.geomantic_hunters_uses() or 0), 1)

        parent = SimpleNamespace(name="Breacher ordnance", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="default",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
            wound = profile._wound_target_with_tracking(
                target,
                attacker.models[0],
                {"_aura_attack_mods": _aura_stub()},
                roll_value=1,
                allow_rerolls=True,
                log_roll=False,
            )

        self.assertEqual(int(wound.get("reroll", 0) or 0), 5)
        self.assertIn("Geomantic Hunters", " ".join(list(wound.get("reroll_full_reasons", []) or [])))

    def test_multiwave_comms_array_refunds_cp_on_5_plus(self):
        game, army, _enemy_army, player, _enemy_player = _build_game()

        ability = {
            "name": "Multiwave Comms Array",
            "description": "Each time you target this unit with a Stratagem, roll one D6: on a 5+, gain 1CP.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Hernkyn Yaegirs", abilities=[ability])
        army.add_unit(unit)
        unit.deployed = True
        game.map.units = [unit]

        player.command_points = 2
        player._pending_stratagem_target_unit_id = str(get_entity_id(unit) or "")
        player._pending_stratagem_name = "Rapid Fire"

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=6):
            ok = bool(player.spend_command_points(1, reason="Stratagem: Rapid Fire", source="stratagem"))

        self.assertTrue(ok)
        self.assertEqual(int(player.command_points or 0), 2)

    def test_resource_transmutation_spend_then_gain_choice(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability = {
            "name": "Resource Transmutation",
            "description": "In your Shooting phase, spend 1 YP when this unit is selected to shoot.",
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Brôkhyr Iron-master", abilities=[ability])
        target = _make_unit("Enemy Unit")
        army.add_unit(attacker)
        enemy_army.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, target]

        pe = getattr(army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)
        pe.add_yield_points(1, game=game)

        game._on_shooting_targets_selected_resource_transmutation(attacking_unit=attacker, target_units=[target])
        pending_confirm = [
            req
            for req in list(game.decision_queue.list() or [])
            if req.decision_type == DECISION_CONFIRM_YES_NO
            and str((req.context or {}).get("ability", "")) == "resource_transmutation"
        ]
        self.assertEqual(len(pending_confirm), 1)
        confirm_req = pending_confirm[0]
        yes_opt = _first_option_with(confirm_req, lambda payload: bool(payload.get("choice", False)))
        self.assertIsNotNone(yes_opt)

        resolve_decision_command(game, confirm_req, yes_opt.option_id, player_id=player.id)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 0)

        target.models[0].wounds = 0
        target.models = []
        game._on_unit_shooting_resolved_resource_transmutation(
            attacker_unit=attacker,
            killing_models_by_target={target: [attacker.models[0]]},
        )

        pending_gain = [
            req
            for req in list(game.decision_queue.list() or [])
            if req.decision_type == DECISION_CHOOSE_QUARRY
            and str((req.context or {}).get("ability", "")) == "resource_transmutation_gain"
        ]
        self.assertEqual(len(pending_gain), 1)
        gain_req = pending_gain[0]
        gain_two = _first_option_with(gain_req, lambda payload: int(payload.get("gain_yp", 0) or 0) == 2)
        self.assertIsNotNone(gain_two)

        resolve_decision_command(game, gain_req, gain_two.option_id, player_id=player.id)

        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 2)
        sr = dict(getattr(attacker, "special_rules", {}) or {})
        self.assertEqual(str(sr.get("resource_transmutation_gain_resolved_turn_owner", "")), str(player.id))
        self.assertEqual(int(sr.get("resource_transmutation_gain_resolved_turn", 0) or 0), int(game.turn))

    def test_seized_opportunity_optional_gain_once_per_phase(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game.turn = 2

        ability = {
            "name": "Seized Opportunity",
            "description": "Each time this unit destroys an enemy unit, you can gain 1 YP once per phase.",
            "type": "Datasheet",
            "parameter": "",
        }
        source = _make_unit("Kahl", abilities=[ability])
        victim = _make_unit("Enemy Unit")
        army.add_unit(source)
        enemy_army.add_unit(victim)
        source.deployed = True
        victim.deployed = True

        game._on_unit_destroyed_seized_opportunity(unit=victim, destroyed_by_unit=source)
        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if req.decision_type == DECISION_CONFIRM_YES_NO
            and str((req.context or {}).get("ability", "")) == "seized_opportunity"
        ]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        yes_opt = _first_option_with(request, lambda payload: bool(payload.get("choice", False)))
        self.assertIsNotNone(yes_opt)

        resolve_decision_command(game, request, yes_opt.option_id, player_id=player.id)

        pe = getattr(army, "prioritised_efficiency", None)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 1)
        self.assertTrue(player._ability_used_this_phase("seized_opportunity"))

    def test_unhinged_vengeance_confirmation_queues_move_and_marks_used(self):
        game, army, enemy_army, player, enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1

        attacker = _make_unit("Enemy Shooters")
        ability = {
            "name": "Unhinged Vengeance",
            "description": (
                "In your opponent's Shooting phase, each time this model loses one or more wounds after an enemy unit has shot, "
                "this unit can make an Unhinged Vengeance move."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        defender = _make_unit("World Eaters Hero", abilities=[ability])
        army.add_unit(attacker)
        enemy_army.add_unit(defender)
        attacker.deployed = True
        defender.deployed = True
        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        defender.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, defender]

        game._on_shooting_targets_selected_unhinged_vengeance(attacking_unit=attacker, target_units=[defender])
        defender.models[0].wounds = max(1, int(defender.models[0].wounds or 0) - 1)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
            game._on_unit_shooting_resolved_unhinged_vengeance(attacker_unit=attacker)

        pending_confirm = [
            req
            for req in list(game.decision_queue.list() or [])
            if req.decision_type == DECISION_CONFIRM_YES_NO
            and str((req.context or {}).get("reactive_move_kind", "")) == "unhinged_vengeance"
        ]
        self.assertEqual(len(pending_confirm), 1)
        confirm_req = pending_confirm[0]
        self.assertEqual(str(confirm_req.player_id), str(enemy_player.id))
        yes_opt = _first_option_with(confirm_req, lambda payload: bool(payload.get("choice", False)))
        self.assertIsNotNone(yes_opt)

        resolve_decision_command(game, confirm_req, yes_opt.option_id, player_id=enemy_player.id)

        pending_move = [
            req
            for req in list(game.decision_queue.list() or [])
            if req.decision_type == DECISION_MOVE_UNIT
            and str((req.context or {}).get("movement_type", "")) == "unhinged_vengeance"
        ]
        self.assertEqual(len(pending_move), 1)
        move_req = pending_move[0]
        move_ctx = dict(move_req.context or {})
        self.assertTrue(bool(move_ctx.get("reactive_move_allow_engagement_range", False)))

        confirm_move = _first_option_with(move_req, lambda payload: str(payload.get("action", "")) == "confirm")
        self.assertIsNotNone(confirm_move)
        model = defender.models[0]
        x, y, z, facing = model.get_location()
        resolve_decision_command(
            game,
            move_req,
            confirm_move.option_id,
            player_id=enemy_player.id,
            result_payload={
                "model_positions": [
                    {
                        "model_id": get_entity_id(model),
                        "position": [float(x), float(y), float(z)],
                        "facing": float(facing),
                    }
                ]
            },
        )

        self.assertTrue(defender.unhinged_vengeance_used_this_phase(game))


if __name__ == "__main__":
    unittest.main()
