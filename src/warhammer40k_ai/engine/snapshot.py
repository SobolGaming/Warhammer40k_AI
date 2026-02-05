from __future__ import annotations

import inspect
from dataclasses import is_dataclass
from enum import Enum
from typing import Any, Dict

from shapely.geometry import Polygon

from .battlefield import Battlefield
from .commands import GameCommand
from .decisions import CandidateAction, DecisionQueue, DecisionRequest
from .game import Game
from .mission_cards import MissionCard, PrimaryMissionCard, SecondaryMissionCard
from .phase import BattleRoundPhases, SetupPhase
from .ref_codec import decode_refs, encode_refs, serialize_modifier, deserialize_modifier
from .ruleset import RulesetBundle
from ..battlefield.map import (
    BarricadeTerrain,
    CraterTerrain,
    DebrisTerrain,
    HillsBuildingsTerrain,
    Map,
    Objective,
    ObjectiveCategory,
    ObjectivePoint,
    RuinsTerrain,
    TerrainFeature,
    TerrainType,
    WoodsTerrain,
)
from ..roster.army import Army
from ..roster.player import Player, PlayerControl
from ..units.model import Model
from ..units.status_effects import BattleShockEffect, StatusEffect
from ..units.unit import Unit, UnitRoundState
from ..units.wargear import Wargear
from ..utility.calcs import clear_enemy_model_cache
from ..utility.entity_ids import get_entity_id
from ..utility.entity_registry import EntityRegistry
from ..utility.model_base import Base, BaseType
from ..waha_helper import WahaHelper

SCHEMA_VERSION = 9
POSITION_SCALE = 1000
ANGLE_SCALE = 10000

_UNIT_STATE_EXCLUDE = {
    "_datasheet",
    "possible_wargear",
    "possible_abilities",
    "wargear_options",
    "models",
    "models_lost",
    "status_effects",
    "transport_passengers",
    "embarked_in",
    "attached_leaders",
    "attached_support_units",
    "attached_to",
    "support_joined_to",
    "parent_army",
    "round_state",
    "_ability_cache",
    "enhancement",
    "_death_ecstasy_pending_models",
    "_deathless_duty_pending_models",
    "_melee_fight_on_death_pending_models",
}

_MODEL_STATE_EXCLUDE = {
    "parent_unit",
    "wargear",
    "abilities",
    "model_base",
}

_PLAYER_STATE_EXCLUDE = {
    "army",
    "game",
    "stratagems",
    "primary_mission",
    "secondary_deck",
    "active_secondaries",
    "discarded_secondaries",
}

_ARMY_STATE_EXCLUDE = {
    "units",
    "player",
    "warlord",
    "enhancements",
    "detachment_managers",
}

_MANAGER_STATE_EXCLUDE = {
    "_waha",
    "_subscribed_handlers",
    "_required_events",
    "_defensive_reaction_cache",
    "_charge_melee_ap_cache",
    "_consolidate_move_cache",
    "_event_group",
    "_subscriptions_enabled",
    "available",
    "game",
    "player",
}

_UNIT_ROUND_FIELDS = [
    "remained_stationary_this_round",
    "advanced_this_round",
    "shot_this_round",
    "fell_back_this_round",
    "reinforced_this_round",
    "attempted_charge_this_round",
    "charged_this_round",
    "charged_turn",
    "charged_turn_owner",
    "charge_bonus_suppressed_turn",
    "charge_bonus_suppressed_turn_owner",
    "moved_this_round",
    "num_lost_models_this_round",
    "advance_roll",
    "embarked_this_round",
    "disembarked_this_round",
    "disembarked_from_moved_transport",
    "disembarked_from_destroyed_transport",
    "disembarked_cannot_charge",
    "performing_action_name",
    "action_started_turn",
    "action_completes_turn",
    "action_locked_until_turn_end",
    "fought_this_phase",
    "engaged_enemies_at_turn_start",
    "charge_target_ids",
]


def _to_fixed(value: float, scale: int = POSITION_SCALE) -> int:
    return int(round(float(value) * scale))


def _from_fixed(value: int, scale: int = POSITION_SCALE) -> float:
    return float(value) / float(scale)


def _to_angle_fixed(value: float) -> int:
    return _to_fixed(value, scale=ANGLE_SCALE)


def _from_angle_fixed(value: int) -> float:
    return _from_fixed(value, scale=ANGLE_SCALE)


def _serialize_polygon(poly: Polygon | None) -> dict | None:
    if poly is None:
        return None
    exterior = [[_to_fixed(x), _to_fixed(y)] for x, y in poly.exterior.coords]
    interiors = []
    for ring in poly.interiors:
        interiors.append([[_to_fixed(x), _to_fixed(y)] for x, y in ring.coords])
    return {"exterior": exterior, "interiors": interiors}


def _deserialize_polygon(data: dict | None) -> Polygon | None:
    if data is None:
        return None
    exterior = [(_from_fixed(x), _from_fixed(y)) for x, y in data.get("exterior", [])]
    interiors = []
    for ring in data.get("interiors", []):
        interiors.append([(_from_fixed(x), _from_fixed(y)) for x, y in ring])
    return Polygon(exterior, interiors)



def _serialize_rng_state(state: Any) -> Any:
    if isinstance(state, tuple):
        return [_serialize_rng_state(v) for v in state]
    if isinstance(state, list):
        return [_serialize_rng_state(v) for v in state]
    return state


def _deserialize_rng_state(state: Any) -> Any:
    if isinstance(state, list):
        return tuple(_deserialize_rng_state(v) for v in state)
    return state


def _serialize_status_effect(effect: StatusEffect) -> dict:
    if isinstance(effect, BattleShockEffect):
        return {
            "type": "BattleShockEffect",
            "id": get_entity_id(effect),
            "turn": int(effect.turn),
            "phase": int(effect.phase),
        }
    raise TypeError(f"Unsupported status effect type: {type(effect).__name__}")


def _deserialize_status_effect(data: dict) -> StatusEffect:
    effect_type = data.get("type")
    if effect_type == "BattleShockEffect":
        effect = BattleShockEffect(current_turn=max(0, int(data.get("turn", 1)) - 1))
        effect._id = str(data.get("id") or effect._id)
        effect.turn = int(data.get("turn", effect.turn))
        effect.phase = int(data.get("phase", effect.phase))
        return effect
    raise TypeError(f"Unsupported status effect type: {effect_type}")


