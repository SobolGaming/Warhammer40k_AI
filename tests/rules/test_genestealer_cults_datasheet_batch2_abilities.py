from __future__ import annotations

from types import MethodType

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
    DECISION_REQUEST_DICE_ROLL,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.cult_ambush import CultAmbushManager, CultAmbushMarker
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, faction_id: str) -> Unit:
    return Unit(_WAHA.get_datasheet(name, faction_id=faction_id))


def _build_game() -> tuple[Game, Player, Player, Army, Army]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    gsc_army = Army.with_detachment("Genestealer Cults", "Other")
    gsc_army.faction_id = "GC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ORK"

    gsc_player = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(gsc_player)
    game.add_player(enemy_player)
    return game, gsc_player, enemy_player, gsc_army, enemy_army


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard


def _find_request(game: Game, *, decision_type: str, ability: str):
    ability_key = str(ability or "").strip().lower()
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != decision_type:
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() != ability_key:
            continue
        return request
    return None


def _resolve_pending_roll(game: Game, player: Player, *, fixed_dice: list[int]) -> None:
    request = _find_request(
        game,
        decision_type=DECISION_REQUEST_DICE_ROLL,
        ability="",
    )
    if request is None:
        for pending in list(game.decision_queue.list() or []):
            if str(getattr(pending, "decision_type", "") or "") == DECISION_REQUEST_DICE_ROLL:
                request = pending
                break
    assert request is not None
    roll_id = int(((request.context or {}).get("roll_id", 0) or 0))
    assert roll_id > 0
    state = game.roll_manager.get_roll(roll_id)
    state.spec["fixed_dice"] = list(fixed_dice)
    resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)


def test_atalan_jackals_demolition_run_queues_target_and_rolls_per_atalan_jackal() -> None:
    game, gsc_player, _enemy_player, gsc_army, enemy_army = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0
    game.auto_resolve_dice_rolls = False

    jackals = _actual_unit("Atalan Jackals", faction_id="GC")
    enemy = _actual_unit("Boyz", faction_id="ORK")
    gsc_army.add_unit(jackals)
    enemy_army.add_unit(enemy)
    _deploy(jackals, 0.0, 0.0)
    _deploy(enemy, 5.0, 0.0)
    _register_units(game, jackals, enemy)

    jackals._attacking_unit_has_any_los_to_target_unit = lambda _target, _game_map: True

    specs = jackals.unit_grenade_pack_flyover_specs()
    assert len(specs) == 1
    spec = specs[0]
    assert str(spec.get("source", "") or "") == "Demolition Run"
    assert int(spec.get("range", 0) or 0) == 6
    assert int(spec.get("threshold", 0) or 0) == 4
    assert int(spec.get("max_mortal", 0) or 0) == 6
    assert bool(spec.get("trigger_on_setup", True)) is False
    assert str(spec.get("model_keyword", "") or "").strip().lower() == "atalan jackals"

    applied: dict[str, int] = {}

    def _apply(self, target_unit, amount, game_map=None):
        target_name = str(getattr(target_unit, "name", "") or "Unit")
        applied[target_name] = applied.get(target_name, 0) + int(amount or 0)
        return 0

    jackals._apply_mortal_wounds_to_unit = MethodType(_apply, jackals)

    game._on_unit_set_up_grenade_pack_flyover(unit=jackals)
    assert not list(game.decision_queue.list() or [])

    game._on_unit_move_ended_grenade_pack_flyover(unit=jackals, action="advance")

    request = _find_request(game, decision_type=DECISION_CHOOSE_QUARRY, ability="grenade_pack_flyover")
    assert request is not None

    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == str(getattr(enemy, "id", enemy._id) or enemy._id)
        or str((opt.payload or {}).get("target_unit_id", "") or "") == str(enemy._id)
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=gsc_player.id)
    assert bool(getattr(result, "ok", False)) is True

    roll_request = next(
        pending
        for pending in list(game.decision_queue.list() or [])
        if str(getattr(pending, "decision_type", "") or "") == DECISION_REQUEST_DICE_ROLL
    )
    roll_ctx = dict(getattr(roll_request, "context", {}) or {})
    roll_id = int(roll_ctx.get("roll_id", 0) or 0)
    assert roll_id > 0
    roll_state = game.roll_manager.get_roll(roll_id)
    assert int((roll_state.spec or {}).get("dice_count", 0) or 0) == 5

    _resolve_pending_roll(game, gsc_player, fixed_dice=[4, 4, 2, 5, 1])

    assert applied.get("Boyz", 0) == 3


