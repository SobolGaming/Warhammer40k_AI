from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SelectedDeploymentPlan:
    mission_pack_id: str
    mission_definition_id: str
    deployment_definition_id: str
    deployment_name: str
    primary_mission_name: str
    layout: int
    available_layouts: tuple[int, ...]
    secondary_rule_set_id: str
    secondary_mission_mode: str
    secondary_selection_stage: str
    twist_definition_id: str
    twist_name: str
    twist_is_stubbed: bool = False
    provisional: bool = False
    force_disposition_pair_key: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
