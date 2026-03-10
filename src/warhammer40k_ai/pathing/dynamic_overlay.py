from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from shapely import STRtree
from shapely.geometry.base import BaseGeometry

from ..utility.entity_ids import maybe_entity_id
from .rules_profile import unit_army_identity_key, units_share_army_identity
from .types import MovementProfile


@dataclass(frozen=True, eq=False)
class DynamicModelBlocker:
    model_id: str
    unit_id: str
    army_identity_key: tuple[str, object]
    is_enemy: bool
    is_friendly: bool
    is_aircraft: bool
    is_big_model: bool
    footprint: BaseGeometry
    z_bottom: float
    z_top: float


@dataclass(frozen=True, eq=False)
class DynamicOverlay:
    blockers: tuple[DynamicModelBlocker, ...]
    friendly_blockers: tuple[DynamicModelBlocker, ...]
    enemy_blockers: tuple[DynamicModelBlocker, ...]
    friendly_tree: Optional[STRtree]
    enemy_tree: Optional[STRtree]
    enemy_engagement_shapes: tuple[BaseGeometry, ...]
    enemy_engagement_tree: Optional[STRtree]


def _unit_models_for_collision(unit: object) -> tuple[object, ...]:
    getter = getattr(unit, "get_models_for_collision", None)
    if callable(getter):
        return tuple(getter() or ())
    return tuple(getattr(unit, "models", ()) or ())


def _model_z_bounds(model: object) -> tuple[float, float]:
    base = getattr(model, "model_base", None)
    volume_bounds = getattr(base, "volume_z_bounds", None)
    if callable(volume_bounds):
        z_bottom, z_top = volume_bounds()
        return float(z_bottom), float(z_top)
    z_center = float(getattr(base, "z", 0.0) or 0.0)
    return z_center, z_center


def _bool_attr(entity: object, attr_name: str) -> bool:
    return bool(getattr(entity, attr_name, False))


def _sort_key_for_entity(entity: object, fallback_prefix: str, fallback_index: int) -> str:
    entity_id = maybe_entity_id(entity)
    if entity_id:
        return entity_id
    return f"{fallback_prefix}:{fallback_index:04d}"


def _tree_query_indices(tree: STRtree, query_geometry: BaseGeometry) -> tuple[int, ...]:
    indices = tree.query(query_geometry)
    if indices is None:
        return ()
    try:
        return tuple(int(i) for i in indices)
    except TypeError:
        return (int(indices),)


def _query_blockers(
    tree: Optional[STRtree],
    blockers: tuple[DynamicModelBlocker, ...],
    query_geometry: BaseGeometry,
) -> tuple[DynamicModelBlocker, ...]:
    if tree is None:
        return ()
    indices = _tree_query_indices(tree, query_geometry)
    if not indices:
        return ()
    deduped = sorted(set(indices))
    return tuple(blockers[index] for index in deduped)


