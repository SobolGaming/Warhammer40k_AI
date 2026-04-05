from __future__ import annotations

from .deployment_types import SelectedDeploymentPlan
from .deployment_validation import validate_selected_mission_choice


def selected_deployment_plan(game) -> SelectedDeploymentPlan:
    selected = dict(getattr(game, "selected_mission_info", {}) or {})
    if not selected:
        raise RuntimeError("No selected mission info available for deployment planning.")
    deployment_definition, selected_layout = validate_selected_mission_choice(
        selected,
        layout=selected.get("layout"),
    )
    return SelectedDeploymentPlan(
        mission_pack_id=str(selected.get("mission_pack_id", "") or ""),
        mission_definition_id=str(selected.get("mission_definition_id", "") or ""),
        deployment_definition_id=deployment_definition.deployment_definition_id,
        deployment_name=deployment_definition.deployment_name,
        primary_mission_name=str(selected.get("primary", "") or ""),
        layout=int(selected_layout),
        available_layouts=tuple(int(value) for value in list(selected.get("layouts", []) or deployment_definition.allowed_layouts)),
        secondary_rule_set_id=str(selected.get("secondary_rule_set_id", "") or ""),
        secondary_mission_mode=str(selected.get("secondary_mission_mode", "") or ""),
        secondary_selection_stage=str(selected.get("secondary_selection_stage", "") or ""),
        twist_definition_id=str(selected.get("twist_definition_id", "") or ""),
        twist_name=str(selected.get("twist_name", "") or ""),
        twist_is_stubbed=bool(selected.get("twist_is_stubbed", False)),
        provisional=bool(selected.get("provisional", False)),
        force_disposition_pair_key=str(selected.get("force_disposition_pair_key", "") or ""),
        metadata=dict(selected.get("metadata", {}) or {}),
    )
