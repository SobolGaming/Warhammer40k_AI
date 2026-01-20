from __future__ import annotations

import importlib
from dataclasses import is_dataclass
from enum import Enum
from typing import Any

from .commands import GameCommand
from .decisions import DecisionRequest
from ..battlefield.map import Objective, ObjectivePoint, TerrainFeature
from ..roster.army import Army
from ..roster.player import Player
from ..units.model import Model
from ..units.unit import Unit
from ..units.wargear import Wargear
from ..utility.entity_ids import get_entity_id
from ..utility.entity_registry import EntityRegistry
from ..utility.modifiers import Modifier, ModifierOp


ENTITY_KIND_BY_TYPE = {
    Player: "player",
    Army: "army",
    Unit: "unit",
    Model: "model",
    Wargear: "wargear",
    Objective: "objective",
    ObjectivePoint: "objective_marker",
    TerrainFeature: "terrain",
    DecisionRequest: "decision",
    GameCommand: "command",
}


def serialize_modifier(mod: Modifier) -> dict:
    return {"op": mod.op.name, "value": int(mod.value), "source": str(mod.source or "")}


def deserialize_modifier(data: dict) -> Modifier:
    return Modifier(
        op=ModifierOp[str(data.get("op"))],
        value=int(data.get("value", 0)),
        source=str(data.get("source", "") or ""),
    )


def encode_entity_ref(value: object) -> dict | None:
    for cls, kind in ENTITY_KIND_BY_TYPE.items():
        if isinstance(value, cls):
            return {"__ref__": {"kind": kind, "id": get_entity_id(value)}}
    return None


def encode_refs(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return {
            "__enum__": {
                "type": f"{value.__class__.__module__}.{value.__class__.__name__}",
                "name": value.name,
            }
        }
    ref = encode_entity_ref(value)
    if ref is not None:
        return ref
    if isinstance(value, Modifier):
        return {"__modifier__": serialize_modifier(value)}
    if isinstance(value, dict):
        encoded: dict = {}
        for key, val in value.items():
            if isinstance(key, (str, int)):
                out_key = str(key)
            else:
                key_ref = encode_entity_ref(key)
                out_key = key_ref["__ref__"]["id"] if key_ref else str(key)
            encoded[out_key] = encode_refs(val)
        return encoded
    if isinstance(value, (list, tuple, set)):
        items = [encode_refs(v) for v in list(value)]
        if isinstance(value, set):
            try:
                return sorted(items, key=lambda item: str(item))
            except Exception:
                return items
        return items
    if is_dataclass(value):
        return encode_refs(value.__dict__)
    raise TypeError(f"Unsupported serialized value type: {type(value).__name__}")


def decode_refs(value: Any, registry: EntityRegistry) -> Any:
    if isinstance(value, dict):
        if "__ref__" in value:
            ref = value["__ref__"] or {}
            kind = ref.get("kind")
            entity_id = ref.get("id")
            resolved = registry.get(entity_id, kind=kind)
            if resolved is None:
                raise KeyError(f"Unknown ref {kind}:{entity_id}")
            return resolved
        if "__enum__" in value:
            enum_info = value["__enum__"] or {}
            enum_path = enum_info.get("type")
            enum_name = enum_info.get("name")
            if not enum_path or not enum_name:
                raise KeyError("Invalid enum reference payload.")
            module_path, _, class_name = enum_path.rpartition(".")
            if not module_path or not class_name:
                raise KeyError(f"Invalid enum type path: {enum_path}")
            enum_module = importlib.import_module(module_path)
            enum_cls = getattr(enum_module, class_name, None)
            if enum_cls is None:
                raise KeyError(f"Enum class not found: {enum_path}")
            return enum_cls[str(enum_name)]
        if "__modifier__" in value:
            return deserialize_modifier(value["__modifier__"] or {})
        decoded: dict = {}
        for key, val in value.items():
            decoded[key] = decode_refs(val, registry)
        return decoded
    if isinstance(value, list):
        return [decode_refs(v, registry) for v in value]
    return value
