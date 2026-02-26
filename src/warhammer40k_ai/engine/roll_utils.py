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


def command_reroll_available(game: object, player: object, *, roll_type: str, unit: Optional[object] = None) -> bool:
    if game is None or player is None:
        return False
    rt = str(roll_type or "").strip().lower()
    if rt and rt not in _COMMAND_REROLL_TYPES:
        return False
    mgr = getattr(player, "stratagems", None)
    if mgr is None:
        return False
    try:
        strat = mgr.get_by_name("COMMAND RE-ROLL")
    except Exception:
        strat = None
    if strat is None:
        return False
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
    return bool(availability.get("available", False))