def test_atalan_jackals_outrider_gangs_requires_cult_ambush_setup_near_battlefield_edge() -> None:
    game, _gsc_player, _enemy_player, gsc_army, _enemy_army = _build_game()
    game.turn = 2

    jackals = _actual_unit("Atalan Jackals", faction_id="GC")
    gsc_army.add_unit(jackals)
    game.map.units = []
    game.rebuild_entity_registry()

    jackals._cult_ambush = True
    jackals.deployed = True
    jackals.reserve_status = "strategic_reserves"
    jackals.embarked_in = None
    jackals.can_arrive_from_reserves = lambda _turn: True

    manager = CultAmbushManager(gsc_army)
    gsc_army.cult_ambush = manager

    center_marker = CultAmbushMarker(
        marker_id="center",
        x=float(game.map.width) / 2.0,
        y=float(game.map.height) / 2.0,
        z=0.0,
        active=True,
    )
    manager.markers = [center_marker]
    assert manager.deploy_unit_from_marker(jackals, center_marker, game=game) is False
    assert bool(center_marker.active) is True
    assert str(getattr(jackals, "reserve_status", "") or "") == "strategic_reserves"

    edge_marker = CultAmbushMarker(
        marker_id="edge",
        x=3.0,
        y=float(game.map.height) / 2.0,
        z=0.0,
        active=True,
    )
    manager.markers = [edge_marker]
    assert manager.deploy_unit_from_marker(jackals, edge_marker, game=game) is True
    assert bool(edge_marker.active) is False
    assert str(getattr(jackals, "reserve_status", "") or "") == "deployed"

    for model in list(getattr(jackals, "models", []) or []):
        x, y, _z, _facing = model.get_location()
        radius = float(model.model_base.get_longest_radius())
        min_edge_distance = min(
            float(x),
            float(y),
            float(game.map.width) - float(x),
            float(game.map.height) - float(y),
        )
        assert min_edge_distance + radius <= 9.0 + 1e-6


