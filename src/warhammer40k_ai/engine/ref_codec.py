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
from ..units.wargear import Wargear, WargearProfile
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


def encode_wargear_profile_ref(value: object) -> dict | None:
    if not isinstance(value, WargearProfile):
        return None
    payload = {
        "profile_name": str(getattr(value, "name", "") or ""),
    }
    parent_wargear = getattr(value, "parent_wargear", None)
    if parent_wargear is not None:
        payload["parent_wargear_id"] = str(get_entity_id(parent_wargear) or "")
    else:
        payload["wargear_data"] = {
            "range": str(getattr(value, "_raw_range", "") or ""),
            "A": str(getattr(value, "_raw_attacks", "") or ""),
            "BS_WS": str(getattr(value, "_raw_skill", "") or ""),
            "S": str(getattr(value, "_raw_strength", "") or ""),
            "AP": str(getattr(value, "_raw_ap", "") or ""),
            "D": str(getattr(value, "_raw_damage", "") or ""),
            "description": str(getattr(value, "_raw_description", "") or ""),
        }
    return {"__wargear_profile__": payload}


def decode_wargear_profile_ref(data: dict, registry: EntityRegistry) -> WargearProfile:
    payload = dict(data or {})
    profile_name = str(payload.get("profile_name", "") or "").strip()
    parent_wargear_id = str(payload.get("parent_wargear_id", "") or "").strip()
    if parent_wargear_id:
        parent_wargear = registry.get(parent_wargear_id, kind="wargear")
        if parent_wargear is None:
            raise KeyError(f"Unknown wargear ref for profile: {parent_wargear_id}")
        profiles = dict(getattr(parent_wargear, "profiles", {}) or {})
        profile = profiles.get(profile_name)
        if profile is not None:
            return profile
        for candidate in profiles.values():
            if str(getattr(candidate, "name", "") or "").strip() == profile_name:
                return candidate
        raise KeyError(f"Unknown profile {profile_name!r} on wargear {parent_wargear_id}")
    wargear_data = dict(payload.get("wargear_data", {}) or {})
    fallback_name = profile_name or "default"
    return WargearProfile(fallback_name, wargear_data, parent_wargear=None)


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
    profile_ref = encode_wargear_profile_ref(value)
    if profile_ref is not None:
        return profile_ref
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
        if "__wargear_profile__" in value:
            return decode_wargear_profile_ref(value["__wargear_profile__"] or {}, registry)
        decoded: dict = {}
        for key, val in value.items():
            decoded[key] = decode_refs(val, registry)
        return decoded
    if isinstance(value, list):
        return [decode_refs(v, registry) for v in value]
    return value