def _serialize_model(model: Model) -> dict:
    base = model.model_base
    radius = list(getattr(base, "radius", (0.0, 0.0)) or (0.0, 0.0))
    pos = model.get_location()
    last_path = []
    for point in list(getattr(model, "last_move_path", []) or []):
        if not point:
            continue
        x, y = point[0], point[1]
        z = point[2] if len(point) > 2 else 0.0
        facing = point[3] if len(point) > 3 else 0.0
        last_path.append([_to_fixed(x), _to_fixed(y), _to_fixed(z), _to_angle_fixed(facing)])
    data = {
        "id": get_entity_id(model),
        "name": str(model.name or ""),
        "base": {
            "type": base.base_type.name,
            "radius": [_to_fixed(radius[0]), _to_fixed(radius[1])],
            "model_height": _to_fixed(getattr(base, "model_height", 0.0)),
        },
        "position": {
            "x": _to_fixed(pos[0]),
            "y": _to_fixed(pos[1]),
            "z": _to_fixed(pos[2]),
            "facing": _to_angle_fixed(pos[3]),
        },
        "stats": {
            "base": {
                "movement": int(getattr(model, "_base_movement", 0)),
                "toughness": int(getattr(model, "_base_toughness", 0)),
                "save": int(getattr(model, "_base_save", 0)),
                "wounds": int(getattr(model, "_base_wounds", 0)),
                "leadership": int(getattr(model, "_base_leadership", 0)),
                "objective_control": int(getattr(model, "_base_objective_control", 0)),
            },
            "current": {
                "movement": int(getattr(model, "_movement", 0)),
                "toughness": int(getattr(model, "_toughness", 0)),
                "save": int(getattr(model, "_save", 0)),
                "wounds": int(getattr(model, "_wounds", 0)),
                "leadership": int(getattr(model, "_leadership", 0)),
                "objective_control": int(getattr(model, "_objective_control", 0)),
            },
            "raw": {
                "movement": getattr(model, "_movement_raw", None),
                "toughness": getattr(model, "_toughness_raw", None),
                "save": getattr(model, "_save_raw", None),
                "wounds": getattr(model, "_wounds_raw", None),
                "leadership": getattr(model, "_leadership_raw", None),
                "objective_control": getattr(model, "_objective_control_raw", None),
                "inv_save": getattr(model, "_inv_save_raw", None),
            },
            "inv_save": {
                "value": getattr(model, "_inv_save", None),
                "condition": getattr(model, "_inv_save_condition", None),
            },
        },
        "optional_wargear": list(getattr(model, "optional_wargear", []) or []),
        "wargear": [
            {"id": get_entity_id(wg), "name": str(getattr(wg, "name", "") or "")}
            for wg in list(getattr(model, "wargear", []) or [])
            if wg is not None
        ],
        "once_per_battle_used": sorted(list(getattr(model, "_once_per_battle_used", set()) or set())),
        "once_per_battle_use_count": {
            str(k): int(v)
            for k, v in sorted(list((getattr(model, "_once_per_battle_use_count", {}) or {}).items()))
        },
        "once_per_battle_extra_uses": {
            str(k): int(v)
            for k, v in sorted(list((getattr(model, "_once_per_battle_extra_uses", {}) or {}).items()))
        },
        "once_per_battle_last_phase": {
            str(k): str(v)
            for k, v in sorted(list((getattr(model, "_once_per_battle_last_phase", {}) or {}).items()))
        },
        "temporary_effects": encode_refs(getattr(model, "_temporary_effects", {}) or {}),
        "last_move_path": last_path,
        "shot_via_firing_deck_this_round": bool(getattr(model, "_shot_via_firing_deck_this_round", False)),
        "pending_placement": bool(getattr(model, "_pending_placement", False)),
        "pending_placement_source": getattr(model, "_pending_placement_source", None),
        "horrors_kind": getattr(model, "_horrors_kind", None),
        "last_damage_source_kind": getattr(model, "_last_damage_source_kind", None),
    }
    return data


def _apply_model_state(model: Model, data: dict, unit: Unit) -> None:
    model._id = str(data.get("id") or model._id)
    stats = data.get("stats", {}) or {}
    base_stats = stats.get("base", {}) or {}
    current_stats = stats.get("current", {}) or {}
    raw_stats = stats.get("raw", {}) or {}
    inv_stats = stats.get("inv_save", {}) or {}

    model._base_movement = int(base_stats.get("movement", 0))
    model._base_toughness = int(base_stats.get("toughness", 0))
    model._base_save = int(base_stats.get("save", 0))
    model._base_wounds = int(base_stats.get("wounds", 0))
    model._base_leadership = int(base_stats.get("leadership", 0))
    model._base_objective_control = int(base_stats.get("objective_control", 0))

    model._movement = int(current_stats.get("movement", model._base_movement))
    model._toughness = int(current_stats.get("toughness", model._base_toughness))
    model._save = int(current_stats.get("save", model._base_save))
    model._wounds = int(current_stats.get("wounds", model._base_wounds))
    model._leadership = int(current_stats.get("leadership", model._base_leadership))
    model._objective_control = int(current_stats.get("objective_control", model._base_objective_control))

    model._movement_raw = raw_stats.get("movement", None)
    model._toughness_raw = raw_stats.get("toughness", None)
    model._save_raw = raw_stats.get("save", None)
    model._wounds_raw = raw_stats.get("wounds", None)
    model._leadership_raw = raw_stats.get("leadership", None)
    model._objective_control_raw = raw_stats.get("objective_control", None)
    model._inv_save_raw = raw_stats.get("inv_save", None)

    model._inv_save = inv_stats.get("value", None)
    model._inv_save_condition = inv_stats.get("condition", None)
    model._pending_placement = bool(data.get("pending_placement", False))
    model._pending_placement_source = data.get("pending_placement_source", None)
    model._horrors_kind = data.get("horrors_kind", None)
    model._last_damage_source_kind = data.get("last_damage_source_kind", None)

    base = data.get("base", {}) or {}
    base_type = BaseType[base.get("type", BaseType.CIRCULAR.name)]
    radius = base.get("radius", [0, 0])
    new_base = Base(base_type, (_from_fixed(radius[0]), _from_fixed(radius[1])))
    new_base.set_model_height(_from_fixed(base.get("model_height", 0)))
    pos = data.get("position", {}) or {}
    new_base.set_position(
        _from_fixed(pos.get("x", 0)),
        _from_fixed(pos.get("y", 0)),
        _from_fixed(pos.get("z", 0)),
    )
    new_base.set_facing(_from_angle_fixed(pos.get("facing", 0)))
    model.model_base = new_base

    model.optional_wargear = list(data.get("optional_wargear", []) or [])
    model._once_per_battle_used = set(data.get("once_per_battle_used", []) or [])
    model._once_per_battle_use_count = {
        str(k): int(v)
        for k, v in dict(data.get("once_per_battle_use_count", {}) or {}).items()
        if str(k)
    }
    if not model._once_per_battle_use_count and model._once_per_battle_used:
        model._once_per_battle_use_count = {str(k): 1 for k in model._once_per_battle_used}
    model._once_per_battle_extra_uses = {
        str(k): int(v)
        for k, v in dict(data.get("once_per_battle_extra_uses", {}) or {}).items()
        if str(k)
    }
    model._once_per_battle_last_phase = {
        str(k): str(v)
        for k, v in dict(data.get("once_per_battle_last_phase", {}) or {}).items()
        if str(k)
    }
    model._temporary_effects = dict(data.get("temporary_effects", {}) or {})
    model.last_move_path = []
    for point in data.get("last_move_path", []) or []:
        if not point:
            continue
        x = _from_fixed(point[0])
        y = _from_fixed(point[1])
        z = _from_fixed(point[2]) if len(point) > 2 else 0.0
        facing = _from_angle_fixed(point[3]) if len(point) > 3 else 0.0
        model.last_move_path.append((x, y, z, facing))
    model._shot_via_firing_deck_this_round = bool(data.get("shot_via_firing_deck_this_round", False))
    model.set_parent_unit(unit)

    model.wargear = []
    wargear_specs = data.get("wargear", []) or []
    if wargear_specs:
        templates = list(getattr(unit, "possible_wargear", []) or [])
        template_by_name = {Unit._norm_wargear_name(getattr(wg, "name", "")): wg for wg in templates}
        for spec in wargear_specs:
            name = str(spec.get("name", "") or "")
            key = Unit._norm_wargear_name(name)
            template = template_by_name.get(key)
            if template is None:
                raise ValueError(f"Unknown wargear {name!r} for unit {unit.name}")
            cloned = template.clone()
            cloned._id = str(spec.get("id") or cloned._id)
            model.wargear.append(cloned)


def _serialize_round_state(unit: Unit) -> dict:
    state: dict[str, Any] = {}
    rs = getattr(unit, "round_state", None)
    for key in _UNIT_ROUND_FIELDS:
        state[key] = getattr(rs, key, None)
    return encode_refs(state)


def _apply_round_state(unit: Unit, data: dict, registry: EntityRegistry) -> None:
    rs = UnitRoundState()
    decoded = decode_refs(data, registry)
    for key in _UNIT_ROUND_FIELDS:
        if key in decoded:
            setattr(rs, key, decoded[key])
    unit.round_state = rs


