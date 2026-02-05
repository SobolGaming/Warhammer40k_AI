from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import register_decision_handler
from ..decision_kinds import DECISION_REQUEST_DICE_ROLL, DECISION_SELECT_DICE_REROLL
from ..decisions import DecisionRequest, DecisionResult
from ._helpers import find_option, resolve_player, resolve_unit, validate_option_choice


def _roll_manager(game: object):
    return getattr(game, "roll_manager", None)


def _validate_request_dice_roll(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    ctx = dict(getattr(request, "context", {}) or {})
    roll_id = ctx.get("roll_id")
    if roll_id is None:
        return ("Dice roll request missing roll_id.",)
    mgr = _roll_manager(game)
    if mgr is None:
        return ("Game missing roll manager.",)
    if mgr.get_roll(int(roll_id)) is None:
        return ("Dice roll state not found.",)
    return ()


def _apply_request_dice_roll(game: object, request: DecisionRequest, result: DecisionResult):
    ctx = dict(getattr(request, "context", {}) or {})
    roll_id = ctx.get("roll_id")
    mgr = _roll_manager(game)
    if mgr is None:
        raise RuntimeError("Game missing roll manager.")
    return mgr.resolve_roll(
        game,
        int(roll_id),
        result_payload=dict(getattr(result, "payload", {}) or {}),
        actor_player_id=getattr(result, "player_id", None),
    )


def _validate_select_reroll(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    ctx = dict(getattr(request, "context", {}) or {})
    roll_id = ctx.get("roll_id")
    if roll_id is None:
        return ("Reroll decision missing roll_id.",)
    mgr = _roll_manager(game)
    if mgr is None:
        return ("Game missing roll manager.",)
    state = mgr.get_roll(int(roll_id))
    if state is None:
        return ("Roll state not found.",)
    if state.status != "rolled":
        return ("Roll is not yet resolved.",)
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    action_id = str(payload.get("action_id", "") or "")
    if not action_id:
        return ("Reroll decision missing action_id.",)
    if action_id == "none":
        return ()
    # Validate action exists
    action = None
    for opt_action in list(getattr(state, "reroll_options", []) or []):
        if str(opt_action.get("action_id", "")) == action_id:
            action = dict(opt_action)
            break
    if action is None:
        return ("Selected reroll action not available.",)
    mode = str(action.get("mode", "") or "")
    selected = result.payload.get("selected_die_ids", None)
    if mode in ("all", "whole"):
        return ()
    if selected is None:
        return ("Reroll selection requires selected_die_ids.",)
    if not isinstance(selected, list):
        return ("selected_die_ids must be a list.",)
    eligible = set(action.get("eligible_die_ids", []) or [])
    for die_id in selected:
        if die_id not in eligible:
            return ("Selected die_id is not eligible for reroll.",)
    max_sel = action.get("max_select")
    if max_sel is not None:
        try:
            if len(selected) > int(max_sel):
                return ("Too many dice selected for reroll.",)
        except Exception:
            pass
    if action_id == "flux_reroll":
        mgr_flux = getattr(game, "fates_in_flux", None)
        if mgr_flux is None:
            return ("Flux token manager missing.",)
        player = resolve_player(game, getattr(result, "player_id", None))
        if player is None:
            return ("Flux re-roll requires a player.",)
        unit = resolve_unit(game, state.spec.get("unit_id"))
        roll_type = str(state.spec.get("roll_type", "") or "")
        if not mgr_flux.can_use_flux_reroll(game=game, player=player, unit=unit, roll_type=roll_type):
            return ("Flux re-roll not available for this roll.",)
        selected_count = len(selected or [])
        if selected_count <= 0:
            return ("Flux re-roll requires selected dice.",)
        if mgr_flux.tokens_for_player(player) < selected_count:
            return ("Insufficient Flux tokens.",)
    # Command reroll validation (CP and phase usage)
    if bool(action.get("is_command", False)) or bool(action.get("consume_cp", False)):
        player = resolve_player(game, getattr(result, "player_id", None))
        if player is None:
            return ("Command reroll requires a player.",)
        mgr_strat = getattr(player, "stratagems", None)
        strat = None
        try:
            if mgr_strat is not None:
                strat = mgr_strat.get_by_name("COMMAND RE-ROLL")
        except Exception:
            strat = None
        if strat is None:
            return ("Command Re-roll stratagem not available.",)
        try:
            phase_name = getattr(game, "_current_phase_label", lambda: "")()
        except Exception:
            phase_name = ""
        ctx = {"phase_name": phase_name}
        is_active_turn = False
        try:
            is_active_turn = bool(getattr(game, "get_current_player", lambda: None)() is player)
        except Exception:
            is_active_turn = False
        try:
            availability = mgr_strat._evaluate_availability(strat, ctx, is_active_turn=is_active_turn)
        except Exception:
            availability = {"available": False, "reason": "Unavailable"}
        if not availability.get("available", False):
            return (str(availability.get("reason") or "Command Re-roll unavailable"),)
    return ()


def _apply_select_reroll(game: object, request: DecisionRequest, result: DecisionResult):
    ctx = dict(getattr(request, "context", {}) or {})
    roll_id = ctx.get("roll_id")
    mgr = _roll_manager(game)
    if mgr is None:
        raise RuntimeError("Game missing roll manager.")
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    action_id = str(payload.get("action_id", "") or "")
    selected = result.payload.get("selected_die_ids", None)
    if action_id == "none":
        return mgr.apply_reroll(
            game,
            int(roll_id),
            action_id=action_id,
            selected_die_ids=[],
            actor_player_id=getattr(result, "player_id", None),
        )
    # Spend CP for command reroll if needed
    state = mgr.get_roll(int(roll_id))
    action = None
    for opt_action in list(getattr(state, "reroll_options", []) or []):
        if str(opt_action.get("action_id", "")) == action_id:
            action = dict(opt_action)
            break
    if action is not None and (bool(action.get("is_command", False)) or bool(action.get("consume_cp", False))):
        player = resolve_player(game, getattr(result, "player_id", None))
        mgr_strat = getattr(player, "stratagems", None) if player is not None else None
        strat = None
        try:
            if mgr_strat is not None:
                strat = mgr_strat.get_by_name("COMMAND RE-ROLL")
        except Exception:
            strat = None
        if strat is not None and player is not None:
            cp_cost = int(getattr(strat, "cp_cost", 1) or 1)
            player.spend_command_points(cp_cost, reason=f"Stratagem: {strat.name}", source="stratagem")
            try:
                mgr_strat._used_stratagems_this_phase.add((strat.name or "").strip().upper())
            except Exception:
                pass
    if action_id == "flux_reroll":
        mgr_flux = getattr(game, "fates_in_flux", None)
        player = resolve_player(game, getattr(result, "player_id", None))
        if mgr_flux is None or player is None:
            raise RuntimeError("Flux token spend failed: manager or player missing.")
        if selected is None:
            selected_count = len(action.get("eligible_die_ids", []) or []) if action is not None else 0
        else:
            selected_count = len(selected or [])
        if selected_count <= 0:
            raise RuntimeError("Flux token spend failed: no dice selected.")
        if not mgr_flux.spend_tokens(player, selected_count, reason="Re-roll"):
            raise RuntimeError("Flux token spend failed: insufficient tokens.")
    # Client-side authoritative roll results (from server broadcast)
    if not bool(getattr(game, "is_authoritative", True)):
        payload = dict(getattr(result, "payload", {}) or {})
        if isinstance(payload.get("roll_results"), dict):
            return mgr.apply_roll_results(
                game,
                int(roll_id),
                payload.get("roll_results", {}),
                actor_player_id=getattr(result, "player_id", None),
            )
    return mgr.apply_reroll(
        game,
        int(roll_id),
        action_id=action_id,
        selected_die_ids=selected,
        actor_player_id=getattr(result, "player_id", None),
    )


register_decision_handler(DECISION_REQUEST_DICE_ROLL, validate=_validate_request_dice_roll, apply=_apply_request_dice_roll)
register_decision_handler(DECISION_SELECT_DICE_REROLL, validate=_validate_select_reroll, apply=_apply_select_reroll)
