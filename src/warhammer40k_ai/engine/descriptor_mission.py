from __future__ import annotations

from typing import Any

from ..battlefield.objective_sites import resolve_objective_id, resolve_objective_site
from .descriptor_bundle import CompiledDescriptor, descriptor_id, iter_objectives, iter_players, json_safe, safe_int


def scoring_window_payload(game: object) -> list[dict[str, Any]]:
    players = iter_players(game)
    player_ids = [str(getattr(player, "id", "") or "") for player in players if str(getattr(player, "id", "") or "")]
    battle_round = safe_int(getattr(game, "turn", 0), 0)
    windows = [
        {
            "window_id": "window_primary_active_command",
            "owner_player_id": player_ids[0] if player_ids else "",
            "phase": "COMMAND_PHASE",
            "battle_round": battle_round,
        },
        {
            "window_id": "window_primary_opponent_command",
            "owner_player_id": player_ids[1] if len(player_ids) > 1 else "",
            "phase": "COMMAND_PHASE",
            "battle_round": battle_round,
        },
        {
            "window_id": "window_endgame",
            "owner_player_id": "",
            "phase": "ENDGAME",
            "battle_round": battle_round,
        },
    ]
    return json_safe(windows)


def build_mission_descriptor_payload(game: object) -> dict[str, Any]:
    selected = dict(getattr(game, "selected_mission_info", {}) or {})
    objective_ids = [resolve_objective_id(objective) for objective in iter_objectives(game)]
    scoring_sources: list[str] = []
    for objective in iter_objectives(game):
        objective_id = resolve_objective_id(objective)
        site = resolve_objective_site(objective)
        if site is None or not hasattr(site, "score_sources"):
            if objective_id:
                scoring_sources.append(f"score_source:objective:{objective_id}")
            continue
        scoring_sources.extend(
            str(getattr(source, "score_source_id", "") or "")
            for source in list(getattr(site, "score_sources", []) or [])
            if str(getattr(source, "score_source_id", "") or "")
        )
    scoring_sources = sorted({source for source in scoring_sources if str(source or "")})
    primary_name = str(selected.get("primary", "") or "").strip().lower()
    action_sites: list[str] = []
    if "terraform" in primary_name:
        action_sites.append("ACTION_SITE_TERRAFORM")
    if "scorched earth" in primary_name:
        action_sites.append("ACTION_SITE_SCORCHED_EARTH")
    payload = {
        "selected_mission_info": json_safe(selected),
        "secondary_mission_mode": str(getattr(game, "secondary_mission_mode", "") or ""),
        "battle_round_structure": {
            "max_rounds": 5,
            "current_battle_round": safe_int(getattr(game, "turn", 0), 0),
        },
        "scoring_windows": scoring_window_payload(game),
        "primary_scoring_sources": scoring_sources,
        "denial_windows": [
            {
                "window_id": "window_primary_opponent_command",
                "type": "PRIMARY_DENIAL",
            }
        ],
        "secondary_generation_mechanics": {
            "deck_mode": str(getattr(game, "secondary_mission_mode", "") or ""),
        },
        "catch_up_mechanics": [],
        "action_site_semantics": sorted(action_sites),
        "deployment_map_hooks": {
            "deployment_name": str(selected.get("deployment", "") or ""),
            "layout": safe_int(selected.get("layout", 0), 0),
        },
    }
    return json_safe(payload)


def compile_mission_descriptor(game: object) -> CompiledDescriptor:
    payload = build_mission_descriptor_payload(game)
    return CompiledDescriptor(
        family="MissionDescriptor",
        descriptor_id=descriptor_id("mission_descriptor", payload),
        payload=payload,
    )


__all__ = ["build_mission_descriptor_payload", "compile_mission_descriptor", "scoring_window_payload"]
