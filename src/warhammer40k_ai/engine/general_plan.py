from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..utility.entity_ids import get_entity_id


GENERAL_RESOURCE_AVAILABLE = "available"
GENERAL_RESOURCE_RESERVED = "reserved"
GENERAL_RESOURCE_AUTHORIZED = "authorized"
GENERAL_RESOURCE_SPENT = "spent"
GENERAL_RESOURCE_FORBIDDEN = "forbidden"

GENERAL_POSTURE_STAGE = "stage"
GENERAL_POSTURE_PUSH = "push"
GENERAL_POSTURE_PRESERVE = "preserve"


def _sorted_strings(values: list[object] | tuple[object, ...] | set[object] | None) -> list[str]:
    return sorted({str(value) for value in list(values or []) if str(value)})


def _sorted_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    return {str(key): value for key, value in sorted(dict(metadata or {}).items(), key=lambda item: str(item[0]))}


def _entity_id(entity: object) -> str:
    return str(get_entity_id(entity) or getattr(entity, "id", "") or getattr(entity, "_id", "") or "")


@dataclass(frozen=True)
class GeneralRoundDirective:
    battle_round: int
    posture: str
    push_priority: float = 0.0
    stage_priority: float = 0.0
    preserve_priority: float = 0.0
    scoring_preservation_priority: float = 0.0
    cp_reserve_target: float = 0.0
    preserve_unit_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "battle_round": int(self.battle_round),
            "posture": str(self.posture),
            "push_priority": float(self.push_priority),
            "stage_priority": float(self.stage_priority),
            "preserve_priority": float(self.preserve_priority),
            "scoring_preservation_priority": float(self.scoring_preservation_priority),
            "cp_reserve_target": float(self.cp_reserve_target),
            "preserve_unit_ids": _sorted_strings(self.preserve_unit_ids),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class LimitedResourcePolicy:
    resource_id: str
    resource_kind: str
    status: str = GENERAL_RESOURCE_AVAILABLE
    reserved_for_round: int | None = None
    reserved_for_target_unit_id: str | None = None
    authorization_threshold: float = 0.0
    fallback_policy: str = "local_fallback"
    owner_unit_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "resource_id": str(self.resource_id),
            "resource_kind": str(self.resource_kind),
            "status": str(self.status),
            "authorization_threshold": float(self.authorization_threshold),
            "fallback_policy": str(self.fallback_policy),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.reserved_for_round is not None:
            data["reserved_for_round"] = int(self.reserved_for_round)
        if self.reserved_for_target_unit_id is not None:
            data["reserved_for_target_unit_id"] = str(self.reserved_for_target_unit_id)
        if self.owner_unit_id is not None:
            data["owner_unit_id"] = str(self.owner_unit_id)
        return data


@dataclass(frozen=True)
class GeneralResourceLedger:
    resources: dict[str, LimitedResourcePolicy] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        for policy in self.resources.values():
            status = str(policy.status)
            status_counts[status] = int(status_counts.get(status, 0) + 1)
        return {
            "resources": {
                str(resource_id): policy.to_dict()
                for resource_id, policy in sorted(self.resources.items(), key=lambda item: str(item[0]))
            },
            "resource_count": int(len(self.resources)),
            "status_counts": {
                str(status): int(count)
                for status, count in sorted(status_counts.items(), key=lambda item: str(item[0]))
            },
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class TransportDoctrine:
    transport_unit_id: str
    doctrine: str = "preserve_and_deliver"
    desired_round: int | None = None
    protected_until_round: int | None = None
    passenger_unit_ids: list[str] = field(default_factory=list)
    destination_region_ids: list[str] = field(default_factory=list)
    preserve_passengers: bool = True
    post_delivery_role: str = "screen_objective"
    priority: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "transport_unit_id": str(self.transport_unit_id),
            "doctrine": str(self.doctrine),
            "passenger_unit_ids": _sorted_strings(self.passenger_unit_ids),
            "destination_region_ids": _sorted_strings(self.destination_region_ids),
            "preserve_passengers": bool(self.preserve_passengers),
            "post_delivery_role": str(self.post_delivery_role),
            "priority": float(self.priority),
            "metadata": _sorted_metadata(self.metadata),
        }
        if self.desired_round is not None:
            data["desired_round"] = int(self.desired_round)
        if self.protected_until_round is not None:
            data["protected_until_round"] = int(self.protected_until_round)
        return data


