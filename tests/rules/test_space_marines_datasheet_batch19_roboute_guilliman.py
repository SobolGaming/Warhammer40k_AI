from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.aura_effects import get_aura_battleshock_test_reroll_sources
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.turn = 1
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, sm_army, enemy_army, sm_player, enemy_player


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _find_request(game: Game, decision_type: str, *, ability: str | None = None, target_slot: str | None = None):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if ability is not None and str(ctx.get("ability", "") or "") != str(ability):
            continue
        slot = str(ctx.get("target_slot", "") or "primary").strip().lower() or "primary"
        if target_slot is not None and slot != str(target_slot):
            continue
        return request
    return None


def _find_option_for_choice_keys(request, choice_keys: tuple[str, str]):
    expected = list(choice_keys)
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if list(payload.get("choice_keys", []) or []) == expected:
            return option
    return None


def _find_option_for_target(request, target_unit_id: str):
    target_id = str(target_unit_id or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return option
    return None


def _ability(unit: Unit, name: str):
    return next(ab for ab in list(getattr(unit, "possible_abilities", []) or []) if getattr(ab, "name", "") == name)


def test_roboute_guilliman_author_of_the_codex_is_queued_before_oath_of_moment() -> None:
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    roboute = _actual_unit("Roboute Guilliman", datasheet_id="000000138")
    enemy_primary = _actual_unit("Outrider Squad", datasheet_id="000002712")
    enemy_backup = _actual_unit("Scout Squad", datasheet_id="000001160")
    sm_army.add_unit(roboute)
    enemy_army.add_unit(enemy_primary)
    enemy_army.add_unit(enemy_backup)
    _deploy(roboute, 10.0, 10.0)
    _deploy(enemy_primary, 20.0, 10.0)
    _deploy(enemy_backup, 24.0, 10.0)
    game.map.units = [roboute, enemy_primary, enemy_backup]
    game.rebuild_entity_registry()

    game.start_command_phase()

    requests = list(game.decision_queue.list() or [])
    author_idx = next(
        idx for idx, request in enumerate(requests)
        if str((getattr(request, "context", {}) or {}).get("ability", "") or "") == "author_of_the_codex"
    )
    oath_idx = next(
        idx for idx, request in enumerate(requests)
        if str((getattr(request, "context", {}) or {}).get("ability", "") or "") == "oath_of_moment"
        and str((getattr(request, "context", {}) or {}).get("target_slot", "") or "primary").strip().lower() == "primary"
    )
    assert author_idx < oath_idx


def test_roboute_guilliman_selected_author_of_the_codex_abilities_gate_aura_and_cp_discount() -> None:
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    roboute = _actual_unit("Roboute Guilliman", datasheet_id="000000138")
    ally = _actual_unit("Intercessor Squad", datasheet_id="000001157")
    enemy_primary = _actual_unit("Outrider Squad", datasheet_id="000002712")
    enemy_backup = _actual_unit("Scout Squad", datasheet_id="000001160")
    sm_army.add_unit(roboute)
    sm_army.add_unit(ally)
    enemy_army.add_unit(enemy_primary)
    enemy_army.add_unit(enemy_backup)
    _deploy(roboute, 10.0, 10.0)
    _deploy(ally, 13.0, 10.0)
    _deploy(enemy_primary, 24.0, 10.0)
    _deploy(enemy_backup, 28.0, 10.0)
    game.map.units = [roboute, ally, enemy_primary, enemy_backup]
    game.rebuild_entity_registry()

    base_oc = int(ally.objective_control)
    assert get_aura_battleshock_test_reroll_sources(ally, game_map=game.map) == []
    preview_discount, preview_names, _preview_specs = sm_player._preview_targeted_stratagem_cp_discount(target_unit=ally)
    assert preview_discount == 0
    assert preview_names == []

    game.start_command_phase()
    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="author_of_the_codex")
    assert request is not None
    option = _find_option_for_choice_keys(request, ("PRIMARCH_OF_THE_XIII", "SUPREME_STRATEGIST"))
    assert option is not None
    result = resolve_decision_command(game, request, option.option_id, player_id=sm_player.id)
    assert bool(getattr(result, "ok", False)) is True

    primarch = _ability(roboute, "Primarch of the XIII (Aura)")
    master = _ability(roboute, "Master of Battle")
    strategist = _ability(roboute, "Supreme Strategist")
    assert roboute._ability_is_active(primarch) is True
    assert roboute._ability_is_active(master) is False
    assert roboute._ability_is_active(strategist) is True

    assert int(ally.objective_control) == base_oc + 1
    reroll_sources = get_aura_battleshock_test_reroll_sources(ally, game_map=game.map)
    assert "Primarch of the XIII (Aura)" in reroll_sources
    preview_discount, preview_names, _preview_specs = sm_player._preview_targeted_stratagem_cp_discount(target_unit=ally)
    assert preview_discount == 1
    assert "Supreme Strategist" in preview_names