def _serialize_unit(unit: Unit) -> dict:
    datasheet = getattr(unit, "_datasheet", None)
    state: dict[str, Any] = {}
    for key, value in unit.__dict__.items():
        if key in _UNIT_STATE_EXCLUDE:
            continue
        if callable(value):
            continue
        state[key] = encode_refs(value)

    modifiers = {}
    for char_name, mods in (getattr(unit, "_characteristic_modifiers", {}) or {}).items():
        modifiers[char_name] = [serialize_modifier(m) for m in list(mods or [])]

    return {
        "id": get_entity_id(unit),
        "datasheet_id": getattr(datasheet, "id", None),
        "datasheet_name": getattr(datasheet, "name", None),
        "faction_id": getattr(datasheet, "faction_id", None),
        "enhancement_id": getattr(getattr(unit, "enhancement", None), "id", None),
        "enhancement_name": getattr(getattr(unit, "enhancement", None), "name", None),
        "state": state,
        "round_state": _serialize_round_state(unit),
        "attached_to_id": get_entity_id(unit.attached_to) if getattr(unit, "attached_to", None) else None,
        "attached_leader_ids": [get_entity_id(u) for u in list(getattr(unit, "attached_leaders", []) or [])],
        "attached_support_ids": [get_entity_id(u) for u in list(getattr(unit, "attached_support_units", []) or [])],
        "support_joined_to_id": get_entity_id(unit.support_joined_to) if getattr(unit, "support_joined_to", None) else None,
        "transport_passenger_ids": [get_entity_id(u) for u in list(getattr(unit, "transport_passengers", []) or [])],
        "embarked_in_id": get_entity_id(unit.embarked_in) if getattr(unit, "embarked_in", None) else None,
        "models": [_serialize_model(m) for m in list(getattr(unit, "models", []) or [])],
        "models_lost": [_serialize_model(m) for m in list(getattr(unit, "models_lost", []) or [])],
        "status_effects": [_serialize_status_effect(eff) for eff in list(getattr(unit, "status_effects", []) or [])],
        "characteristic_modifiers": modifiers,
    }


def _apply_unit_state(unit: Unit, data: dict, registry: EntityRegistry) -> None:
    unit._id = str(data.get("id") or unit._id)
    state = data.get("state", {}) or {}
    decoded_state = decode_refs(state, registry)
    for key, value in decoded_state.items():
        if key in _UNIT_STATE_EXCLUDE:
            continue
        setattr(unit, key, value)

    # Snapshot encoding stringifies dict keys. Units store points buckets in
    # `models_cost` with integer keys, so convert numeric string keys back.
    models_cost = getattr(unit, "models_cost", None)
    if isinstance(models_cost, dict):
        fixed_models_cost: dict = {}
        for raw_key, raw_val in models_cost.items():
            key = raw_key
            if isinstance(raw_key, str):
                txt = raw_key.strip()
                if txt.isdigit():
                    key = int(txt)
            fixed_models_cost[key] = raw_val
        unit.models_cost = fixed_models_cost

    modifiers = {}
    for char_name, mods in (data.get("characteristic_modifiers", {}) or {}).items():
        modifiers[char_name] = [deserialize_modifier(m) for m in list(mods or [])]
    unit._characteristic_modifiers = modifiers


def _serialize_objective_point(point: ObjectivePoint) -> dict:
    return {
        "id": get_entity_id(point),
        "x": _to_fixed(point.x),
        "y": _to_fixed(point.y),
        "z": _to_fixed(point.z),
        "control_radius": _to_fixed(point.control_radius),
        "controlling_player_id": get_entity_id(point.controlling_player) if point.controlling_player else None,
        "terraformed_by_id": get_entity_id(point.terraformed_by) if point.terraformed_by else None,
        "cleansed_by_id": get_entity_id(point.cleansed_by) if point.cleansed_by else None,
        "is_hazard": bool(getattr(point, "is_hazard", False)),
        "removed": bool(getattr(point, "removed", False)),
        "sticky_controller_id": get_entity_id(point.sticky_controller) if point.sticky_controller else None,
        "sticky_source": getattr(point, "sticky_source", None),
        "worldblight_controller_id": get_entity_id(getattr(point, "worldblight_controller", None))
        if getattr(point, "worldblight_controller", None)
        else None,
        "worldblight_source": getattr(point, "worldblight_source", None),
    }


def _deserialize_objective_point(data: dict) -> ObjectivePoint:
    point = ObjectivePoint(
        x=_from_fixed(data["x"]),
        y=_from_fixed(data["y"]),
        z=_from_fixed(data.get("z", 0)),
        control_radius=_from_fixed(data.get("control_radius", 0)),
    )
    point._id = str(data.get("id") or point._id)
    point.is_hazard = bool(data.get("is_hazard", False))
    point.removed = bool(data.get("removed", False))
    point.sticky_source = data.get("sticky_source", None)
    point.worldblight_source = data.get("worldblight_source", None)
    return point


def _serialize_objective(obj: Objective) -> dict:
    return {
        "id": get_entity_id(obj),
        "name": str(obj.name or ""),
        "category": obj.category.name if isinstance(obj.category, Enum) else str(obj.category),
        "points": int(obj.points),
        "description": str(obj.description or ""),
        "completed": bool(getattr(obj, "completed", False)),
        "location_id": get_entity_id(obj.location) if getattr(obj, "location", None) else None,
    }


def _deserialize_objective(data: dict, points_by_id: dict[str, ObjectivePoint]) -> Objective:
    category_name = data.get("category", ObjectiveCategory.PRIMARY.name)
    category = ObjectiveCategory[category_name]
    loc = points_by_id.get(data.get("location_id"))

    def _cond(game, point=loc):
        return point is not None and getattr(point, "controlling_player", None) is not None

    obj = Objective(
        name=str(data.get("name", "") or ""),
        category=category,
        points=int(data.get("points", 0)),
        description=str(data.get("description", "") or ""),
        conditions=_cond,
        location=loc,
    )
    obj._id = str(data.get("id") or obj._id)
    obj.completed = bool(data.get("completed", False))
    return obj


def _serialize_terrain_feature(feature: TerrainFeature) -> dict:
    base = {
        "id": get_entity_id(feature),
        "terrain_type": feature.terrain_type.name,
        "footprint": _serialize_polygon(feature.footprint),
        "bounding_box": {
            "min": [_to_fixed(v) for v in feature.bounding_box.get("min", (0, 0, 0))],
            "max": [_to_fixed(v) for v in feature.bounding_box.get("max", (0, 0, 0))],
        },
        "traversal_rules": encode_refs(feature.traversal_rules or {}),
        "shadow_of_chaos_owner_ids": sorted(str(v) for v in (getattr(feature, "shadow_of_chaos_owner_ids", []) or [])),
    }
    if isinstance(feature, RuinsTerrain):
        base["walls"] = [
            {
                "polygon": _serialize_polygon(w.get("polygon")),
                "z_bottom": _to_fixed(w.get("z_bottom", 0.0)),
                "z_top": _to_fixed(w.get("z_top", 0.0)),
                "thickness": _to_fixed(w.get("thickness", 0.0)),
            }
            for w in list(getattr(feature, "walls", []) or [])
        ]
        base["openings"] = [
            {
                "polygon": _serialize_polygon(o.get("polygon")),
                "z_bottom": _to_fixed(o.get("z_bottom", 0.0)),
                "z_top": _to_fixed(o.get("z_top", 0.0)),
                "allows_movement": bool(o.get("allows_movement", False)),
                "allows_los": bool(o.get("allows_los", False)),
            }
            for o in list(getattr(feature, "openings", []) or [])
        ]
        base["floors"] = [
            {
                "polygon": _serialize_polygon(f.get("polygon")),
                "elevation": _to_fixed(f.get("elevation", 0.0)),
                "thickness": _to_fixed(f.get("thickness", 0.0)),
            }
            for f in list(getattr(feature, "floors", []) or [])
        ]
        height_map = []
        for (x, y), z in (getattr(feature, "height_map", {}) or {}).items():
            height_map.append({
                "x": _to_fixed(x),
                "y": _to_fixed(y),
                "z": _to_fixed(z),
            })
        base["height_map"] = height_map
    if isinstance(feature, WoodsTerrain):
        base["height"] = _to_fixed(getattr(feature, "height", 0.0))
        base["density"] = float(getattr(feature, "density", 0.0))
    if isinstance(feature, CraterTerrain):
        base["depth"] = _to_fixed(getattr(feature, "depth", 0.0))
        base["rim_height"] = _to_fixed(getattr(feature, "rim_height", 0.0))
    if isinstance(feature, BarricadeTerrain):
        base["height"] = _to_fixed(getattr(feature, "height", 0.0))
        base["thickness"] = _to_fixed(getattr(feature, "thickness", 0.0))
    if isinstance(feature, DebrisTerrain):
        base["height"] = _to_fixed(getattr(feature, "height", 0.0))
        base["scatter_density"] = float(getattr(feature, "scatter_density", 0.0))
    if isinstance(feature, HillsBuildingsTerrain):
        base["height"] = _to_fixed(getattr(feature, "height", 0.0))
        base["max_base_size"] = _to_fixed(getattr(feature, "max_base_size", 0.0))
        base["access_points"] = [
            _serialize_polygon(p) for p in list(getattr(feature, "access_points", []) or [])
        ]
    return base


