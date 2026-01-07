from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .army import Army, ArmyValidationError, get_faction_id_from_name, _assert_supported_faction
from ..waha_helper import WahaHelper


@dataclass
class UnitSelection:
    """Placeholder for unit picks during in-engine mustering."""
    name: str
    count: int = 1
    wargear: List[str] = field(default_factory=list)
    enhancements: List[str] = field(default_factory=list)
    is_warlord: bool = False


@dataclass
class ArmyMusterRequest:
    """Minimal spec for in-engine army mustering (units to be wired later)."""
    faction: str
    detachment_type: str
    points_limit: int = 2000
    units: List[UnitSelection] = field(default_factory=list)


class ArmyMusterer:
    """Scaffolding for building armies without loading an army list file."""
    def __init__(self, waha_helper: WahaHelper) -> None:
        self._waha = waha_helper

    def muster_army(self, request: ArmyMusterRequest) -> Army:
        if request is None:
            raise ArmyValidationError("Army mustering request is missing.")
        faction_id = get_faction_id_from_name(request.faction)
        _assert_supported_faction(request.faction, faction_id)
        army = Army(
            faction=request.faction,
            detachment_type=request.detachment_type,
            points_limit=request.points_limit,
        )
        if faction_id:
            army.faction_id = faction_id
        if request.units:
            raise NotImplementedError(
                "Unit selection mustering is not implemented yet; provide an empty units list."
            )
        return army
