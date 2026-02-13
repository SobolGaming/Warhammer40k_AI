from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

from ..units.unit import Unit
from ..waha_helper import WahaHelper


_AOI_FACTION_ID = "AOI"
_AOI_WAHA_FACTION_ID = "AoI"
_SHADOW_ASSIGNMENT_NAME = "shadow assignment"
_OFFICIO_ASSASSINORUM_KEYWORD = "OFFICIO ASSASSINORUM"
_ASSASSIN_NAMES = (
    "Callidus Assassin",
    "Culexus Assassin",
    "Eversor Assassin",
    "Vindicare Assassin",
)


@dataclass(frozen=True)
class ShadowAssignmentCandidate:
    name: str
    datasheet_id: str
    points: int

    @property
    def name_key(self) -> str:
        return _normalize_name(self.name)


def _normalize_name(value: str) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").strip().lower())
    return re.sub(r"\s+", " ", text).strip()


def _unit_name_key(unit: object) -> str:
    return _normalize_name(str(getattr(unit, "name", "") or ""))


@lru_cache(maxsize=1)
def _get_waha_helper() -> WahaHelper:
    return WahaHelper("wahapedia_data")


@lru_cache(maxsize=1)
def get_shadow_assignment_catalog() -> tuple[ShadowAssignmentCandidate, ...]:
    helper = _get_waha_helper()
    candidates: list[ShadowAssignmentCandidate] = []
    for name in _ASSASSIN_NAMES:
        datasheet = helper.get_full_datasheet_info_by_name(name, faction_id=_AOI_WAHA_FACTION_ID)
        if datasheet is None:
            raise RuntimeError(f"Shadow Assignment datasheet not found: {name}.")
        unit = Unit(datasheet)
        candidates.append(
            ShadowAssignmentCandidate(
                name=str(getattr(unit, "name", "") or name),
                datasheet_id=str(getattr(datasheet, "id", "") or ""),
                points=int(unit.get_unit_cost()),
            )
        )
    candidates.sort(key=lambda c: (int(c.points), c.name_key))
    return tuple(candidates)


def get_shadow_assignment_candidate(
    *,
    replacement_name: str = "",
    replacement_datasheet_id: str = "",
) -> ShadowAssignmentCandidate | None:
    name_key = _normalize_name(replacement_name)
    datasheet_id = str(replacement_datasheet_id or "").strip()
    for candidate in get_shadow_assignment_catalog():
        if datasheet_id and str(candidate.datasheet_id) == datasheet_id:
            return candidate
        if name_key and candidate.name_key == name_key:
            return candidate
    return None


def army_supports_shadow_assignment(army: object) -> bool:
    fid = str(getattr(army, "faction_id", "") or "").strip().upper()
    return fid == _AOI_FACTION_ID


def unit_has_shadow_assignment(unit: object) -> bool:
    if unit is None:
        return False
    iter_fn = getattr(unit, "_iter_ability_entries_for_rules", None)
    if callable(iter_fn):
        for name, _desc in iter_fn(model=None):
            if _normalize_name(name) == _SHADOW_ASSIGNMENT_NAME:
                return True
    return False


def unit_is_officio_assassinorum(unit: object) -> bool:
    if unit is None:
        return False
    has_any = getattr(unit, "has_any_keyword", None)
    if callable(has_any):
        return bool(has_any(_OFFICIO_ASSASSINORUM_KEYWORD))
    keywords = [
        str(k).strip().upper()
        for k in (getattr(unit, "keywords", []) or [])
        if str(k).strip()
    ]
    faction_keywords = [
        str(k).strip().upper()
        for k in (getattr(unit, "faction_keywords", []) or [])
        if str(k).strip()
    ]
    return _OFFICIO_ASSASSINORUM_KEYWORD in set(keywords + faction_keywords)


def shadow_assignment_candidates_for_unit(
    source_unit: object,
    army_units: Iterable[object],
) -> list[ShadowAssignmentCandidate]:
    if source_unit is None:
        return []
    source_name_key = _unit_name_key(source_unit)
    source_points = int(getattr(source_unit, "get_unit_cost", lambda: 0)() or 0)
    taken_name_keys = {
        _unit_name_key(unit)
        for unit in list(army_units or [])
        if unit is not None and unit is not source_unit and unit_is_officio_assassinorum(unit)
    }
    options: list[ShadowAssignmentCandidate] = []
    for candidate in get_shadow_assignment_catalog():
        if candidate.name_key == source_name_key:
            continue
        if int(candidate.points) > source_points:
            continue
        if candidate.name_key in taken_name_keys:
            continue
        options.append(candidate)
    options.sort(key=lambda c: (int(c.points), c.name_key))
    return options


def shadow_assignment_options_for_unit(
    source_unit: object,
    army_units: Iterable[object],
) -> list[tuple[str, dict]]:
    source_id = str(getattr(source_unit, "id", "") or "")
    options: list[tuple[str, dict]] = [
        (
            "None",
            {
                "action": "skip",
                "unit_id": source_id,
                "replacement_name": None,
                "replacement_datasheet_id": None,
            },
        )
    ]
    for candidate in shadow_assignment_candidates_for_unit(source_unit, army_units):
        label = f"{candidate.name} ({int(candidate.points)} pts)"
        payload = {
            "action": "replace",
            "unit_id": source_id,
            "replacement_name": candidate.name,
            "replacement_datasheet_id": candidate.datasheet_id,
            "replacement_points": int(candidate.points),
        }
        options.append((label, payload))
    return options


def build_shadow_assignment_unit(candidate: ShadowAssignmentCandidate) -> Unit:
    helper = _get_waha_helper()
    datasheet = helper.get_full_datasheet_info_by_name(
        candidate.name,
        datasheet_id=candidate.datasheet_id,
        faction_id=_AOI_WAHA_FACTION_ID,
    )
    if datasheet is None:
        raise RuntimeError(
            f"Shadow Assignment datasheet lookup failed for {candidate.name} ({candidate.datasheet_id})."
        )
    return Unit(datasheet)
