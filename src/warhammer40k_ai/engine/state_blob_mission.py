from __future__ import annotations

from typing import Any

from .state_blob_rules import json_safe, safe_int


def mission_state(game: object) -> dict[str, Any]:
    selected = dict(getattr(game, "selected_mission_info", {}) or {})
    return {
        "secondary_mission_mode": str(getattr(game, "secondary_mission_mode", "") or ""),
        "selected_mission_info": json_safe(selected),
        "battle_shock_step_active": bool(getattr(game, "battle_shock_step_active", False)),
    }


def deployment_state(game: object) -> dict[str, Any]:
    deployment_zones = dict(getattr(game, "deployment_zones", {}) or {})
    return {
        "setup_phase": str(getattr(getattr(game, "setup_phase", None), "name", "") or ""),
        "setup_complete": bool(getattr(game, "setup_complete", False)),
        "attacker_index": getattr(game, "attacker_index", None),
        "defender_index": getattr(game, "defender_index", None),
        "deployment_turn_index": safe_int(getattr(game, "deployment_turn_index", 0), 0),
        "waiting_for_deployment_input": bool(getattr(game, "waiting_for_deployment_input", False)),
        "deployment_notice": str(getattr(game, "deployment_notice", "") or ""),
        "deployment_zone_player_ids": sorted(str(player_id) for player_id in deployment_zones.keys()),
    }


__all__ = ["deployment_state", "mission_state"]
