from __future__ import annotations

from typing import Iterable

from .aura_utils import distance_between_bases_3d


CONVERGENCE_OF_DOMINION_DATASHEET_ID = "000002361"
CONVERGENCE_OF_DOMINION_CHAIN_DISTANCE = 12.0


def _norm_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def is_convergence_of_dominion_deployment_unit(unit: object) -> bool:
    """Return True when the unit uses Convergence Of Dominion DEPLOYMENT rules."""
    if unit is None:
        return False

    datasheet_id = ""
    get_datasheet_id = getattr(unit, "get_datasheet_id", None)
    if callable(get_datasheet_id):
        datasheet_id = str(get_datasheet_id() or "").strip()
    if not datasheet_id:
        datasheet_id = str(getattr(getattr(unit, "_datasheet", None), "id", "") or "").strip()
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
