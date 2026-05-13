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


def _unit_id(unit: object | None) -> str:
    if unit is None:
        return ""
    entity_id = maybe_entity_id(unit)
    if entity_id:
        return entity_id
    return str(id(unit))


def _cache_tuple(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple((str(key), _cache_tuple(inner)) for key, inner in sorted(value.items(), key=lambda item: str(item[0])))
    if isinstance(value, (list, tuple)):
        return tuple(_cache_tuple(inner) for inner in value)
    if isinstance(value, set):
        return tuple(sorted(_cache_tuple(inner) for inner in value))
    return value


@dataclass(frozen=True)
class HiddenShootingExemption:
    exemption_id: str
    unit_id: str
    source_id: str
    duration: str
    enabled_by_profile: str = "11e_preview"
    source_provenance: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        exemption_id = _clean_text(self.exemption_id)
        unit_id = _clean_text(self.unit_id)
        if not exemption_id:
            raise ValueError("HiddenShootingExemption.exemption_id is required.")
        if not unit_id:
            raise ValueError("HiddenShootingExemption.unit_id is required.")
        object.__setattr__(self, "exemption_id", exemption_id)
        object.__setattr__(self, "unit_id", unit_id)
        object.__setattr__(self, "source_id", _clean_text(self.source_id))
        object.__setattr__(self, "duration", _clean_text(self.duration))
        object.__setattr__(self, "enabled_by_profile", _clean_text(self.enabled_by_profile) or "11e_preview")
        object.__setattr__(self, "source_provenance", _clean_sources(self.source_provenance))

    def applies_to(self, *, unit_id: str) -> bool:
        return self.unit_id == _clean_text(unit_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "exemption_id": self.exemption_id,
            "unit_id": self.unit_id,
            "source_id": self.source_id,
            "duration": self.duration,
            "enabled_by_profile": self.enabled_by_profile,
            "source_provenance": list(self.source_provenance),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HiddenShootingExemption":
        return cls(
            exemption_id=str(data.get("exemption_id", "") or ""),
            unit_id=str(data.get("unit_id", "") or ""),
            source_id=str(data.get("source_id", "") or ""),
            duration=str(data.get("duration", "") or ""),
            enabled_by_profile=str(data.get("enabled_by_profile", "") or "11e_preview"),
            source_provenance=_clean_sources(data.get("source_provenance", ())),
        )


def hidden_shooting_exemptions_on_map(game_map: object) -> tuple[HiddenShootingExemption, ...]:
    exemptions: list[HiddenShootingExemption] = []
    for exemption in list(getattr(game_map, "hidden_shooting_exemptions", []) or []):
        if isinstance(exemption, HiddenShootingExemption):
            exemptions.append(exemption)
        elif isinstance(exemption, Mapping):
            exemptions.append(HiddenShootingExemption.from_dict(exemption))
    return tuple(sorted(exemptions, key=lambda item: (item.unit_id, item.exemption_id, item.source_id)))


def hidden_shooting_exemption_signature(game_map: object) -> tuple[Any, ...]:
    return tuple(_cache_tuple(exemption.to_dict()) for exemption in hidden_shooting_exemptions_on_map(game_map))


def hidden_preserving_exemption_ids_for_unit(game_map: object, unit: object | None) -> tuple[str, ...]:
    unit_id = _unit_id(unit)
    ids = [
        exemption.exemption_id
        for exemption in hidden_shooting_exemptions_on_map(game_map)
        if exemption.applies_to(unit_id=unit_id)
    ]
    return tuple(sorted(ids))


def has_hidden_preserving_shooting_exemption(game_map: object, unit: object | None) -> bool:
    return bool(hidden_preserving_exemption_ids_for_unit(game_map, unit))


def _provenance_bool(provenance: object, field_name: str) -> bool:
    if isinstance(provenance, Mapping):
        return bool(provenance.get(field_name, False))
    return bool(getattr(provenance, field_name, False))


def _provenance_hidden_exemptions(provenance: object) -> tuple[str, ...]:
    if isinstance(provenance, Mapping):
        values = provenance.get("hidden_shooting_exemptions", ())
    else:
        values = getattr(provenance, "hidden_shooting_exemptions", ())
    return _clean_sources(values)


def hidden_shot_breaks_hidden_from_provenance(unit_turn_provenance: object) -> bool:
    if not (
        _provenance_bool(unit_turn_provenance, "shot_this_turn")
        or _provenance_bool(unit_turn_provenance, "shot_previous_player_turn")
    ):
        return False
    return not bool(_provenance_hidden_exemptions(unit_turn_provenance))


def hidden_shot_breaks_hidden(
    game_map: object,
    unit: object | None,
    *,
    last_shot_turn: str,
    current_turn: str,
    previous_turn: str,
    unit_turn_provenance: object | None = None,
) -> bool:
    if unit_turn_provenance is not None:
        return hidden_shot_breaks_hidden_from_provenance(unit_turn_provenance)
    last_shot_turn = _clean_text(last_shot_turn)
    active_turns = {_clean_text(current_turn), _clean_text(previous_turn)}
    active_turns.discard("")
    if not last_shot_turn or last_shot_turn not in active_turns:
        return False
    return not has_hidden_preserving_shooting_exemption(game_map, unit)


def add_hidden_shooting_exemption_to_map(
    game_map: object,
    exemption: HiddenShootingExemption | Mapping[str, Any],
) -> HiddenShootingExemption:
    exemption_obj = exemption if isinstance(exemption, HiddenShootingExemption) else HiddenShootingExemption.from_dict(exemption)
    existing = list(getattr(game_map, "hidden_shooting_exemptions", []) or [])
    existing.append(exemption_obj)
    existing.sort(key=lambda item: (item.unit_id, item.exemption_id, item.source_id))
    setattr(game_map, "hidden_shooting_exemptions", existing)
    bump = getattr(game_map, "bump_state_generation", None)
    if callable(bump):
        bump("hidden_shooting_exemption_added")
    game = getattr(game_map, "game", None)
    event_log = getattr(game, "event_log", None)
    if event_log is not None and callable(getattr(event_log, "record", None)):
        event_log.record(
            "hidden_shooting_exemption_added",
            actor_id=exemption_obj.source_id or None,
            payload={"hidden_shooting_exemption": exemption_obj.to_dict()},
        )
    return exemption_obj


def mark_unit_shot_for_hidden(unit: object, game_map: object, *, player_turn_id: str) -> None:
    setattr(unit, "terrain_hidden_last_shot_player_turn", _clean_text(player_turn_id))
    bump = getattr(game_map, "bump_state_generation", None)
    if callable(bump):
        bump("hidden_shot_recorded")


__all__ = [
    "HiddenShootingExemption",
    "add_hidden_shooting_exemption_to_map",
    "has_hidden_preserving_shooting_exemption",
    "hidden_preserving_exemption_ids_for_unit",
    "hidden_shooting_exemption_signature",
    "hidden_shooting_exemptions_on_map",
    "hidden_shot_breaks_hidden",
    "hidden_shot_breaks_hidden_from_provenance",
    "mark_unit_shot_for_hidden",
]
