from __future__ import annotations

from typing import Any, Optional

from .entity_ids import maybe_entity_id


def army_identifier(army: Any) -> Optional[str]:
    """Return the stable army id used for ownership checks."""
    return maybe_entity_id(army)


def same_army(army_a: Any, army_b: Any) -> bool:
    """Compare army ownership by army identifier, falling back only to object identity."""
    if army_a is None or army_b is None:
        return False
    if army_a is army_b:
        return True
    id_a = army_identifier(army_a)
    id_b = army_identifier(army_b)
    if id_a is None or id_b is None:
        return False
    return id_a == id_b


def unit_root(unit: Any) -> Any:
    if unit is None:
        return None
    get_root = getattr(unit, "get_attached_unit_root", None)
    if not callable(get_root):
        return unit
    try:
        root = get_root()
    except (AttributeError, TypeError, ValueError):
        return unit
    return root if root is not None else unit


def unit_parent_army(unit: Any) -> Any:
    root = unit_root(unit)
    if root is None:
        return None
    get_parent_army = getattr(root, "get_parent_army", None)
    if callable(get_parent_army):
        return get_parent_army()
    parent_army = getattr(root, "parent_army", None)
    if parent_army is not None:
        return parent_army
    return getattr(root, "_army", None)


def unit_belongs_to_army(unit: Any, army: Any) -> bool:
    return same_army(unit_parent_army(unit), army)


def units_share_army(unit_a: Any, unit_b: Any) -> bool:
    return same_army(unit_parent_army(unit_a), unit_parent_army(unit_b))


def units_are_enemies(unit_a: Any, unit_b: Any) -> bool:
    army_a = unit_parent_army(unit_a)
    army_b = unit_parent_army(unit_b)
    if army_a is None or army_b is None:
        return False
    return not same_army(army_a, army_b)


def player_army(player: Any) -> Any:
    if player is None:
        return None
    get_army = getattr(player, "get_army", None)
    if callable(get_army):
        return get_army()
    return getattr(player, "army", None)


def unit_owned_by_player(unit: Any, player: Any) -> bool:
    if unit is None or player is None:
        return False
    parent_army = unit_parent_army(unit)
    if parent_army is None:
        return False
    owning_army = player_army(player)
    if owning_army is not None:
        return same_army(parent_army, owning_army)
    owner = getattr(parent_army, "player", None)
    if owner is player:
        return True
    owner_id = maybe_entity_id(owner)
    player_id = maybe_entity_id(player)
    return owner_id is not None and player_id is not None and owner_id == player_id