def _deserialize_terrain_feature(data: dict) -> TerrainFeature:
    terrain_type = TerrainType[str(data.get("terrain_type"))]
    footprint = _deserialize_polygon(data.get("footprint"))
    feature: TerrainFeature
    if terrain_type == TerrainType.RUINS:
        feature = RuinsTerrain(
            footprint,
            walls=[
                {
                    "polygon": _deserialize_polygon(w.get("polygon")),
                    "z_bottom": _from_fixed(w.get("z_bottom", 0)),
                    "z_top": _from_fixed(w.get("z_top", 0)),
                    "thickness": _from_fixed(w.get("thickness", 0)),
                }
                for w in data.get("walls", []) or []
            ],
            openings=[
                {
                    "polygon": _deserialize_polygon(o.get("polygon")),
                    "z_bottom": _from_fixed(o.get("z_bottom", 0)),
                    "z_top": _from_fixed(o.get("z_top", 0)),
                    "allows_movement": bool(o.get("allows_movement", False)),
                    "allows_los": bool(o.get("allows_los", False)),
                }
                for o in data.get("openings", []) or []
            ],
            floors=[
                {
                    "polygon": _deserialize_polygon(f.get("polygon")),
                    "elevation": _from_fixed(f.get("elevation", 0)),
                    "thickness": _from_fixed(f.get("thickness", 0)),
                }
                for f in data.get("floors", []) or []
            ],
            height_map={
                (_from_fixed(entry["x"]), _from_fixed(entry["y"])): _from_fixed(entry["z"])
                for entry in data.get("height_map", []) or []
            },
        )
    elif terrain_type == TerrainType.WOODS:
        feature = WoodsTerrain(
            footprint,
            height=_from_fixed(data.get("height", 0)),
            density=float(data.get("density", 0.0)),
        )
    elif terrain_type == TerrainType.CRATER_AND_RUBBLE:
        feature = CraterTerrain(
            footprint,
            depth=_from_fixed(data.get("depth", 0)),
            rim_height=_from_fixed(data.get("rim_height", 0)),
        )
    elif terrain_type == TerrainType.BARRICADE_AND_FUEL_PIPES:
        feature = BarricadeTerrain(
            footprint,
            height=_from_fixed(data.get("height", 0)),
            thickness=_from_fixed(data.get("thickness", 0)),
        )
    elif terrain_type == TerrainType.DEBRIS_AND_STATUARY:
        feature = DebrisTerrain(
            footprint,
            height=_from_fixed(data.get("height", 0)),
            scatter_density=float(data.get("scatter_density", 0.0)),
        )
    elif terrain_type == TerrainType.HILLS_AND_SEALED_BUILDINGS:
        access = [_deserialize_polygon(p) for p in data.get("access_points", []) or []]
        feature = HillsBuildingsTerrain(
            footprint,
            height=_from_fixed(data.get("height", 0)),
            access_points=access,
            max_base_size=_from_fixed(data.get("max_base_size", 0)),
        )
    else:
        feature = TerrainFeature(terrain_type, footprint, {"min": (0, 0, 0), "max": (0, 0, 0)})

    feature._id = str(data.get("id") or feature._id)
    if "bounding_box" in data:
        bb = data["bounding_box"]
        feature.bounding_box = {
            "min": tuple(_from_fixed(v) for v in bb.get("min", (0, 0, 0))),
            "max": tuple(_from_fixed(v) for v in bb.get("max", (0, 0, 0))),
        }
    if "traversal_rules" in data:
        feature.traversal_rules = dict(data.get("traversal_rules", {}) or {})
    if "shadow_of_chaos_owner_ids" in data:
        try:
            owners = set(str(v) for v in (data.get("shadow_of_chaos_owner_ids") or []))
        except Exception:
            owners = set()
        feature.shadow_of_chaos_owner_ids = owners
    return feature


def _serialize_map(game_map) -> dict:
    if game_map is None:
        return {
            "width": 0,
            "height": 0,
            "terrain_features": [],
            "objective_points": [],
            "objectives": [],
            "deployment_zones": {},
            "units": [],
        }
    objectives = list(getattr(game_map, "objectives", []) or [])
    objective_points = []
    for obj in objectives:
        loc = getattr(obj, "location", None)
        if isinstance(loc, ObjectivePoint):
            objective_points.append(loc)
    return {
        "width": int(getattr(game_map, "width", 0)),
        "height": int(getattr(game_map, "height", 0)),
        "terrain_features": [_serialize_terrain_feature(t) for t in list(getattr(game_map, "terrain_features", []) or [])],
        "objective_points": [_serialize_objective_point(p) for p in objective_points],
        "objectives": [_serialize_objective(o) for o in objectives],
        "deployment_zones": _serialize_deployment_zones(getattr(game_map, "deployment_zones", {}) or {}),
        "units": [get_entity_id(u) for u in list(getattr(game_map, "units", []) or [])],
    }


def _serialize_decision(request: DecisionRequest) -> dict:
    data = request.to_dict()
    data["context"] = encode_refs(data.get("context", {}) or {})
    data["options"] = [
        {
            "option_id": opt.get("option_id"),
            "label": opt.get("label"),
            "payload": encode_refs(opt.get("payload", {}) or {}),
        }
        for opt in data.get("options", []) or []
    ]
    data["candidates"] = [
        {
            "action_id": cand.get("action_id"),
            "params": encode_refs(cand.get("params", {}) or {}),
            "metadata": encode_refs(cand.get("metadata", {}) or {}),
        }
        for cand in data.get("candidates", []) or []
    ]
    return data


def _deserialize_decision(data: dict) -> DecisionRequest:
    options = []
    for opt in data.get("options", []) or []:
        opt_payload = opt.get("payload", {}) or {}
        options.append(
            {
                "option_id": str(opt.get("option_id", "") or ""),
                "label": str(opt.get("label", "") or ""),
                "payload": opt_payload,
            }
        )
    candidates = []
    for cand in data.get("candidates", []) or []:
        candidates.append(
            {
                "action_id": cand.get("action_id"),
                "params": cand.get("params", {}) or {},
                "metadata": cand.get("metadata", {}) or {},
            }
        )
    return DecisionRequest.from_dict(
        {
            "decision_id": data.get("decision_id"),
            "player_id": data.get("player_id"),
            "decision_type": data.get("decision_type"),
            "prompt": data.get("prompt"),
            "options": options,
            "context": data.get("context", {}),
            "candidates": candidates,
            "mask": list(data.get("mask", []) or []),
            "mask_reasons": list(data.get("mask_reasons", []) or []),
            "created_at": data.get("created_at"),
            "timeout_seconds": data.get("timeout_seconds"),
        }
    )


