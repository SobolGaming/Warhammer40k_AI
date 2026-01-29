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


def handle_daemonic_poisons_roll(game: object, state: DiceRollState):
    spec = dict(getattr(state, "spec", {}) or {})
    unit_id = spec.get("unit_id")
    unit = _get_unit(game, unit_id)
    if unit is None:
        return None
    roll_val = int(state.total or 0)
    ability_name = str(spec.get("ability_name", "") or "Daemonic Poisons").strip() or "Daemonic Poisons"
    player = unit.get_parent_army().player if hasattr(unit, "get_parent_army") else None
    if roll_val < 4:
        try:
            from ..utility.event_bus import append_action
            if player is not None:
                append_action(player, f"{ability_name}: {getattr(unit, 'name', 'Unit')} rolled {roll_val} (no effect).")
        except Exception:
            pass
        return 0
    if not bool(getattr(game, "is_authoritative", True)):
        return None
    roll_spec = {
        "dice_count": 1,
        "faces": 3,
        "reason": f"{ability_name}: {getattr(unit, 'name', 'Unit')} damage",
        "roll_type": "daemonic_poisons_damage",
        "unit_id": unit_id,
        "handler_key": "daemonic_poisons_damage",
        "handler_payload": {"ability_name": ability_name, "source_roll": roll_val},
    }
    try:
        if hasattr(game, "request_dice_roll"):
            game.request_dice_roll(player_id=getattr(player, "id", None), spec=roll_spec, prompt=roll_spec["reason"])
    except Exception:
        pass
    return None


def handle_daemonic_poisons_damage_roll(game: object, state: DiceRollState):
    spec = dict(getattr(state, "spec", {}) or {})
    unit_id = spec.get("unit_id")
    unit = _get_unit(game, unit_id)
    if unit is None:
        return None
    damage = int(state.total or 0)
    ability_name = str(spec.get("ability_name", "") or "Daemonic Poisons").strip() or "Daemonic Poisons"
    if damage <= 0:
        return 0
    try:
        game_map = getattr(game, "map", None)
    except Exception:
        game_map = None
    try:
        if hasattr(unit, "_apply_mortal_wounds_to_unit"):
            unit._apply_mortal_wounds_to_unit(unit, damage, game_map=game_map)
    except Exception:
        pass
    try:
        from ..utility.event_bus import append_action
        player = unit.get_parent_army().player if hasattr(unit, "get_parent_army") else None
        if player is not None:
            append_action(
                player,
                f"{ability_name}: {getattr(unit, 'name', 'Unit')} suffers {damage} mortal wounds.",
            )
    except Exception:
        pass
    return damage