def test_benefictus_psionic_shield_queues_once_per_battle_phase_invulnerable_save() -> None:
    game, gsc_player, _enemy_player, gsc_army, _enemy_army = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0

    benefictus = _actual_unit("Benefictus", faction_id="GC")
    gsc_army.add_unit(benefictus)
    _deploy(benefictus, 0.0, 0.0)
    _register_units(game, benefictus)

    game._on_phase_start_optional_abilities(phase=game.phase)

    request = next(
        pending
        for pending in list(game.decision_queue.list() or [])
        if str(getattr(pending, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str(((pending.context or {}).get("ability_name", "") or "")).strip() == "Psionic Shield (Psychic)"
    )
    option = next(opt for opt in list(request.options or []) if bool((opt.payload or {}).get("choice", False)))
    result = resolve_decision_command(game, request, option.option_id, player_id=gsc_player.id)
    assert bool(getattr(result, "ok", False)) is True

    model = benefictus.models[0]
    invuln_value, invuln_source = model.get_temporary_invulnerable_save()
    assert int(invuln_value or 0) == 4
    assert "Psionic Shield" in str(invuln_source or "")

    buff_key = str(((request.context or {}).get("buff_key", "") or "")).strip()
    assert buff_key
    assert bool(model.has_used_once_per_battle(buff_key)) is True

    game._on_phase_start_optional_abilities(phase=game.phase)
    duplicate = [
        pending
        for pending in list(game.decision_queue.list() or [])
        if str(getattr(pending, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str(((pending.context or {}).get("ability_name", "") or "")).strip() == "Psionic Shield (Psychic)"
    ]
    assert duplicate == []


def test_biophagus_loadout_parses_injector_goad_and_alchemicus_familiar() -> None:
    biophagus = _actual_unit("Biophagus", faction_id="GC")
    model = biophagus.models[0]

    wargear_names = sorted(str(getattr(wg, "name", "") or "") for wg in list(getattr(model, "wargear", []) or []))
    assert "Injector goad" in wargear_names
    assert "Autopistol" in wargear_names
    assert "Chemical vials" in wargear_names

    optional_wargear = list(getattr(model, "optional_wargear", []) or [])
    assert "Alchemicus Familiar" in optional_wargear


def test_biophagus_biological_warfare_queues_and_applies_injector_goad_attacks_and_damage_bonus() -> None:
    game, gsc_player, _enemy_player, gsc_army, enemy_army = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0

    aberrants = _actual_unit("Aberrants", faction_id="GC")
    biophagus = _actual_unit("Biophagus", faction_id="GC")
    enemy = _actual_unit("Boyz", faction_id="ORK")
    _attach_leader(aberrants, biophagus)

    gsc_army.add_unit(aberrants)
    gsc_army.add_unit(biophagus)
    enemy_army.add_unit(enemy)
    _deploy(aberrants, 0.0, 0.0)
    _deploy(biophagus, 0.5, 0.5)
    _deploy(enemy, 1.0, 0.0)
    _register_units(game, aberrants, biophagus, enemy)

    game._on_fight_unit_selected_biological_warfare(unit=aberrants, selecting_player=gsc_player)

    request = _find_request(game, decision_type=DECISION_CONFIRM_YES_NO, ability="biological_warfare")
    assert request is not None
    option = next(opt for opt in list(request.options or []) if bool((opt.payload or {}).get("choice", False)))
    result = resolve_decision_command(game, request, option.option_id, player_id=gsc_player.id)
    assert bool(getattr(result, "ok", False)) is True

    leader_model = biophagus.models[0]
    attacks_bonus, _attack_reasons = leader_model.get_temporary_weapon_attacks_bonus("Injector goad")
    damage_bonus, _damage_reasons = leader_model.get_temporary_weapon_damage_bonus("Injector goad")
    assert int(attacks_bonus or 0) == 3
    assert int(damage_bonus or 0) == 3
    assert bool(leader_model.has_used_once_per_battle("fight_selected_weapon_attacks_damage_bonus:biological warfare")) is True

    game._on_fight_unit_selected_biological_warfare(unit=aberrants, selecting_player=gsc_player)
    assert _find_request(game, decision_type=DECISION_CONFIRM_YES_NO, ability="biological_warfare") is None


def test_biophagus_alchemicus_familiar_applies_bearers_unit_wound_bonus_vs_infantry_only() -> None:
    game, gsc_player, _enemy_player, gsc_army, enemy_army = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0

    aberrants = _actual_unit("Aberrants", faction_id="GC")
    biophagus = _actual_unit("Biophagus", faction_id="GC")
    infantry_enemy = _actual_unit("Boyz", faction_id="ORK")
    vehicle_enemy = _actual_unit("Deff Dread", faction_id="ORK")
    _attach_leader(aberrants, biophagus)

    gsc_army.add_unit(aberrants)
    gsc_army.add_unit(biophagus)
    enemy_army.add_unit(infantry_enemy)
    enemy_army.add_unit(vehicle_enemy)
    _deploy(aberrants, 0.0, 0.0)
    _deploy(biophagus, 0.5, 0.5)
    _deploy(infantry_enemy, 1.0, 0.0)
    _deploy(vehicle_enemy, 2.0, 0.0)
    _register_units(game, aberrants, biophagus, infantry_enemy, vehicle_enemy)

    game._on_fight_unit_selected_alchemicus_familiar(unit=aberrants, selecting_player=gsc_player)

    request = _find_request(game, decision_type=DECISION_CONFIRM_YES_NO, ability="alchemicus_familiar")
    assert request is not None
    option = next(opt for opt in list(request.options or []) if bool((opt.payload or {}).get("choice", False)))
    result = resolve_decision_command(game, request, option.option_id, player_id=gsc_player.id)
    assert bool(getattr(result, "ok", False)) is True

    bodyguard_model = next(
        model
        for model in list(getattr(aberrants, "models", []) or [])
        if any(bool(getattr(wg, "is_melee", lambda: False)()) for wg in list(getattr(model, "wargear", []) or []))
    )
    bodyguard_weapon = next(
        str(getattr(wg, "name", "") or "")
        for wg in list(getattr(bodyguard_model, "wargear", []) or [])
        if bool(getattr(wg, "is_melee", lambda: False)())
    )
    leader_model = biophagus.models[0]
    bodyguard_infantry_bonus, _ = bodyguard_model.get_temporary_weapon_wound_bonus(
        bodyguard_weapon,
        target=infantry_enemy,
    )
    bodyguard_vehicle_bonus, _ = bodyguard_model.get_temporary_weapon_wound_bonus(
        bodyguard_weapon,
        target=vehicle_enemy,
    )
    leader_infantry_bonus, _ = leader_model.get_temporary_weapon_wound_bonus(
        "Injector goad",
        target=infantry_enemy,
    )

    assert int(bodyguard_infantry_bonus or 0) == 1
    assert int(bodyguard_vehicle_bonus or 0) == 0
    assert int(leader_infantry_bonus or 0) == 1
    assert bool(leader_model.has_used_once_per_battle("fight_selected_unit_target_keyword_wound_bonus:alchemicus familiar")) is True


def test_clamavus_voice_of_new_truths_parses_and_queues_battleshock_target_selection() -> None:
    game, gsc_player, _enemy_player, gsc_army, enemy_army = _build_game()
    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0

    clamavus = _actual_unit("Clamavus", faction_id="GC")
    enemy = _actual_unit("Boyz", faction_id="ORK")
    target_calls: list[int] = []
    enemy.take_battle_shock_test = lambda current_turn=1: target_calls.append(int(current_turn))

    gsc_army.add_unit(clamavus)
    enemy_army.add_unit(enemy)
    _deploy(clamavus, 0.0, 0.0)
    _deploy(enemy, 10.0, 0.0)
    _register_units(game, clamavus, enemy)

    specs = clamavus.model_start_selected_phases_enemy_range_battleshock_specs(clamavus.models[0])
    assert len(specs) == 1
    spec = specs[0]
    assert int(spec.get("range", 0) or 0) == 18
    assert bool(spec.get("optional", False)) is True
    assert bool(spec.get("once_per_turn", True)) is False
    assert str(spec.get("context_ability", "") or "") == "command_phase_select_enemy_battleshock"
    assert str(spec.get("army_usage_scope", "") or "") == "battle_round"
    assert str(spec.get("army_usage_key", "") or "") == "COMMAND_PHASE_SELECT_ENEMY_BATTLESHOCK:VOICE_OF_NEW_TRUTHS"

    game.event_system.publish("phase_start", player=gsc_player, phase=game.phase)

    request = _find_request(game, decision_type=DECISION_CHOOSE_QUARRY, ability="command_phase_select_enemy_battleshock")
    assert request is not None
    assert str(((request.context or {}).get("army_usage_key", "") or "")).strip() == "COMMAND_PHASE_SELECT_ENEMY_BATTLESHOCK:VOICE_OF_NEW_TRUTHS"
    skip_option = next(
        opt for opt in list(request.options or []) if str((opt.payload or {}).get("action", "") or "") == "skip"
    )
    assert skip_option is not None
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(enemy) or "")
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=gsc_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert target_calls == [2]
    assert int(gsc_player._ability_used_battle_round.get("COMMAND_PHASE_SELECT_ENEMY_BATTLESHOCK:VOICE_OF_NEW_TRUTHS", 0) or 0) == 2

    game.event_system.publish("phase_start", player=gsc_player, phase=game.phase)
    assert _find_request(game, decision_type=DECISION_CHOOSE_QUARRY, ability="command_phase_select_enemy_battleshock") is None


def test_clamavus_voice_of_new_truths_uses_single_grouped_request_across_multiple_models() -> None:
    game, gsc_player, _enemy_player, gsc_army, enemy_army = _build_game()
    game.turn = 3
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0

    clamavus_a = _actual_unit("Clamavus", faction_id="GC")
    clamavus_b = _actual_unit("Clamavus", faction_id="GC")
    enemy_a = _actual_unit("Boyz", faction_id="ORK")
    enemy_b = _actual_unit("Boyz", faction_id="ORK")

    gsc_army.add_unit(clamavus_a)
    gsc_army.add_unit(clamavus_b)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)
    _deploy(clamavus_a, 0.0, 0.0)
    _deploy(clamavus_b, 40.0, 0.0)
    _deploy(enemy_a, 10.0, 0.0, spacing=0.0)
    _deploy(enemy_b, 50.0, 0.0, spacing=0.0)
    _register_units(game, clamavus_a, clamavus_b, enemy_a, enemy_b)

    game.event_system.publish("phase_start", player=gsc_player, phase=game.phase)

    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str(((req.context or {}).get("ability", "") or "")).strip().lower() == "command_phase_select_enemy_battleshock"
    ]
    assert len(requests) == 1

    request = requests[0]
    target_payloads = [
        dict((opt.payload or {}))
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "").strip()
    ]
    assert len(target_payloads) == 2
    assert {
        str(payload.get("model_id", "") or "")
        for payload in target_payloads
    } == {
        str(get_entity_id(clamavus_a.models[0]) or ""),
        str(get_entity_id(clamavus_b.models[0]) or ""),
    }


def test_goliath_rockgrinder_grinding_clearance_flags_desperate_escape_rule() -> None:
    rockgrinder = _actual_unit("Goliath Rockgrinder", faction_id="GC")
    sr = dict(getattr(rockgrinder, "special_rules", {}) or {})
    assert bool(sr.get("enemy_fallback_desperate_escape")) is True
    assert bool(sr.get("enemy_fallback_desperate_escape_exclude_monster_vehicle")) is True
    assert int(sr.get("enemy_fallback_desperate_escape_bs_penalty", 0) or 0) == 1
