from __future__ import annotations

from typing import Optional


def get_entity_id(entity: object) -> str:
    if entity is None:
        raise ValueError("Entity is None; cannot resolve id.")
    value = getattr(entity, "id", None)
    if value:
        return str(value)
    value = getattr(entity, "_id", None)
    if value:
        return str(value)
    raise ValueError(f"Entity {type(entity).__name__} has no id.")


def maybe_entity_id(entity: object) -> Optional[str]:
    if entity is None:
        return None
    value = getattr(entity, "id", None)
    if value:
        return str(value)
    value = getattr(entity, "_id", None)
    if value:
        return str(value)
    return None