def _serialize_command(command: GameCommand) -> dict:
    data = command.to_dict()
    data["payload"] = encode_refs(data.get("payload", {}) or {})
    data["metadata"] = encode_refs(data.get("metadata", {}) or {})
    return data


def _deserialize_command(data: dict) -> GameCommand:
    return GameCommand.from_dict(data)


_CARD_REGISTRY: dict[str, dict[str, type]] | None = None


def _build_card_registry() -> dict[str, dict[str, type]]:
    registry: dict[str, dict[str, type]] = {"primary": {}, "secondary": {}}
    from . import mission_cards as cards_module
    for _name, cls in cards_module.__dict__.items():
        if not inspect.isclass(cls):
            continue
        if not issubclass(cls, MissionCard):
            continue
        if cls in (MissionCard, PrimaryMissionCard, SecondaryMissionCard):
            continue
        instance = cls()
        kind = "primary" if isinstance(instance, PrimaryMissionCard) else "secondary"
        registry[kind][instance.name] = cls
    return registry


def _get_card_registry() -> dict[str, dict[str, type]]:
    global _CARD_REGISTRY
    if _CARD_REGISTRY is None:
        _CARD_REGISTRY = _build_card_registry()
    return _CARD_REGISTRY


def _serialize_card(card: MissionCard | None) -> dict | None:
    if card is None:
        return None
    kind = "primary" if isinstance(card, PrimaryMissionCard) else "secondary"
    state: dict[str, Any] = {}
    for key, value in card.__dict__.items():
        if callable(value):
            continue
        state[key] = encode_refs(value)
    return {"kind": kind, "name": str(card.name or ""), "state": state}


def _deserialize_card(data: dict | None, registry: EntityRegistry) -> MissionCard | None:
    if data is None:
        return None
    kind = data.get("kind")
    name = data.get("name")
    card_registry = _get_card_registry()
    cls = card_registry.get(kind, {}).get(name)
    if cls is None:
        raise KeyError(f"Unknown mission card {kind}:{name}")
    card = cls()
    state = decode_refs(data.get("state", {}) or {}, registry)
    for key, value in state.items():
        setattr(card, key, value)
    return card


def _serialize_player(player: Player) -> dict:
    state: dict[str, Any] = {}
    for key, value in player.__dict__.items():
        if key in _PLAYER_STATE_EXCLUDE:
            continue
        if callable(value):
            continue
        state[key] = encode_refs(value)
    return {
        "id": get_entity_id(player),
        "name": str(player.name or ""),
        "control": player.control.name if isinstance(player.control, Enum) else str(player.control),
        "state": state,
        "army_id": get_entity_id(player.army) if getattr(player, "army", None) else None,
        "primary_mission": _serialize_card(getattr(player, "primary_mission", None)),
        "secondary_deck": [_serialize_card(c) for c in list(getattr(player, "secondary_deck", []) or [])],
        "active_secondaries": [_serialize_card(c) for c in list(getattr(player, "active_secondaries", []) or [])],
        "discarded_secondaries": [_serialize_card(c) for c in list(getattr(player, "discarded_secondaries", []) or [])],
        "stratagems_state": _serialize_manager_state(getattr(player, "stratagems", None)),
    }


def _apply_player_state(player: Player, data: dict, registry: EntityRegistry) -> None:
    player._id = str(data.get("id") or player._id)
    state = decode_refs(data.get("state", {}) or {}, registry)
    for key, value in state.items():
        if key in _PLAYER_STATE_EXCLUDE:
            continue
        setattr(player, key, value)


def _is_rule_manager(value: object) -> bool:
    if value is None:
        return False
    module = getattr(value.__class__, "__module__", "")
    return module.startswith("warhammer40k_ai.rules")


def _serialize_manager_state(manager: object) -> dict | None:
    if manager is None:
        return None
    state: dict[str, Any] = {}
    for key, value in manager.__dict__.items():
        if key in _MANAGER_STATE_EXCLUDE:
            continue
        if callable(value):
            continue
        if is_dataclass(value):
            continue
        state[key] = encode_refs(value)
    return state


def _apply_manager_state(manager: object, data: dict | None, registry: EntityRegistry) -> None:
    if manager is None or data is None:
        return
    decoded = decode_refs(data, registry)
    for key, value in decoded.items():
        if key in _MANAGER_STATE_EXCLUDE:
            continue
        setattr(manager, key, value)


def _serialize_army(army: Army) -> dict:
    state: dict[str, Any] = {}
    for key, value in army.__dict__.items():
        if key in _ARMY_STATE_EXCLUDE:
            continue
        if callable(value):
            continue
        if _is_rule_manager(value):
            continue
        state[key] = encode_refs(value)

    managers = {}
    for key, value in army.__dict__.items():
        if key in _ARMY_STATE_EXCLUDE:
            continue
        if _is_rule_manager(value):
            managers[key] = _serialize_manager_state(value)

    return {
        "id": get_entity_id(army),
        "faction": str(getattr(army, "faction", "") or ""),
        "faction_id": getattr(army, "faction_id", None),
        "detachment_type": str(getattr(army, "detachment_type", "") or ""),
        "points_limit": int(getattr(army, "points_limit", 0) or 0),
        "state": state,
        "units": [get_entity_id(u) for u in list(getattr(army, "units", []) or [])],
        "warlord_id": get_entity_id(army.warlord) if getattr(army, "warlord", None) else None,
        "enhancements": [get_entity_id(e) for e in list(getattr(army, "enhancements", []) or [])],
        "rule_managers": managers,
    }


def _apply_army_state(army: Army, data: dict, registry: EntityRegistry) -> None:
    army._id = str(data.get("id") or army._id)
    state = decode_refs(data.get("state", {}) or {}, registry)
    for key, value in state.items():
        if key in _ARMY_STATE_EXCLUDE:
            continue
        setattr(army, key, value)

    managers = data.get("rule_managers", {}) or {}
    for key, mgr_state in managers.items():
        _apply_manager_state(getattr(army, key, None), mgr_state, registry)


def _serialize_deployment_zones(zones: dict) -> dict:
    encoded = {}
    for player_id, zone in (zones or {}).items():
        if not isinstance(zone, dict):
            encoded[str(player_id)] = encode_refs(zone)
            continue
        zone_copy = {}
        for key, value in zone.items():
            if key == "mission_zones":
                zone_copy[key] = [
                    {
                        "name": z.name,
                        "zone_type": z.zone_type.value if isinstance(z.zone_type, Enum) else str(z.zone_type),
                        "vertices": [[_to_fixed(x), _to_fixed(y)] for x, y in list(z.vertices or [])],
                        "cutouts": [
                            {
                                "cutout_type": c.cutout_type.value if isinstance(c.cutout_type, Enum) else str(c.cutout_type),
                                "center_x": _to_fixed(c.center_x),
                                "center_y": _to_fixed(c.center_y),
                                "parameters": encode_refs(_serialize_cutout_parameters(c.cutout_type, c.parameters)),
                            }
                            for c in list(z.cutouts or [])
                        ] if getattr(z, "cutouts", None) else [],
                    }
                    for z in list(value or [])
                ]
            else:
                zone_copy[key] = encode_refs(value)
        encoded[str(player_id)] = zone_copy
    return encoded


def _serialize_cutout_parameters(cutout_type: object, parameters: object) -> object:
    kind = str(getattr(cutout_type, "value", cutout_type) or "").lower()
    if kind == "circle":
        return _to_fixed(parameters)
    if kind == "rectangle":
        if parameters is None:
            return [_to_fixed(0), _to_fixed(0)]
        return [_to_fixed(parameters[0]), _to_fixed(parameters[1])]
    if kind == "polygon":
        return [[_to_fixed(x), _to_fixed(y)] for x, y in list(parameters or [])]
    return parameters


