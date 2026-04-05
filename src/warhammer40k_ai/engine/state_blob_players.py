from __future__ import annotations

from typing import Any

from .descriptor_army_build import compile_army_build_descriptor
from .state_blob_rules import safe_int, sorted_players


def player_card_state(player: object, *, viewer_id: str | None, include_hidden: bool) -> dict[str, Any]:
    active = list(getattr(player, "active_secondaries", []) or [])
    discarded = list(getattr(player, "discarded_secondaries", []) or [])
    deck = list(getattr(player, "secondary_deck", []) or [])
    if include_hidden or str(getattr(player, "id", "") or "") == str(viewer_id or ""):
        return {
            "active_secondary_names": sorted(str(getattr(card, "name", "") or "") for card in active),
            "discarded_secondary_names": sorted(str(getattr(card, "name", "") or "") for card in discarded),
            "secondary_deck_count": int(len(deck)),
        }
    return {
        "active_secondary_count": int(len(active)),
        "discarded_secondary_count": int(len(discarded)),
        "secondary_deck_count": int(len(deck)),
    }


def player_entry(player: object, *, viewer_id: str | None, include_hidden: bool) -> dict[str, Any]:
    get_score = getattr(player, "get_score", None)
    score = get_score() if callable(get_score) else getattr(player, "score", 0)
    entry = {
        "player_id": str(getattr(player, "id", "") or ""),
        "name": str(getattr(player, "name", "") or ""),
        "command_points": safe_int(getattr(player, "command_points", 0), 0),
        "score": safe_int(score, 0),
    }
    entry.update(player_card_state(player, viewer_id=viewer_id, include_hidden=include_hidden))
    return entry


def player_entries(game: object, *, viewer_id: str | None, include_hidden: bool) -> list[dict[str, Any]]:
    return [
        player_entry(player, viewer_id=viewer_id, include_hidden=include_hidden)
        for player in sorted_players(game)
    ]


def army_build_state(game: object) -> dict[str, Any]:
    descriptor = compile_army_build_descriptor(game)
    payload = dict(descriptor.payload or {})
    payload["army_build_descriptor_id"] = str(descriptor.descriptor_id or "")
    return payload


__all__ = ["army_build_state", "player_entries"]
