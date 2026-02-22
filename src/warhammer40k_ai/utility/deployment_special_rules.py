from __future__ import annotations

from collections import deque
import math
from typing import Iterable

from .aura_utils import distance_between_bases_3d
from .model_base import create_ellipse, create_rectangle


CONVERGENCE_OF_DOMINION_DATASHEET_ID = "000002361"
CONVERGENCE_OF_DOMINION_CHAIN_DISTANCE = 12.0
AEGIS_DEFENCE_LINE_DATASHEET_IDS = frozenset({"000002619", "000003955"})
AEGIS_DEFENCE_LINE_MAX_SHIELDS = 5
AEGIS_DEFENCE_LINE_MAX_BROKEN_SHIELDS = 2
AEGIS_DEFENCE_LINE_MAX_ENDS = 2
AEGIS_DEFENCE_LINE_BROKEN_MIDDLE_DISTANCE = 0.5
AEGIS_DEFENCE_LINE_TOUCH_EPSILON = 0.01


def _norm_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _unit_datasheet_id(unit: object) -> str:
    if unit is None:
        return ""
    datasheet_id = ""
    get_datasheet_id = getattr(unit, "get_datasheet_id", None)
    if callable(get_datasheet_id):
        datasheet_id = str(get_datasheet_id() or "").strip()
    if not datasheet_id:
        datasheet_id = str(getattr(getattr(unit, "_datasheet", None), "id", "") or "").strip()
    return datasheet_id


def is_convergence_of_dominion_deployment_unit(unit: object) -> bool:
    """Return True when the unit uses Convergence Of Dominion DEPLOYMENT rules."""
    if unit is None:
        return False

    datasheet_id = _unit_datasheet_id(unit)
    if datasheet_id == CONVERGENCE_OF_DOMINION_DATASHEET_ID:
        return True

    for ability in list(getattr(unit, "possible_abilities", []) or []):
        name_norm = _norm_text(getattr(ability, "name", ""))
        desc_norm = _norm_text(getattr(ability, "description", ""))
        if name_norm != "deployment":
            continue
        if (
            "do not have to be set up in unit coherency" in desc_norm
            and "wholly within 12" in desc_norm
            and "treated as a separate unit" in desc_norm
        ):
            return True
    return False


def is_aegis_defence_line_deployment_unit(unit: object) -> bool:
    """Return True when the unit uses Aegis Defence Line DEPLOYMENT section rules."""
    if unit is None:
        return False

    if _unit_datasheet_id(unit) in AEGIS_DEFENCE_LINE_DATASHEET_IDS:
        return True

    for ability in list(getattr(unit, "possible_abilities", []) or []):
        name_norm = _norm_text(getattr(ability, "name", ""))
        desc_norm = _norm_text(getattr(ability, "description", ""))
        if name_norm != "deployment":
            continue
        if (
            "1 platform section" in desc_norm
            and "up to 5 shield sections" in desc_norm
            and "up to 2 broken shield sections" in desc_norm
            and "up to 2 end sections" in desc_norm
            and "treated as a single model" in desc_norm
        ):
            return True
    return False


def _aegis_section_type(part: dict) -> str:
    explicit = _norm_text(part.get("section_type", ""))
    if explicit in {"platform", "shield", "broken_shield", "end"}:
        return explicit
    part_id = _norm_text(part.get("part_id", ""))
    if part_id.startswith("platform"):
        return "platform"
    if "broken" in part_id:
        return "broken_shield"
    if part_id.startswith("shield"):
        return "shield"
    if part_id.startswith("end"):
        return "end"
    return ""


def _compound_part_shape(part: dict, *, x: float, y: float, facing: float):
    local_x, local_y = part["offset"]
    cos_f = math.cos(facing)
    sin_f = math.sin(facing)
    global_x = x + (local_x * cos_f - local_y * sin_f)
    global_y = y + (local_x * sin_f + local_y * cos_f)
    total_facing = facing + float(part.get("facing", 0.0))
    shape = str(part["shape"]).lower()
    radius = (float(part["radius"][0]), float(part["radius"][1]))
    if shape in {"circle", "ellipse"}:
        return create_ellipse((global_x, global_y), radius, total_facing)
    if shape == "hull":
        return create_rectangle((global_x, global_y), radius, total_facing)
    raise ValueError(f"Unsupported Aegis section shape '{shape}'.")


