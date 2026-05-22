from __future__ import annotations

from typing import Iterable, Optional, Sequence

from ..decision_dispatcher import _validate_choice_from_options
from ..decisions import DecisionOption, DecisionRequest, DecisionResult
from ...utility.entity_ids import maybe_entity_id
from ...utility.unit_models import unit_group_members, unit_group_models
import logging
logger = logging.getLogger(__name__)


def find_option(request: DecisionRequest, option_id: str) -> Optional[DecisionOption]:
    for opt in list(getattr(request, "options", []) or []):
        if opt.option_id == option_id:
            return opt
    return None


def validate_option_choice(request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    return _validate_choice_from_options(request, result)


def get_registry(game: object):
    return getattr(game, "entity_registry", None)


def _matches_entity_id(entity: object, entity_id: str) -> bool:
    if entity is None or not entity_id:
        return False
    maybe_id = maybe_entity_id(entity)
    if not maybe_id:
        return False
    return str(maybe_id) == str(entity_id)


def _iter_player_armies(game: object):
    for player in list(getattr(game, "players", []) or []):
        army = getattr(player, "army", None)
        if army is None:
            getter = getattr(player, "get_army", None)
            if callable(getter):
                army = getter()
        if army is not None:
            yield player, army


def _iter_lookup_models(unit: object):
    seen: set[str] = set()
    for model in unit_group_models(unit, include_pending=True):
        model_id = str(maybe_entity_id(model) or "").strip()
        if model_id and model_id in seen:
            continue
        if model_id:
            seen.add(model_id)
        yield model
    for member in unit_group_members(unit):
        for model in list(getattr(member, "models_lost", []) or []):
            model_id = str(maybe_entity_id(model) or "").strip()
            if model_id and model_id in seen:
                continue
            if model_id:
                seen.add(model_id)
            yield model


def _fallback_entity_lookup(game: object, entity_id: str, *, kind: str) -> Optional[object]:
    if kind == "player":
        for player in list(getattr(game, "players", []) or []):
            if _matches_entity_id(player, entity_id):
                return player
        return None

    if kind == "army":
        for _player, army in _iter_player_armies(game):
            if _matches_entity_id(army, entity_id):
                return army
        return None

    if kind == "unit":
        for _player, army in _iter_player_armies(game):
            for unit in list(getattr(army, "units", []) or []):
                if _matches_entity_id(unit, entity_id):
                    return unit
        game_map = getattr(game, "map", None)
        for unit in list(getattr(game_map, "units", []) or []):
            if _matches_entity_id(unit, entity_id):
                return unit
        return None

    if kind == "model":
        for _player, army in _iter_player_armies(game):
            for unit in list(getattr(army, "units", []) or []):
                for model in _iter_lookup_models(unit):
                    if _matches_entity_id(model, entity_id):
                        return model
        return None

    if kind == "wargear":
        for _player, army in _iter_player_armies(game):
            for unit in list(getattr(army, "units", []) or []):
                for model in _iter_lookup_models(unit):
                    for wargear in list(getattr(model, "wargear", []) or []):
                        if _matches_entity_id(wargear, entity_id):
                            return wargear
        return None

    if kind == "objective":
        game_map = getattr(game, "map", None)
        for objective in list(getattr(game_map, "objectives", []) or []):
            if _matches_entity_id(objective, entity_id):
                return objective
        for objective in list(getattr(game, "objectives", []) or []):
            if _matches_entity_id(objective, entity_id):
                return objective
        return None

    if kind == "terrain":
        game_map = getattr(game, "map", None)
        for terrain_feature in list(getattr(game_map, "terrain_features", []) or []):
            if _matches_entity_id(terrain_feature, entity_id):
                return terrain_feature
        return None

    return None


def get_entity(game: object, entity_id: str, *, kind: str) -> Optional[object]:
    if not entity_id:
        return None
    registry = get_registry(game)
    if registry is not None:
        entity = registry.get(entity_id, kind=kind)
        if entity is not None:
            return entity
        rebuild = getattr(game, "rebuild_entity_registry", None)
        if callable(rebuild):
            try:
                rebuild()
            except (AttributeError, TypeError, ValueError):
                pass
            else:
                entity = registry.get(entity_id, kind=kind)
                if entity is not None:
                    return entity
    return _fallback_entity_lookup(game, entity_id, kind=kind)


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


def get_terrain(game: object, terrain_id: str) -> Optional[object]:
    return get_entity(game, terrain_id, kind="terrain")


def resolve_unit(game: object, value: object) -> Optional[object]:
    return resolve_entity(game, value, kind="unit")


def resolve_model(game: object, value: object) -> Optional[object]:
    return resolve_entity(game, value, kind="model")


def resolve_wargear(game: object, value: object) -> Optional[object]:
    return resolve_entity(game, value, kind="wargear")


def resolve_objective(game: object, value: object) -> Optional[object]:
    return resolve_entity(game, value, kind="objective")


def resolve_terrain(game: object, value: object) -> Optional[object]:
    return resolve_entity(game, value, kind="terrain")


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
    logger.debug(f"DEBUG: Validating model positions for {unit}")
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
