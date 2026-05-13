from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
from typing import Any, Mapping

from .decision_kinds import (
    DECISION_REACTIVE_MOVE,
    DECISION_SELECT_HEROIC_INTERVENTION_MODE,
    DECISION_SELECT_REACTIVE_RESERVE_EXIT,
    DECISION_SELECT_STRATAGEM_MODE,
    DECISION_SURGE_MOVE,
)
from .decisions import CandidateAction, DecisionRequest
from ..utility.entity_ids import maybe_entity_id


MOVE_KIND_NORMAL = "normal"
MOVE_KIND_SURGE = "surge"
MOVE_KIND_FALLBACK_LIKE = "fallback_like"
MOVE_KIND_RESERVE_EXIT = "reserve_exit"

DESTINATION_ANY_LEGAL_NORMAL_MOVE = "any_legal_normal_move"
DESTINATION_TOWARD_CLOSEST_ENEMY = "toward_closest_enemy"
DESTINATION_AWAY_FROM_REFERENCE = "away_from_reference"
DESTINATION_STRATEGIC_RESERVES = "strategic_reserves"

END_STATE_NORMAL_MOVE_END = "normal_move_end"
END_STATE_ATTEMPT_ENGAGED_WITH_CLOSEST_ENEMY = "attempt_engaged_with_closest_enemy"
END_STATE_FALLBACK_RESTRICTIONS = "fallback_restrictions"
END_STATE_STRATEGIC_RESERVES = "strategic_reserves"

_REACTIVE_MOVE_KINDS = {
    MOVE_KIND_NORMAL,
    MOVE_KIND_SURGE,
    MOVE_KIND_FALLBACK_LIKE,
    MOVE_KIND_RESERVE_EXIT,
}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_tuple(values: Any) -> tuple[str, ...]:
    return tuple(sorted(_clean_text(value) for value in list(values or []) if _clean_text(value)))