def test_roboute_guilliman_master_of_battle_selects_backup_target_and_promotes_it() -> None:
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    roboute = _actual_unit("Roboute Guilliman", datasheet_id="000000138")
    enemy_primary = _actual_unit("Outrider Squad", datasheet_id="000002712")
    enemy_backup = _actual_unit("Scout Squad", datasheet_id="000001160")
    sm_army.add_unit(roboute)
    enemy_army.add_unit(enemy_primary)
    enemy_army.add_unit(enemy_backup)
    _deploy(roboute, 10.0, 10.0)
    _deploy(enemy_primary, 20.0, 10.0)
    _deploy(enemy_backup, 24.0, 10.0)
    game.map.units = [roboute, enemy_primary, enemy_backup]
    game.rebuild_entity_registry()

    game.start_command_phase()

    author_request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="author_of_the_codex")
    assert author_request is not None
    author_option = _find_option_for_choice_keys(author_request, ("MASTER_OF_BATTLE", "SUPREME_STRATEGIST"))
    assert author_option is not None
    author_result = resolve_decision_command(game, author_request, author_option.option_id, player_id=sm_player.id)
    assert bool(getattr(author_result, "ok", False)) is True

    primary_request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="oath_of_moment", target_slot="primary")
    assert primary_request is not None
    primary_option = _find_option_for_target(primary_request, str(get_entity_id(enemy_primary) or ""))
    assert primary_option is not None
    primary_result = resolve_decision_command(game, primary_request, primary_option.option_id, player_id=sm_player.id)
    assert bool(getattr(primary_result, "ok", False)) is True

    backup_request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="oath_of_moment", target_slot="backup")
    assert backup_request is not None
    backup_option = _find_option_for_target(backup_request, str(get_entity_id(enemy_backup) or ""))
    assert backup_option is not None
    backup_result = resolve_decision_command(game, backup_request, backup_option.option_id, player_id=sm_player.id)
    assert bool(getattr(backup_result, "ok", False)) is True

    mgr = getattr(sm_army, "oath_of_moment", None)
    assert mgr is not None
    enemy_primary_id = str(get_entity_id(enemy_primary) or "")
    enemy_backup_id = str(get_entity_id(enemy_backup) or "")
    assert str(getattr(mgr, "oathOfMomentTargetUnitId", "") or "") == enemy_primary_id
    assert str(getattr(mgr, "oathOfMomentBackupTargetUnitId", "") or "") == enemy_backup_id
    assert mgr.is_oath_target(enemy_backup) is False

    promoted = mgr.on_oath_target_destroyed(enemy_primary, game=game, player=sm_player)

    assert promoted is True
    assert str(getattr(mgr, "oathOfMomentTargetUnitId", "") or "") == enemy_backup_id
    assert str(getattr(mgr, "oathOfMomentBackupTargetUnitId", "") or "") == ""
    assert mgr.is_oath_target(enemy_backup) is True
