from __future__ import annotations

from typing import Iterable, List, Optional

from .decisions import DecisionOption, DecisionRequest
from .decision_kinds import (
    DECISION_ATTACH_LEADER,
    DECISION_ATTACH_SUPPORT_ARTILLERY,
    DECISION_ASSIGN_TRANSPORT,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_RESERVES,
    DECISION_SCOUT_MOVE,
)
from ..utility.entity_ids import get_entity_id


def _iter_units(units: Iterable[object] | None) -> List[object]:
    return [u for u in list(units or []) if u is not None]


def _player_id_for_unit(unit: object) -> Optional[str]:
    try:
        army = unit.get_parent_army()
    except Exception:
        army = getattr(unit, "parent_army", None)
    if army is None:
        return None
    try:
        player = getattr(army, "player", None)
    except Exception:
        player = None
    return getattr(player, "id", None) if player is not None else None


def _player_for_unit(unit: object):
    try:
        army = unit.get_parent_army()
    except Exception:
        army = getattr(unit, "parent_army", None)
    if army is None:
        return None
    return getattr(army, "player", None)


def _leader_attachment_options(leader, bodyguards: List[object]) -> List[DecisionOption]:
    leader_id = get_entity_id(leader)
    options = [DecisionOption.create("Unattached", payload={"leader_id": leader_id, "bodyguard_id": None})]
    current = getattr(leader, "attached_to", None)
    for bg in bodyguards:
        try:
            if not leader.can_attach_to(bg):
                continue
        except Exception:
            continue
        if bg is not current:
            try:
                max_leaders = int(bg.max_attached_leaders())
            except Exception:
                max_leaders = 1
            try:
                current_leaders = list(getattr(bg, "attached_leaders", []) or [])
            except Exception:
                current_leaders = []
            if len(current_leaders) >= max_leaders:
                continue
        label = str(getattr(bg, "name", "Bodyguard"))
        options.append(
            DecisionOption.create(
                label,
                payload={"leader_id": leader_id, "bodyguard_id": get_entity_id(bg)},
            )
        )
    return options


