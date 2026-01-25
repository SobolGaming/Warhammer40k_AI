from __future__ import annotations

from typing import Optional

from .dice_rolls import DiceRollState, register_roll_handler


def _get_unit(game: object, unit_id: Optional[str]):
    if not unit_id:
        return None
    registry = getattr(game, "entity_registry", None)
    if registry is None:
        registry = None
    try:
        if registry is not None:
            found = registry.get(str(unit_id), kind="unit")
            if found is not None:
                return found
    except Exception:
        pass
    try:
        game_map = getattr(game, "map", None)
        for unit in list(getattr(game_map, "units", []) or []):
            try:
                from ..utility.entity_ids import get_entity_id
                if str(get_entity_id(unit)) == str(unit_id):
                    return unit
            except Exception:
                continue
    except Exception:
        pass
    try:
        players = list(getattr(game, "players", []) or [])
        from ..utility.entity_ids import get_entity_id
        for player in players:
            try:
                army = player.get_army()
            except Exception:
                army = getattr(player, "army", None)
            for unit in list(getattr(army, "units", []) or []):
                try:
                    if str(get_entity_id(unit)) == str(unit_id):
                        return unit
                except Exception:
                    continue
    except Exception:
        pass
    return None


def handle_advance_roll(game: object, state: DiceRollState):
    spec = dict(getattr(state, "spec", {}) or {})
    unit_id = spec.get("unit_id")
    unit = _get_unit(game, unit_id)
    if unit is None:
        return None
    roll_val = int(state.total or 0)
    try:
        roll_val = int(unit._apply_advance_roll_modifiers(roll_val))
    except Exception:
        pass
    try:
        unit.round_state.advance_roll = roll_val
    except Exception:
        pass
    return roll_val


def handle_charge_roll(game: object, state: DiceRollState):
    from ..utility.charge_roll import ChargeRollResult, ChargeRollSpec

    spec = dict(getattr(state, "spec", {}) or {})
    unit_id = spec.get("unit_id")
    unit = _get_unit(game, unit_id)
    if unit is None:
        return None
    charge_spec_data = dict(spec.get("charge_spec", {}) or {})
    try:
        charge_spec = ChargeRollSpec(
            dice_count=int(charge_spec_data.get("dice_count", 2) or 2),
            keep_highest=int(charge_spec_data.get("keep_highest", 2) or 2),
        )
    except Exception:
        charge_spec = ChargeRollSpec()
    dice_vals = [int(d.get("value", 0) or 0) for d in list(state.dice or [])]
    roll_result = ChargeRollResult.from_dice(charge_spec, dice_vals)
    state.spec["kept_indices"] = list(getattr(roll_result, "kept_indices", []) or [])
    state.spec["dropped_indices"] = list(getattr(roll_result, "dropped_indices", []) or [])
    try:
        state.total = int(roll_result.total or 0)
    except Exception:
        pass
    try:
        unit.round_state.charge_roll = int(roll_result.total or 0)
        unit.round_state.charge_dice = list(dice_vals)
    except Exception:
        pass
    return {
        "base_roll": int(roll_result.total or 0),
        "dice": list(dice_vals),
        "kept_indices": list(getattr(roll_result, "kept_indices", []) or []),
        "dropped_indices": list(getattr(roll_result, "dropped_indices", []) or []),
        "target_unit_ids": list(spec.get("target_unit_ids", []) or []),
    }


def handle_battle_shock_roll(game: object, state: DiceRollState):
    spec = dict(getattr(state, "spec", {}) or {})
    unit_id = spec.get("unit_id")
    unit = _get_unit(game, unit_id)
    if unit is None:
        return None
    try:
        leadership_value = int(spec.get("leadership", getattr(unit, "leadership", 0)) or 0)
    except Exception:
        leadership_value = int(getattr(unit, "leadership", 0) or 0)
    try:
        total_mod = int(spec.get("sum_modifier", 0) or 0)
    except Exception:
        total_mod = 0
    roll_total = int(getattr(state, "total", 0) or 0)
    mod_roll = roll_total + total_mod
    passed = mod_roll <= leadership_value
    try:
        current_turn = int(spec.get("current_turn", getattr(game, "turn", 1)) or 1)
    except Exception:
        current_turn = int(getattr(game, "turn", 1) or 1)
    was_battle_shocked = bool(spec.get("was_battle_shocked", False))
    shadow_ctx = None
    try:
        from ..rules.shadow_of_chaos import ShadowBattleShockContext

        shadow_ctx = ShadowBattleShockContext(
            modifier=int(spec.get("shadow_modifier", 0) or 0),
            manifestation_active=bool(spec.get("shadow_manifestation_active", False)),
            terror_active=bool(spec.get("shadow_terror_active", False)),
        )
    except Exception:
        shadow_ctx = None
    event_system = getattr(game, "event_system", None)
    try:
        unit._apply_battle_shock_outcome(
            passed=bool(passed),
            current_turn=int(current_turn),
            was_battle_shocked=bool(was_battle_shocked),
            shadow_ctx=shadow_ctx,
            game=game,
            event_system=event_system,
        )
    except Exception:
        pass
    return {"passed": bool(passed), "modified_roll": int(mod_roll), "leadership": int(leadership_value)}


def handle_attack_roll(game: object, state: DiceRollState):
    mgr = getattr(game, "attack_manager", None)
    if mgr is None:
        return None
    try:
        mgr.handle_roll(game, state)
    except Exception:
        return None
    return None


register_roll_handler("advance_roll", handle_advance_roll)
register_roll_handler("charge_roll", handle_charge_roll)
register_roll_handler("battle_shock", handle_battle_shock_roll)
register_roll_handler("attack_hits", handle_attack_roll)
register_roll_handler("attack_counts", handle_attack_roll)
register_roll_handler("attack_wounds", handle_attack_roll)
register_roll_handler("attack_saves", handle_attack_roll)
register_roll_handler("attack_damage", handle_attack_roll)
register_roll_handler("attack_hazardous", handle_attack_roll)
