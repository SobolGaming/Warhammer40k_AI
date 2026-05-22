from __future__ import annotations

from typing import Any


def _model_list(values: object, *, include_pending: bool) -> list[Any]:
    return [
        model
        for model in list(values or [])
        if model is not None and (include_pending or not getattr(model, "_pending_placement", False))
    ]


def unit_group_members(unit: object) -> list[Any]:
    """Return the unit objects that act as one rules unit, including attachments."""
    if unit is None:
        return []
    root_getter = getattr(unit, "get_attached_unit_root", None)
    root = root_getter() if callable(root_getter) else unit
    if root is None:
        return []
    get_members = getattr(root, "get_attached_unit_members", None)
    if callable(get_members):
        members = [member for member in list(get_members() or []) if member is not None]
        if members:
            return members
    return [root]


def unit_group_models(unit: object, *, include_pending: bool = True) -> list[Any]:
    """Return the models that act as one rules unit, including attached members."""
    if unit is None:
        return []
    models: list[Any] = []
    for member in unit_group_members(unit):
        models.extend(_model_list(getattr(member, "models", []) or [], include_pending=include_pending))
    if models:
        return models
    get_models = getattr(unit, "get_models_for_collision", None)
    if callable(get_models):
        models = _model_list(get_models() or [], include_pending=include_pending)
        if models:
            return models
    get_models = getattr(unit, "get_attached_unit_models", None)
    if callable(get_models):
        models = _model_list(get_models() or [], include_pending=include_pending)
        if models:
            return models
    return _model_list(getattr(unit, "models", []) or [], include_pending=include_pending)


def alive_unit_group_models(unit: object, *, include_pending: bool = True) -> list[Any]:
    models: list[Any] = []
    for model in unit_group_models(unit, include_pending=include_pending):
        alive_value = getattr(model, "is_alive", True)
        if bool(alive_value() if callable(alive_value) else alive_value):
            models.append(model)
    return models
