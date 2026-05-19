from __future__ import annotations

from typing import Optional


_COMMAND_REROLL_TYPES = {
    "advance",
    "charge",
    "hit",
    "wound",
    "save",
    "damage",
    "attacks",
    "hazardous",
    "leadership",
    "battle_shock",
}


def _coerce_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _current_cp(player: object) -> int:
    return max(0, _coerce_int(getattr(player, "command_points", 0), default=0))


def _stratagem_base_cost(stratagem: object) -> int:
    return max(0, _coerce_int(getattr(stratagem, "cp_cost", 1), default=1))


def _cp_increase_amount(spec: dict) -> int:
    return max(1, _coerce_int(spec.get("cp_increase", 1), default=1))


def _preview_opponent_cp_increase(
    *,
    game: object,
    player: object,
    stratagem: object,
    target_unit: Optional[object],
    current_cost: int,
) -> dict:
    get_opponent = getattr(player, "_get_opponent_player", None)
    opponent = get_opponent() if callable(get_opponent) else None
    if opponent is None:
        players = list(getattr(game, "players", []) or []) if game is not None else []
        for candidate in players:
            if candidate is not player:
                opponent = candidate
                break
    preview = getattr(opponent, "preview_targeted_stratagem_cp_increase", None) if opponent is not None else None
    if not callable(preview):
        return {"increase": 0, "reasons": []}
    info = preview(target_unit=target_unit, current_cost=int(current_cost or 0))
    auto_specs = list((info or {}).get("auto_specs", []) or [])
    optional_specs = list((info or {}).get("optional_specs", []) or [])
    used_spec = auto_specs[0] if auto_specs else None
    if used_spec is None and optional_specs:
        candidate = optional_specs[0]
        ctx = {
            "ability_name": str(candidate.get("name", "") or "Stratagem CP Increase"),
            "stratagem": getattr(stratagem, "name", None) or "",
            "target_unit": getattr(target_unit, "name", None) or "",
            "current_cp_cost": int(current_cost or 0),
        }
        should_preview = getattr(opponent, "_should_preview_optional_ability", None)
        if callable(should_preview) and bool(
            should_preview("OPPONENT_STRATAGEM_CP_INCREASE", ctx, assume=None)
        ):
            used_spec = candidate
    if used_spec is None:
        return {"increase": 0, "reasons": []}
    label = str(used_spec.get("name", "") or "Stratagem CP Increase").strip() or "Stratagem CP Increase"
    increase = _cp_increase_amount(used_spec)
    return {"increase": increase, "reasons": [f"{label}: +{increase}CP"]}


def command_reroll_status(
    game: object,
    player: object,
    *,
    roll_type: str = "",
    unit: Optional[object] = None,
) -> dict:
    if game is None or player is None:
        return {"available": False, "reason": "Command Re-roll requires a game and player.", "cp_cost": 0}
    rt = str(roll_type or "").strip().lower()
    if rt and rt not in _COMMAND_REROLL_TYPES:
        return {"available": False, "reason": f"Command Re-roll cannot be used for {rt}.", "cp_cost": 0}
    mgr = getattr(player, "stratagems", None)
    if mgr is None:
        return {"available": False, "reason": "Command Re-roll stratagem manager missing.", "cp_cost": 0}
    try:
        strat = mgr.get_by_name("COMMAND RE-ROLL")
    except Exception:
        strat = None
    if strat is None:
        return {"available": False, "reason": "Command Re-roll stratagem not available.", "cp_cost": 0}
    try:
        phase_name = getattr(game, "_current_phase_label", lambda: "")()
    except Exception:
        phase_name = ""
    is_active_turn = False
    try:
        is_active_turn = bool(getattr(game, "get_current_player", lambda: None)() is player)
    except Exception:
        is_active_turn = False
    ctx = {"phase_name": phase_name}
    if unit is not None:
        ctx["unit"] = unit
        ctx["target_unit"] = unit
    try:
        availability = mgr._evaluate_availability(strat, ctx, is_active_turn=is_active_turn)
    except Exception:
        availability = {"available": False}
    if not bool((availability or {}).get("available", False)):
        return {
            "available": False,
            "reason": str((availability or {}).get("reason") or "Command Re-roll unavailable."),
            "cp_cost": _stratagem_base_cost(strat),
        }

    preview_cost = getattr(player, "preview_stratagem_cp_cost", None)
    if callable(preview_cost):
        cp_info = preview_cost(strat, target_unit=unit, assume_optional_discounts=None)
    else:
        cp_info = {"cost": _stratagem_base_cost(strat), "base": _stratagem_base_cost(strat)}
    if bool((cp_info or {}).get("denied", False)):
        return {
            "available": False,
            "reason": str((cp_info or {}).get("reason") or "Command Re-roll CP cost denied."),
            "cp_cost": _stratagem_base_cost(strat),
        }
    cp_cost = max(0, _coerce_int((cp_info or {}).get("cost", _stratagem_base_cost(strat)), default=_stratagem_base_cost(strat)))
    increase_info = _preview_opponent_cp_increase(
        game=game,
        player=player,
        stratagem=strat,
        target_unit=unit,
        current_cost=cp_cost,
    )
    cp_cost += max(0, _coerce_int(increase_info.get("increase", 0), default=0))
    current_cp = _current_cp(player)
    if cp_cost > current_cp:
        return {
            "available": False,
            "reason": f"Insufficient CP for Command Re-roll: requires {cp_cost}, has {current_cp}.",
            "cp_cost": cp_cost,
            "current_cp": current_cp,
            "cp_reasons": list((cp_info or {}).get("reasons", []) or []) + list(increase_info.get("reasons", []) or []),
        }
    return {
        "available": True,
        "reason": "",
        "cp_cost": cp_cost,
        "current_cp": current_cp,
        "cp_reasons": list((cp_info or {}).get("reasons", []) or []) + list(increase_info.get("reasons", []) or []),
    }


def command_reroll_available(game: object, player: object, *, roll_type: str, unit: Optional[object] = None) -> bool:
    return bool(command_reroll_status(game, player, roll_type=roll_type, unit=unit).get("available", False))
