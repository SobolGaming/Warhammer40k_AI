from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from threading import Lock
from typing import Any

FrozenValue = tuple[str, Any]


def _freeze_static_value(value: Any) -> FrozenValue:
    if isinstance(value, dict):
        return (
            "dict",
            tuple((deepcopy(key), _freeze_static_value(item)) for key, item in value.items()),
        )
    if isinstance(value, list):
        return ("list", tuple(_freeze_static_value(item) for item in value))
    if isinstance(value, tuple):
        return ("tuple", tuple(_freeze_static_value(item) for item in value))
    if isinstance(value, set):
        frozen_items = tuple(
            sorted((_freeze_static_value(item) for item in value), key=repr)
        )
        return ("set", frozen_items)
    return ("value", deepcopy(value))


def _thaw_static_value(value: FrozenValue) -> Any:
    kind, payload = value
    if kind == "dict":
        return {deepcopy(key): _thaw_static_value(item) for key, item in payload}
    if kind == "list":
        return [_thaw_static_value(item) for item in payload]
    if kind == "tuple":
        return tuple(_thaw_static_value(item) for item in payload)
    if kind == "set":
        return {_thaw_static_value(item) for item in payload}
    if kind == "value":
        return deepcopy(payload)
    raise ValueError(f"Unknown frozen static value kind: {kind!r}")


@dataclass(frozen=True)
class ParsedDatasheetRecord:
    """Immutable parsed datasheet snapshot for static unit construction data."""

    keywords: tuple[str, ...]
    faction_keywords: tuple[str, ...]
    unit_composition: FrozenValue
    unit_composition_options: FrozenValue
    unit_models_maximum: int | None
    models_cost: FrozenValue
    models_cost_addons: FrozenValue
    possible_wargear: tuple[Any, ...]
    wargear_options: FrozenValue
    possible_abilities: tuple[Any, ...]
    wargear_constraints: FrozenValue

    @classmethod
    def from_parsed(
        cls,
        *,
        keywords: tuple[str, ...],
        faction_keywords: tuple[str, ...],
        unit_composition: dict[str, tuple[int, int]],
        unit_composition_options: list[dict[str, tuple[int, int]]],
        unit_models_maximum: int | None,
        models_cost: dict[Any, int],
        models_cost_addons: dict[str, int],
        possible_wargear: list[Any],
        wargear_options: Any,
        possible_abilities: list[Any],
        wargear_constraints: dict[str, Any],
    ) -> "ParsedDatasheetRecord":
        return cls(
            keywords=tuple(keywords),
            faction_keywords=tuple(faction_keywords),
            unit_composition=_freeze_static_value(unit_composition),
            unit_composition_options=_freeze_static_value(unit_composition_options),
            unit_models_maximum=unit_models_maximum,
            models_cost=_freeze_static_value(models_cost),
            models_cost_addons=_freeze_static_value(models_cost_addons),
            possible_wargear=tuple(deepcopy(list(possible_wargear))),
            wargear_options=_freeze_static_value(wargear_options),
            possible_abilities=tuple(deepcopy(list(possible_abilities))),
            wargear_constraints=_freeze_static_value(wargear_constraints),
        )

    def clone_unit_composition(self) -> dict[str, tuple[int, int]]:
        return _thaw_static_value(self.unit_composition)

    def clone_unit_composition_options(self) -> list[dict[str, tuple[int, int]]]:
        return _thaw_static_value(self.unit_composition_options)

    def clone_models_cost(self) -> dict[str, int]:
        return _thaw_static_value(self.models_cost)

    def clone_models_cost_addons(self) -> dict[str, int]:
        return _thaw_static_value(self.models_cost_addons)

    def clone_possible_wargear(self) -> list[Any]:
        return deepcopy(list(self.possible_wargear))

    def clone_wargear_options(self) -> Any:
        return _thaw_static_value(self.wargear_options)

    def clone_possible_abilities(self) -> list[Any]:
        return deepcopy(list(self.possible_abilities))

    def clone_wargear_constraints(self) -> dict[str, Any]:
        return _thaw_static_value(self.wargear_constraints)


_PARSED_DATASHEET_CACHE: dict[str, ParsedDatasheetRecord] = {}
_PARSED_DATASHEET_CACHE_LOCK = Lock()


def get_cached_parsed_datasheet_record(cache_key: str) -> ParsedDatasheetRecord | None:
    with _PARSED_DATASHEET_CACHE_LOCK:
        return _PARSED_DATASHEET_CACHE.get(cache_key)


def put_cached_parsed_datasheet_record(cache_key: str, record: ParsedDatasheetRecord) -> None:
    with _PARSED_DATASHEET_CACHE_LOCK:
        _PARSED_DATASHEET_CACHE[cache_key] = record