def build_leader_attachment_requests(
    game: object,
    units: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_units = _iter_units(units)
    leaders = [u for u in all_units if bool(getattr(u, "is_leader", False))]
    bodyguards = [
        u for u in all_units
        if not bool(getattr(u, "is_leader", False))
        and not bool(getattr(u, "is_joined_support", False))
    ]
    requests: List[DecisionRequest] = []
    for leader in leaders:
        options = _leader_attachment_options(leader, bodyguards)
        prompt = f"Attach leader {getattr(leader, 'name', 'Leader')}"
        request = DecisionRequest.create(
            DECISION_ATTACH_LEADER,
            prompt,
            player_id=_player_id_for_unit(leader),
            options=options,
            context={"leader_id": get_entity_id(leader)},
        )
        requests.append(request)
        if queue_requests and hasattr(game, "request_decision"):
            game.request_decision(request)
    return requests


def _support_artillery_attachment_options(support_unit, bodyguards: List[object]) -> List[DecisionOption]:
    support_id = get_entity_id(support_unit)
    options = [DecisionOption.create("Unattached", payload={"support_unit_id": support_id, "bodyguard_id": None})]
    current = getattr(support_unit, "support_joined_to", None)
    for bg in bodyguards:
        try:
            if not support_unit.can_join_support_artillery(bg):
                continue
        except Exception:
            continue
        if bg is not current:
            try:
                supports = list(getattr(bg, "attached_support_units", []) or [])
            except Exception:
                supports = []
            if supports:
                continue
        label = str(getattr(bg, "name", "Bodyguard"))
        options.append(
            DecisionOption.create(
                label,
                payload={"support_unit_id": support_id, "bodyguard_id": get_entity_id(bg)},
            )
        )
    return options


def build_support_artillery_attachment_requests(
    game: object,
    units: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_units = _iter_units(units)
    supports = [
        u for u in all_units
        if bool(getattr(u, "has_support_artillery_ability", lambda: False)())
    ]
    bodyguards = [u for u in all_units if bool(getattr(u, "is_guardian_defenders_unit", lambda: False)())]
    requests: List[DecisionRequest] = []
    for support_unit in supports:
        options = _support_artillery_attachment_options(support_unit, bodyguards)
        prompt = f"Attach support weapon {getattr(support_unit, 'name', 'Support Weapon')}"
        request = DecisionRequest.create(
            DECISION_ATTACH_SUPPORT_ARTILLERY,
            prompt,
            player_id=_player_id_for_unit(support_unit),
            options=options,
            context={"support_unit_id": get_entity_id(support_unit)},
        )
        requests.append(request)
        if queue_requests and hasattr(game, "request_decision"):
            game.request_decision(request)
    return requests


def build_transport_assignment_requests(
    game: object,
    units: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_units = _iter_units(units)
    transports = [u for u in all_units if bool(getattr(u, "is_transport", False))]
    requests: List[DecisionRequest] = []
    for unit in all_units:
        if bool(getattr(unit, "is_transport", False)):
            continue
        if bool(getattr(unit, "is_attached_leader", False)):
            continue
        if bool(getattr(unit, "is_joined_support", False)):
            continue
        if getattr(unit, "deployed", False):
            continue
        options = [
            DecisionOption.create(
                "No transport",
                payload={"unit_id": get_entity_id(unit), "transport_id": None},
            )
        ]
        for transport in transports:
            try:
                if not transport.can_transport(unit):
                    continue
            except Exception:
                continue
            label = str(getattr(transport, "name", "Transport"))
            options.append(
                DecisionOption.create(
                    label,
                    payload={"unit_id": get_entity_id(unit), "transport_id": get_entity_id(transport)},
                )
            )
        if len(options) <= 1:
            continue
        prompt = f"Assign transport for {getattr(unit, 'name', 'Unit')}"
        request = DecisionRequest.create(
            DECISION_ASSIGN_TRANSPORT,
            prompt,
            player_id=_player_id_for_unit(unit),
            options=options,
            context={"unit_id": get_entity_id(unit)},
        )
        requests.append(request)
        if queue_requests and hasattr(game, "request_decision"):
            game.request_decision(request)
    return requests


def build_reserves_allocation_request(
    game: object,
    army: object,
    *,
    queue_requests: bool = True,
) -> Optional[DecisionRequest]:
    if army is None:
        return None
    player = getattr(army, "player", None)
    player_id = getattr(player, "id", None) if player is not None else None
    option = DecisionOption.create("Confirm reserves")
    request = DecisionRequest.create(
        DECISION_DECLARE_RESERVES,
        "Allocate reserves for this army.",
        player_id=player_id,
        options=[option],
        context={"army_id": get_entity_id(army)},
    )
    if queue_requests and hasattr(game, "request_decision"):
        game.request_decision(request)
    return request


def build_hover_mode_requests(
    game: object,
    units: Iterable[object],
    *,
    queue_requests: bool = True,
) -> List[DecisionRequest]:
    all_units = _iter_units(units)
    requests: List[DecisionRequest] = []
    for unit in all_units:
        if bool(getattr(unit, "hover_declared", False)):
            continue
        has_hover = getattr(unit, "has_hover", None)
        if not callable(has_hover) or not has_hover():
            continue
        has_keyword = getattr(unit, "has_keyword", None)
        if not callable(has_keyword) or not has_keyword("Aircraft"):
            continue
        unit_id = get_entity_id(unit)
        player = _player_for_unit(unit)
        player_id = _player_id_for_unit(unit)
        player_name = str(getattr(player, "name", "Player") or "Player")
        unit_name = str(getattr(unit, "name", "Unit") or "Unit")
        message = (
            f"Enable Hover mode for {unit_name} ({player_name})?\n\n"
            "Hover removes the AIRCRAFT keyword and sets Move to 20\"."
        )
        options = [
            DecisionOption.create("Hover", payload={"choice": True, "unit_id": unit_id}),
            DecisionOption.create("Aircraft", payload={"choice": False, "unit_id": unit_id}),
        ]
        request = DecisionRequest.create(
            DECISION_CONFIRM_YES_NO,
            "Hover Mode",
            player_id=player_id,
            options=options,
            context={"ability": "hover_mode", "unit_id": unit_id, "message": message},
        )
        requests.append(request)
        if queue_requests and hasattr(game, "request_decision"):
            game.request_decision(request)
    return requests


def build_scout_move_request(game: object, unit: object) -> Optional[DecisionRequest]:
    if unit is None:
        return None
    unit_id = get_entity_id(unit)
    options = [
        DecisionOption.create(
            "Scout move",
            payload={"unit_id": unit_id, "action": "scout"},
        ),
        DecisionOption.create(
            "Skip scout move",
            payload={"unit_id": unit_id, "action": "skip"},
        ),
    ]
    prompt = f"Scout move for {getattr(unit, 'name', 'Unit')}"
    request = DecisionRequest.create(
        DECISION_SCOUT_MOVE,
        prompt,
        player_id=_player_id_for_unit(unit),
        options=options,
        context={"unit_id": unit_id},
    )
    if hasattr(game, "request_decision"):
        game.request_decision(request)
    return request
