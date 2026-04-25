from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FactionRuntimeState:
    adepta_sororitas_destroyers_by_army_id: dict[str, set[str]] = field(default_factory=dict)
    shadow_of_chaos_zone_overrides: dict[str, set[str]] = field(default_factory=dict)
    corrupt_realspace_check: bool = False
    phoenix_gem_pending: list[dict[str, Any]] = field(default_factory=list)
    blood_surge_shooting_snapshot: dict[object, dict[object, int]] = field(default_factory=dict)
    brazen_fury_shooting_snapshot: dict[object, dict[object, int]] = field(default_factory=dict)
    horde_move_shooting_snapshot: dict[object, dict[object, int]] = field(default_factory=dict)
    unhinged_vengeance_shooting_snapshot: dict[object, dict[object, int]] = field(default_factory=dict)
    blistering_assault_shooting_snapshot: dict[object, dict[object, int]] = field(default_factory=dict)
    aggressive_leader_beast_shooting_snapshot: dict[object, dict[object, int]] = field(default_factory=dict)
    guns_blazing_shooting_targets: dict[object, list[object]] = field(default_factory=dict)
    frenzy_shooting_targets: dict[object, list[object]] = field(default_factory=dict)
    frenzy_fight_targets: dict[object, list[object]] = field(default_factory=dict)
    pain_parasite_shooting_snapshot: dict[object, dict[object, int]] = field(default_factory=dict)
    pain_parasite_fight_snapshot: dict[object, dict[object, int]] = field(default_factory=dict)
    repair_barge_shooting_snapshot: dict[object, dict[object, int]] = field(default_factory=dict)
    repair_barge_fight_snapshot: dict[object, dict[object, int]] = field(default_factory=dict)
