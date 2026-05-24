from __future__ import annotations

from .decision_kinds import DECISION_REQUEST_DICE_ROLL, DECISION_REROLL_ROLL, DECISION_SELECT_DICE_REROLL
from .descriptor_bundle import descriptor_bundle_id


MECHANICAL_DECISION_TYPES = frozenset(
    {
        DECISION_REQUEST_DICE_ROLL,
        DECISION_REROLL_ROLL,
        DECISION_SELECT_DICE_REROLL,
    }
)

MECHANICAL_DESCRIPTOR_IDS = {
    "mission_descriptor_id": "mechanical_mission_descriptor",
    "objective_descriptor_ids": [],
    "terrain_descriptor_ids": [],
    "deployment_descriptor_id": "mechanical_deployment_descriptor",
    "army_build_descriptor_id": "mechanical_army_build_descriptor",
    "tool_descriptor_ids": [],
}

MECHANICAL_DESCRIPTOR_BUNDLE_ID = descriptor_bundle_id(
    mission_descriptor_id=MECHANICAL_DESCRIPTOR_IDS["mission_descriptor_id"],
    objective_descriptor_ids=list(MECHANICAL_DESCRIPTOR_IDS["objective_descriptor_ids"]),
    terrain_descriptor_ids=list(MECHANICAL_DESCRIPTOR_IDS["terrain_descriptor_ids"]),
    deployment_descriptor_id=MECHANICAL_DESCRIPTOR_IDS["deployment_descriptor_id"],
    army_build_descriptor_id=MECHANICAL_DESCRIPTOR_IDS["army_build_descriptor_id"],
    tool_descriptor_ids=list(MECHANICAL_DESCRIPTOR_IDS["tool_descriptor_ids"]),
)


def mechanical_descriptor_ids() -> dict[str, object]:
    return {
        "mission_descriptor_id": str(MECHANICAL_DESCRIPTOR_IDS["mission_descriptor_id"]),
        "objective_descriptor_ids": list(MECHANICAL_DESCRIPTOR_IDS["objective_descriptor_ids"]),
        "terrain_descriptor_ids": list(MECHANICAL_DESCRIPTOR_IDS["terrain_descriptor_ids"]),
        "deployment_descriptor_id": str(MECHANICAL_DESCRIPTOR_IDS["deployment_descriptor_id"]),
        "army_build_descriptor_id": str(MECHANICAL_DESCRIPTOR_IDS["army_build_descriptor_id"]),
        "tool_descriptor_ids": list(MECHANICAL_DESCRIPTOR_IDS["tool_descriptor_ids"]),
    }


__all__ = [
    "MECHANICAL_DECISION_TYPES",
    "MECHANICAL_DESCRIPTOR_BUNDLE_ID",
    "MECHANICAL_DESCRIPTOR_IDS",
    "mechanical_descriptor_ids",
]