@dataclass(frozen=True)
class GeneralDirtyFlags:
    resource_policy_dirty: bool = False
    transport_policy_dirty: bool = False
    round_directives_dirty: bool = False
    full_replan_required: bool = False
    reasons: list[str] = field(default_factory=list)

    def any_dirty(self) -> bool:
        return bool(
            self.resource_policy_dirty
            or self.transport_policy_dirty
            or self.round_directives_dirty
            or self.full_replan_required
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_policy_dirty": bool(self.resource_policy_dirty),
            "transport_policy_dirty": bool(self.transport_policy_dirty),
            "round_directives_dirty": bool(self.round_directives_dirty),
            "full_replan_required": bool(self.full_replan_required),
            "reasons": _sorted_strings(self.reasons),
        }


@dataclass(frozen=True)
class GeneralVarianceReport:
    player_id: str
    plan_id: str
    variance_kind: str
    severity: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_id": str(self.player_id),
            "plan_id": str(self.plan_id),
            "variance_kind": str(self.variance_kind),
            "severity": float(self.severity),
            "metadata": _sorted_metadata(self.metadata),
        }


@dataclass(frozen=True)
class GeneralPlan:
    plan_id: str
    player_id: str
    created_at_generation: int
    strategic_posture: str
    battle_round_directives: dict[int, GeneralRoundDirective] = field(default_factory=dict)
    limited_resource_policy: dict[str, LimitedResourcePolicy] = field(default_factory=dict)
    resource_ledger: GeneralResourceLedger = field(default_factory=GeneralResourceLedger)
    transport_policy: dict[str, TransportDoctrine] = field(default_factory=dict)
    reserve_policy: dict[str, Any] = field(default_factory=dict)
    target_priority_doctrine: dict[str, Any] = field(default_factory=dict)
    cp_policy: dict[str, Any] = field(default_factory=dict)
    dirty_flags: GeneralDirtyFlags = field(default_factory=GeneralDirtyFlags)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": str(self.plan_id),
            "player_id": str(self.player_id),
            "created_at_generation": int(self.created_at_generation),
            "strategic_posture": str(self.strategic_posture),
            "battle_round_directives": {
                str(round_number): directive.to_dict()
                for round_number, directive in sorted(
                    self.battle_round_directives.items(),
                    key=lambda item: int(item[0]),
                )
            },
            "limited_resource_policy": {
                str(resource_id): policy.to_dict()
                for resource_id, policy in sorted(
                    self.limited_resource_policy.items(),
                    key=lambda item: str(item[0]),
                )
            },
            "resource_ledger": self.resource_ledger.to_dict(),
            "transport_policy": {
                str(unit_id): doctrine.to_dict()
                for unit_id, doctrine in sorted(self.transport_policy.items(), key=lambda item: str(item[0]))
            },
            "reserve_policy": _sorted_metadata(self.reserve_policy),
            "target_priority_doctrine": _sorted_metadata(self.target_priority_doctrine),
            "cp_policy": _sorted_metadata(self.cp_policy),
            "dirty_flags": self.dirty_flags.to_dict(),
            "metadata": _sorted_metadata(self.metadata),
        }


def _player_for_id(game: object, player_id: str):
    for player in list(getattr(game, "players", []) or []):
        if str(getattr(player, "id", "") or "") == str(player_id or ""):
            return player
    return None


def _player_army(player: object):
    get_army = getattr(player, "get_army", None)
    if callable(get_army):
        return get_army()
    return getattr(player, "army", None)


def _friendly_units(player: object) -> list[object]:
    army = _player_army(player)
    return sorted(
        [
            unit
            for unit in list(getattr(army, "units", []) or [])
            if unit is not None and bool(getattr(unit, "deployed", True))
        ],
        key=lambda unit: _entity_id(unit),
    )


def _unit_keywords(unit: object) -> set[str]:
    keywords: list[object] = []
    keywords.extend(list(getattr(unit, "keywords", []) or []))
    keywords.extend(list(getattr(unit, "faction_keywords", []) or []))
    for model in list(getattr(unit, "models", []) or []):
        keywords.extend(list(getattr(model, "keywords", []) or []))
        keywords.extend(list(getattr(model, "faction_keywords", []) or []))
    return {str(keyword).strip().upper() for keyword in keywords if str(keyword).strip()}


def _unit_text_blob(unit: object) -> str:
    parts: list[str] = [
        str(getattr(unit, "name", "") or ""),
        str(getattr(unit, "id", "") or getattr(unit, "_id", "") or ""),
    ]
    for model in list(getattr(unit, "models", []) or []):
        parts.append(str(getattr(model, "name", "") or ""))
        for wargear in list(getattr(model, "wargear", []) or []):
            parts.append(str(getattr(wargear, "name", "") or getattr(wargear, "id", "") or ""))
    special_rules = getattr(unit, "special_rules", None)
    if isinstance(special_rules, dict):
        parts.extend(str(key) for key in special_rules.keys())
        parts.extend(str(value) for value in special_rules.values())
    return " ".join(parts).lower()