def _deserialize_deployment_zones(data: dict) -> dict:
    from .missions import DeploymentZone, DeploymentZoneType, ZoneCutout, CutoutType

    zones = {}
    for player_id, zone in (data or {}).items():
        if not isinstance(zone, dict):
            zones[player_id] = zone
            continue
        zone_copy = {}
        for key, value in zone.items():
            if key == "mission_zones":
                mission_zones = []
                for z in value or []:
                    zone_type = DeploymentZoneType(z.get("zone_type"))
                    vertices = [(_from_fixed(x), _from_fixed(y)) for x, y in z.get("vertices", []) or []]
                    cutouts = []
                    for c in z.get("cutouts", []) or []:
                        cutout_type = CutoutType(c.get("cutout_type"))
                        params = c.get("parameters")
                        if cutout_type == CutoutType.CIRCLE:
                            params = _from_fixed(params) if params is not None else 0.0
                        elif cutout_type == CutoutType.RECTANGLE:
                            params = (_from_fixed(params[0]), _from_fixed(params[1]))
                        elif cutout_type == CutoutType.POLYGON:
                            params = [(_from_fixed(x), _from_fixed(y)) for x, y in params]
                        cutouts.append(
                            ZoneCutout(
                                cutout_type=cutout_type,
                                center_x=_from_fixed(c.get("center_x", 0)),
                                center_y=_from_fixed(c.get("center_y", 0)),
                                parameters=params,
                            )
                        )
                    mission_zones.append(DeploymentZone(name=z.get("name", ""), zone_type=zone_type, vertices=vertices, cutouts=cutouts))
                zone_copy[key] = mission_zones
            else:
                zone_copy[key] = value
        zones[player_id] = zone_copy
    return zones


def _serialize_game_state(game: Game) -> dict:
    destroyed_by_player = []
    for player, count in (getattr(game, "destroyed_units_this_battle_round_by_player", {}) or {}).items():
        if player is None:
            continue
        destroyed_by_player.append({"player_id": get_entity_id(player), "count": int(count or 0)})
    skip_turns = []
    for idx, count in (getattr(game, "deployment_skip_turns", {}) or {}).items():
        skip_turns.append({"player_index": int(idx), "skip_count": int(count or 0)})
    ruleset_bundle = getattr(game, "ruleset_bundle", None)
    ruleset_payload = ruleset_bundle.to_dict() if ruleset_bundle is not None else RulesetBundle.from_values().to_dict()

    return {
        "ruleset": ruleset_payload,
        "battle_round": int(getattr(game, "turn", 0) or 0),
        "phase": getattr(getattr(game, "phase", None), "name", None),
        "setup_phase": getattr(getattr(game, "setup_phase", None), "name", None),
        "setup_complete": bool(getattr(game, "setup_complete", False)),
        "battle_shock_step_active": bool(getattr(game, "battle_shock_step_active", False)),
        "current_player_index": int(getattr(game, "current_player_index", 0) or 0),
        "attacker_index": getattr(game, "attacker_index", None),
        "defender_index": getattr(game, "defender_index", None),
        "deployment_turn_index": int(getattr(game, "deployment_turn_index", 0) or 0),
        "first_turn_player_index": getattr(game, "first_turn_player_index", None),
        "battle_round_starting_player_index": getattr(game, "battle_round_starting_player_index", None),
        "deployment_zones": _serialize_deployment_zones(getattr(game, "deployment_zones", {}) or {}),
        "deployment_actions": dict(getattr(game, "deployment_actions", {}) or {}),
        "deployment_skip_turns": skip_turns,
        "deployment_notice": getattr(game, "deployment_notice", None),
        "waiting_for_deployment_input": bool(getattr(game, "waiting_for_deployment_input", False)),
        "selected_mission_info": dict(getattr(game, "selected_mission_info", {}) or {}),
        "commands": list(getattr(game, "commands", []) or []),
        "secondary_mission_mode": getattr(game, "secondary_mission_mode", None),
        "in_progress_actions": [encode_refs(a) for a in list(getattr(game, "in_progress_actions", []) or [])],
        "completed_actions_this_turn": [encode_refs(a) for a in list(getattr(game, "completed_actions_this_turn", []) or [])],
        "destroyed_units_this_turn": [get_entity_id(u) for u in list(getattr(game, "destroyed_units_this_turn", []) or [])],
        "models_destroyed_this_turn": [get_entity_id(m) for m in list(getattr(game, "models_destroyed_this_turn", []) or [])],
        "destroyed_units_this_battle_round_by_player": destroyed_by_player,
        "phase_targeted_units": {
            str(k): sorted(list(v or [])) for k, v in (getattr(game, "phase_targeted_units", {}) or {}).items()
        },
        "phase_charge_targets": {
            str(k): sorted(list(v or [])) for k, v in (getattr(game, "phase_charge_targets", {}) or {}).items()
        },
        "_phoenix_gem_pending": encode_refs(list(getattr(game, "_phoenix_gem_pending", []) or [])),
        "_blood_surge_shooting_snapshot": encode_refs(getattr(game, "_blood_surge_shooting_snapshot", {}) or {}),
        "_brazen_fury_shooting_snapshot": encode_refs(getattr(game, "_brazen_fury_shooting_snapshot", {}) or {}),
        "_horde_move_shooting_snapshot": encode_refs(getattr(game, "_horde_move_shooting_snapshot", {}) or {}),
        "_frenzy_shooting_targets": encode_refs(getattr(game, "_frenzy_shooting_targets", {}) or {}),
        "_frenzy_fight_targets": encode_refs(getattr(game, "_frenzy_fight_targets", {}) or {}),
        "_pain_parasite_shooting_snapshot": encode_refs(getattr(game, "_pain_parasite_shooting_snapshot", {}) or {}),
        "_pain_parasite_fight_snapshot": encode_refs(getattr(game, "_pain_parasite_fight_snapshot", {}) or {}),
        "army_muster_requests": encode_refs(getattr(game, "army_muster_requests", {}) or {}),
        "fates_in_flux": getattr(getattr(game, "fates_in_flux", None), "to_dict", lambda: {})(),
    }