def handle_advance_roll(game: object, state: DiceRollState):
    spec = dict(getattr(state, "spec", {}) or {})
    unit_id = spec.get("unit_id")
    unit = _get_unit(game, unit_id)
    if unit is None:
        return None
    roll_val = int(state.total or 0)
    try:
        from ..rules.wrathful_presence import driven_by_ultimate_rage_applies, DRIVEN_BY_ULTIMATE_RAGE_NAME
        from ..rules.emperors_children import INTERNAL_RIVALRIES_NAME
        from ..utility.modifier_choice import CHOICE_LABELS, options_for_signed_pairs
        from ..engine.decision_kinds import DECISION_CHOOSE_ADVANCE_MODIFIER_IGNORES
        from ..engine.decisions import DecisionOption, DecisionRequest
    except Exception:
        driven_by_ultimate_rage_applies = None
        DRIVEN_BY_ULTIMATE_RAGE_NAME = ""
        INTERNAL_RIVALRIES_NAME = ""
        DECISION_CHOOSE_ADVANCE_MODIFIER_IGNORES = None
        DecisionOption = None
        DecisionRequest = None
        options_for_signed_pairs = None
        CHOICE_LABELS = {}

    army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
    mgr = None
    if army is not None:
        mgr = getattr(army, "emperors_children", None)
        if mgr is None:
            mgr = getattr(army, "emperors_children_detachments", None)
    internal_rivalries = bool(mgr and getattr(mgr, "internal_rivalries_applies", lambda _u: False)(unit))
    driven_by_rage = bool(
        callable(driven_by_ultimate_rage_applies)
        and driven_by_ultimate_rage_applies(unit, game_map=getattr(game, "map", None))
    )
    ability_name = INTERNAL_RIVALRIES_NAME if internal_rivalries else DRIVEN_BY_ULTIMATE_RAGE_NAME

    if (
        bool(getattr(game, "is_authoritative", True))
        and (internal_rivalries or driven_by_rage)
        and options_for_signed_pairs is not None
    ):
        try:
            mods = list(unit._collect_advance_roll_modifiers() or [])
        except Exception:
            mods = []
        options = options_for_signed_pairs(mods)
        if options and DecisionRequest is not None and DecisionOption is not None and DECISION_CHOOSE_ADVANCE_MODIFIER_IGNORES:
            queue = getattr(game, "decision_queue", None)
            pending = False
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_ADVANCE_MODIFIER_IGNORES:
                        continue
                    ctx = getattr(req, "context", {}) or {}
                    if str(ctx.get("unit_id", "")) == str(unit_id):
                        pending = True
                        break
            if not pending:
                req_options = [
                    DecisionOption.create(CHOICE_LABELS.get(opt, str(opt)), payload={"choice": opt})
                    for opt in options
                ]
                request = DecisionRequest.create(
                    DECISION_CHOOSE_ADVANCE_MODIFIER_IGNORES,
                    "Choose which modifiers to ignore.",
                    player_id=getattr(getattr(unit.get_parent_army(), "player", None), "id", None),
                    options=req_options,
                    context={"unit_id": unit_id, "ability_name": ability_name},
                )
                if hasattr(game, "request_decision"):
                    game.request_decision(request)
            try:
                unit.round_state.advance_roll_unmodified = int(roll_val)
                unit.round_state.advance_modifier_choice_pending = True
                unit.round_state.advance_modifier_choice = None
                unit.round_state.advance_roll = None
            except Exception:
                pass
            return None

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
    try:
        from ..rules.wrathful_presence import driven_by_ultimate_rage_applies, DRIVEN_BY_ULTIMATE_RAGE_NAME
        from ..rules.emperors_children import INTERNAL_RIVALRIES_NAME
        from ..utility.modifier_choice import CHOICE_LABELS, options_for_signed_pairs
        from ..engine.decision_kinds import DECISION_CHOOSE_CHARGE_MODIFIER_IGNORES
        from ..engine.decisions import DecisionOption, DecisionRequest
    except Exception:
        driven_by_ultimate_rage_applies = None
        DRIVEN_BY_ULTIMATE_RAGE_NAME = ""
        INTERNAL_RIVALRIES_NAME = ""
        DECISION_CHOOSE_CHARGE_MODIFIER_IGNORES = None
        DecisionOption = None
        DecisionRequest = None
        options_for_signed_pairs = None
        CHOICE_LABELS = {}

    army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
    mgr = None
    if army is not None:
        mgr = getattr(army, "emperors_children", None)
        if mgr is None:
            mgr = getattr(army, "emperors_children_detachments", None)
    internal_rivalries = bool(mgr and getattr(mgr, "internal_rivalries_applies", lambda _u: False)(unit))
    driven_by_rage = bool(
        callable(driven_by_ultimate_rage_applies)
        and driven_by_ultimate_rage_applies(unit, game_map=getattr(game, "map", None))
    )
    ability_name = INTERNAL_RIVALRIES_NAME if internal_rivalries else DRIVEN_BY_ULTIMATE_RAGE_NAME

    if (
        bool(getattr(game, "is_authoritative", True))
        and (internal_rivalries or driven_by_rage)
        and options_for_signed_pairs is not None
    ):
        target_ids = list(spec.get("target_unit_ids", []) or [])
        targets = []
        registry = getattr(game, "entity_registry", None)
        for tid in target_ids:
            try:
                if registry is not None:
                    tgt = registry.get(str(tid), kind="unit")
                    if tgt is not None:
                        targets.append(tgt)
            except Exception:
                continue
        all_mods = []
        try:
            if targets:
                for tgt in targets:
                    all_mods.extend(list(game._collect_charge_modifiers(unit, target_unit=tgt) or []))
            else:
                all_mods = list(game._collect_charge_modifiers(unit, target_unit=None) or [])
        except Exception:
            all_mods = []
        options = options_for_signed_pairs(all_mods)
        if options and DecisionRequest is not None and DecisionOption is not None and DECISION_CHOOSE_CHARGE_MODIFIER_IGNORES:
            queue = getattr(game, "decision_queue", None)
            pending = False
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_CHARGE_MODIFIER_IGNORES:
                        continue
                    ctx = getattr(req, "context", {}) or {}
                    if str(ctx.get("unit_id", "")) == str(unit_id):
                        pending = True
                        break
            if not pending:
                req_options = [
                    DecisionOption.create(CHOICE_LABELS.get(opt, str(opt)), payload={"choice": opt})
                    for opt in options
                ]
                request = DecisionRequest.create(
                    DECISION_CHOOSE_CHARGE_MODIFIER_IGNORES,
                    "Choose which modifiers to ignore.",
                    player_id=getattr(getattr(unit.get_parent_army(), "player", None), "id", None),
                    options=req_options,
                    context={
                        "unit_id": unit_id,
                        "ability_name": ability_name,
                        "target_unit_ids": list(target_ids or []),
                    },
                )
                if hasattr(game, "request_decision"):
                    game.request_decision(request)
            try:
                unit.round_state.charge_modifier_choice_pending = True
                unit.round_state.charge_modifier_choice = None
                unit.round_state.charge_modifier_choice_targets = list(target_ids or [])
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
register_roll_handler("daemonic_poisons", handle_daemonic_poisons_roll)
register_roll_handler("daemonic_poisons_damage", handle_daemonic_poisons_damage_roll)
