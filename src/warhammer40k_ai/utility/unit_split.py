from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Optional

from ..units.status_effects import BattleShockEffect, StatusEffect
from .entity_ids import get_entity_id


def _clone_status_effect(effect: StatusEffect) -> Optional[StatusEffect]:
    """Best-effort clone for duration-based status effects."""
    if effect is None:
        return None
    if isinstance(effect, BattleShockEffect):
        # Preserve the same expiration turn/phase.
        new_effect = BattleShockEffect(current_turn=max(0, int(getattr(effect, "turn", 1)) - 1))
        try:
            new_effect.turn = int(getattr(effect, "turn", new_effect.turn))
        except Exception:
            pass
        try:
            new_effect.phase = int(getattr(effect, "phase", new_effect.phase))
        except Exception:
            pass
        return new_effect
    try:
        return copy.deepcopy(effect)
    except Exception:
        return None


def _extract_expiring_special_rules(special_rules: Any) -> Dict[str, Any]:
    """Return only time-limited/expiring special rule entries."""
    if not isinstance(special_rules, dict):
        return {}

    expiring_suffixes = ("_expires_phase", "_expires_turn", "_expires_round")
    expiring_keys = [k for k in special_rules.keys() if str(k).endswith(expiring_suffixes)]
    prefixes = {str(k).rsplit("_expires_", 1)[0] for k in expiring_keys}

    def _deepcopy(value: Any) -> Any:
        try:
            return copy.deepcopy(value)
        except Exception:
            return value

    out: Dict[str, Any] = {}
    for key, value in special_rules.items():
        key_str = str(key)
        if key in expiring_keys:
            out[key] = _deepcopy(value)
            continue
        if any(key_str.startswith(prefix + "_") for prefix in prefixes):
            out[key] = _deepcopy(value)
            continue
        if isinstance(value, list):
            if any(
                isinstance(entry, dict)
                and any(k in entry for k in ("expires_phase", "expires_turn", "expires_round"))
                for entry in value
            ):
                out[key] = _deepcopy(value)
                continue
        if isinstance(value, dict):
            if any(str(k).endswith(expiring_suffixes) for k in value.keys()):
                out[key] = _deepcopy(value)
                continue
            if any(
                isinstance(v, dict)
                and any(k in v for k in ("expires_phase", "expires_turn", "expires_round"))
                for v in value.values()
            ):
                out[key] = _deepcopy(value)
                continue
    return out


def snapshot_persistent_unit_state(unit: Any) -> Dict[str, Any]:
    """Capture duration-based state that should persist through a unit split."""
    if unit is None:
        return {}
    effects = []
    for eff in list(getattr(unit, "status_effects", []) or []):
        cloned = _clone_status_effect(eff)
        if cloned is not None:
            effects.append(cloned)
    round_state = None
    try:
        round_state = copy.deepcopy(getattr(unit, "round_state", None))
    except Exception:
        round_state = None
    return {
        "status_effects": effects,
        "special_rules": _extract_expiring_special_rules(getattr(unit, "special_rules", None)),
        "round_state": round_state,
        "reserve_turn_deployed": getattr(unit, "reserve_turn_deployed", None),
        "arrived_from_reserves_this_turn": bool(getattr(unit, "arrived_from_reserves_this_turn", False)),
        "deployed": bool(getattr(unit, "deployed", False)),
        "reserve_status": str(getattr(unit, "reserve_status", "deployed") or "deployed"),
        "hover_mode": bool(getattr(unit, "hover_mode", False)),
        "hover_declared": bool(getattr(unit, "hover_declared", False)),
    }