def _resource_policy_for_unit(unit: object) -> list[LimitedResourcePolicy]:
    unit_id = _entity_id(unit)
    if not unit_id:
        return []
    text = _unit_text_blob(unit)
    policies: list[LimitedResourcePolicy] = []
    if any(token in text for token in ("hunter-killer", "one-shot", "one shot")):
        policies.append(
            LimitedResourcePolicy(
                resource_id=f"{unit_id}:one_shot_weapon",
                resource_kind="one_shot_weapon",
                status=GENERAL_RESOURCE_RESERVED,
                reserved_for_round=3,
                authorization_threshold=0.8,
                fallback_policy="preserve_until_high_value_target",
                owner_unit_id=unit_id,
                metadata={"source": "general_scaffold_keyword_scan"},
            )
        )
    if "once per battle" in text or "once-per-battle" in text:
        policies.append(
            LimitedResourcePolicy(
                resource_id=f"{unit_id}:once_per_battle_ability",
                resource_kind="once_per_battle_ability",
                status=GENERAL_RESOURCE_RESERVED,
                reserved_for_round=3,
                authorization_threshold=0.75,
                fallback_policy="preserve_until_push_round",
                owner_unit_id=unit_id,
                metadata={"source": "general_scaffold_keyword_scan"},
            )
        )
    return policies


def _is_transport_unit(unit: object) -> bool:
    keywords = _unit_keywords(unit)
    transport_capacity = getattr(unit, "transport_capacity", 0)
    try:
        capacity_value = int(transport_capacity or 0)
    except (TypeError, ValueError):
        capacity_value = 0
    return bool(getattr(unit, "is_transport", False)) or "TRANSPORT" in keywords or capacity_value > 0


def _current_transport_passenger_ids(transport: object, units: list[object]) -> list[str]:
    passenger_ids: list[str] = []
    for passenger in list(getattr(transport, "transport_passengers", []) or []):
        passenger_id = _entity_id(passenger)
        if passenger_id:
            passenger_ids.append(passenger_id)
    for unit in list(units or []):
        if getattr(unit, "embarked_in", None) is not transport:
            continue
        passenger_id = _entity_id(unit)
        if passenger_id:
            passenger_ids.append(passenger_id)
    return _sorted_strings(passenger_ids)


def _can_transport_unit(transport: object, passenger: object) -> bool:
    can_transport = getattr(transport, "can_transport", None)
    if not callable(can_transport):
        return False
    try:
        return bool(can_transport(passenger))
    except (AttributeError, TypeError, ValueError):
        return False


def _candidate_transport_passenger_ids(
    transport: object,
    units: list[object],
    assigned_unit_ids: set[str],
) -> list[str]:
    passenger_ids: list[str] = []
    for unit in sorted(list(units or []), key=lambda candidate: _entity_id(candidate)):
        unit_id = _entity_id(unit)
        if not unit_id or unit is transport or unit_id in assigned_unit_ids:
            continue
        if _is_transport_unit(unit):
            continue
        if getattr(unit, "embarked_in", None) is not None:
            continue
        if _can_transport_unit(transport, unit):
            passenger_ids.append(unit_id)
            break
    return _sorted_strings(passenger_ids)


def _transport_policy_for_units(units: list[object]) -> dict[str, TransportDoctrine]:
    policies: dict[str, TransportDoctrine] = {}
    assigned_passenger_ids: set[str] = set()
    transports = [
        unit
        for unit in list(units or [])
        if unit is not None and _entity_id(unit) and _is_transport_unit(unit)
    ]
    for unit in sorted(transports, key=lambda candidate: _entity_id(candidate)):
        unit_id = _entity_id(unit)
        if not unit_id:
            continue
        current_passenger_ids = _current_transport_passenger_ids(unit, list(units or []))
        passenger_ids = current_passenger_ids
        if not passenger_ids:
            passenger_ids = _candidate_transport_passenger_ids(unit, list(units or []), assigned_passenger_ids)
        assigned_passenger_ids.update(passenger_ids)
        doctrine = "preserve_and_deliver" if passenger_ids else "screen_or_reposition"
        policies[unit_id] = TransportDoctrine(
            transport_unit_id=unit_id,
            doctrine=doctrine,
            desired_round=2,
            protected_until_round=2,
            passenger_unit_ids=passenger_ids,
            destination_region_ids=["midboard_stage"],
            preserve_passengers=bool(passenger_ids),
            post_delivery_role="screen_objective",
            priority=0.7 if passenger_ids else 0.4,
            metadata={
                "source": "general_scaffold_transport_doctrine",
                "current_passenger_unit_ids": current_passenger_ids,
                "planned_passenger_unit_ids": passenger_ids,
            },
        )
    return policies


