from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import Any, Mapping

from ..battlefield.hidden_state import hidden_preserving_exemption_ids_for_unit
from ..utility.entity_ids import maybe_entity_id


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clean_strings(values: object) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values.strip(),) if values.strip() else ()
    return tuple(sorted(str(value).strip() for value in list(values or []) if str(value).strip()))


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(inner) for key, inner in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(inner) for inner in value]
    if isinstance(value, set):
        return sorted((_json_safe(inner) for inner in value), key=lambda item: str(item))
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _json_safe(to_dict())
    return str(value)


def _object_bool(source: object, field_name: str) -> bool:
    if isinstance(source, Mapping):
        return bool(source.get(field_name, False))
    return bool(getattr(source, field_name, False))


def _object_float(source: object, field_name: str, default: float = 0.0) -> float:
    value = source.get(field_name, default) if isinstance(source, Mapping) else getattr(source, field_name, default)
    return _safe_float(value, default)


def _unit_id(unit: object | None) -> str:
    if unit is None:
        return ""
    return str(maybe_entity_id(unit) or "")


def _battle_round(game: object | None, fallback: int = 0) -> int:
    if game is None:
        return int(fallback)
    getter = getattr(game, "get_battle_round", None)
    if callable(getter):
        return _safe_int(getter(), fallback)
    return _safe_int(getattr(game, "turn", fallback), fallback)


def _current_player_id(game: object | None) -> str:
    if game is None:
        return ""
    getter = getattr(game, "get_current_player", None)
    player = getter() if callable(getter) else None
    if player is None:
        players = list(getattr(game, "players", []) or [])
        idx = _safe_int(getattr(game, "current_player_index", 0), 0)
        if 0 <= idx < len(players):
            player = players[idx]
    return str(getattr(player, "id", "") or "")


def default_player_turn_id(game: object | None, battle_round: int | None = None) -> str:
    round_value = _safe_int(battle_round, _battle_round(game, 0))
    player_id = _current_player_id(game)
    if round_value <= 0 and not player_id:
        return ""
    return f"battle_round:{round_value}:player:{player_id}"


def _path_distance(path: object) -> float:
    points = list(path or [])
    if len(points) < 2:
        return 0.0
    total = 0.0
    previous = points[0]
    for current in points[1:]:
        if not isinstance(previous, (list, tuple)) or not isinstance(current, (list, tuple)):
            previous = current
            continue
        if len(previous) < 2 or len(current) < 2:
            previous = current
            continue
        z_prev = _safe_float(previous[2], 0.0) if len(previous) > 2 else 0.0
        z_cur = _safe_float(current[2], 0.0) if len(current) > 2 else 0.0
        dx = _safe_float(current[0], 0.0) - _safe_float(previous[0], 0.0)
        dy = _safe_float(current[1], 0.0) - _safe_float(previous[1], 0.0)
        dz = z_cur - z_prev
        total += sqrt((dx * dx) + (dy * dy) + (dz * dz))
        previous = current
    return float(total)


def max_model_move_distance_from_paths(unit: object | None) -> float:
    if unit is None:
        return 0.0
    best = 0.0
    for model in list(getattr(unit, "models", []) or []) + list(getattr(unit, "models_lost", []) or []):
        best = max(best, _path_distance(getattr(model, "last_move_path", []) or []))
    return float(best)


