from __future__ import annotations

from .descriptor_army_build import compile_army_build_descriptor
from .descriptor_bundle import CompiledDescriptor, CompiledDescriptorBundle, descriptor_bundle_id
from .descriptor_deployment import compile_deployment_descriptor
from .descriptor_mission import compile_mission_descriptor
from .descriptor_objectives import compile_objective_descriptors
from .descriptor_terrain import compile_terrain_descriptors
from .descriptor_tools import compile_tool_descriptors
from ..utility.entity_ids import get_entity_id
from ..utility.profiling_sections import profile_section, profiled_section


_CACHE_ATTR = "_descriptor_compiler_cache"
_CACHE_LIMIT_PER_FAMILY = 8


def _game_cache(game: object) -> dict[str, dict[tuple[object, ...], object]]:
    cache = getattr(game, _CACHE_ATTR, None)
    if not isinstance(cache, dict):
        cache = {}
        setattr(game, _CACHE_ATTR, cache)
    return cache


def _cached_descriptor_value(game: object, family: str, key: tuple[object, ...], builder):
    cache = _game_cache(game)
    family_cache = cache.setdefault(str(family), {})
    cached = family_cache.get(key)
    if cached is not None:
        return cached
    value = builder()
    if len(family_cache) >= _CACHE_LIMIT_PER_FAMILY:
        family_cache.clear()
    family_cache[key] = value
    return value


def _rules_bundle_id(game: object) -> str:
    rules_bundle = getattr(game, "ruleset_bundle", None)
    return str(getattr(rules_bundle, "rules_bundle_id", "") or "")


def _safe_bounds(entity: object) -> tuple[float, float, float, float] | tuple[()]:
    footprint = getattr(entity, "footprint", None)
    bounds = getattr(footprint, "bounds", None)
    if not bounds:
        return ()
    try:
        return tuple(round(float(value), 6) for value in tuple(bounds)[:4])
    except (TypeError, ValueError):
        return ()


def _terrain_entity_signature(entity: object) -> tuple[object, ...]:
    return (
        str(getattr(entity, "id", "") or ""),
        type(entity).__name__,
        _safe_bounds(entity),
        len(list(getattr(entity, "floors", []) or [])),
        len(list(getattr(entity, "walls", []) or [])),
        len(list(getattr(entity, "openings", []) or [])),
        str(getattr(entity, "layout_slot_id", "") or ""),
        tuple(str(tag) for tag in sorted(list(getattr(entity, "effect_tags", []) or []))),
        str(getattr(entity, "cover_mode", "") or ""),
        bool(getattr(entity, "obscuring", False)),
        tuple(sorted((str(k), str(v)) for k, v in dict(getattr(entity, "traversal_rules", {}) or {}).items())),
    )


def _terrain_cache_key(game: object) -> tuple[object, ...]:
    game_map = getattr(game, "map", None)
    terrain_revision = getattr(game_map, "terrain_revision", None)
    terrain_features = tuple(getattr(game_map, "terrain_features", []) or ())
    terrain_areas = tuple(getattr(game_map, "terrain_areas", []) or ())
    return (
        _rules_bundle_id(game),
        id(game_map),
        terrain_revision,
        tuple(_terrain_entity_signature(entity) for entity in terrain_features),
        tuple(_terrain_entity_signature(entity) for entity in terrain_areas),
    )


def _tool_cache_key(game: object) -> tuple[object, ...]:
    player_entries: list[tuple[object, ...]] = []
    for player in sorted(list(getattr(game, "players", []) or []), key=lambda item: str(getattr(item, "id", "") or "")):
        stratagem_manager = getattr(player, "stratagems", None)
        available = tuple(
            sorted(
                (
                    str(getattr(stratagem, "id", "") or ""),
                    str(getattr(stratagem, "name", "") or ""),
                    id(getattr(stratagem, "tool_descriptor", None)),
                )
                for stratagem in list(getattr(stratagem_manager, "available", []) or [])
            )
        )
        player_entries.append((str(getattr(player, "id", "") or ""), available))

    enhancement_entries: list[tuple[str, str, str]] = []
    for player in list(getattr(game, "players", []) or []):
        army = getattr(player, "army", None)
        for unit in list(getattr(army, "units", []) or []):
            enhancement = getattr(unit, "enhancement", None)
            if enhancement is None:
                continue
            enhancement_entries.append(
                (
                    str(get_entity_id(unit) or ""),
                    str(getattr(enhancement, "id", "") or ""),
                    str(getattr(enhancement, "name", "") or ""),
                )
            )

    return (
        _rules_bundle_id(game),
        tuple(player_entries),
        tuple(sorted(enhancement_entries)),
    )


@profiled_section("descriptor.compile_bundle")
def compile_descriptor_bundle(game: object) -> CompiledDescriptorBundle:
    with profile_section("descriptor.compile_mission"):
        mission_descriptor = compile_mission_descriptor(game)
    with profile_section("descriptor.compile_objectives"):
        objective_descriptors = compile_objective_descriptors(game)
    with profile_section("descriptor.compile_terrain"):
        terrain_descriptors = _cached_descriptor_value(
            game,
            "terrain",
            _terrain_cache_key(game),
            lambda: compile_terrain_descriptors(game),
        )
    with profile_section("descriptor.compile_deployment"):
        deployment_descriptor = compile_deployment_descriptor(game)
    with profile_section("descriptor.compile_army_build"):
        army_build_descriptor = compile_army_build_descriptor(game)
    with profile_section("descriptor.compile_tools"):
        tool_descriptors = _cached_descriptor_value(
            game,
            "tools",
            _tool_cache_key(game),
            lambda: compile_tool_descriptors(game),
        )

    bundle_id = descriptor_bundle_id(
        mission_descriptor_id=mission_descriptor.descriptor_id,
        objective_descriptor_ids=[descriptor.descriptor_id for descriptor in objective_descriptors],
        terrain_descriptor_ids=[descriptor.descriptor_id for descriptor in terrain_descriptors],
        deployment_descriptor_id=deployment_descriptor.descriptor_id,
        army_build_descriptor_id=army_build_descriptor.descriptor_id,
        tool_descriptor_ids=[descriptor.descriptor_id for descriptor in tool_descriptors],
    )
    return CompiledDescriptorBundle(
        mission_descriptor=mission_descriptor,
        objective_descriptors=tuple(objective_descriptors),
        terrain_descriptors=tuple(terrain_descriptors),
        deployment_descriptor=deployment_descriptor,
        army_build_descriptor=army_build_descriptor,
        tool_descriptors=tuple(tool_descriptors),
        bundle_id=bundle_id,
    )


__all__ = [
    "CompiledDescriptor",
    "CompiledDescriptorBundle",
    "compile_descriptor_bundle",
]
