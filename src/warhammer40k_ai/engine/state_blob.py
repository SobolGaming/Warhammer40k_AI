from __future__ import annotations

from .state_blob_mission import deployment_state, mission_state
from .state_blob_objectives import control_regions, objective_entries, scoring_surfaces
from .state_blob_players import army_build_state, player_entries
from .state_blob_rules import STATE_BLOB_VERSION, battle_round, current_player_id, phase_name, rules_bundle_entry, sorted_players
from .state_blob_terrain import terrain_entries
from .state_blob_units import unit_entries


def canonical_omniscient_state(game: object) -> dict[str, object]:
    objectives = objective_entries(game)
    return {
        "state_blob_version": STATE_BLOB_VERSION,
        "rules_bundle": rules_bundle_entry(game),
        "battle_round": battle_round(game),
        "phase": phase_name(game),
        "active_player_id": current_player_id(game),
        "players": player_entries(game, viewer_id=None, include_hidden=True),
        "army_build_state": army_build_state(game),
        "mission_state": mission_state(game),
        "deployment_state": deployment_state(game),
        "objectives": objectives,
        "scoring_surfaces": scoring_surfaces(objectives),
        "control_regions": control_regions(objectives),
        "terrain": terrain_entries(game),
        "units": unit_entries(game, viewer_id=None, include_hidden=True),
    }


def player_obs_state(game: object, player_id: str) -> dict[str, object]:
    objectives = objective_entries(game)
    return {
        "state_blob_version": STATE_BLOB_VERSION,
        "rules_bundle": rules_bundle_entry(game),
        "battle_round": battle_round(game),
        "phase": phase_name(game),
        "active_player_id": current_player_id(game),
        "viewer_player_id": str(player_id or ""),
        "players": player_entries(game, viewer_id=str(player_id or ""), include_hidden=False),
        "army_build_state": army_build_state(game),
        "mission_state": mission_state(game),
        "deployment_state": deployment_state(game),
        "objectives": objectives,
        "scoring_surfaces": scoring_surfaces(objectives),
        "control_regions": control_regions(objectives),
        "terrain": terrain_entries(game),
        "units": unit_entries(game, viewer_id=str(player_id or ""), include_hidden=False),
    }


def all_player_obs_states(game: object) -> dict[str, dict[str, object]]:
    states: dict[str, dict[str, object]] = {}
    for player in sorted_players(game):
        player_id = str(getattr(player, "id", "") or "")
        if not player_id:
            continue
        states[player_id] = player_obs_state(game, player_id)
    return states


__all__ = [
    "STATE_BLOB_VERSION",
    "all_player_obs_states",
    "canonical_omniscient_state",
    "player_obs_state",
]
