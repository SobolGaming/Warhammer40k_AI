from __future__ import annotations

from ..decisions import DecisionRequest, DecisionResult
from ._helpers import find_option, resolve_army, resolve_player


def _option_payload(request: DecisionRequest, result: DecisionResult) -> dict:
    opt = find_option(request, result.option_id)
    return dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}


def _option_label(request: DecisionRequest, result: DecisionResult) -> str:
    opt = find_option(request, result.option_id)
    if opt is None:
        return ""
    return str(getattr(opt, "label", "") or "")


def _log_action_for_players(game: object, player: object, text: str) -> None:
    if not text:
        return
    from ...utility.event_bus import append_action

    if player is not None:
        append_action(player, text)

    if game is None:
        return
    for opp in list(getattr(game, "players", []) or []):
        if opp is None or opp is player:
            continue
        append_action(opp, text)


def _resolve_player(game: object, request: DecisionRequest, payload: dict):
    player_val = payload.get("player_id", None)
    if player_val is None:
        player_val = request.player_id
    if player_val is None:
        player_val = payload.get("player", None)
    return resolve_player(game, player_val)


def _resolve_army(game: object, request: DecisionRequest, payload: dict):
    army_val = payload.get("army_id", None)
    if army_val is None:
        army_val = request.context.get("army_id")
    army = resolve_army(game, army_val)
    if army is not None:
        return army
    player = _resolve_player(game, request, payload)
    if player is None:
        return None
    get_army = getattr(player, "get_army", None)
    if callable(get_army):
        return get_army()
    return getattr(player, "army", None)
