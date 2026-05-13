from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ..rules.mechanic_registry import (
    DEFAULT_MECHANIC_REGISTRY,
    MechanicRegistry,
    normalize_profile_id,
)
from ..utility.entity_ids import maybe_entity_id


@dataclass(frozen=True)
class MovementKeywordInstance:
    keyword_id: str
    raw_keyword: str
    display_name: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    timing_window: str = ""
    source_provenance: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "keyword_id": str(self.keyword_id or ""),
            "raw_keyword": str(self.raw_keyword or ""),
            "display_name": str(self.display_name or ""),
            "parameters": dict(self.parameters or {}),
            "timing_window": str(self.timing_window or ""),
            "source_provenance": [dict(item) for item in self.source_provenance],
        }


@dataclass(frozen=True)
class MovementKeywordRuntimeState:
    unit_id: str
    profile_id: str
    keyword_instances: tuple[MovementKeywordInstance, ...] = field(default_factory=tuple)

    def has_keyword(self, keyword_id: str) -> bool:
        normalized = str(keyword_id or "").strip().upper().replace(" ", "_").replace("-", "_")
        return any(str(instance.keyword_id or "").upper() == normalized for instance in self.keyword_instances)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id or ""),
            "profile_id": str(self.profile_id or ""),
            "keyword_instances": [instance.to_dict() for instance in self.keyword_instances],
        }


def _unit_keywords(unit: object) -> tuple[str, ...]:
    values: list[str] = []
    get_effective = getattr(unit, "get_effective_keywords", None)
    if callable(get_effective):
        values.extend(str(value or "").strip() for value in list(get_effective() or []))
    else:
        values.extend(str(value or "").strip() for value in list(getattr(unit, "keywords", []) or []))
    return tuple(value for value in values if value)


def collect_movement_keyword_instances(
    unit: object,
    *,
    profile_id: object,
    registry: MechanicRegistry = DEFAULT_MECHANIC_REGISTRY,
) -> tuple[MovementKeywordInstance, ...]:
    normalized_profile = normalize_profile_id(profile_id)
    if not registry.is_enabled("MOBILE", normalized_profile):
        return ()
    definition = registry.get("MOBILE")
    if definition is None:
        return ()
    instances: list[MovementKeywordInstance] = []
    for raw_keyword in _unit_keywords(unit):
        if str(raw_keyword or "").strip().upper() != "MOBILE":
            continue
        instances.append(
            MovementKeywordInstance(
                keyword_id="MOBILE",
                raw_keyword=str(raw_keyword),
                display_name=definition.display_name,
                parameters={"terrain_traversal_hook": "preview_inert"},
                timing_window=definition.timing_window,
                source_provenance=tuple(source.to_dict() for source in definition.source_provenance),
            )
        )
    instances.sort(key=lambda item: (str(item.keyword_id), str(item.raw_keyword)))
    return tuple(instances)


def movement_keyword_runtime_state(
    unit: object,
    *,
    profile_id: object,
    registry: MechanicRegistry = DEFAULT_MECHANIC_REGISTRY,
) -> MovementKeywordRuntimeState:
    return MovementKeywordRuntimeState(
        unit_id=str(maybe_entity_id(unit) or ""),
        profile_id=normalize_profile_id(profile_id),
        keyword_instances=collect_movement_keyword_instances(unit, profile_id=profile_id, registry=registry),
    )