def apply_persistent_unit_state(unit: Any, snapshot: Dict[str, Any], *, clear_existing: bool = True) -> None:
    """Apply a persistent state snapshot onto a unit."""
    if unit is None or not isinstance(snapshot, dict):
        return
    if clear_existing:
        for eff in list(getattr(unit, "status_effects", []) or []):
            try:
                unit.remove_status_effect(eff)
            except Exception:
                continue
        try:
            unit.status_effects = []
        except Exception:
            pass

    base_rules = dict(getattr(unit, "special_rules", {}) or {})
    base_rules.update(dict(snapshot.get("special_rules", {}) or {}))
    unit.special_rules = base_rules

    # Apply status effects after special rule snapshot so effect hooks can adjust state.
    for eff in list(snapshot.get("status_effects", []) or []):
        try:
            unit.apply_status_effect(eff)
        except Exception:
            continue

    if snapshot.get("round_state") is not None:
        try:
            unit.round_state = copy.deepcopy(snapshot["round_state"])
        except Exception:
            pass

    try:
        unit.reserve_turn_deployed = snapshot.get("reserve_turn_deployed")
    except Exception:
        pass
    try:
        unit.arrived_from_reserves_this_turn = bool(snapshot.get("arrived_from_reserves_this_turn", False))
    except Exception:
        pass
    try:
        unit.deployed = bool(snapshot.get("deployed", False))
    except Exception:
        pass
    try:
        unit.reserve_status = str(snapshot.get("reserve_status") or "deployed")
    except Exception:
        pass
    try:
        unit.hover_mode = bool(snapshot.get("hover_mode", False))
    except Exception:
        pass
    try:
        unit.hover_declared = bool(snapshot.get("hover_declared", False))
    except Exception:
        pass


def split_unit_into_single_model_units(
    unit: Any,
    *,
    game: Optional[Any] = None,
    game_map: Optional[Any] = None,
) -> List[Any]:
    """
    Split an Attached unit into single-model units.

    - All models in the attached group become their own unit.
    - Duration-based status effects and expiring special rules are copied to each new unit.
    - Leading/attached-only effects should be cleared by detaching leaders before applying snapshot.
    """
    if unit is None:
        return []

    root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
    if root is None:
        return []

    snapshot = snapshot_persistent_unit_state(root)

    army = None
    try:
        army = root.get_parent_army()
    except Exception:
        army = None

    if game is None:
        try:
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        except Exception:
            game = None
    if game_map is None:
        game_map = getattr(game, "map", None) if game is not None else None

    leaders = list(getattr(root, "attached_leaders", []) or [])
    bodyguard_models = [m for m in list(getattr(root, "models", []) or []) if getattr(m, "is_alive", True)]

    # If there is only one model and no leaders, keep the unit and just reset starting strength.
    if not leaders and len(bodyguard_models) == 1:
        model = bodyguard_models[0]
        try:
            root.starting_model_count = 1
        except Exception:
            pass
        try:
            root.starting_total_wounds = int(getattr(model, "_base_wounds", getattr(model, "wounds", 0)))
        except Exception:
            pass
        return [root]

    for leader in leaders:
        try:
            leader.detach_from_unit()
        except Exception:
            continue

    try:
        root.attached_leaders = []
    except Exception:
        pass

    # Remove the root unit from army/map without firing destroyed triggers.
    try:
        if army is not None and root in getattr(army, "units", []):
            army.units.remove(root)
    except Exception:
        pass
    try:
        if game_map is not None and hasattr(game_map, "units") and root in game_map.units:
            game_map.units.remove(root)
    except Exception:
        pass
    try:
        root.models = []
        root.models_lost = []
    except Exception:
        pass

    resulting_units: List[Any] = []

    # Existing leader units become single-model units in their own right.
    for leader in leaders:
        try:
            if not list(getattr(leader, "models", []) or []):
                continue
        except Exception:
            continue
        apply_persistent_unit_state(leader, snapshot, clear_existing=True)
        try:
            leader.attached_to = None
            leader.attached_leaders = []
        except Exception:
            pass
        try:
            leader.starting_model_count = 1
        except Exception:
            pass
        try:
            model = leader.models[0]
            leader.starting_total_wounds = int(getattr(model, "_base_wounds", getattr(model, "wounds", 0)))
        except Exception:
            pass
        try:
            leader.deployed = True
            leader.reserve_status = "deployed"
            leader.embarked_in = None
        except Exception:
            pass
        try:
            if army is not None and leader not in getattr(army, "units", []):
                army.add_unit(leader)
        except Exception:
            pass
        try:
            if game_map is not None and hasattr(game_map, "units") and leader not in game_map.units:
                game_map.units.append(leader)
        except Exception:
            pass
        try:
            if hasattr(leader, "_invalidate_ability_cache"):
                leader._invalidate_ability_cache()
        except Exception:
            pass
        try:
            if hasattr(leader, "update_coherency"):
                leader.update_coherency()
        except Exception:
            pass
        resulting_units.append(leader)

    # Create new single-model units for each bodyguard model.
    for model in bodyguard_models:
        try:
            from ..units.unit import Unit as UnitClass
        except Exception:
            continue
        datasheet = getattr(root, "_datasheet", None)
        if datasheet is None:
            continue
        try:
            new_unit = UnitClass(datasheet, quantity=1, enhancement=getattr(root, "enhancement", None))
        except Exception:
            new_unit = UnitClass(datasheet, quantity=1)

        try:
            new_unit.models = [model]
            if hasattr(model, "set_parent_unit"):
                model.set_parent_unit(new_unit)
            else:
                model.parent_unit = new_unit
        except Exception:
            continue

        apply_persistent_unit_state(new_unit, snapshot, clear_existing=True)
        try:
            new_unit.attached_leaders = []
            new_unit.attached_to = None
        except Exception:
            pass
        try:
            new_unit.models_lost = []
        except Exception:
            pass
        try:
            new_unit.starting_model_count = 1
        except Exception:
            pass
        try:
            new_unit.starting_total_wounds = int(getattr(model, "_base_wounds", getattr(model, "wounds", 0)))
        except Exception:
            pass
        try:
            new_unit.deployed = True
            new_unit.reserve_status = "deployed"
            new_unit.embarked_in = None
        except Exception:
            pass
        try:
            new_unit.set_parent_army(army)
        except Exception:
            pass
        try:
            if army is not None:
                army.add_unit(new_unit)
        except Exception:
            pass
        try:
            if game_map is not None and hasattr(game_map, "units"):
                game_map.units.append(new_unit)
        except Exception:
            pass
        try:
            if hasattr(new_unit, "_invalidate_ability_cache"):
                new_unit._invalidate_ability_cache()
        except Exception:
            pass
        try:
            if hasattr(new_unit, "update_coherency"):
                new_unit.update_coherency()
        except Exception:
            pass
        resulting_units.append(new_unit)

    # Rebuild entity registry to include new units.
    try:
        if game is not None and hasattr(game, "rebuild_entity_registry"):
            game.rebuild_entity_registry()
    except Exception:
        pass
    try:
        if game is not None and hasattr(game, "refresh_rule_subscribers"):
            game.refresh_rule_subscribers()
    except Exception:
        pass

    return resulting_units


