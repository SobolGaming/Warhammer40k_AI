from __future__ import annotations

from types import SimpleNamespace


def attach_detachment_helpers(army):
    def _normalize(value: object) -> str:
        return " ".join(str(value or "").lower().split())

    def get_primary_detachment_type(_faction_id=None):
        return str(getattr(army, "detachment_type", "") or "")

    def get_detachment_types(_faction_id=None):
        primary = get_primary_detachment_type(_faction_id)
        return [primary] if primary else []

    def get_detachment_instances():
        primary = get_primary_detachment_type()
        if not primary:
            return []
        return [
            SimpleNamespace(
                detachment_type=primary,
                faction_id=str(getattr(army, "faction_id", "") or "").strip().upper(),
                selection_id="stub_detachment",
            )
        ]

    def get_detachment_instances_for_faction(faction_id=None):
        target = str(faction_id or getattr(army, "faction_id", "") or "").strip().upper()
        if not target:
            return get_detachment_instances()
        return [
            detachment
            for detachment in get_detachment_instances()
            if str(getattr(detachment, "faction_id", "") or "").strip().upper() in {"", target}
        ]

    def has_detachment_type(*names, faction_id=None):
        if faction_id:
            target_faction_id = str(faction_id or "").strip().upper()
            army_faction_id = str(getattr(army, "faction_id", "") or "").strip().upper()
            if army_faction_id and army_faction_id != target_faction_id:
                return False
        detachment = _normalize(get_primary_detachment_type())
        if not detachment:
            return False
        for name in names:
            target = _normalize(name)
            if not target:
                continue
            if detachment == target or detachment in target or target in detachment:
                return True
        return False

    army.get_primary_detachment_type = get_primary_detachment_type
    army.get_detachment_types = get_detachment_types
    army.get_detachment_instances = get_detachment_instances
    army.get_detachment_instances_for_faction = get_detachment_instances_for_faction
    army.has_detachment_type = has_detachment_type
    return army
