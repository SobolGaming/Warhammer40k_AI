from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping


PROFILE_CURRENT = "current"
PROFILE_11E_PREVIEW = "11e_preview"
PROFILE_11E_RELEASE = "11e_release"


def normalize_mechanic_id(value: object) -> str:
    text = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text


def normalize_profile_id(value: object) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"", "10e", "10e_current", "10th_current", "current_10e"}:
        return PROFILE_CURRENT
    if text in {"11e", "11th", "11e_preview", "11th_preview", "preview_11e", "combat_preview_11e"}:
        return PROFILE_11E_PREVIEW
    if text in {"11e_release", "11th_release", "release_11e"}:
        return PROFILE_11E_RELEASE
    return text


@dataclass(frozen=True)
class SourceProvenance:
    source_id: str
    label: str
    preview_only: bool = True
    url: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_id": str(self.source_id or ""),
            "label": str(self.label or ""),
            "preview_only": bool(self.preview_only),
        }
        if self.url:
            payload["url"] = str(self.url)
        return payload


@dataclass(frozen=True)
class MechanicDefinition:
    keyword_id: str
    display_name: str
    scope: str
    timing_window: str
    parameter_schema: Mapping[str, Any] = field(default_factory=dict)
    enabled_by_profile: tuple[str, ...] = field(default_factory=tuple)
    source_provenance: tuple[SourceProvenance, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "keyword_id", normalize_mechanic_id(self.keyword_id))
        object.__setattr__(self, "enabled_by_profile", tuple(normalize_profile_id(v) for v in self.enabled_by_profile))
        object.__setattr__(self, "parameter_schema", MappingProxyType(dict(self.parameter_schema or {})))

    def enabled_for_profile(self, profile_id: object) -> bool:
        normalized = normalize_profile_id(profile_id)
        return normalized in set(self.enabled_by_profile)

    def to_dict(self) -> dict[str, Any]:
        return {
            "keyword_id": str(self.keyword_id or ""),
            "display_name": str(self.display_name or ""),
            "scope": str(self.scope or ""),
            "timing_window": str(self.timing_window or ""),
            "parameter_schema": dict(self.parameter_schema or {}),
            "enabled_by_profile": list(self.enabled_by_profile),
            "source_provenance": [source.to_dict() for source in self.source_provenance],
        }


KeywordDefinition = MechanicDefinition


class MechanicRegistry:
    def __init__(self, definitions: Iterable[MechanicDefinition] = ()) -> None:
        self._definitions: dict[str, MechanicDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: MechanicDefinition) -> None:
        self._definitions[normalize_mechanic_id(definition.keyword_id)] = definition

    def get(self, keyword_id: object) -> MechanicDefinition | None:
        return self._definitions.get(normalize_mechanic_id(keyword_id))

    def definitions(self) -> tuple[MechanicDefinition, ...]:
        return tuple(self._definitions[key] for key in sorted(self._definitions))

    def enabled_definitions(self, profile_id: object, *, timing_window: str | None = None) -> tuple[MechanicDefinition, ...]:
        timing = str(timing_window or "").strip().lower()
        enabled: list[MechanicDefinition] = []
        for definition in self.definitions():
            if not definition.enabled_for_profile(profile_id):
                continue
            if timing and str(definition.timing_window or "").strip().lower() != timing:
                continue
            enabled.append(definition)
        return tuple(enabled)

    def is_enabled(self, keyword_id: object, profile_id: object) -> bool:
        definition = self.get(keyword_id)
        return bool(definition is not None and definition.enabled_for_profile(profile_id))

    def to_dict(self) -> dict[str, Any]:
        return {
            "definitions": [definition.to_dict() for definition in self.definitions()],
        }


_FACTION_FOCUS_SOURCE = SourceProvenance(
    source_id="preview_sources:11e_faction_focus_may2026",
    label="May 2026 Warhammer Community faction-focus preview source catalog",
    preview_only=True,
    url="docs/preview_sources/11e_faction_focus_may2026.json",
)


def _definition(
    keyword_id: str,
    display_name: str,
    *,
    scope: str,
    timing_window: str,
    parameter_schema: Mapping[str, Any] | None = None,
) -> MechanicDefinition:
    return MechanicDefinition(
        keyword_id=keyword_id,
        display_name=display_name,
        scope=scope,
        timing_window=timing_window,
        parameter_schema=dict(parameter_schema or {}),
        enabled_by_profile=(PROFILE_11E_PREVIEW, PROFILE_11E_RELEASE),
        source_provenance=(_FACTION_FOCUS_SOURCE,),
    )


DEFAULT_MECHANIC_REGISTRY = MechanicRegistry(
    (
        _definition(
            "CLEAVE",
            "Cleave X",
            scope="weapon",
            timing_window="gather_attack_dice",
            parameter_schema={
                "x": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Extra attack dice per five models in the target unit.",
                }
            },
        ),
        _definition(
            "HEAVY_UPDATED",
            "Heavy",
            scope="weapon",
            timing_window="hit_roll",
            parameter_schema={
                "requires_unengaged": True,
                "requires_not_set_up_this_turn": True,
                "max_model_move_distance_this_turn": 3.0,
            },
        ),
        _definition(
            "MOBILE",
            "Mobile",
            scope="movement",
            timing_window="move_validation",
            parameter_schema={"terrain_traversal_hook": "preview_inert"},
        ),
        _definition("ASSAULT", "Assault", scope="weapon", timing_window="shooting_eligibility"),
        _definition("LANCE", "Lance", scope="weapon", timing_window="wound_roll"),
        _definition("HAZARDOUS", "Hazardous", scope="weapon", timing_window="post_attack_resolution"),
        _definition(
            "RAPID_FIRE",
            "Rapid Fire X",
            scope="weapon",
            timing_window="gather_attack_dice",
            parameter_schema={"x": {"type": "integer_or_dice", "minimum": 1}},
        ),
        _definition(
            "SUSTAINED_HITS",
            "Sustained Hits X",
            scope="weapon",
            timing_window="hit_roll",
            parameter_schema={"x": {"type": "integer_or_dice", "minimum": 1}},
        ),
        _definition("LETHAL_HITS", "Lethal Hits", scope="weapon", timing_window="wound_roll"),
    )
)


def default_registry() -> MechanicRegistry:
    return DEFAULT_MECHANIC_REGISTRY