def _norm_ability_name(value: str) -> str:
    import re

    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _unit_has_ability_name(unit: Any, ability_name: str) -> bool:
    target = _norm_ability_name(ability_name)
    if not target or unit is None:
        return False

    iter_entries = getattr(unit, "_iter_ability_entries_for_rules", None)
    if callable(iter_entries):
        entries = None
        try:
            entries = iter_entries(model=None)
        except TypeError:
            entries = iter_entries()
        if entries is not None:
            for name, _desc in entries:
                if _norm_ability_name(name) == target:
                    return True
            return False

    for ability in list(getattr(unit, "possible_abilities", []) or []):
        if isinstance(ability, str):
            name = ability
        else:
            name = getattr(ability, "name", "")
        if _norm_ability_name(name) == target:
            return True
    return False


def _add_disabled_ability_names(unit: Any, names: Iterable[str]) -> None:
    if unit is None:
        return
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    existing = list(sr.get("disabled_ability_names", []) or [])
    merged: dict[str, str] = {}
    for name in existing:
        norm = _norm_ability_name(name)
        if norm:
            merged[norm] = str(name)
    for name in list(names or []):
        norm = _norm_ability_name(name)
        if norm and norm not in merged:
            merged[norm] = str(name)
    sr["disabled_ability_names"] = [merged[k] for k in sorted(merged.keys())]
    unit.special_rules = sr


