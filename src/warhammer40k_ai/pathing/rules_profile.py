from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, FREELY_CLIMBABLE_RANGE
from .types import MovementProfile

if TYPE_CHECKING:
    from ..units.unit import Unit


def movement_type_tag(movement_type: object) -> Optional[str]:
    if movement_type is None:
        return None
    value = getattr(movement_type, "value", movement_type)
    tag = str(value or "").strip().lower()
    return tag or None


def move_type_matches(value: object, movement_type: object) -> bool:
    move_tag = movement_type_tag(movement_type)
    if move_tag is None or value is None:
        return False
    if isinstance(value, str):
        return move_tag == str(value).strip().lower()
    if isinstance(value, (list, tuple, set)):
        for item in value:
            if item is None:
                continue
            if move_tag == str(item).strip().lower():
                return True
    return False


def counts_as_infantry_for_terrain(unit: "Unit") -> bool:
    fn = getattr(unit, "counts_as_infantry_for_terrain", None)
    if callable(fn):
        return bool(fn())
    return bool(getattr(unit, "is_infantry", False))


def can_breach_ruins_walls(unit: "Unit") -> bool:
    fn = getattr(unit, "can_move_through_ruins_walls", None)
    if callable(fn):
        return bool(fn())
    if counts_as_infantry_for_terrain(unit):
        return True
    if bool(getattr(unit, "is_beast", False)):
        return True
    if bool(getattr(unit, "is_imperium_primarch", False)):
        return True
    if bool(getattr(unit, "is_belisarius_cawl", False)):
        return True
    return False


def unit_move_over_low_terrain_height(unit: "Unit", movement_type: object) -> Optional[float]:
    special_rules = getattr(unit, "special_rules", None)
    if not isinstance(special_rules, dict):
        return None
    height = special_rules.get("move_over_low_terrain_height_value")
    if height is None:
        return None
    if not move_type_matches(special_rules.get("move_over_low_terrain_height_types"), movement_type):
        return None
    try:
        return float(height)
    except (TypeError, ValueError):
        return None


def unit_can_move_over_friendly_monster_vehicle(unit: "Unit", movement_type: object) -> bool:
    special_rules = getattr(unit, "special_rules", None)
    if not isinstance(special_rules, dict):
        return False
    return move_type_matches(special_rules.get("move_over_friendly_monster_vehicle_types"), movement_type)


def super_heavy_walker_active_for_move(unit: "Unit", movement_type: object) -> bool:
    move_tag = movement_type_tag(movement_type)
    if move_tag not in ("move", "advance", "fall_back"):
        return False
    fn = getattr(unit, "has_super_heavy_walker", None)
    if callable(fn):
        return bool(fn())
    return False


def ruins_wall_traversal_allowed(unit: "Unit", movement_type: object = None) -> bool:
    if can_breach_ruins_walls(unit):
        return True
    return super_heavy_walker_active_for_move(unit, movement_type)


def movement_type_allows_fly_over(movement_type: object) -> bool:
    move_tag = movement_type_tag(movement_type)
    return move_tag in ("move", "advance", "fall_back", "charge")


def movement_type_allows_flip_belt(movement_type: object) -> bool:
    move_tag = movement_type_tag(movement_type)
    return move_tag in ("move", "advance", "fall_back", "charge")


def unit_ignores_vertical_distance(unit: "Unit", movement_type: object = None) -> bool:
    move_tag = movement_type_tag(movement_type)
    fn = getattr(unit, "ignores_vertical_distance_for_move_type", None)
    if callable(fn) and bool(fn(movement_type)):
        return True
    if move_tag == "advance":
        advance_fn = getattr(unit, "advance_ignores_vertical_distance", None)
        if callable(advance_fn) and bool(advance_fn()):
            return True
    if not movement_type_allows_flip_belt(movement_type):
        return False
    flip_belt_fn = getattr(unit, "has_flip_belt", None)
    if callable(flip_belt_fn):
        return bool(flip_belt_fn())
    return False


def unit_is_fly_move(unit: "Unit", movement_type: object = None) -> bool:
    if not movement_type_allows_fly_over(movement_type):
        return False
    return bool(getattr(unit, "is_flying", False))


def unit_can_fly_over_big_models(unit: "Unit", movement_type: object = None) -> bool:
    if not unit_is_fly_move(unit, movement_type):
        return False
    return bool(getattr(unit, "is_monster", False) or getattr(unit, "is_vehicle", False))


def unit_is_vehicle(unit: "Unit") -> bool:
    if bool(getattr(unit, "is_vehicle", False)):
        return True
    keywords = tuple(getattr(unit, "keywords", ()) or ())
    for keyword in keywords:
        if str(keyword or "").strip().lower() == "vehicle":
            return True
    return False


def get_freely_climbable_range(unit: "Unit", movement_type: object = None) -> float:
    threshold = float(FREELY_CLIMBABLE_RANGE)
    if super_heavy_walker_active_for_move(unit, movement_type):
        threshold = max(threshold, 4.0)
    height = unit_move_over_low_terrain_height(unit, movement_type)
    if height is not None:
        threshold = max(threshold, float(height))
    return float(threshold)