def validate_aegis_defence_line_deployment_base(base: object) -> tuple[bool, str]:
    """Validate Aegis section composition/connectivity on a compound model base."""
    if base is None:
        return False, "Aegis DEPLOYMENT requires a model base."

    get_parts = getattr(base, "get_compound_parts", None)
    if not callable(get_parts):
        return False, "Aegis DEPLOYMENT requires compound section geometry."
    parts = list(get_parts() or [])
    if not parts:
        return False, "Aegis DEPLOYMENT requires compound section geometry."

    section_indexes: dict[str, list[int]] = {
        "platform": [],
        "shield": [],
        "broken_shield": [],
        "end": [],
    }
    for idx, part in enumerate(parts):
        section_type = _aegis_section_type(part)
        if not section_type:
            part_id = str(part.get("part_id", "") or f"section_{idx + 1}")
            return False, f"Aegis DEPLOYMENT has unknown section type for '{part_id}'."
        section_indexes[section_type].append(idx)

    if len(section_indexes["platform"]) != 1:
        return False, "Aegis DEPLOYMENT requires exactly 1 platform section."
    if len(section_indexes["shield"]) > AEGIS_DEFENCE_LINE_MAX_SHIELDS:
        return False, "Aegis DEPLOYMENT allows up to 5 shield sections."
    if len(section_indexes["broken_shield"]) > AEGIS_DEFENCE_LINE_MAX_BROKEN_SHIELDS:
        return False, "Aegis DEPLOYMENT allows up to 2 broken shield sections."
    if len(section_indexes["end"]) > AEGIS_DEFENCE_LINE_MAX_ENDS:
        return False, "Aegis DEPLOYMENT allows up to 2 end sections."

    x = float(getattr(base, "x", 0.0))
    y = float(getattr(base, "y", 0.0))
    facing = float(getattr(base, "facing", 0.0))
    part_shapes = [_compound_part_shape(part, x=x, y=y, facing=facing) for part in parts]

    adjacency: dict[int, set[int]] = {idx: set() for idx in range(len(parts))}
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            distance = float(part_shapes[i].distance(part_shapes[j]))
            if distance <= AEGIS_DEFENCE_LINE_TOUCH_EPSILON:
                adjacency[i].add(j)
                adjacency[j].add(i)

    broken_indexes = list(section_indexes["broken_shield"])
    broken_pair_distance = float("inf")
    if len(broken_indexes) == 2:
        left_idx, right_idx = broken_indexes
        broken_pair_distance = float(part_shapes[left_idx].distance(part_shapes[right_idx]))
        if broken_pair_distance <= AEGIS_DEFENCE_LINE_BROKEN_MIDDLE_DISTANCE + AEGIS_DEFENCE_LINE_TOUCH_EPSILON:
            adjacency[left_idx].add(right_idx)
            adjacency[right_idx].add(left_idx)

    visited: set[int] = set()
    queue: deque[int] = deque([0])
    while queue:
        idx = queue.popleft()
        if idx in visited:
            continue
        visited.add(idx)
        for nxt in sorted(adjacency[idx]):
            if nxt not in visited:
                queue.append(nxt)
    if len(visited) != len(parts):
        return False, "Aegis DEPLOYMENT requires all sections to be connected in one continuous defence line."

    platform_indexes = set(section_indexes["platform"])

    def _non_platform_degree(idx: int) -> int:
        return sum(1 for neighbor in adjacency[idx] if neighbor not in platform_indexes)

    if len(broken_indexes) == 1 and _non_platform_degree(broken_indexes[0]) > 1:
        return False, "Aegis DEPLOYMENT broken shield sections can only be in the middle as a pair."

    if (
        len(broken_indexes) == 2
        and broken_pair_distance > AEGIS_DEFENCE_LINE_BROKEN_MIDDLE_DISTANCE + AEGIS_DEFENCE_LINE_TOUCH_EPSILON
    ):
        if any(_non_platform_degree(idx) > 1 for idx in broken_indexes):
            return False, "Aegis DEPLOYMENT broken shield sections in the middle must be within 1/2\" of each other."

    return True, ""


def validate_aegis_defence_line_deployment(
    base_entries: Iterable[tuple[str, object]],
) -> tuple[bool, str]:
    entries = [(str(label or "").strip(), base) for label, base in list(base_entries or [])]
    if not entries:
        return True, ""
    for idx, (label, base) in enumerate(entries):
        valid, reason = validate_aegis_defence_line_deployment_base(base)
        if valid:
            continue
        model_label = label or f"Model #{idx + 1}"
        return False, f"{model_label}: {reason}"
    return True, ""


def validate_each_model_within_distance_of_another(
    base_entries: Iterable[tuple[str, object]],
    *,
    max_distance: float,
) -> tuple[bool, str]:
    """
    Validate that each listed model base is within max_distance (3D) of at least one other.
    """
    entries = [(str(label or "").strip(), base) for label, base in list(base_entries or [])]
    if len(entries) <= 1:
        return True, ""

    threshold = float(max_distance)
    for idx, (label, base) in enumerate(entries):
        if base is None:
            model_label = label or f"Model #{idx + 1}"
            return False, f"{model_label} has no base for distance validation."

        has_neighbor = False
        for jdx, (_other_label, other_base) in enumerate(entries):
            if jdx == idx or other_base is None:
                continue
            if float(distance_between_bases_3d(base, other_base)) <= threshold + 1e-6:
                has_neighbor = True
                break

        if not has_neighbor:
            model_label = label or f"Model #{idx + 1}"
            return False, f"{model_label} must be within {threshold:g}\" of one other model from its unit."

    return True, ""


def validate_convergence_of_dominion_deployment(
    base_entries: Iterable[tuple[str, object]],
) -> tuple[bool, str]:
    return validate_each_model_within_distance_of_another(
        base_entries,
        max_distance=CONVERGENCE_OF_DOMINION_CHAIN_DISTANCE,
    )