@dataclass(frozen=True)
class UnitTurnProvenance:
    unit_id: str
    battle_round: int
    player_turn_id: str
    set_up_this_turn: bool = False
    arrived_from_reserves_this_turn: bool = False
    made_normal_move: bool = False
    made_advance_move: bool = False
    made_fall_back_move: bool = False
    made_disembark_move: bool = False
    made_charge_move: bool = False
    shot_this_turn: bool = False
    shot_previous_player_turn: bool = False
    max_model_move_distance_this_turn: float = 0.0
    hidden_shooting_exemptions: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        unit_id = _clean_text(self.unit_id)
        if not unit_id:
            raise ValueError("UnitTurnProvenance.unit_id is required.")
        object.__setattr__(self, "unit_id", unit_id)
        object.__setattr__(self, "battle_round", _safe_int(self.battle_round, 0))
        object.__setattr__(self, "player_turn_id", _clean_text(self.player_turn_id))
        object.__setattr__(self, "set_up_this_turn", bool(self.set_up_this_turn))
        object.__setattr__(self, "arrived_from_reserves_this_turn", bool(self.arrived_from_reserves_this_turn))
        object.__setattr__(self, "made_normal_move", bool(self.made_normal_move))
        object.__setattr__(self, "made_advance_move", bool(self.made_advance_move))
        object.__setattr__(self, "made_fall_back_move", bool(self.made_fall_back_move))
        object.__setattr__(self, "made_disembark_move", bool(self.made_disembark_move))
        object.__setattr__(self, "made_charge_move", bool(self.made_charge_move))
        object.__setattr__(self, "shot_this_turn", bool(self.shot_this_turn))
        object.__setattr__(self, "shot_previous_player_turn", bool(self.shot_previous_player_turn))
        object.__setattr__(
            self,
            "max_model_move_distance_this_turn",
            _safe_float(self.max_model_move_distance_this_turn, 0.0),
        )
        object.__setattr__(self, "hidden_shooting_exemptions", _clean_strings(self.hidden_shooting_exemptions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "battle_round": int(self.battle_round),
            "player_turn_id": self.player_turn_id,
            "set_up_this_turn": bool(self.set_up_this_turn),
            "arrived_from_reserves_this_turn": bool(self.arrived_from_reserves_this_turn),
            "made_normal_move": bool(self.made_normal_move),
            "made_advance_move": bool(self.made_advance_move),
            "made_fall_back_move": bool(self.made_fall_back_move),
            "made_disembark_move": bool(self.made_disembark_move),
            "made_charge_move": bool(self.made_charge_move),
            "shot_this_turn": bool(self.shot_this_turn),
            "shot_previous_player_turn": bool(self.shot_previous_player_turn),
            "max_model_move_distance_this_turn": float(self.max_model_move_distance_this_turn),
            "hidden_shooting_exemptions": list(self.hidden_shooting_exemptions),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "UnitTurnProvenance":
        return cls(
            unit_id=str(data.get("unit_id", "") or ""),
            battle_round=_safe_int(data.get("battle_round", 0), 0),
            player_turn_id=str(data.get("player_turn_id", "") or ""),
            set_up_this_turn=bool(data.get("set_up_this_turn", False)),
            arrived_from_reserves_this_turn=bool(data.get("arrived_from_reserves_this_turn", False)),
            made_normal_move=bool(data.get("made_normal_move", False)),
            made_advance_move=bool(data.get("made_advance_move", False)),
            made_fall_back_move=bool(data.get("made_fall_back_move", False)),
            made_disembark_move=bool(data.get("made_disembark_move", False)),
            made_charge_move=bool(data.get("made_charge_move", False)),
            shot_this_turn=bool(data.get("shot_this_turn", False)),
            shot_previous_player_turn=bool(data.get("shot_previous_player_turn", False)),
            max_model_move_distance_this_turn=_safe_float(data.get("max_model_move_distance_this_turn", 0.0), 0.0),
            hidden_shooting_exemptions=_clean_strings(data.get("hidden_shooting_exemptions", ())),
        )


@dataclass(frozen=True)
class PhaseBoundary:
    phase: str
    battle_round: int | None = None
    player_turn_id: str = ""
    boundary: str = "end"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "phase_boundary",
            "phase": _clean_text(self.phase),
            "battle_round": None if self.battle_round is None else _safe_int(self.battle_round, 0),
            "player_turn_id": _clean_text(self.player_turn_id),
            "boundary": _clean_text(self.boundary) or "end",
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PhaseBoundary":
        raw_round = data.get("battle_round", None)
        return cls(
            phase=str(data.get("phase", "") or ""),
            battle_round=None if raw_round is None else _safe_int(raw_round, 0),
            player_turn_id=str(data.get("player_turn_id", "") or ""),
            boundary=str(data.get("boundary", "") or "end"),
        )


@dataclass(frozen=True)
class TurnBoundary:
    battle_round: int | None = None
    player_turn_id: str = ""
    boundary: str = "end"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "turn_boundary",
            "battle_round": None if self.battle_round is None else _safe_int(self.battle_round, 0),
            "player_turn_id": _clean_text(self.player_turn_id),
            "boundary": _clean_text(self.boundary) or "end",
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TurnBoundary":
        raw_round = data.get("battle_round", None)
        return cls(
            battle_round=None if raw_round is None else _safe_int(raw_round, 0),
            player_turn_id=str(data.get("player_turn_id", "") or ""),
            boundary=str(data.get("boundary", "") or "end"),
        )


@dataclass(frozen=True)
class Manual:
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "manual", "reason": _clean_text(self.reason)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Manual":
        return cls(reason=str(data.get("reason", "") or ""))


TokenExpiry = PhaseBoundary | TurnBoundary | Manual


def token_expiry_from_dict(data: Mapping[str, Any] | str | None) -> TokenExpiry:
    if data is None:
        return Manual()
    if isinstance(data, str):
        return Manual(reason=data)
    kind = str(data.get("kind", "") or "").strip().lower()
    if kind == "phase_boundary":
        return PhaseBoundary.from_dict(data)
    if kind == "turn_boundary":
        return TurnBoundary.from_dict(data)
    if kind in {"manual", ""}:
        return Manual.from_dict(data)
    raise ValueError(f"Unknown status token expiry kind: {kind!r}.")


@dataclass(frozen=True)
class StatusToken:
    token_id: str
    unit_id: str
    source_id: str
    condition_kind: str
    expires_at: TokenExpiry = field(default_factory=Manual)
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        token_id = _clean_text(self.token_id)
        unit_id = _clean_text(self.unit_id)
        condition_kind = _clean_text(self.condition_kind)
        if not token_id:
            raise ValueError("StatusToken.token_id is required.")
        if not unit_id:
            raise ValueError("StatusToken.unit_id is required.")
        if not condition_kind:
            raise ValueError("StatusToken.condition_kind is required.")
        expiry = self.expires_at
        if isinstance(expiry, Mapping) or isinstance(expiry, str) or expiry is None:
            expiry = token_expiry_from_dict(expiry)
        if not isinstance(expiry, (PhaseBoundary, TurnBoundary, Manual)):
            raise TypeError("StatusToken.expires_at must be PhaseBoundary, TurnBoundary, or Manual.")
        object.__setattr__(self, "token_id", token_id)
        object.__setattr__(self, "unit_id", unit_id)
        object.__setattr__(self, "source_id", _clean_text(self.source_id))
        object.__setattr__(self, "condition_kind", condition_kind)
        object.__setattr__(self, "expires_at", expiry)
        object.__setattr__(self, "payload", _json_safe(dict(self.payload or {})))

    def to_dict(self) -> dict[str, Any]:
        return {
            "token_id": self.token_id,
            "unit_id": self.unit_id,
            "source_id": self.source_id,
            "condition_kind": self.condition_kind,
            "expires_at": self.expires_at.to_dict(),
            "payload": _json_safe(dict(self.payload or {})),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StatusToken":
        return cls(
            token_id=str(data.get("token_id", "") or ""),
            unit_id=str(data.get("unit_id", "") or ""),
            source_id=str(data.get("source_id", "") or ""),
            condition_kind=str(data.get("condition_kind", "") or ""),
            expires_at=token_expiry_from_dict(data.get("expires_at", {})),
            payload=dict(data.get("payload", {}) or {}),
        )


UnitCondition = StatusToken


def status_token_from_condition(
    *,
    token_id: str,
    unit_id: str,
    source_id: str,
    condition_kind: str,
    expires_at: TokenExpiry | Mapping[str, Any] | str | None,
    payload: Mapping[str, Any] | None = None,
) -> StatusToken:
    return StatusToken(
        token_id=token_id,
        unit_id=unit_id,
        source_id=source_id,
        condition_kind=condition_kind,
        expires_at=expires_at,
        payload=dict(payload or {}),
    )


def battle_shock_status_token(
    *,
    unit_id: str,
    source_id: str,
    battle_round: int,
    player_turn_id: str,
) -> StatusToken:
    return StatusToken(
        token_id=f"status:battle_shock:{unit_id}:{battle_round}:{player_turn_id}",
        unit_id=unit_id,
        source_id=source_id,
        condition_kind="battle_shock",
        expires_at=Manual(reason="clear_after_successful_command_phase_leadership_test"),
        payload={
            "battle_round": int(battle_round),
            "player_turn_id": str(player_turn_id or ""),
            "requires_command_phase_leadership_test_to_clear": True,
        },
    )


def set_up_this_turn_modifier_token(
    *,
    unit_id: str,
    source_id: str,
    modifier_id: str,
    battle_round: int,
    player_turn_id: str,
    payload: Mapping[str, Any] | None = None,
) -> StatusToken:
    token_payload = {
        "modifier_id": str(modifier_id or ""),
        "battle_round": int(battle_round),
        "player_turn_id": str(player_turn_id or ""),
        "requires_set_up_this_turn": True,
    }
    token_payload.update(dict(payload or {}))
    return StatusToken(
        token_id=f"status:set_up_this_turn_modifier:{unit_id}:{modifier_id}:{battle_round}:{player_turn_id}",
        unit_id=unit_id,
        source_id=source_id,
        condition_kind="set_up_this_turn_modifier",
        expires_at=TurnBoundary(battle_round=int(battle_round), player_turn_id=str(player_turn_id or ""), boundary="end"),
        payload=token_payload,
    )


def fights_first_status_token(
    *,
    unit_id: str,
    source_id: str,
    expires_at: TokenExpiry | Mapping[str, Any] | str | None,
    payload: Mapping[str, Any] | None = None,
) -> StatusToken:
    return StatusToken(
        token_id=f"status:fights_first:{unit_id}:{source_id}",
        unit_id=unit_id,
        source_id=source_id,
        condition_kind="fights_first",
        expires_at=expires_at,
        payload=dict(payload or {}),
    )


def must_fight_next_status_token(
    *,
    unit_id: str,
    source_id: str,
    expires_at: TokenExpiry | Mapping[str, Any] | str | None,
    payload: Mapping[str, Any] | None = None,
) -> StatusToken:
    return StatusToken(
        token_id=f"status:must_fight_next:{unit_id}:{source_id}",
        unit_id=unit_id,
        source_id=source_id,
        condition_kind="must_fight_next",
        expires_at=expires_at,
        payload=dict(payload or {}),
    )


def temporary_attack_modifier_status_token(
    *,
    unit_id: str,
    source_id: str,
    modifier_id: str,
    expires_at: TokenExpiry | Mapping[str, Any] | str | None,
    payload: Mapping[str, Any] | None = None,
) -> StatusToken:
    token_payload = {"modifier_id": str(modifier_id or "")}
    token_payload.update(dict(payload or {}))
    return StatusToken(
        token_id=f"status:temporary_attack_modifier:{unit_id}:{modifier_id}:{source_id}",
        unit_id=unit_id,
        source_id=source_id,
        condition_kind="temporary_attack_modifier",
        expires_at=expires_at,
        payload=token_payload,
    )


def derive_unit_turn_provenance(
    unit: object,
    *,
    game: object | None = None,
    battle_round: int | None = None,
    player_turn_id: str | None = None,
    game_map: object | None = None,
) -> UnitTurnProvenance:
    unit_id = _unit_id(unit)
    if not unit_id:
        raise ValueError("Cannot derive UnitTurnProvenance for a unit without an id.")
    round_value = _safe_int(battle_round, _battle_round(game, 0))
    turn_id = _clean_text(player_turn_id) or default_player_turn_id(game, round_value)
    round_state = getattr(unit, "round_state", None)
    set_up_this_turn = bool(
        getattr(unit, "set_up_this_turn", False)
        or getattr(unit, "arrived_from_reserves_this_turn", False)
        or _object_bool(round_state, "reinforced_this_round")
    )
    arrived_from_reserves = bool(
        getattr(unit, "arrived_from_reserves_this_turn", False)
        or _object_bool(round_state, "reinforced_this_round")
    )
    advanced = _object_bool(round_state, "advanced_this_round")
    fell_back = _object_bool(round_state, "fell_back_this_round")
    moved = _object_bool(round_state, "moved_this_round")
    made_normal = bool(getattr(unit, "made_normal_move_this_turn", False) or (moved and not advanced and not fell_back))
    explicit_max_move = _object_float(round_state, "max_model_move_distance_this_turn", -1.0)
    if explicit_max_move < 0.0:
        explicit_max_move = _object_float(unit, "max_model_move_distance_this_turn", -1.0)
    max_model_move = explicit_max_move if explicit_max_move >= 0.0 else max_model_move_distance_from_paths(unit)
    map_for_hidden = game_map if game_map is not None else getattr(game, "map", None)
    hidden_exemptions = hidden_preserving_exemption_ids_for_unit(map_for_hidden, unit) if map_for_hidden is not None else ()
    hidden_exemptions = hidden_exemptions or _clean_strings(getattr(unit, "hidden_shooting_exemptions", ()))
    return UnitTurnProvenance(
        unit_id=unit_id,
        battle_round=round_value,
        player_turn_id=turn_id,
        set_up_this_turn=set_up_this_turn,
        arrived_from_reserves_this_turn=arrived_from_reserves,
        made_normal_move=made_normal,
        made_advance_move=advanced,
        made_fall_back_move=fell_back,
        made_disembark_move=_object_bool(round_state, "disembarked_this_round"),
        made_charge_move=_object_bool(round_state, "charged_this_round"),
        shot_this_turn=_object_bool(round_state, "shot_this_round"),
        shot_previous_player_turn=bool(getattr(unit, "shot_previous_player_turn", False)),
        max_model_move_distance_this_turn=max_model_move,
        hidden_shooting_exemptions=hidden_exemptions,
    )


def unit_turn_provenance_on_unit(
    unit: object,
    *,
    game: object | None = None,
    battle_round: int | None = None,
    player_turn_id: str | None = None,
    game_map: object | None = None,
) -> UnitTurnProvenance:
    existing = getattr(unit, "unit_turn_provenance", None)
    if isinstance(existing, UnitTurnProvenance):
        return existing
    if isinstance(existing, Mapping):
        return UnitTurnProvenance.from_dict(existing)
    return derive_unit_turn_provenance(
        unit,
        game=game,
        battle_round=battle_round,
        player_turn_id=player_turn_id,
        game_map=game_map,
    )


def set_unit_turn_provenance(unit: object, provenance: UnitTurnProvenance | Mapping[str, Any]) -> UnitTurnProvenance:
    provenance_obj = provenance if isinstance(provenance, UnitTurnProvenance) else UnitTurnProvenance.from_dict(provenance)
    setattr(unit, "unit_turn_provenance", provenance_obj)
    return provenance_obj


def hidden_clears_from_provenance(provenance: UnitTurnProvenance | Mapping[str, Any]) -> bool:
    provenance_obj = provenance if isinstance(provenance, UnitTurnProvenance) else UnitTurnProvenance.from_dict(provenance)
    if not (provenance_obj.shot_this_turn or provenance_obj.shot_previous_player_turn):
        return False
    return not bool(provenance_obj.hidden_shooting_exemptions)


def status_tokens_on_unit(unit: object | None) -> tuple[StatusToken, ...]:
    if unit is None:
        return ()
    tokens: list[StatusToken] = []
    for token in list(getattr(unit, "status_tokens", []) or []):
        if isinstance(token, StatusToken):
            tokens.append(token)
        elif isinstance(token, Mapping):
            tokens.append(StatusToken.from_dict(token))
    return tuple(sorted(tokens, key=lambda item: (item.unit_id, item.condition_kind, item.token_id)))


def set_status_tokens_on_unit(unit: object, tokens: object) -> tuple[StatusToken, ...]:
    normalized: list[StatusToken] = []
    for token in list(tokens or []):
        if isinstance(token, StatusToken):
            normalized.append(token)
        elif isinstance(token, Mapping):
            normalized.append(StatusToken.from_dict(token))
        else:
            raise TypeError(f"Unsupported status token type: {type(token).__name__}")
    normalized.sort(key=lambda item: (item.unit_id, item.condition_kind, item.token_id))
    setattr(unit, "status_tokens", tuple(normalized))
    return tuple(normalized)


def add_status_token_to_unit(unit: object, token: StatusToken | Mapping[str, Any]) -> StatusToken:
    token_obj = token if isinstance(token, StatusToken) else StatusToken.from_dict(token)
    existing = [item for item in status_tokens_on_unit(unit) if item.token_id != token_obj.token_id]
    existing.append(token_obj)
    set_status_tokens_on_unit(unit, existing)
    return token_obj


def status_token_dicts_on_unit(unit: object | None) -> list[dict[str, Any]]:
    return [token.to_dict() for token in status_tokens_on_unit(unit)]


def unit_has_status_token_kind(unit: object | None, condition_kind: str) -> bool:
    kind = _clean_text(condition_kind)
    return any(token.condition_kind == kind for token in status_tokens_on_unit(unit))


__all__ = [
    "Manual",
    "PhaseBoundary",
    "StatusToken",
    "TokenExpiry",
    "TurnBoundary",
    "UnitCondition",
    "UnitTurnProvenance",
    "add_status_token_to_unit",
    "battle_shock_status_token",
    "default_player_turn_id",
    "derive_unit_turn_provenance",
    "fights_first_status_token",
    "hidden_clears_from_provenance",
    "max_model_move_distance_from_paths",
    "must_fight_next_status_token",
    "set_status_tokens_on_unit",
    "set_unit_turn_provenance",
    "set_up_this_turn_modifier_token",
    "status_token_dicts_on_unit",
    "status_token_from_condition",
    "status_tokens_on_unit",
    "temporary_attack_modifier_status_token",
    "token_expiry_from_dict",
    "unit_has_status_token_kind",
    "unit_turn_provenance_on_unit",
]