def _apply_game_state(game: Game, data: dict, registry: EntityRegistry) -> None:
    ruleset_payload = data.get("ruleset") or {}
    game.ruleset_bundle = RulesetBundle.from_dict(ruleset_payload)
    game.turn = int(data.get("battle_round", 0) or 0)
    phase = data.get("phase")
    if phase:
        game.phase = BattleRoundPhases[phase]
    setup_phase = data.get("setup_phase")
    if setup_phase:
        game.setup_phase = SetupPhase[setup_phase]
    game.setup_complete = bool(data.get("setup_complete", False))
    game.battle_shock_step_active = bool(data.get("battle_shock_step_active", False))
    game.current_player_index = int(data.get("current_player_index", 0) or 0)
    game.attacker_index = data.get("attacker_index", None)
    game.defender_index = data.get("defender_index", None)
    game.deployment_turn_index = int(data.get("deployment_turn_index", 0) or 0)
    game.first_turn_player_index = data.get("first_turn_player_index", None)
    game.battle_round_starting_player_index = data.get("battle_round_starting_player_index", None)
    game.deployment_zones = _deserialize_deployment_zones(data.get("deployment_zones", {}) or {})
    game.deployment_actions = dict(data.get("deployment_actions", {}) or {})
    skip_map = {}
    for entry in data.get("deployment_skip_turns", []) or []:
        try:
            skip_map[int(entry.get("player_index"))] = int(entry.get("skip_count", 0))
        except Exception:
            continue
    game.deployment_skip_turns = skip_map
    game.deployment_notice = data.get("deployment_notice", None)
    game.waiting_for_deployment_input = bool(data.get("waiting_for_deployment_input", False))
    game.selected_mission_info = dict(data.get("selected_mission_info", {}) or {})
    game.commands = list(data.get("commands", []) or [])
    if data.get("secondary_mission_mode") is not None:
        game.secondary_mission_mode = data.get("secondary_mission_mode")

    game.in_progress_actions = decode_refs(data.get("in_progress_actions", []) or [], registry)
    game.completed_actions_this_turn = decode_refs(data.get("completed_actions_this_turn", []) or [], registry)
    game.destroyed_units_this_turn = [
        registry.get(uid, kind="unit") for uid in data.get("destroyed_units_this_turn", []) or []
    ]
    game.models_destroyed_this_turn = [
        registry.get(mid, kind="model") for mid in data.get("models_destroyed_this_turn", []) or []
    ]
    destroyed_map = {}
    for entry in data.get("destroyed_units_this_battle_round_by_player", []) or []:
        player = registry.get(entry.get("player_id"), kind="player")
        if player is None:
            continue
        destroyed_map[player] = int(entry.get("count", 0))
    game.destroyed_units_this_battle_round_by_player = destroyed_map
    game.phase_targeted_units = {
        str(k): set(v or []) for k, v in (data.get("phase_targeted_units", {}) or {}).items()
    }
    game.phase_charge_targets = {
        str(k): set(v or []) for k, v in (data.get("phase_charge_targets", {}) or {}).items()
    }
    game._phoenix_gem_pending = decode_refs(data.get("_phoenix_gem_pending", []) or [], registry)
    game._blood_surge_shooting_snapshot = decode_refs(data.get("_blood_surge_shooting_snapshot", {}) or {}, registry)
    game._brazen_fury_shooting_snapshot = decode_refs(data.get("_brazen_fury_shooting_snapshot", {}) or {}, registry)
    game._horde_move_shooting_snapshot = decode_refs(data.get("_horde_move_shooting_snapshot", {}) or {}, registry)
    game._frenzy_shooting_targets = decode_refs(data.get("_frenzy_shooting_targets", {}) or {}, registry)
    game._frenzy_fight_targets = decode_refs(data.get("_frenzy_fight_targets", {}) or {}, registry)
    game._pain_parasite_shooting_snapshot = decode_refs(data.get("_pain_parasite_shooting_snapshot", {}) or {}, registry)
    game._pain_parasite_fight_snapshot = decode_refs(data.get("_pain_parasite_fight_snapshot", {}) or {}, registry)
    game.army_muster_requests = decode_refs(data.get("army_muster_requests", {}) or {}, registry)
    fates_payload = data.get("fates_in_flux", {}) or {}
    if isinstance(fates_payload, dict):
        from ..rules.fates_in_flux import FatesInFluxManager
        game.fates_in_flux = FatesInFluxManager.from_dict(fates_payload, game=game)


def snapshot_game(game: Game) -> dict:
    if int(getattr(game, "get_battle_round", lambda: 0)() or 0) < 1:
        raise RuntimeError("Snapshots are only allowed once battle round 1 has started.")

    players = list(getattr(game, "players", []) or [])
    armies = []
    units = []
    for player in players:
        army = getattr(player, "army", None)
        if army is None:
            continue
        armies.append(_serialize_army(army))
        for unit in list(getattr(army, "units", []) or []):
            units.append(_serialize_unit(unit))

    decision_queue = getattr(game, "decision_queue", None)
    decisions = decision_queue.list() if decision_queue is not None else []
    event_log = getattr(game, "event_log", None)
    events = event_log.serialize_events() if event_log is not None else []

    return {
        "schema_version": SCHEMA_VERSION,
        "fixed_point_scale": POSITION_SCALE,
        "angle_scale": ANGLE_SCALE,
        "game": _serialize_game_state(game),
        "players": [_serialize_player(p) for p in players],
        "armies": armies,
        "units": units,
        "map": _serialize_map(getattr(game, "map", None)),
        "decisions": [_serialize_decision(d) for d in list(decisions or [])],
        "commands": [_serialize_command(c) for c in list(getattr(game, "command_queue", []) or [])],
        "events": list(events or []),
        "rng_state": _serialize_rng_state(getattr(game, "random_source").getstate()),
        "roll_manager": getattr(game, "roll_manager", None).to_dict() if getattr(game, "roll_manager", None) is not None else {},
        "attack_manager": getattr(game, "attack_manager", None).to_dict() if getattr(game, "attack_manager", None) is not None else {},
    }


