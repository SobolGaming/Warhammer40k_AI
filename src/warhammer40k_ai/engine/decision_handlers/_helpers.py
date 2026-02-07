from __future__ import annotations

from typing import Iterable, Optional, Sequence

from ..decision_dispatcher import _validate_choice_from_options
from ..decisions import DecisionOption, DecisionRequest, DecisionResult
from ...utility.entity_ids import maybe_entity_id


def find_option(request: DecisionRequest, option_id: str) -> Optional[DecisionOption]:
    for opt in list(getattr(request, "options", []) or []):
        if opt.option_id == option_id:
            return opt
    return None


def validate_option_choice(request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    return _validate_choice_from_options(request, result)


def get_registry(game: object):
    return getattr(game, "entity_registry", None)


def get_entity(game: object, entity_id: str, *, kind: str) -> Optional[object]:
    if not entity_id:
        return None
    registry = get_registry(game)
    if registry is None:
        return None
    return registry.get(entity_id, kind=kind)


def _coerce_entity_id(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return maybe_entity_id(value)


def resolve_entity(game: object, value: object, *, kind: str) -> Optional[object]:
    if value is None:
        return None
    if not isinstance(value, str):
        entity_id = maybe_entity_id(value)
        if entity_id:
            return value
    return get_entity(game, str(value or ""), kind=kind)


def get_unit(game: object, unit_id: str) -> Optional[object]:
    return get_entity(game, unit_id, kind="unit")


def get_model(game: object, model_id: str) -> Optional[object]:
    return get_entity(game, model_id, kind="model")


def get_wargear(game: object, wargear_id: str) -> Optional[object]:
    return get_entity(game, wargear_id, kind="wargear")


def get_objective(game: object, objective_id: str) -> Optional[object]:
    return get_entity(game, objective_id, kind="objective")


def resolve_unit(game: object, value: object) -> Optional[object]:
    return resolve_entity(game, value, kind="unit")


def resolve_model(game: object, value: object) -> Optional[object]:
    return resolve_entity(game, value, kind="model")


def resolve_wargear(game: object, value: object) -> Optional[object]:
    return resolve_entity(game, value, kind="wargear")


def resolve_objective(game: object, value: object) -> Optional[object]:
    return resolve_entity(game, value, kind="objective")


def coerce_entity_id(value: object) -> str:
    entity_id = _coerce_entity_id(value)
    return str(entity_id or "")


def resolve_player(game: object, value: object) -> Optional[object]:
    return resolve_entity(game, value, kind="player")


def resolve_army(game: object, value: object) -> Optional[object]:
    return resolve_entity(game, value, kind="army")


def is_skip_choice(request: DecisionRequest, result: DecisionResult) -> bool:
    if result is None:
        return False
    payload = dict(getattr(result, "payload", {}) or {})
    if bool(payload.get("skipped", False)):
        return True
    if str(payload.get("action", "") or "") == "skip":
        return True
    opt = find_option(request, getattr(result, "option_id", ""))
    opt_payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    if bool(opt_payload.get("skip", False)):
        return True
    return str(opt_payload.get("action", "") or "") == "skip"


def validate_model_positions(game: object, unit: object, model_positions: object, *, context: str = "Move unit") -> Sequence[str]:
    print(f"DEBUG: Validating model positions for {unit}")
    if not isinstance(model_positions, list) or not model_positions:
        return (f"{context} requires model_positions list.",)
    for entry in model_positions:
        if not isinstance(entry, dict):
            return ("Each model position entry must be a dict.",)
        model_id = str(entry.get("model_id", "") or "")
        if not model_id:
            return ("Model position entry missing model_id.",)
        model = get_model(game, model_id)
        if model is None:
            return (f"Model not found: {model_id}",)
        pos = entry.get("position")
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            return ("Model position entry missing position.",)
        try:
            float(pos[0])
            float(pos[1])
            if len(pos) > 2:
                float(pos[2])
        except (TypeError, ValueError):
            return ("Model position coordinates must be numeric.",)
        parent_unit = getattr(model, "parent_unit", None)
        if parent_unit is not unit:
            members = None
            try:
                members = set(unit.get_attached_unit_members() or [])
            except (AttributeError, TypeError):
                members = None
            if not members or parent_unit not in members:
                return ("Model does not belong to the selected unit.",)
    return ()


def apply_model_positions(game: object, model_positions: Iterable[dict]) -> None:
    for entry in list(model_positions or []):
        model = get_model(game, str(entry.get("model_id", "") or ""))
        if model is None:
            continue
        pos = entry.get("position") or []
        if len(pos) < 2:
            continue
        x = float(pos[0])
        y = float(pos[1])
        z = float(pos[2]) if len(pos) > 2 else float(getattr(model.model_base, "z", 0.0))
        facing = entry.get("facing", None)
        if facing is None:
            facing = getattr(model.model_base, "facing", 0.0)
        model.set_location(x, y, z, float(facing))
