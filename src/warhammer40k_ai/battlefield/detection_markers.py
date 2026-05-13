from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ..utility.entity_ids import maybe_entity_id


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _clean_sources(values: object) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values.strip(),) if values.strip() else ()
    return tuple(sorted(str(value).strip() for value in list(values or []) if str(value).strip()))


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Expected numeric detection range override, got {value!r}.") from None


def _cache_tuple(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple((str(key), _cache_tuple(inner)) for key, inner in sorted(value.items(), key=lambda item: str(item[0])))
    if isinstance(value, (list, tuple)):
        return tuple(_cache_tuple(inner) for inner in value)
    if isinstance(value, set):
        return tuple(sorted(_cache_tuple(inner) for inner in value))
    return value


@dataclass(frozen=True)
class DetectionMarker:
    marker_id: str
    source_unit_id: str
    target_unit_id: str
    detection_range_delta: float
    duration: str
    source_detachment_id: str = ""
    enabled_by_profile: str = "11e_preview"
    source_provenance: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        marker_id = _clean_text(self.marker_id)
        source_unit_id = _clean_text(self.source_unit_id)
        target_unit_id = _clean_text(self.target_unit_id)
        if not marker_id:
            raise ValueError("DetectionMarker.marker_id is required.")
        if not target_unit_id:
            raise ValueError("DetectionMarker.target_unit_id is required.")
        object.__setattr__(self, "marker_id", marker_id)
        object.__setattr__(self, "source_unit_id", source_unit_id)
        object.__setattr__(self, "target_unit_id", target_unit_id)
        object.__setattr__(self, "detection_range_delta", _safe_float(self.detection_range_delta))
        object.__setattr__(self, "duration", _clean_text(self.duration))
        object.__setattr__(self, "source_detachment_id", _clean_text(self.source_detachment_id))
        object.__setattr__(self, "enabled_by_profile", _clean_text(self.enabled_by_profile) or "11e_preview")
        object.__setattr__(self, "source_provenance", _clean_sources(self.source_provenance))

    def applies_to(self, *, target_unit_id: str) -> bool:
        return self.target_unit_id == _clean_text(target_unit_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "marker_id": self.marker_id,
            "source_unit_id": self.source_unit_id,
            "target_unit_id": self.target_unit_id,
            "detection_range_delta": float(self.detection_range_delta),
            "duration": self.duration,
            "source_detachment_id": self.source_detachment_id,
            "enabled_by_profile": self.enabled_by_profile,
            "source_provenance": list(self.source_provenance),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DetectionMarker":
        return cls(
            marker_id=str(data.get("marker_id", "") or ""),
            source_unit_id=str(data.get("source_unit_id", "") or ""),
            target_unit_id=str(data.get("target_unit_id", "") or ""),
            detection_range_delta=_safe_float(data.get("detection_range_delta", 0.0)),
            duration=str(data.get("duration", "") or ""),
            source_detachment_id=str(data.get("source_detachment_id", "") or ""),
            enabled_by_profile=str(data.get("enabled_by_profile", "") or "11e_preview"),
            source_provenance=_clean_sources(data.get("source_provenance", ())),
        )


@dataclass(frozen=True)
class VisibilityRangeModifier:
    modifier_id: str
    detection_range_delta: float = 0.0
    fixed_detection_range: float | None = None
    source_unit_id: str = ""
    target_unit_id: str = ""
    active_unit_id: str = ""
    scope: str = "attack"
    source_provenance: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        modifier_id = _clean_text(self.modifier_id)
        if not modifier_id:
            raise ValueError("VisibilityRangeModifier.modifier_id is required.")
        object.__setattr__(self, "modifier_id", modifier_id)
        object.__setattr__(self, "detection_range_delta", _safe_float(self.detection_range_delta))
        object.__setattr__(self, "fixed_detection_range", _optional_float(self.fixed_detection_range))
        object.__setattr__(self, "source_unit_id", _clean_text(self.source_unit_id))
        object.__setattr__(self, "target_unit_id", _clean_text(self.target_unit_id))
        object.__setattr__(self, "active_unit_id", _clean_text(self.active_unit_id))
        object.__setattr__(self, "scope", _clean_text(self.scope).lower() or "attack")
        object.__setattr__(self, "source_provenance", _clean_sources(self.source_provenance))

    def applies_to(
        self,
        *,
        source_unit_id: str,
        target_unit_id: str,
        active_shooting_unit_id: str,
    ) -> bool:
        source_unit_id = _clean_text(source_unit_id)
        target_unit_id = _clean_text(target_unit_id)
        active_shooting_unit_id = _clean_text(active_shooting_unit_id)
        if self.source_unit_id and self.source_unit_id != source_unit_id:
            return False
        if self.target_unit_id and self.target_unit_id != target_unit_id:
            return False
        if self.scope in {"while_shooting", "attack", "attack_scoped"}:
            expected_active = self.active_unit_id or self.source_unit_id
            if not active_shooting_unit_id:
                return False
            if expected_active and expected_active != active_shooting_unit_id:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "modifier_id": self.modifier_id,
            "detection_range_delta": float(self.detection_range_delta),
            "fixed_detection_range": self.fixed_detection_range,
            "source_unit_id": self.source_unit_id,
            "target_unit_id": self.target_unit_id,
            "active_unit_id": self.active_unit_id,
            "scope": self.scope,
            "source_provenance": list(self.source_provenance),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "VisibilityRangeModifier":
        return cls(
            modifier_id=str(data.get("modifier_id", "") or ""),
            detection_range_delta=_safe_float(data.get("detection_range_delta", 0.0)),
            fixed_detection_range=data.get("fixed_detection_range", None),
            source_unit_id=str(data.get("source_unit_id", "") or ""),
            target_unit_id=str(data.get("target_unit_id", "") or ""),
            active_unit_id=str(data.get("active_unit_id", "") or ""),
            scope=str(data.get("scope", "") or "attack"),
            source_provenance=_clean_sources(data.get("source_provenance", ())),
        )


@dataclass(frozen=True)
class VisibilityModifierQuery:
    source_unit_id: str
    target_unit_id: str
    base_detection_range: float | None = None
    active_shooting_unit_id: str = ""
    attack_context_id: str = ""
    attack_scoped_modifiers: tuple[VisibilityRangeModifier, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_unit_id", _clean_text(self.source_unit_id))
        object.__setattr__(self, "target_unit_id", _clean_text(self.target_unit_id))
        object.__setattr__(self, "base_detection_range", _optional_float(self.base_detection_range))
        object.__setattr__(self, "active_shooting_unit_id", _clean_text(self.active_shooting_unit_id))
        object.__setattr__(self, "attack_context_id", _clean_text(self.attack_context_id))
        modifiers = tuple(
            modifier if isinstance(modifier, VisibilityRangeModifier) else VisibilityRangeModifier.from_dict(modifier)
            for modifier in tuple(self.attack_scoped_modifiers or ())
        )
        object.__setattr__(self, "attack_scoped_modifiers", tuple(sorted(modifiers, key=lambda item: item.modifier_id)))

    def with_base_detection_range(self, base_detection_range: float | None) -> "VisibilityModifierQuery":
        return VisibilityModifierQuery(
            source_unit_id=self.source_unit_id,
            target_unit_id=self.target_unit_id,
            base_detection_range=base_detection_range,
            active_shooting_unit_id=self.active_shooting_unit_id,
            attack_context_id=self.attack_context_id,
            attack_scoped_modifiers=self.attack_scoped_modifiers,
        )

    def cache_key(self) -> tuple[Any, ...]:
        return (
            self.source_unit_id,
            self.target_unit_id,
            self.base_detection_range,
            self.active_shooting_unit_id,
            self.attack_context_id,
            tuple(_cache_tuple(modifier.to_dict()) for modifier in self.attack_scoped_modifiers),
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "VisibilityModifierQuery":
        return cls(
            source_unit_id=str(data.get("source_unit_id", "") or ""),
            target_unit_id=str(data.get("target_unit_id", "") or ""),
            base_detection_range=data.get("base_detection_range", None),
            active_shooting_unit_id=str(data.get("active_shooting_unit_id", "") or ""),
            attack_context_id=str(data.get("attack_context_id", "") or ""),
            attack_scoped_modifiers=tuple(
                VisibilityRangeModifier.from_dict(dict(modifier or {}))
                for modifier in list(data.get("attack_scoped_modifiers", []) or [])
            ),
        )


@dataclass(frozen=True)
class VisibilityModifierResult:
    base_detection_range: float | None
    effective_detection_range: float | None
    marker_detection_range_delta: float
    attack_scoped_detection_range_delta: float
    fixed_detection_range: float | None
    applied_detection_marker_ids: tuple[str, ...]
    applied_visibility_modifier_ids: tuple[str, ...]
    reason_trace: tuple[dict[str, Any], ...]

    def to_context_fields(self) -> dict[str, Any]:
        return {
            "hidden_detection_range_base": self.base_detection_range,
            "hidden_detection_range": self.effective_detection_range,
            "detection_marker_delta": float(self.marker_detection_range_delta),
            "attack_scoped_detection_range_delta": float(self.attack_scoped_detection_range_delta),
            "fixed_detection_range_override": self.fixed_detection_range,
            "applied_detection_marker_ids": list(self.applied_detection_marker_ids),
            "applied_visibility_modifier_ids": list(self.applied_visibility_modifier_ids),
        }


def _unit_id(value: object | None) -> str:
    if value is None:
        return ""
    entity_id = maybe_entity_id(value)
    if entity_id:
        return entity_id
    return str(id(value))


def coerce_visibility_modifier_query(
    value: VisibilityModifierQuery | Mapping[str, Any] | None,
    *,
    source_unit: object | None,
    target_unit: object | None,
    base_detection_range: float | None,
) -> VisibilityModifierQuery:
    if isinstance(value, VisibilityModifierQuery):
        query = value
    elif isinstance(value, Mapping):
        query = VisibilityModifierQuery.from_dict(value)
    elif value is None:
        query = VisibilityModifierQuery(
            source_unit_id=_unit_id(source_unit),
            target_unit_id=_unit_id(target_unit),
            base_detection_range=base_detection_range,
        )
    else:
        raise TypeError(f"Unsupported visibility modifier query: {type(value).__name__}")

    source_unit_id = query.source_unit_id or _unit_id(source_unit)
    target_unit_id = query.target_unit_id or _unit_id(target_unit)
    return VisibilityModifierQuery(
        source_unit_id=source_unit_id,
        target_unit_id=target_unit_id,
        base_detection_range=base_detection_range,
        active_shooting_unit_id=query.active_shooting_unit_id,
        attack_context_id=query.attack_context_id,
        attack_scoped_modifiers=query.attack_scoped_modifiers,
    )


def detection_markers_on_map(game_map: object) -> tuple[DetectionMarker, ...]:
    markers: list[DetectionMarker] = []
    for marker in list(getattr(game_map, "detection_markers", []) or []):
        if isinstance(marker, DetectionMarker):
            markers.append(marker)
        elif isinstance(marker, Mapping):
            markers.append(DetectionMarker.from_dict(marker))
    return tuple(sorted(markers, key=lambda item: (item.target_unit_id, item.marker_id, item.source_unit_id)))


def detection_marker_signature(game_map: object) -> tuple[Any, ...]:
    return tuple(_cache_tuple(marker.to_dict()) for marker in detection_markers_on_map(game_map))


def visibility_query_signature(value: VisibilityModifierQuery | Mapping[str, Any] | None) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, VisibilityModifierQuery):
        return value.cache_key()
    if isinstance(value, Mapping):
        return VisibilityModifierQuery.from_dict(value).cache_key()
    return (type(value).__name__, str(value))


def add_detection_marker_to_map(game_map: object, marker: DetectionMarker | Mapping[str, Any]) -> DetectionMarker:
    marker_obj = marker if isinstance(marker, DetectionMarker) else DetectionMarker.from_dict(marker)
    existing = list(getattr(game_map, "detection_markers", []) or [])
    existing.append(marker_obj)
    existing.sort(key=lambda item: (item.target_unit_id, item.marker_id, item.source_unit_id))
    setattr(game_map, "detection_markers", existing)
    bump = getattr(game_map, "bump_state_generation", None)
    if callable(bump):
        bump("detection_marker_added")
    game = getattr(game_map, "game", None)
    event_log = getattr(game, "event_log", None)
    if event_log is not None and callable(getattr(event_log, "record", None)):
        event_log.record(
            "detection_marker_added",
            actor_id=marker_obj.source_unit_id or None,
            payload={"detection_marker": marker_obj.to_dict()},
        )
    return marker_obj


def collect_visibility_modifiers(game_map: object, query: VisibilityModifierQuery) -> VisibilityModifierResult:
    applied_marker_ids: list[str] = []
    applied_modifier_ids: list[str] = []
    marker_delta = 0.0
    attack_delta = 0.0
    fixed_detection_range: float | None = None
    reason_trace: list[dict[str, Any]] = []

    for marker in detection_markers_on_map(game_map):
        if not marker.applies_to(target_unit_id=query.target_unit_id):
            continue
        marker_delta += float(marker.detection_range_delta)
        applied_marker_ids.append(marker.marker_id)
        reason_trace.append(
            {
                "code": "DETECTION_MARKER_DELTA_APPLIED",
                "detail": "Detection marker modifies the target unit detection range.",
                "metadata": {
                    "marker_id": marker.marker_id,
                    "source_unit_id": marker.source_unit_id,
                    "target_unit_id": marker.target_unit_id,
                    "detection_range_delta": float(marker.detection_range_delta),
                    "source_provenance": list(marker.source_provenance),
                },
            }
        )

    for modifier in query.attack_scoped_modifiers:
        if not modifier.applies_to(
            source_unit_id=query.source_unit_id,
            target_unit_id=query.target_unit_id,
            active_shooting_unit_id=query.active_shooting_unit_id,
        ):
            continue
        attack_delta += float(modifier.detection_range_delta)
        applied_modifier_ids.append(modifier.modifier_id)
        if modifier.fixed_detection_range is not None:
            if fixed_detection_range is None or float(modifier.fixed_detection_range) > fixed_detection_range:
                fixed_detection_range = float(modifier.fixed_detection_range)
        reason_trace.append(
            {
                "code": "VISIBILITY_MODIFIER_APPLIED",
                "detail": "Attack-scoped visibility modifier applies to this query.",
                "metadata": {
                    "modifier_id": modifier.modifier_id,
                    "scope": modifier.scope,
                    "detection_range_delta": float(modifier.detection_range_delta),
                    "fixed_detection_range": modifier.fixed_detection_range,
                    "source_provenance": list(modifier.source_provenance),
                },
            }
        )

    effective: float | None
    if query.base_detection_range is None:
        effective = fixed_detection_range
    else:
        effective = float(query.base_detection_range) + marker_delta + attack_delta
        if fixed_detection_range is not None:
            effective = max(float(effective), fixed_detection_range)

    return VisibilityModifierResult(
        base_detection_range=query.base_detection_range,
        effective_detection_range=effective,
        marker_detection_range_delta=marker_delta,
        attack_scoped_detection_range_delta=attack_delta,
        fixed_detection_range=fixed_detection_range,
        applied_detection_marker_ids=tuple(sorted(applied_marker_ids)),
        applied_visibility_modifier_ids=tuple(sorted(applied_modifier_ids)),
        reason_trace=tuple(reason_trace),
    )


__all__ = [
    "DetectionMarker",
    "VisibilityModifierQuery",
    "VisibilityModifierResult",
    "VisibilityRangeModifier",
    "add_detection_marker_to_map",
    "coerce_visibility_modifier_query",
    "collect_visibility_modifiers",
    "detection_marker_signature",
    "detection_markers_on_map",
    "visibility_query_signature",
]