def build_dynamic_overlay(
    game_map: object,
    moving_unit: object,
    movement_profile: Optional[MovementProfile] = None,
    *,
    moving_model: object = None,
) -> DynamicOverlay:
    unit_records: list[tuple[str, int, object]] = []
    for unit_index, unit in enumerate(tuple(getattr(game_map, "units", ()) or ())):
        unit_records.append((_sort_key_for_entity(unit, "unit", unit_index), unit_index, unit))
    unit_records.sort(key=lambda item: (item[0], item[1]))

    blockers: list[DynamicModelBlocker] = []
    friendly_blockers: list[DynamicModelBlocker] = []
    enemy_blockers: list[DynamicModelBlocker] = []

    for _, unit_index, unit in unit_records:
        is_alive_fn = getattr(unit, "is_alive", None)
        if callable(is_alive_fn) and not bool(is_alive_fn()):
            continue
        if not bool(getattr(unit, "deployed", False)):
            continue

        unit_id = _sort_key_for_entity(unit, "unit", unit_index)
        army_key = unit_army_identity_key(unit)
        is_friendly = units_share_army_identity(unit, moving_unit)
        is_enemy = not is_friendly
        is_aircraft = _bool_attr(unit, "is_aircraft")
        is_big_model = _bool_attr(unit, "is_vehicle") or _bool_attr(unit, "is_monster") or _bool_attr(unit, "is_titanic")

        model_records: list[tuple[str, int, object]] = []
        for model_index, model in enumerate(_unit_models_for_collision(unit)):
            model_records.append((_sort_key_for_entity(model, f"{unit_id}:model", model_index), model_index, model))
        model_records.sort(key=lambda item: (item[0], item[1]))

        for _, model_index, model in model_records:
            if model is moving_model:
                continue
            if not bool(getattr(model, "is_alive", False)):
                continue
            model_base = getattr(model, "model_base", None)
            if model_base is None:
                continue
            model_shape = model_base.get_base_shape()
            z_bottom, z_top = _model_z_bounds(model)
            blocker = DynamicModelBlocker(
                model_id=_sort_key_for_entity(model, f"{unit_id}:model", model_index),
                unit_id=unit_id,
                army_identity_key=army_key,
                is_enemy=is_enemy,
                is_friendly=is_friendly,
                is_aircraft=is_aircraft,
                is_big_model=is_big_model,
                footprint=model_shape,
                z_bottom=z_bottom,
                z_top=z_top,
            )
            blockers.append(blocker)
            if is_enemy:
                enemy_blockers.append(blocker)
            else:
                friendly_blockers.append(blocker)

    blockers.sort(key=lambda blocker: blocker.model_id)
    friendly_blockers.sort(key=lambda blocker: blocker.model_id)
    enemy_blockers.sort(key=lambda blocker: blocker.model_id)

    friendly_shapes = tuple(blocker.footprint for blocker in friendly_blockers)
    enemy_shapes = tuple(blocker.footprint for blocker in enemy_blockers)

    friendly_tree = STRtree(friendly_shapes) if friendly_shapes else None
    enemy_tree = STRtree(enemy_shapes) if enemy_shapes else None

    engagement_buffer = 1.0
    if movement_profile is not None:
        engagement_buffer = float(
            movement_profile.engagement_buffer_rules.get("normal_move_buffer_inches", 1.0)
        )
    enemy_engagement_shapes = tuple(shape.buffer(engagement_buffer) for shape in enemy_shapes)
    enemy_engagement_tree = STRtree(enemy_engagement_shapes) if enemy_engagement_shapes else None

    return DynamicOverlay(
        blockers=tuple(blockers),
        friendly_blockers=tuple(friendly_blockers),
        enemy_blockers=tuple(enemy_blockers),
        friendly_tree=friendly_tree,
        enemy_tree=enemy_tree,
        enemy_engagement_shapes=enemy_engagement_shapes,
        enemy_engagement_tree=enemy_engagement_tree,
    )


def query_friendly_blockers(
    overlay: DynamicOverlay,
    query_geometry: BaseGeometry,
) -> tuple[DynamicModelBlocker, ...]:
    return _query_blockers(overlay.friendly_tree, overlay.friendly_blockers, query_geometry)


def query_enemy_blockers(
    overlay: DynamicOverlay,
    query_geometry: BaseGeometry,
) -> tuple[DynamicModelBlocker, ...]:
    return _query_blockers(overlay.enemy_tree, overlay.enemy_blockers, query_geometry)


def query_enemy_engagement_masks(
    overlay: DynamicOverlay,
    query_geometry: BaseGeometry,
) -> tuple[BaseGeometry, ...]:
    if overlay.enemy_engagement_tree is None:
        return ()
    indices = _tree_query_indices(overlay.enemy_engagement_tree, query_geometry)
    if not indices:
        return ()
    return tuple(overlay.enemy_engagement_shapes[index] for index in sorted(set(indices)))


__all__ = [
    "DynamicModelBlocker",
    "DynamicOverlay",
    "build_dynamic_overlay",
    "query_enemy_blockers",
    "query_enemy_engagement_masks",
    "query_friendly_blockers",
]