def _canonical(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value.keys(), key=lambda item: str(item))}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, set):
        return sorted((_canonical(item) for item in value), key=lambda item: str(item))
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _canonical(to_dict())
    entity_id = maybe_entity_id(value)
    if entity_id:
        return entity_id
    return str(value)


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    blob = json.dumps(_canonical(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}:{digest}"


@dataclass(frozen=True)
class ReactiveMoveSpec:
    spec_id: str
    trigger_window: str
    source_unit_id: str
    target_reference: Mapping[str, Any] = field(default_factory=dict)
    move_kind: str = MOVE_KIND_NORMAL
    max_distance_expr: str = ""
    destination_policy: str = DESTINATION_ANY_LEGAL_NORMAL_MOVE
    end_state_policy: str = END_STATE_NORMAL_MOVE_END
    enabled_by_profile: str = "11e_preview"
    source_provenance: tuple[str, ...] = field(default_factory=tuple)
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        spec_id = _clean_text(self.spec_id)
        if not spec_id:
            raise ValueError("ReactiveMoveSpec requires spec_id.")
        source_unit_id = _clean_text(self.source_unit_id)
        if not source_unit_id:
            raise ValueError("ReactiveMoveSpec requires source_unit_id.")
        move_kind = _clean_text(self.move_kind).lower()
        if move_kind not in _REACTIVE_MOVE_KINDS:
            raise ValueError(f"Unsupported reactive move kind: {self.move_kind}")
        object.__setattr__(self, "spec_id", spec_id)
        object.__setattr__(self, "trigger_window", _clean_text(self.trigger_window))
        object.__setattr__(self, "source_unit_id", source_unit_id)
        object.__setattr__(self, "target_reference", dict(self.target_reference or {}))
        object.__setattr__(self, "move_kind", move_kind)
        object.__setattr__(self, "max_distance_expr", _clean_text(self.max_distance_expr))
        object.__setattr__(self, "destination_policy", _clean_text(self.destination_policy))
        object.__setattr__(self, "end_state_policy", _clean_text(self.end_state_policy))
        object.__setattr__(self, "enabled_by_profile", _clean_text(self.enabled_by_profile) or "11e_preview")
        object.__setattr__(self, "source_provenance", _clean_tuple(self.source_provenance))
        object.__setattr__(self, "payload", dict(self.payload or {}))

    @property
    def decision_kind(self) -> str:
        if self.move_kind == MOVE_KIND_SURGE:
            return DECISION_SURGE_MOVE
        if self.move_kind == MOVE_KIND_RESERVE_EXIT:
            return DECISION_SELECT_REACTIVE_RESERVE_EXIT
        return DECISION_REACTIVE_MOVE

    def reason_trace(self) -> tuple[dict[str, str], ...]:
        return (
            {
                "reason": "reactive_move_spec",
                "spec_id": self.spec_id,
                "trigger_window": self.trigger_window,
                "move_kind": self.move_kind,
            },
            {
                "reason": "movement_policy",
                "max_distance_expr": self.max_distance_expr,
                "destination_policy": self.destination_policy,
                "end_state_policy": self.end_state_policy,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "trigger_window": self.trigger_window,
            "source_unit_id": self.source_unit_id,
            "target_reference": dict(self.target_reference or {}),
            "move_kind": self.move_kind,
            "max_distance_expr": self.max_distance_expr,
            "destination_policy": self.destination_policy,
            "end_state_policy": self.end_state_policy,
            "enabled_by_profile": self.enabled_by_profile,
            "source_provenance": list(self.source_provenance),
            "payload": dict(self.payload or {}),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ReactiveMoveSpec":
        return cls(
            spec_id=_clean_text(data.get("spec_id", "")),
            trigger_window=_clean_text(data.get("trigger_window", "")),
            source_unit_id=_clean_text(data.get("source_unit_id", "")),
            target_reference=dict(data.get("target_reference", {}) or {}),
            move_kind=_clean_text(data.get("move_kind", MOVE_KIND_NORMAL)),
            max_distance_expr=_clean_text(data.get("max_distance_expr", "")),
            destination_policy=_clean_text(data.get("destination_policy", DESTINATION_ANY_LEGAL_NORMAL_MOVE)),
            end_state_policy=_clean_text(data.get("end_state_policy", END_STATE_NORMAL_MOVE_END)),
            enabled_by_profile=_clean_text(data.get("enabled_by_profile", "11e_preview")),
            source_provenance=tuple(data.get("source_provenance", ()) or ()),
            payload=dict(data.get("payload", {}) or {}),
        )


@dataclass(frozen=True)
class StratagemMode:
    mode_id: str
    cp_delta: int = 0
    charge_target_policy: str = ""
    max_roll_cap: int | None = None
    display_name: str = ""
    enabled_by_profile: str = "11e_preview"
    source_provenance: tuple[str, ...] = field(default_factory=tuple)
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        mode_id = _clean_text(self.mode_id)
        if not mode_id:
            raise ValueError("StratagemMode requires mode_id.")
        cap = self.max_roll_cap
        if cap is not None:
            cap = int(cap)
            if cap < 0:
                raise ValueError("StratagemMode max_roll_cap cannot be negative.")
        object.__setattr__(self, "mode_id", mode_id)
        object.__setattr__(self, "cp_delta", int(self.cp_delta or 0))
        object.__setattr__(self, "charge_target_policy", _clean_text(self.charge_target_policy))
        object.__setattr__(self, "max_roll_cap", cap)
        object.__setattr__(self, "display_name", _clean_text(self.display_name) or mode_id.replace("_", " ").title())
        object.__setattr__(self, "enabled_by_profile", _clean_text(self.enabled_by_profile) or "11e_preview")
        object.__setattr__(self, "source_provenance", _clean_tuple(self.source_provenance))
        object.__setattr__(self, "payload", dict(self.payload or {}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode_id": self.mode_id,
            "display_name": self.display_name,
            "cp_delta": self.cp_delta,
            "charge_target_policy": self.charge_target_policy,
            "max_roll_cap": self.max_roll_cap,
            "enabled_by_profile": self.enabled_by_profile,
            "source_provenance": list(self.source_provenance),
            "payload": dict(self.payload or {}),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StratagemMode":
        return cls(
            mode_id=_clean_text(data.get("mode_id", "")),
            display_name=_clean_text(data.get("display_name", "")),
            cp_delta=int(data.get("cp_delta", 0) or 0),
            charge_target_policy=_clean_text(data.get("charge_target_policy", "")),
            max_roll_cap=data.get("max_roll_cap", None),
            enabled_by_profile=_clean_text(data.get("enabled_by_profile", "11e_preview")),
            source_provenance=tuple(data.get("source_provenance", ()) or ()),
            payload=dict(data.get("payload", {}) or {}),
        )


@dataclass(frozen=True)
class ReactiveReserveExitTransition:
    transition_id: str
    unit_id: str
    from_reserve_status: str
    to_reserve_status: str
    transition_kind: str
    spec_id: str
    reason_trace: tuple[dict[str, str], ...]
    applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "unit_id": self.unit_id,
            "from_reserve_status": self.from_reserve_status,
            "to_reserve_status": self.to_reserve_status,
            "transition_kind": self.transition_kind,
            "spec_id": self.spec_id,
            "reason_trace": [dict(item) for item in self.reason_trace],
            "applied": bool(self.applied),
        }


def build_reactive_move_request(
    *,
    player_id: str,
    spec: ReactiveMoveSpec,
    active_player_id: str | None = None,
    prompt: str | None = None,
    allow_skip: bool = True,
) -> DecisionRequest:
    spec_payload = spec.to_dict()
    context = {
        "reactive_move_spec": spec_payload,
        "reactive_move_kind": spec.move_kind,
        "reactive_move_unit_id": spec.source_unit_id,
        "unit_id": spec.source_unit_id,
        "trigger_window": spec.trigger_window,
        "target_reference": dict(spec.target_reference or {}),
        "movement_type": "reactive",
        "destination_policy": spec.destination_policy,
        "end_state_policy": spec.end_state_policy,
        "max_distance_expr": spec.max_distance_expr,
        "enabled_by_profile": spec.enabled_by_profile,
        "preview_gated": spec.enabled_by_profile != "current",
        "reason_trace": [dict(item) for item in spec.reason_trace()],
    }
    if active_player_id:
        context["active_player_id"] = _clean_text(active_player_id)
        context["opponent_turn"] = _clean_text(active_player_id) != _clean_text(player_id)
    candidates = [
        CandidateAction(
            action_id=_stable_id(
                spec.decision_kind,
                {"spec_id": spec.spec_id, "unit_id": spec.source_unit_id, "action": "move"},
            ),
            params={
                "action": "move",
                "unit_id": spec.source_unit_id,
                "reactive_move_spec_id": spec.spec_id,
                "move_kind": spec.move_kind,
            },
            metadata={
                "candidate_kind": "reactive_move",
                "destination_policy": spec.destination_policy,
                "end_state_policy": spec.end_state_policy,
            },
        )
    ]
    if allow_skip:
        candidates.append(
            CandidateAction(
                action_id=_stable_id(
                    spec.decision_kind,
                    {"spec_id": spec.spec_id, "unit_id": spec.source_unit_id, "action": "skip"},
                ),
                params={
                    "action": "skip",
                    "unit_id": spec.source_unit_id,
                    "reactive_move_spec_id": spec.spec_id,
                },
                metadata={"candidate_kind": "noop"},
            )
        )
    return DecisionRequest.create(
        spec.decision_kind,
        prompt or f"Resolve reactive move for {spec.source_unit_id}",
        player_id=player_id,
        candidates=tuple(candidates),
        mask=[True] * len(candidates),
        context=context,
    )


def build_stratagem_mode_request(
    *,
    player_id: str,
    stratagem_name: str,
    modes: tuple[StratagemMode, ...],
    source_unit_id: str | None = None,
    target_unit_id: str | None = None,
    decision_kind: str = DECISION_SELECT_STRATAGEM_MODE,
    prompt: str | None = None,
) -> DecisionRequest:
    ordered_modes = tuple(sorted(modes, key=lambda mode: mode.mode_id))
    if not ordered_modes:
        raise ValueError("A stratagem mode request requires at least one mode.")
    stratagem_label = _clean_text(stratagem_name)
    if not stratagem_label:
        raise ValueError("A stratagem mode request requires stratagem_name.")
    context = {
        "stratagem_name": stratagem_label,
        "stratagem_modes": [mode.to_dict() for mode in ordered_modes],
        "selection_kind": "stratagem_mode",
        "preview_gated": any(mode.enabled_by_profile != "current" for mode in ordered_modes),
    }
    if source_unit_id:
        context["source_unit_id"] = _clean_text(source_unit_id)
    if target_unit_id:
        context["target_unit_id"] = _clean_text(target_unit_id)
    candidates = []
    for mode in ordered_modes:
        params = {
            "mode_id": mode.mode_id,
            "stratagem_name": stratagem_label,
            "cp_delta": mode.cp_delta,
            "charge_target_policy": mode.charge_target_policy,
            "max_roll_cap": mode.max_roll_cap,
        }
        if source_unit_id:
            params["source_unit_id"] = _clean_text(source_unit_id)
        if target_unit_id:
            params["target_unit_id"] = _clean_text(target_unit_id)
        candidates.append(
            CandidateAction(
                action_id=_stable_id(decision_kind, params),
                params=params,
                metadata={
                    "label": mode.display_name,
                    "candidate_kind": "stratagem_mode",
                    "mode": mode.to_dict(),
                },
            )
        )
    return DecisionRequest.create(
        decision_kind,
        prompt or f"Select mode for {stratagem_label}",
        player_id=player_id,
        candidates=tuple(candidates),
        mask=[True] * len(candidates),
        context=context,
    )


def build_heroic_intervention_mode_request(
    *,
    player_id: str,
    stratagem_name: str,
    modes: tuple[StratagemMode, ...],
    source_unit_id: str | None = None,
    target_unit_id: str | None = None,
    prompt: str | None = None,
) -> DecisionRequest:
    request = build_stratagem_mode_request(
        player_id=player_id,
        stratagem_name=stratagem_name,
        modes=modes,
        source_unit_id=source_unit_id,
        target_unit_id=target_unit_id,
        decision_kind=DECISION_SELECT_HEROIC_INTERVENTION_MODE,
        prompt=prompt or f"Select Heroic Intervention mode for {stratagem_name}",
    )
    request.context["selection_kind"] = "heroic_intervention_mode"
    return request


def build_reactive_reserve_exit_transition(
    unit: object,
    spec: ReactiveMoveSpec,
    *,
    applied: bool = False,
) -> ReactiveReserveExitTransition:
    unit_id = _clean_text(maybe_entity_id(unit) or getattr(unit, "id", "") or getattr(unit, "name", ""))
    if not unit_id:
        raise ValueError("Reactive reserve exit transition requires a unit id.")
    from_status = _clean_text(getattr(unit, "reserve_status", "deployed")) or "deployed"
    payload = {
        "unit_id": unit_id,
        "from_reserve_status": from_status,
        "to_reserve_status": "strategic_reserves",
        "transition_kind": "reactive_reserve_exit",
        "spec_id": spec.spec_id,
    }
    reason_trace = (
        *spec.reason_trace(),
        {
            "reason": "reactive_reserve_transition",
            "from_reserve_status": from_status,
            "to_reserve_status": "strategic_reserves",
        },
    )
    return ReactiveReserveExitTransition(
        transition_id=_stable_id("reactive_reserve_exit", payload),
        unit_id=unit_id,
        from_reserve_status=from_status,
        to_reserve_status="strategic_reserves",
        transition_kind="reactive_reserve_exit",
        spec_id=spec.spec_id,
        reason_trace=reason_trace,
        applied=applied,
    )


def apply_reactive_reserve_exit_transition(
    unit: object,
    spec: ReactiveMoveSpec,
    *,
    game: object | None = None,
    game_map: object | None = None,
) -> ReactiveReserveExitTransition:
    transition = build_reactive_reserve_exit_transition(unit, spec, applied=False)
    place_fn = getattr(unit, "enter_strategic_reserves_midgame", None)
    if callable(place_fn):
        applied = bool(place_fn(game=game, game_map=game_map, reason=spec.spec_id))
        return replace(transition, applied=applied)

    set_status = getattr(unit, "set_reserve_status", None)
    if callable(set_status):
        set_status("strategic_reserves")
    else:
        setattr(unit, "reserve_status", "strategic_reserves")
    setattr(unit, "deployed", True)
    setattr(unit, "arrived_from_reserves_this_turn", False)
    if game_map is not None and hasattr(game_map, "units") and unit in list(getattr(game_map, "units", []) or []):
        game_map.units.remove(unit)
    return replace(transition, applied=True)
