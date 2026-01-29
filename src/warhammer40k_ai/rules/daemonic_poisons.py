from __future__ import annotations

from typing import Optional

from ..utility.entity_ids import get_entity_id

DAEMONIC_POISONS_NAME = "Daemonic Poisons"
POISONED_FLAG = "daemonic_poisons_poisoned"
POISONED_SOURCE = "daemonic_poisons_source"
POISONED_SOURCE_ID = "daemonic_poisons_source_id"


def unit_is_poisoned(unit) -> bool:
    if unit is None:
        return False
    try:
        root = unit.get_attached_unit_root()
    except Exception:
        root = unit
    for obj in (root, unit):
        sr = getattr(obj, "special_rules", None)
        if isinstance(sr, dict) and sr.get(POISONED_FLAG):
            return True
    return False


def apply_daemonic_poisons(
    target_unit,
    *,
    source_unit=None,
    ability_name: Optional[str] = None,
    game=None,
    player=None,
):
    if target_unit is None:
        return None
    try:
        root = target_unit.get_attached_unit_root()
    except Exception:
        root = target_unit
    if root is None:
        return None
    try:
        members = list(root.get_attached_unit_members() or [])
    except Exception:
        members = []
    if not members:
        members = [root]

    ability_name = str(ability_name or DAEMONIC_POISONS_NAME).strip() or DAEMONIC_POISONS_NAME
    source_id = get_entity_id(source_unit) if source_unit is not None else ""

    for unit in members:
        if unit is None:
            continue
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[POISONED_FLAG] = True
        sr[POISONED_SOURCE] = ability_name
        if source_id:
            sr[POISONED_SOURCE_ID] = source_id
        unit.special_rules = sr

    if game is not None:
        event_system = getattr(game, "event_system", None)
        if event_system is not None:
            event_system.publish(
                "daemonic_poisons_applied",
                player=player,
                source_unit=source_unit,
                target_unit=root,
                ability_name=ability_name,
            )

    return root