def _round_directives(current_round: int) -> dict[int, GeneralRoundDirective]:
    directives: dict[int, GeneralRoundDirective] = {}
    for round_number in range(1, 6):
        if round_number <= 1:
            posture = GENERAL_POSTURE_STAGE
        elif round_number <= 3:
            posture = GENERAL_POSTURE_PUSH
        else:
            posture = GENERAL_POSTURE_PRESERVE
        directives[round_number] = GeneralRoundDirective(
            battle_round=round_number,
            posture=posture,
            push_priority=0.75 if posture == GENERAL_POSTURE_PUSH else 0.35,
            stage_priority=0.8 if posture == GENERAL_POSTURE_STAGE else 0.3,
            preserve_priority=0.85 if posture == GENERAL_POSTURE_PRESERVE else 0.45,
            scoring_preservation_priority=0.4 + round_number * 0.1,
            cp_reserve_target=1.0 if round_number >= max(2, int(current_round)) else 0.5,
            preserve_unit_ids=[],
            metadata={"source": "general_scaffold_default_directive"},
        )
    return directives


def build_general_plan(game: object, player_id: str) -> GeneralPlan:
    pid = str(player_id or "")
    if not pid:
        raise ValueError("General plan requires player_id.")
    player = _player_for_id(game, pid)
    if player is None:
        raise ValueError(f"Cannot build General plan for unknown player_id: {pid}")

    game_map = getattr(game, "map", None)
    generation = int(getattr(game_map, "state_generation", 0) or 0)
    get_round = getattr(game, "get_battle_round", None)
    current_round = int(get_round() or 1) if callable(get_round) else int(getattr(game, "turn", 1) or 1)
    units = _friendly_units(player)

    resource_policies: dict[str, LimitedResourcePolicy] = {
        f"{pid}:cp_pool": LimitedResourcePolicy(
            resource_id=f"{pid}:cp_pool",
            resource_kind="cp_pool",
            status=GENERAL_RESOURCE_RESERVED,
            reserved_for_round=max(1, min(5, current_round)),
            authorization_threshold=0.6,
            fallback_policy="preserve_for_reactive_defense",
            metadata={"source": "general_scaffold_default_cp_policy"},
        ),
        f"{pid}:stratagem_reserve": LimitedResourcePolicy(
            resource_id=f"{pid}:stratagem_reserve",
            resource_kind="stratagem",
            status=GENERAL_RESOURCE_RESERVED,
            reserved_for_round=max(2, min(5, current_round + 1)),
            authorization_threshold=0.7,
            fallback_policy="preserve_for_interrupt_overwatch_or_defense",
            metadata={"source": "general_scaffold_default_stratagem_policy"},
        ),
    }
    for unit in units:
        for policy in _resource_policy_for_unit(unit):
            resource_policies[policy.resource_id] = policy

    transport_policy = _transport_policy_for_units(units)
    strategic_posture = (
        GENERAL_POSTURE_STAGE
        if current_round <= 1
        else GENERAL_POSTURE_PUSH if current_round <= 3 else GENERAL_POSTURE_PRESERVE
    )
    directives = _round_directives(current_round)
    return GeneralPlan(
        plan_id=f"general:{pid}:game",
        player_id=pid,
        created_at_generation=generation,
        strategic_posture=strategic_posture,
        battle_round_directives=directives,
        limited_resource_policy=resource_policies,
        resource_ledger=GeneralResourceLedger(
            resources=resource_policies,
            metadata={"source": "general_scaffold"},
        ),
        transport_policy=transport_policy,
        reserve_policy={
            "reserve_commitment_posture": "stage_until_round_2",
            "late_game_scoring_preservation": True,
        },
        target_priority_doctrine={
            "prefer_high_threat_scoring_targets": True,
            "authorize_limited_resources_threshold": 0.8,
        },
        cp_policy={
            "reserve_for_interrupt_or_overwatch": 1,
            "reserve_for_defensive_reaction": 1,
            "local_ranker_may_request_authorization": True,
        },
        dirty_flags=GeneralDirtyFlags(),
        metadata={
            "source": "general_scaffold",
            "friendly_unit_count": int(len(units)),
            "transport_policy_count": int(len(transport_policy)),
        },
    )