def _split_unit_into_model_groups(
    unit: Any,
    *,
    model_groups: Iterable[Iterable[Any]],
    declaration_flag: str,
    split_applied_flag: str,
    split_index_flag: str,
    split_origin_flag: str,
    per_unit_disabled_names: Optional[Iterable[Iterable[str]]] = None,
    game: Optional[Any] = None,
    game_map: Optional[Any] = None,
) -> List[Any]:
    """
    Split a unit into explicitly provided model groups.

    - Each group becomes a new unit built from the same datasheet.
    - Groups must partition the root unit's alive bodyguard models exactly once.
    - Persistent/expiring state is copied to both new units.
    """
    if unit is None:
        return []

    root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
    if root is None:
        return []

    leaders = list(getattr(root, "attached_leaders", []) or [])
    if leaders:
        return []

    alive_models = [m for m in list(getattr(root, "models", []) or []) if getattr(m, "is_alive", True)]
    if not alive_models:
        return []

    split_groups = [list(group) for group in list(model_groups or [])]
    if len(split_groups) < 2 or any(not group for group in split_groups):
        return []

    grouped_model_ids: list[int] = []
    seen_model_ids: set[int] = set()
    for group in split_groups:
        for model in group:
            if model is None or not getattr(model, "is_alive", True):
                return []
            model_id = id(model)
            if model_id in seen_model_ids:
                return []
            seen_model_ids.add(model_id)
            grouped_model_ids.append(model_id)
    alive_model_ids = [id(model) for model in alive_models]
    if len(grouped_model_ids) != len(alive_model_ids):
        return []
    if set(grouped_model_ids) != set(alive_model_ids):
        return []

    snapshot = snapshot_persistent_unit_state(root)

    army_getter = getattr(root, "get_parent_army", None)
    army = army_getter() if callable(army_getter) else getattr(root, "parent_army", None)
    if army is None:
        return []

    if game is None:
        game = getattr(getattr(army, "player", None), "game", None)
    if game_map is None:
        game_map = getattr(game, "map", None) if game is not None else None

    map_units = getattr(game_map, "units", None) if game_map is not None else None
    root_was_on_map = bool(map_units is not None and root in list(map_units or []))

    from ..units.unit import Unit as UnitClass

    datasheet = getattr(root, "_datasheet", None)
    if datasheet is None:
        return []

    root_id = str(get_entity_id(root) or "")
    resulting_units: List[Any] = []
    disabled_groups = [list(group or []) for group in list(per_unit_disabled_names or [])]

    for index, group in enumerate(split_groups):
        new_unit = UnitClass(datasheet, quantity=len(group), enhancement=getattr(root, "enhancement", None))
        new_unit.models = list(group)
        for model in group:
            if hasattr(model, "set_parent_unit"):
                model.set_parent_unit(new_unit)
            else:
                model.parent_unit = new_unit

        apply_persistent_unit_state(new_unit, snapshot, clear_existing=True)
        new_unit.attached_leaders = []
        new_unit.attached_to = None
        new_unit.models_lost = []
        new_unit.starting_model_count = int(len(group))
        new_unit.starting_total_wounds = int(
            sum(int(getattr(model, "_base_wounds", getattr(model, "wounds", 0)) or 0) for model in group)
        )
        new_unit.embarked_in = None

        sr = getattr(new_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[str(declaration_flag or "split_declared")] = True
        sr[str(split_applied_flag or "split_applied")] = True
        sr[str(split_index_flag or "split_index")] = int(index + 1)
        if root_id:
            sr[str(split_origin_flag or "split_origin_unit_id")] = root_id
        new_unit.special_rules = sr
        if index < len(disabled_groups) and disabled_groups[index]:
            _add_disabled_ability_names(new_unit, disabled_groups[index])

        resulting_units.append(new_unit)

    # Remove the root unit from army/map without firing destroyed triggers.
    if root in list(getattr(army, "units", []) or []):
        army.units.remove(root)
    if map_units is not None and root in list(map_units or []):
        map_units.remove(root)
    root.models = []
    root.models_lost = []

    for new_unit in resulting_units:
        army.add_unit(new_unit)
        if root_was_on_map and map_units is not None:
            map_units.append(new_unit)
        invalidate_cache = getattr(new_unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()
        update_coherency = getattr(new_unit, "update_coherency", None)
        if callable(update_coherency):
            update_coherency()

    rebuild_registry = getattr(game, "rebuild_entity_registry", None) if game is not None else None
    if callable(rebuild_registry):
        rebuild_registry()
    refresh_subscribers = getattr(game, "refresh_rule_subscribers", None) if game is not None else None
    if callable(refresh_subscribers):
        refresh_subscribers()

    return resulting_units


def _split_unit_into_two_five_model_units(
    unit: Any,
    *,
    declaration_flag: str,
    split_applied_flag: str,
    split_index_flag: str,
    split_origin_flag: str,
    second_unit_disabled: Optional[list[str]] = None,
    game: Optional[Any] = None,
    game_map: Optional[Any] = None,
) -> List[Any]:
    """
    Split a 10-model unit into two 5-model units.

    - Uses current alive model order: first 5 models become split unit #1, next 5 become split unit #2.
    - Persistent/expiring state is copied to both new units.
    """
    if unit is None:
        return []

    root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
    if root is None:
        return []

    models = [m for m in list(getattr(root, "models", []) or []) if getattr(m, "is_alive", True)]
    if len(models) != 10:
        return []

    return _split_unit_into_model_groups(
        unit,
        model_groups=[models[:5], models[5:10]],
        declaration_flag=declaration_flag,
        split_applied_flag=split_applied_flag,
        split_index_flag=split_index_flag,
        split_origin_flag=split_origin_flag,
        per_unit_disabled_names=[[], list(second_unit_disabled or [])],
        game=game,
        game_map=game_map,
    )


def split_unit_into_patrol_squad_units(
    unit: Any,
    *,
    game: Optional[Any] = None,
    game_map: Optional[Any] = None,
) -> List[Any]:
    """
    Split a PATROL SQUAD unit into two 5-model units.

    - Uses current alive model order: first 5 models become split unit #1, next 5 become split unit #2.
    - If the source has Bomb Squigs/Distraction Grot, split unit #2 has those abilities disabled.
    - Persistent/expiring state is copied to both new units.
    """
    root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
    if root is None:
        return []
    second_unit_disabled: list[str] = []
    if _unit_has_ability_name(root, "Bomb Squigs"):
        second_unit_disabled.append("Bomb Squigs")
    if _unit_has_ability_name(root, "Distraction Grot"):
        second_unit_disabled.append("Distraction Grot")
    return _split_unit_into_two_five_model_units(
        unit,
        declaration_flag="patrol_squad_declared",
        split_applied_flag="patrol_squad_split_applied",
        split_index_flag="patrol_squad_split_index",
        split_origin_flag="patrol_squad_split_origin_unit_id",
        second_unit_disabled=second_unit_disabled,
        game=game,
        game_map=game_map,
    )


def split_unit_into_combat_squad_units(
    unit: Any,
    *,
    game: Optional[Any] = None,
    game_map: Optional[Any] = None,
) -> List[Any]:
    """
    Split a COMBAT SQUADS unit into two 5-model units.
    """
    return _split_unit_into_two_five_model_units(
        unit,
        declaration_flag="combat_squads_declared",
        split_applied_flag="combat_squads_split_applied",
        split_index_flag="combat_squads_split_index",
        split_origin_flag="combat_squads_split_origin_unit_id",
        second_unit_disabled=[],
        game=game,
        game_map=game_map,
    )


def split_unit_into_wolf_guard_headtakers_units(
    unit: Any,
    *,
    game: Optional[Any] = None,
    game_map: Optional[Any] = None,
) -> List[Any]:
    """
    Split a Wolf Guard Headtakers unit into separate HEADTAKERS and HUNTING WOLVES units.

    - Uses current alive bodyguard models.
    - The resulting Headtakers unit keeps Headhunters support; both resulting units have
      Let Loose the Wolves disabled to prevent repeated splitting.
    """
    if unit is None:
        return []

    root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
    if root is None:
        return []

    alive_models = [m for m in list(getattr(root, "models", []) or []) if getattr(m, "is_alive", True)]
    if not alive_models:
        return []

    headtakers: list[Any] = []
    wolves: list[Any] = []
    for model in alive_models:
        normalized_name = _norm_ability_name(getattr(model, "name", ""))
        if "hunting wolve" in normalized_name or "hunting wolf" in normalized_name or "hunting wolves" in normalized_name:
            wolves.append(model)
            continue
        if "headtaker" in normalized_name:
            headtakers.append(model)
            continue
        return []

    if not headtakers or not wolves:
        return []

    return _split_unit_into_model_groups(
        unit,
        model_groups=[headtakers, wolves],
        declaration_flag="let_loose_the_wolves_declared",
        split_applied_flag="let_loose_the_wolves_split_applied",
        split_index_flag="let_loose_the_wolves_split_index",
        split_origin_flag="let_loose_the_wolves_split_origin_unit_id",
        per_unit_disabled_names=[
            ["Let Loose the Wolves"],
            ["Let Loose the Wolves"],
        ],
        game=game,
        game_map=game_map,
    )