def load_game_snapshot(snapshot: dict) -> Game:
    if int(snapshot.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError(f"Unsupported snapshot schema version: {snapshot.get('schema_version')}")

    map_data = snapshot.get("map", {}) or {}
    battlefield = Battlefield(width=int(map_data.get("width", 0) or 0), height=int(map_data.get("height", 0) or 0))
    players_data = list(snapshot.get("players", []) or [])
    players = []
    for pdata in players_data:
        control_name = pdata.get("control", PlayerControl.LOCAL.name)
        player = Player(name=str(pdata.get("name", "") or ""), control=PlayerControl[control_name])
        player._id = str(pdata.get("id") or player._id)
        players.append(player)

    game_ruleset = RulesetBundle.from_dict(dict(snapshot.get("game", {}) or {}).get("ruleset", {}))
    game = Game(battlefield, players=players, ruleset_bundle=game_ruleset)
    roll_mgr_payload = snapshot.get("roll_manager")
    if isinstance(roll_mgr_payload, dict):
        try:
            from .dice_rolls import DiceRollManager
            game.roll_manager = DiceRollManager.from_dict(roll_mgr_payload)
        except Exception:
            pass
    attack_mgr_payload = snapshot.get("attack_manager")
    if isinstance(attack_mgr_payload, dict):
        try:
            from .attack_resolution import AttackResolutionManager
            game.attack_manager = AttackResolutionManager.from_dict(attack_mgr_payload)
        except Exception:
            pass
    events_payload = list(snapshot.get("events", []) or [])
    from .event_log import DeterministicEventLog
    existing_log = getattr(game, "event_log", None)
    if existing_log is not None:
        existing_log.detach()
    game.event_log = DeterministicEventLog.from_payload(events_payload)
    game.event_log.attach(game)

    units_by_id: dict[str, Unit] = {}
    armies_by_id: dict[str, Army] = {}
    waha = WahaHelper()
    units_data = {u["id"]: u for u in list(snapshot.get("units", []) or [])}

    for adata in list(snapshot.get("armies", []) or []):
        army = Army(
            faction=str(adata.get("faction", "") or ""),
            detachment_type=str(adata.get("detachment_type", "") or ""),
            points_limit=int(adata.get("points_limit", 0) or 0),
        )
        army._id = str(adata.get("id") or army._id)
        if adata.get("faction_id"):
            army.faction_id = adata.get("faction_id")
        armies_by_id[army.id] = army

        for unit_id in adata.get("units", []) or []:
            udata = units_data.get(unit_id)
            if udata is None:
                raise KeyError(f"Missing unit {unit_id} in snapshot.")
            datasheet_id = udata.get("datasheet_id")
            datasheet_name = udata.get("datasheet_name")
            faction_id = udata.get("faction_id")
            datasheet = waha.get_full_datasheet_info_by_name(
                datasheet_name or "",
                datasheet_id=datasheet_id,
                faction_id=faction_id,
            )
            if datasheet is None:
                raise KeyError(f"Datasheet not found for unit {datasheet_name} ({datasheet_id}).")
            starting_models = len(udata.get("models", []) or []) + len(udata.get("models_lost", []) or [])
            unit = Unit(datasheet, quantity=starting_models or None)
            unit._id = str(udata.get("id") or unit._id)
            units_by_id[unit.id] = unit
            unit.parent_army = army
            army.units.append(unit)

    for player, pdata in zip(players, players_data):
        army_id = pdata.get("army_id")
        if army_id:
            army = armies_by_id.get(army_id)
            if army is None:
                raise KeyError(f"Missing army {army_id} for player {player.name}")
            player.army = army
            army.player = player

    game.map = Map(int(map_data.get("width", 0) or 0), int(map_data.get("height", 0) or 0))
    game.map.terrain_features = [_deserialize_terrain_feature(t) for t in map_data.get("terrain_features", []) or []]

    point_objs = {}
    for pdata in map_data.get("objective_points", []) or []:
        point = _deserialize_objective_point(pdata)
        point_objs[point.id] = point

    objectives = [_deserialize_objective(o, point_objs) for o in map_data.get("objectives", []) or []]
    game.map.objectives = objectives
    game.objectives = objectives
    game.map.deployment_zones = _deserialize_deployment_zones(map_data.get("deployment_zones", {}) or {})

    game.map.units = []
    for uid in map_data.get("units", []) or []:
        unit = units_by_id.get(uid)
        if unit is not None:
            game.map.units.append(unit)

    for unit_id, udata in units_data.items():
        unit = units_by_id.get(unit_id)
        if unit is None:
            continue
        all_models = list(getattr(unit, "models", []) or [])
        models_by_name: dict[str, list[Model]] = {}
        for model in all_models:
            models_by_name.setdefault(model.name.lower(), []).append(model)

        alive_models = []
        lost_models = []
        for mdata in udata.get("models", []) or []:
            name_key = str(mdata.get("name", "") or "").lower()
            candidates = models_by_name.get(name_key, [])
            if not candidates:
                raise ValueError(f"Missing model {name_key} for unit {unit.name}")
            model = candidates.pop(0)
            _apply_model_state(model, mdata, unit)
            alive_models.append(model)

        for mdata in udata.get("models_lost", []) or []:
            name_key = str(mdata.get("name", "") or "").lower()
            candidates = models_by_name.get(name_key, [])
            if not candidates:
                raise ValueError(f"Missing lost model {name_key} for unit {unit.name}")
            model = candidates.pop(0)
            _apply_model_state(model, mdata, unit)
            lost_models.append(model)

        unit.models = alive_models
        unit.models_lost = lost_models
        unit.status_effects = []
        for eff_data in udata.get("status_effects", []) or []:
            unit.status_effects.append(_deserialize_status_effect(eff_data))

        unit.attached_leaders = [
            units_by_id[uid] for uid in udata.get("attached_leader_ids", []) or [] if uid in units_by_id
        ]
        unit.attached_support_units = [
            units_by_id[uid] for uid in udata.get("attached_support_ids", []) or [] if uid in units_by_id
        ]
        attached_to_id = udata.get("attached_to_id")
        unit.attached_to = units_by_id.get(attached_to_id) if attached_to_id else None
        support_joined_to_id = udata.get("support_joined_to_id")
        unit.support_joined_to = units_by_id.get(support_joined_to_id) if support_joined_to_id else None
        if unit.support_joined_to is not None:
            try:
                supports = list(getattr(unit.support_joined_to, "attached_support_units", []) or [])
            except Exception:
                supports = []
            if unit not in supports:
                supports.append(unit)
            unit.support_joined_to.attached_support_units = supports
        unit.transport_passengers = [
            units_by_id[uid] for uid in udata.get("transport_passenger_ids", []) or [] if uid in units_by_id
        ]
        embarked_id = udata.get("embarked_in_id")
        unit.embarked_in = units_by_id.get(embarked_id) if embarked_id else None

        if udata.get("enhancement_id"):
            enh = waha.get_enhancement(udata.get("enhancement_id"))
            unit.enhancement = enh

        if hasattr(unit, "_invalidate_ability_cache"):
            unit._invalidate_ability_cache()

    game.rebuild_entity_registry()

    for pdata in map_data.get("objective_points", []) or []:
        point = game.entity_registry.get(pdata.get("id"), kind="objective_marker")
        if point is None:
            continue
        point.controlling_player = game.entity_registry.get(pdata.get("controlling_player_id"), kind="player")
        point.terraformed_by = game.entity_registry.get(pdata.get("terraformed_by_id"), kind="player")
        point.cleansed_by = game.entity_registry.get(pdata.get("cleansed_by_id"), kind="player")
        point.sticky_controller = game.entity_registry.get(pdata.get("sticky_controller_id"), kind="player")
        point.worldblight_controller = game.entity_registry.get(pdata.get("worldblight_controller_id"), kind="player")
        point.worldblight_source = pdata.get("worldblight_source", None)

    for player, pdata in zip(players, players_data):
        _apply_player_state(player, pdata, game.entity_registry)
        if getattr(player, "stratagems", None) is not None:
            _apply_manager_state(player.stratagems, pdata.get("stratagems_state"), game.entity_registry)

    for unit_id, udata in units_data.items():
        unit = units_by_id.get(unit_id)
        if unit is None:
            continue
        _apply_unit_state(unit, udata, game.entity_registry)
        _apply_round_state(unit, udata.get("round_state", {}) or {}, game.entity_registry)
        models = list(getattr(unit, "models", []) or []) + list(getattr(unit, "models_lost", []) or [])
        for model in models:
            if getattr(model, "_temporary_effects", None) is not None:
                model._temporary_effects = decode_refs(model._temporary_effects, game.entity_registry)

    for adata in list(snapshot.get("armies", []) or []):
        army = armies_by_id.get(adata.get("id"))
        if army is None:
            continue
        _apply_army_state(army, adata, game.entity_registry)
        enhancements = []
        for enh_id in adata.get("enhancements", []) or []:
            enh = waha.get_enhancement(enh_id)
            if enh is not None:
                enhancements.append(enh)
        army.enhancements = enhancements
        warlord_id = adata.get("warlord_id")
        if warlord_id:
            army.warlord = units_by_id.get(warlord_id)

    for player, pdata in zip(players, players_data):
        player.primary_mission = _deserialize_card(pdata.get("primary_mission"), game.entity_registry)
        player.secondary_deck = [
            _deserialize_card(c, game.entity_registry) for c in pdata.get("secondary_deck", []) or []
        ]
        player.active_secondaries = [
            _deserialize_card(c, game.entity_registry) for c in pdata.get("active_secondaries", []) or []
        ]
        player.discarded_secondaries = [
            _deserialize_card(c, game.entity_registry) for c in pdata.get("discarded_secondaries", []) or []
        ]

    decision_queue = DecisionQueue()
    for ddata in list(snapshot.get("decisions", []) or []):
        req = _deserialize_decision(ddata)
        req.context = decode_refs(req.context, game.entity_registry)
        for opt in req.options:
            opt.payload = decode_refs(opt.payload, game.entity_registry)
        if req.candidates:
            decoded_candidates = []
            for cand in list(req.candidates or []):
                decoded_candidates.append(
                    CandidateAction(
                        action_id=cand.action_id,
                        params=decode_refs(cand.params, game.entity_registry),
                        metadata=decode_refs(cand.metadata, game.entity_registry),
                    )
                )
            req.candidates = decoded_candidates
        decision_queue.add(req)
    game.decision_queue = decision_queue

    command_queue = []
    for cdata in list(snapshot.get("commands", []) or []):
        cmd = _deserialize_command(cdata)
        cmd.payload = decode_refs(cmd.payload, game.entity_registry)
        cmd.metadata = decode_refs(cmd.metadata, game.entity_registry)
        command_queue.append(cmd)
    game.command_queue = command_queue

    _apply_game_state(game, snapshot.get("game", {}) or {}, game.entity_registry)

    rng_state = _deserialize_rng_state(snapshot.get("rng_state", None))
    if rng_state is not None:
        game.random_source.setstate(rng_state)

    for player in players:
        if getattr(player, "stratagems", None) is not None:
            player.stratagems.refresh_available()

    game.refresh_rule_subscribers()
    clear_enemy_model_cache(id(game.map))
    return game