def can_end_on_upper_surfaces(unit: "Unit") -> bool:
    fn = getattr(unit, "can_access_upper_floors", None)
    if callable(fn):
        return bool(fn())
    return can_breach_ruins_walls(unit) or bool(getattr(unit, "is_flying", False))


def _unit_parent_army(unit: "Unit") -> object:
    getter = getattr(unit, "get_parent_army", None)
    if callable(getter):
        return getter()
    return getattr(unit, "parent_army", None)


def unit_army_identity_key(unit: "Unit") -> tuple[str, object]:
    army = _unit_parent_army(unit)
    if army is not None:
        return ("army", id(army))
    faction = str(getattr(unit, "faction", "") or "")
    return ("fallback_faction", faction)


def units_share_army_identity(unit_a: "Unit", unit_b: "Unit") -> bool:
    if unit_a is unit_b:
        return True
    army_a = _unit_parent_army(unit_a)
    army_b = _unit_parent_army(unit_b)
    if army_a is not None or army_b is not None:
        return army_a is not None and army_b is not None and army_a is army_b
    faction_a = str(getattr(unit_a, "faction", "") or "")
    faction_b = str(getattr(unit_b, "faction", "") or "")
    return bool(faction_a and faction_b and faction_a == faction_b)


def _engagement_buffer_rules(move_tag: str) -> dict[str, object]:
    return {
        "normal_move_buffer_inches": float(ENGAGEMENT_RANGE_HORIZONTAL),
        "scout_buffer_inches": 9.0,
        "use_normal_move_buffer": move_tag in ("move", "advance"),
        "use_scout_buffer": move_tag == "scout",
        "allow_engagement_range_entry": move_tag in ("charge", "pile_in", "consolidate", "fall_back"),
    }


def _terrain_transition_rules(unit: "Unit", movement_type: object, free_climb_height: float) -> dict[str, object]:
    return {
        "free_climb_height_inches": float(free_climb_height),
        "can_breach_ruins_walls": can_breach_ruins_walls(unit),
        "ruins_wall_traversal_allowed": ruins_wall_traversal_allowed(unit, movement_type),
        "is_fly_move": unit_is_fly_move(unit, movement_type),
        "is_vehicle_unit": unit_is_vehicle(unit),
        "can_fly_over_big_models": unit_can_fly_over_big_models(unit, movement_type),
        "can_move_over_friendly_monster_vehicle": unit_can_move_over_friendly_monster_vehicle(unit, movement_type),
    }


def _fall_back_interaction_rules(move_tag: str) -> dict[str, object]:
    return {
        "check_desperate_escape": move_tag == "fall_back",
        "cannot_end_in_engagement_range": move_tag == "fall_back",
    }


def _can_move_through_enemy_models(move_tag: str) -> bool:
    return move_tag == "fall_back"


def _can_move_through_friendly_models(_move_tag: str) -> bool:
    return False


def _pivot_cost_mode(_unit: "Unit") -> str:
    return "map_calculated"


def build_movement_profile(
    unit: "Unit",
    movement_type: object,
    *,
    target_unit: object = None,
    target_units: object = None,
) -> MovementProfile:
    del target_unit, target_units
    move_tag = movement_type_tag(movement_type) or "move"

    free_climb_height_inches = float(FREELY_CLIMBABLE_RANGE)
    can_ignore_vertical = False
    can_breach = False
    can_end_upper = True
    if unit is not None:
        free_climb_height_inches = get_freely_climbable_range(unit, movement_type)
        can_ignore_vertical = unit_ignores_vertical_distance(unit, movement_type)
        can_breach = can_breach_ruins_walls(unit)
        can_end_upper = can_end_on_upper_surfaces(unit)

    return MovementProfile(
        movement_type_tag=move_tag,
        free_climb_height_inches=float(free_climb_height_inches),
        can_ignore_vertical_distance=bool(can_ignore_vertical),
        can_breach_ruins_walls=bool(can_breach),
        can_end_on_upper_surfaces=bool(can_end_upper),
        can_move_through_enemy_models=bool(_can_move_through_enemy_models(move_tag)),
        can_move_through_friendly_models=bool(_can_move_through_friendly_models(move_tag)),
        pivot_cost_mode=_pivot_cost_mode(unit),
        engagement_buffer_rules=_engagement_buffer_rules(move_tag),
        terrain_transition_rules=_terrain_transition_rules(unit, movement_type, free_climb_height_inches)
        if unit is not None
        else {},
        fall_back_interaction_rules=_fall_back_interaction_rules(move_tag),
    )


__all__ = [
    "MovementProfile",
    "build_movement_profile",
    "can_breach_ruins_walls",
    "can_end_on_upper_surfaces",
    "counts_as_infantry_for_terrain",
    "get_freely_climbable_range",
    "move_type_matches",
    "movement_type_allows_flip_belt",
    "movement_type_allows_fly_over",
    "movement_type_tag",
    "ruins_wall_traversal_allowed",
    "super_heavy_walker_active_for_move",
    "unit_army_identity_key",
    "unit_can_fly_over_big_models",
    "unit_is_vehicle",
    "unit_can_move_over_friendly_monster_vehicle",
    "unit_ignores_vertical_distance",
    "unit_is_fly_move",
    "unit_move_over_low_terrain_height",
    "units_share_army_identity",
]
