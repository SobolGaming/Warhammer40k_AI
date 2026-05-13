from __future__ import annotations

from typing import Any


_RULES_BUNDLE_FIELDS = (
    "core_rules_id",
    "rules_commentary_id",
    "mission_pack_id",
    "terrain_pack_id",
    "dataslate_id",
    "points_id",
    "faction_pack_id",
    "detachment_pack_id",
)

_STATE_BLOB_REQUIRED_FIELDS = (
    "state_blob_version",
    "rules_bundle",
    "battle_round",
    "phase",
    "active_player_id",
    "players",
    "army_build_state",
    "mission_state",
    "deployment_state",
    "objectives",
    "scoring_surfaces",
    "control_regions",
    "terrain",
    "units",
)

_STATE_BLOB_ALLOWED_FIELDS = set(_STATE_BLOB_REQUIRED_FIELDS) | {
    "viewer_player_id",
    "detection_markers",
    "hidden_shooting_exemptions",
}


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _is_optional_int(value: Any) -> bool:
    return value is None or isinstance(value, int)


def _validate_rules_bundle(value: Any, *, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{label} must be an object"]
    missing = sorted(field for field in _RULES_BUNDLE_FIELDS if field not in value)
    if missing:
        errors.append(f"{label} missing required fields: {', '.join(missing)}")
    for field in _RULES_BUNDLE_FIELDS:
        if field in value and not isinstance(value.get(field), str):
            errors.append(f"{label}.{field} must be a string")
    return errors


def _validate_player_entries(value: Any, *, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list):
        return [f"{label} must be a list"]
    for idx, entry in enumerate(value):
        if not isinstance(entry, dict):
            errors.append(f"{label}[{idx}] must be an object")
            continue
        if not isinstance(entry.get("player_id"), str):
            errors.append(f"{label}[{idx}].player_id must be a string")
    return errors


def _validate_army_build_state(value: Any, *, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{label} must be an object"]
    if not _is_non_empty_string(value.get("army_build_descriptor_id")):
        errors.append(f"{label}.army_build_descriptor_id must be a non-empty string")
    players = value.get("players")
    if not isinstance(players, list):
        errors.append(f"{label}.players must be a list")
        return errors
    for idx, entry in enumerate(players):
        if not isinstance(entry, dict):
            errors.append(f"{label}.players[{idx}] must be an object")
            continue
        if not isinstance(entry.get("player_id"), str):
            errors.append(f"{label}.players[{idx}].player_id must be a string")
        if not isinstance(entry.get("army_present"), bool):
            errors.append(f"{label}.players[{idx}].army_present must be a boolean")
            continue
        if not bool(entry.get("army_present", False)):
            continue
        if not isinstance(entry.get("army_blueprint_hash"), str):
            errors.append(f"{label}.players[{idx}].army_blueprint_hash must be a string")
        if not isinstance(entry.get("detachments"), list):
            errors.append(f"{label}.players[{idx}].detachments must be a list")
        else:
            for detachment_idx, detachment in enumerate(entry.get("detachments", []) or []):
                if not isinstance(detachment, dict):
                    errors.append(f"{label}.players[{idx}].detachments[{detachment_idx}] must be an object")
                    continue
                if not isinstance(detachment.get("selection_id"), str):
                    errors.append(
                        f"{label}.players[{idx}].detachments[{detachment_idx}].selection_id must be a string"
                    )
                if not isinstance(detachment.get("detachment_type"), str):
                    errors.append(
                        f"{label}.players[{idx}].detachments[{detachment_idx}].detachment_type must be a string"
                    )
        if not isinstance(entry.get("upgrade_assignments", []), list):
            errors.append(f"{label}.players[{idx}].upgrade_assignments must be a list")
        else:
            for upgrade_idx, upgrade in enumerate(entry.get("upgrade_assignments", []) or []):
                if not isinstance(upgrade, dict):
                    errors.append(f"{label}.players[{idx}].upgrade_assignments[{upgrade_idx}] must be an object")
                    continue
                if not isinstance(upgrade.get("upgrade_id"), str):
                    errors.append(
                        f"{label}.players[{idx}].upgrade_assignments[{upgrade_idx}].upgrade_id must be a string"
                    )
        if not isinstance(entry.get("attachment_bindings"), list):
            errors.append(f"{label}.players[{idx}].attachment_bindings must be a list")
        else:
            for binding_idx, binding in enumerate(entry.get("attachment_bindings", []) or []):
                if not isinstance(binding, dict):
                    errors.append(f"{label}.players[{idx}].attachment_bindings[{binding_idx}] must be an object")
                    continue
                if not isinstance(binding.get("binding_id"), str):
                    errors.append(
                        f"{label}.players[{idx}].attachment_bindings[{binding_idx}].binding_id must be a string"
                    )
        summary = entry.get("detachment_points_summary")
        if not isinstance(summary, dict):
            errors.append(f"{label}.players[{idx}].detachment_points_summary must be an object")
        else:
            if "spent" not in summary or not isinstance(summary.get("spent"), int):
                errors.append(f"{label}.players[{idx}].detachment_points_summary.spent must be an integer")
            for field in ("budget", "remaining"):
                if field not in summary or not _is_optional_int(summary.get(field)):
                    errors.append(
                        f"{label}.players[{idx}].detachment_points_summary.{field} must be an integer or null"
                    )
        if not isinstance(entry.get("force_disposition"), str):
            errors.append(f"{label}.players[{idx}].force_disposition must be a string")
        if not isinstance(entry.get("allowed_force_dispositions"), list):
            errors.append(f"{label}.players[{idx}].allowed_force_dispositions must be a list")
    return errors


def _validate_score_source(value: Any, *, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{label} must be an object"]
    if not _is_non_empty_string(value.get("score_source_id")):
        errors.append(f"{label}.score_source_id must be a non-empty string")
    if not isinstance(value.get("kind"), str):
        errors.append(f"{label}.kind must be a string")
    return errors


def _validate_control_region(value: Any, *, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{label} must be an object"]
    if not _is_non_empty_string(value.get("region_id")):
        errors.append(f"{label}.region_id must be a non-empty string")
    if not isinstance(value.get("kind"), str):
        errors.append(f"{label}.kind must be a string")
    return errors


def _validate_objectives(value: Any, *, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list):
        return [f"{label} must be a list"]
    for idx, entry in enumerate(value):
        if not isinstance(entry, dict):
            errors.append(f"{label}[{idx}] must be an object")
            continue
        if not isinstance(entry.get("objective_id"), str):
            errors.append(f"{label}[{idx}].objective_id must be a string")
        if not isinstance(entry.get("objective_site_id"), str):
            errors.append(f"{label}[{idx}].objective_site_id must be a string")
        if not isinstance(entry.get("site_kind"), str):
            errors.append(f"{label}[{idx}].site_kind must be a string")
        geometry = entry.get("geometry")
        if not isinstance(geometry, dict):
            errors.append(f"{label}[{idx}].geometry must be an object")
        elif not isinstance(geometry.get("kind"), str):
            errors.append(f"{label}[{idx}].geometry.kind must be a string")
        errors.extend(_validate_control_region(entry.get("control_region"), label=f"{label}[{idx}].control_region"))
        score_sources = entry.get("score_sources")
        if not isinstance(score_sources, list):
            errors.append(f"{label}[{idx}].score_sources must be a list")
        else:
            for source_idx, score_source in enumerate(score_sources):
                errors.extend(
                    _validate_score_source(
                        score_source,
                        label=f"{label}[{idx}].score_sources[{source_idx}]",
                    )
                )
    return errors


def _validate_scoring_surfaces(value: Any, *, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list):
        return [f"{label} must be a list"]
    for idx, entry in enumerate(value):
        errors.extend(_validate_score_source(entry, label=f"{label}[{idx}]"))
    return errors


def _validate_control_regions(value: Any, *, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list):
        return [f"{label} must be a list"]
    for idx, entry in enumerate(value):
        errors.extend(_validate_control_region(entry, label=f"{label}[{idx}]"))
    return errors


def validate_state_blob(value: Any, *, label: str, expected_viewer_player_id: str | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{label} must be an object"]
    missing = sorted(field for field in _STATE_BLOB_REQUIRED_FIELDS if field not in value)
    if missing:
        errors.append(f"{label} missing required fields: {', '.join(missing)}")
    unknown = sorted(str(key) for key in value.keys() if str(key) not in _STATE_BLOB_ALLOWED_FIELDS)
    if unknown:
        errors.append(f"{label} contains unknown fields: {', '.join(unknown)}")
    if not isinstance(value.get("state_blob_version"), str):
        errors.append(f"{label}.state_blob_version must be a string")
    if not isinstance(value.get("battle_round"), int):
        errors.append(f"{label}.battle_round must be an integer")
    if not isinstance(value.get("phase"), str):
        errors.append(f"{label}.phase must be a string")
    if not isinstance(value.get("active_player_id"), str):
        errors.append(f"{label}.active_player_id must be a string")
    if expected_viewer_player_id is not None:
        if str(value.get("viewer_player_id", "") or "") != str(expected_viewer_player_id):
            errors.append(f"{label}.viewer_player_id must match player_obs_state key")
    elif "viewer_player_id" in value and not isinstance(value.get("viewer_player_id"), str):
        errors.append(f"{label}.viewer_player_id must be a string when present")
    errors.extend(_validate_rules_bundle(value.get("rules_bundle"), label=f"{label}.rules_bundle"))
    errors.extend(_validate_player_entries(value.get("players"), label=f"{label}.players"))
    errors.extend(_validate_army_build_state(value.get("army_build_state"), label=f"{label}.army_build_state"))
    if not isinstance(value.get("mission_state"), dict):
        errors.append(f"{label}.mission_state must be an object")
    if not isinstance(value.get("deployment_state"), dict):
        errors.append(f"{label}.deployment_state must be an object")
    errors.extend(_validate_objectives(value.get("objectives"), label=f"{label}.objectives"))
    errors.extend(_validate_scoring_surfaces(value.get("scoring_surfaces"), label=f"{label}.scoring_surfaces"))
    errors.extend(_validate_control_regions(value.get("control_regions"), label=f"{label}.control_regions"))
    if not isinstance(value.get("terrain"), list):
        errors.append(f"{label}.terrain must be a list")
    if "detection_markers" in value and not isinstance(value.get("detection_markers"), list):
        errors.append(f"{label}.detection_markers must be a list")
    if "hidden_shooting_exemptions" in value and not isinstance(value.get("hidden_shooting_exemptions"), list):
        errors.append(f"{label}.hidden_shooting_exemptions must be a list")
    if not isinstance(value.get("units"), list):
        errors.append(f"{label}.units must be a list")

    objectives = list(value.get("objectives", []) or []) if isinstance(value.get("objectives"), list) else []
    known_region_ids = {
        str(dict(entry.get("control_region", {}) or {}).get("region_id", "") or "")
        for entry in objectives
        if isinstance(entry, dict)
    }
    known_score_source_ids = {
        str(dict(source or {}).get("score_source_id", "") or "")
        for entry in objectives
        if isinstance(entry, dict)
        for source in list(entry.get("score_sources", []) or [])
    }
    for idx, entry in enumerate(list(value.get("control_regions", []) or [])):
        region_id = str(dict(entry or {}).get("region_id", "") or "")
        if region_id and known_region_ids and region_id not in known_region_ids:
            errors.append(f"{label}.control_regions[{idx}].region_id is not declared by any objective.control_region")
    for idx, entry in enumerate(list(value.get("scoring_surfaces", []) or [])):
        score_source_id = str(dict(entry or {}).get("score_source_id", "") or "")
        if score_source_id and known_score_source_ids and score_source_id not in known_score_source_ids:
            errors.append(
                f"{label}.scoring_surfaces[{idx}].score_source_id is not declared by any objective.score_sources"
            )
    return errors


def validate_player_obs_state_map(value: Any, *, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{label} must be an object"]
    for player_id, state in sorted(value.items(), key=lambda item: str(item[0])):
        if not isinstance(player_id, str):
            errors.append(f"{label} keys must be strings")
            continue
        errors.extend(
            validate_state_blob(
                state,
                label=f"{label}.{player_id}",
                expected_viewer_player_id=str(player_id),
            )
        )
    return errors


__all__ = ["validate_player_obs_state_map", "validate_state_blob"]
