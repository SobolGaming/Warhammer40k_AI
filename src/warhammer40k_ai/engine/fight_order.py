from __future__ import annotations

from ..utility.calcs import clear_enemy_model_cache
from ..utility.entity_ids import get_entity_id


def _reset_fight_phase_eligibility_flags(manager, current_player, opponent_player) -> None:
    seen: set[str] = set()
    for player in (current_player, opponent_player):
        if player is None:
            continue
        army = player.get_army() if hasattr(player, "get_army") else None
        if army is None:
            continue
        units = getattr(army, "units", None)
        if not isinstance(units, (list, tuple, set)):
            continue
        for unit in list(units or []):
            if unit is None:
                continue
            try:
                root = manager._canonical_unit_for_fight(unit)
            except Exception:
                root = unit
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "")
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            try:
                root.round_state.eligible_to_fight_this_phase = False
            except Exception:
                pass


def _mark_units_eligible_to_fight_this_phase(manager, units) -> None:
    for unit in list(units or []):
        if unit is None:
            continue
        try:
            root = manager._canonical_unit_for_fight(unit)
        except Exception:
            root = unit
        if root is None:
            continue
        try:
            root.round_state.eligible_to_fight_this_phase = True
        except Exception:
            pass


def _get_eligible_units_for_player(manager, player):
    if manager.current_stage.name == "FIGHT_FIRST":
        all_units = manager.game.get_fight_first_units(player)
    elif manager.current_stage.name == "REMAINING_COMBATANTS":
        all_units = manager.game.get_remaining_combatant_units(player)
    else:
        return []

    roots = []
    seen = set()
    for unit in list(all_units or []):
        try:
            root = manager._canonical_unit_for_fight(unit)
        except Exception:
            root = unit
        if root is None:
            continue
        root_id = get_entity_id(root)
        if root_id in seen:
            continue
        seen.add(root_id)
        try:
            if root in manager.fought_units:
                continue
        except Exception:
            pass
        try:
            if not root.is_alive():
                continue
        except Exception:
            continue
        roots.append(root)
    manager._mark_units_eligible_to_fight_this_phase(roots)
    return roots


def _is_forced_unit_valid(manager, unit) -> bool:
    if unit is None:
        return False
    try:
        if unit in manager.fought_units:
            return False
    except Exception:
        pass
    try:
        if not unit.is_alive():
            return False
    except Exception:
        pass
    try:
        if not unit.is_eligible_to_fight(manager.game.map):
            return False
    except Exception:
        pass
    return True


def _switch_active_player(manager, current_player, opponent_player) -> None:
    manager.active_player = opponent_player if manager.active_player == current_player else current_player
    clear_enemy_model_cache(manager.game.map)
    manager._request_unit_selection(current_player, opponent_player)
