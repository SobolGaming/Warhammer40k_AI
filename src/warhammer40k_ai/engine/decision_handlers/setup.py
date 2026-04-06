from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import _validate_choice_from_options, register_decision_handler
from ..decision_kinds import (
    DECISION_CHOOSE_MISSION,
    DECISION_CHOOSE_PLAYER_COLOR,
    DECISION_CONFIRM_MODAL,
)
from ..decisions import DecisionOption, DecisionRequest, DecisionResult


def _find_option(request: DecisionRequest, option_id: str) -> DecisionOption | None:
    for opt in list(getattr(request, "options", []) or []):
        if opt.option_id == option_id:
            return opt
    return None


def _validate_choose_mission(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(_validate_choice_from_options(request, result))
    if errors:
        return errors
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    combo = payload.get("combination")
    if not isinstance(combo, dict):
        return ("Mission selection requires a mission-pack entry dict in the option payload.",)
    required = {"id", "primary", "deployment", "layouts"}
    missing = required - set(combo.keys())
    if missing:
        return (f"Mission-pack entry missing keys: {sorted(missing)}",)
    layout = result.payload.get("layout")
    if layout is None:
        return ("Mission selection requires layout in result payload.",)
    if layout not in list(combo.get("layouts", []) or []):
        return ("Selected layout is not valid for this mission-pack entry.",)
    return ()


def _apply_choose_mission(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    combo = payload.get("combination")
    layout = result.payload.get("layout")
    apply_fn = getattr(game, "_apply_selected_mission", None)
    if not callable(apply_fn):
        raise RuntimeError("Game missing _apply_selected_mission.")
    apply_fn(combo, layout)
    return None


def _validate_confirm_modal(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    return _validate_choice_from_options(request, result)


def _apply_confirm_modal(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    return None


def _find_player(game: object, player_id: str):
    pid = str(player_id or "")
    if not pid:
        return None
    for player in list(getattr(game, "players", []) or []):
        if str(getattr(player, "id", "") or "") == pid:
            return player
    return None


def _validate_choose_player_color(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(_validate_choice_from_options(request, result))
    if errors:
        return errors
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    player_id = str(payload.get("player_id", "") or request.context.get("player_id", "") or request.player_id or "")
    if not player_id:
        return ("Player color selection requires player_id.",)
    if request.player_id and str(request.player_id) != player_id:
        return ("Player color selection player_id mismatch.",)
    if _find_player(game, player_id) is None:
        return ("Player color selection references unknown player_id.",)

    rgb = payload.get("rgb")
    if not isinstance(rgb, (list, tuple)) or len(rgb) != 3:
        return ("Player color selection requires rgb triplet.",)
    for idx, value in enumerate(list(rgb)):
        ivalue = int(value)
        if ivalue < 0 or ivalue > 255:
            return (f"Player color RGB component {idx} out of range: {ivalue}.",)

    hue = payload.get("hue_degrees", None)
    if hue is not None:
        hue_val = int(hue)
        if hue_val < 0 or hue_val >= 360:
            return ("Player color hue_degrees must be within [0, 359].",)
    return ()


def _apply_choose_player_color(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = _find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    player_id = str(payload.get("player_id", "") or request.context.get("player_id", "") or request.player_id or "")
    player = _find_player(game, player_id)
    if player is None:
        raise RuntimeError("Player color selection target player was not found.")
    rgb = list(payload.get("rgb", []) or [])
    hue = payload.get("hue_degrees", None)
    player.set_ui_color(rgb, hue_degrees=hue, selected=True, source="selected")
    return None


register_decision_handler(DECISION_CHOOSE_MISSION, validate=_validate_choose_mission, apply=_apply_choose_mission)
register_decision_handler(DECISION_CONFIRM_MODAL, validate=_validate_confirm_modal, apply=_apply_confirm_modal)
register_decision_handler(DECISION_CHOOSE_PLAYER_COLOR, validate=_validate_choose_player_color, apply=_apply_choose_player_color)
