from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any

from .path_witness import current_model_positions
from ..utility.entity_ids import get_entity_id

_FIRST_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
MOVEMENT_DISTANCE_EPSILON = 1e-4


@dataclass(frozen=True)
class ModelMovementDistance:
    model_id: str
    distance: float
    normal_limit: float


@dataclass(frozen=True)
class MovementDistanceProfile:
    entries: tuple[ModelMovementDistance, ...]

    @property
    def max_distance(self) -> float:
        return max((entry.distance for entry in self.entries), default=0.0)

    @property
    def max_normal_limit(self) -> float:
        return max((entry.normal_limit for entry in self.entries), default=0.0)

    @property
    def all_within_normal(self) -> bool:
        return all(
            entry.distance <= entry.normal_limit + MOVEMENT_DISTANCE_EPSILON
            for entry in self.entries
        )


def movement_value_to_inches(value: object, default: float = 0.0) -> float:
    if value is None:
        return float(default)
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return float(default)
    match = _FIRST_NUMBER_RE.search(text.replace('"', ""))
    if match is None:
        return float(default)
    return float(match.group(0))


def model_normal_move_limit(unit: object, model: object | None, game: object | None = None) -> float:
    value: object = getattr(unit, "movement", 0.0)
    resolver = getattr(unit, "get_effective_model_characteristic", None)
    if callable(resolver) and model is not None:
        game_map = getattr(game, "map", None) if game is not None else None
        try:
            value = resolver(model, "movement", game_map=game_map)
        except TypeError:
            value = resolver(model, "movement")
    limit = movement_value_to_inches(value, movement_value_to_inches(getattr(unit, "movement", 0.0), 0.0))
    bonus_fn = getattr(unit, "get_phase_movement_distance_bonus", None)
    if callable(bonus_fn):
        try:
            limit += movement_value_to_inches(bonus_fn("move", game=game), 0.0)
        except TypeError:
            limit += movement_value_to_inches(bonus_fn("move"), 0.0)
    return max(0.0, float(limit))


def unit_normal_move_limit(unit: object, game: object | None = None) -> float:
    get_models = getattr(unit, "get_attached_unit_models", None)
    models = list(get_models() or []) if callable(get_models) else list(getattr(unit, "models", []) or [])
    limits: list[float] = []
    for model in models:
        if model is None:
            continue
        alive_value = getattr(model, "is_alive", True)
        alive = bool(alive_value() if callable(alive_value) else alive_value)
        if not alive:
            continue
        limits.append(model_normal_move_limit(unit, model, game=game))
    if limits:
        return max(limits)
    return model_normal_move_limit(unit, None, game=game)


def movement_distance_profile(
    unit: object,
    model_positions: object,
    *,
    game: object | None = None,
) -> MovementDistanceProfile:
    if not isinstance(model_positions, list):
        return MovementDistanceProfile(entries=())
    starts = {
        str(entry.get("model_id", "") or ""): entry
        for entry in current_model_positions(unit)
        if str(entry.get("model_id", "") or "")
    }
    models_by_id = {
        str(get_entity_id(model) or ""): model
        for model in list(getattr(unit, "models", []) or [])
        if model is not None and str(get_entity_id(model) or "")
    }
    entries: list[ModelMovementDistance] = []
    for entry in list(model_positions or []):
        if not isinstance(entry, dict):
            continue
        model_id = str(entry.get("model_id", "") or "")
        start = starts.get(model_id)
        if start is None:
            continue
        start_pos = list(start.get("position", []) or [])
        end_pos = list(entry.get("position", []) or [])
        if len(start_pos) < 2 or len(end_pos) < 2:
            continue
        sx = movement_value_to_inches(start_pos[0], 0.0)
        sy = movement_value_to_inches(start_pos[1], 0.0)
        ex = movement_value_to_inches(end_pos[0], 0.0)
        ey = movement_value_to_inches(end_pos[1], 0.0)
        model = models_by_id.get(model_id)
        entries.append(
            ModelMovementDistance(
                model_id=model_id,
                distance=float(math.hypot(ex - sx, ey - sy)),
                normal_limit=model_normal_move_limit(unit, model, game=game),
            )
        )
    return MovementDistanceProfile(entries=tuple(entries))


def max_model_displacement(unit: object, model_positions: object) -> float:
    return movement_distance_profile(unit, model_positions).max_distance
