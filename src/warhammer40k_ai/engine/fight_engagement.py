from __future__ import annotations

from ..utility.entity_ids import get_entity_id


def _canonical_unit_for_fight(manager, unit):
    try:
        root = unit.get_attached_unit_root()
        if root is None:
            return unit
        models = getattr(root, "models", None)
        if not isinstance(models, list):
            return unit
        return root
    except Exception:
        return unit


def _as_attached_view(manager, unit):
    try:
        from ..units.attached_unit import AttachedUnitView
    except Exception:
        AttachedUnitView = None
    root = manager._canonical_unit_for_fight(unit)
    if AttachedUnitView is None:
        return root
    try:
        members = list(root.get_attached_unit_members())
        if members and len(members) > 1:
            return AttachedUnitView(root)
    except Exception:
        pass
    return root


def _serialize_target_declarations(manager, target_declarations) -> list[dict]:
    serialized: list[dict] = []
    for target_unit in sorted(list(target_declarations or {}), key=lambda unit: str(get_entity_id(unit) or "")):
        target_unit_id = str(get_entity_id(target_unit) or "").strip()
        if not target_unit_id:
            continue
        models = []
        for model in list(target_declarations.get(target_unit, []) or []):
            model_id = str(get_entity_id(model) or "").strip()
            if model_id:
                models.append(model_id)
        serialized.append(
            {
                "target_unit_id": target_unit_id,
                "attacking_model_ids": sorted(set(models)),
            }
        )
    return serialized


def _resolve_model_by_id(manager, model_id: str):
    key = str(model_id or "").strip()
    if not key:
        return None
    registry = getattr(manager.game, "entity_registry", None)
    getter = getattr(registry, "get", None)
    if callable(getter):
        model = getter(key, kind="model")
        if model is not None:
            return model
    for player in list(getattr(manager.game, "players", []) or []):
        army = player.get_army() if hasattr(player, "get_army") else getattr(player, "army", None)
        for unit in list(getattr(army, "units", []) or []):
            try:
                models = list(unit.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(unit, "models", []) or [])
            for model in models:
                if str(get_entity_id(model) or "").strip() == key:
                    return model
    return None


def _deserialize_target_declarations(manager, serialized: list[dict]):
    declarations = {}
    resolve_unit = getattr(manager.game, "_resolve_unit_by_id", None)
    if not callable(resolve_unit):
        return declarations
    for entry in list(serialized or []):
        target_unit_id = str(dict(entry or {}).get("target_unit_id", "") or "").strip()
        if not target_unit_id:
            continue
        target_unit = resolve_unit(target_unit_id)
        if target_unit is None:
            continue
        models = []
        for model_id in list(dict(entry or {}).get("attacking_model_ids", []) or []):
            model = manager._resolve_model_by_id(str(model_id or ""))
            if model is not None:
                models.append(model)
        declarations[target_unit] = models
    return declarations
