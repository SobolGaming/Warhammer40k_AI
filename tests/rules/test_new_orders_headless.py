from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.abilities import (
    _apply_discard_secondary,
    _validate_discard_secondary,
)
from warhammer40k_ai.engine.decision_kinds import DECISION_DISCARD_SECONDARY
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionQueue, DecisionRequest, DecisionResult
from warhammer40k_ai.rules.stratagems import StratagemManager


def _new_orders_request(*, player_id: str, card_name: str = "Cleanse") -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_DISCARD_SECONDARY,
        "NEW ORDERS: discard one active Secondary Mission card and draw a new one.",
        player_id=player_id,
        options=[
            DecisionOption.create(
                card_name,
                payload={
                    "card_name": card_name,
                    "card_slot": 0,
                    "ability_key": "new_orders",
                    "stratagem_name": "NEW ORDERS",
                },
            ),
            DecisionOption.create(
                "Do not use",
                payload={
                    "action": "skip",
                    "skip": True,
                    "ability_key": "new_orders",
                    "stratagem_name": "NEW ORDERS",
                },
            ),
        ],
        context={
            "ability": "new_orders",
            "phase_name": "Command phase",
            "stratagem_name": "NEW ORDERS",
            "optional": True,
        },
    )


def test_queue_new_orders_decision_publishes_optional_discard_request() -> None:
    manager = StratagemManager.__new__(StratagemManager)
    decision_queue = DecisionQueue()
    game = SimpleNamespace(
        is_authoritative=True,
        decision_queue=decision_queue,
        request_decision=decision_queue.add,
    )
    active_secondaries = [
        SimpleNamespace(name="Cleanse"),
        SimpleNamespace(name="Secure No Man's Land"),
    ]
    player = SimpleNamespace(
        id="player:new-orders",
        active_secondaries=active_secondaries,
        can_draw_secondary=lambda: True,
    )
    stratagem = SimpleNamespace(name="NEW ORDERS", cp_cost=1, can_use=lambda *_args, **_kwargs: True)
    manager.game = game
    manager.player = player
    manager.get_by_name = lambda name: stratagem if str(name or "").upper() == "NEW ORDERS" else None

    assert manager._queue_new_orders_decision(phase_name="Command phase") is True
    pending = list(decision_queue.list() or [])
    assert len(pending) == 1

    request = pending[0]
    assert request.decision_type == DECISION_DISCARD_SECONDARY
    assert request.context["ability"] == "new_orders"
    assert request.context["tool_id"] == "stratagem:new_orders"
    assert request.context["optional"] is True
    payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    assert [payload.get("card_name") for payload in payloads[:-1]] == [
        "Cleanse",
        "Secure No Man's Land",
    ]
    assert str(payloads[-1].get("action", "")) == "skip"

    assert manager._queue_new_orders_decision(phase_name="Command phase") is False
    assert len(list(decision_queue.list() or [])) == 1


def test_queue_new_orders_decision_respects_once_per_battle_ledger() -> None:
    manager = StratagemManager.__new__(StratagemManager)
    decision_queue = DecisionQueue()
    game = SimpleNamespace(
        is_authoritative=True,
        decision_queue=decision_queue,
        request_decision=decision_queue.add,
    )
    player = SimpleNamespace(
        id="player:new-orders",
        active_secondaries=[SimpleNamespace(name="Cleanse")],
        can_draw_secondary=lambda: True,
    )
    stratagem = SimpleNamespace(name="NEW ORDERS", cp_cost=1, can_use=lambda *_args, **_kwargs: True)
    manager.game = game
    manager.player = player
    manager._used_once_per_battle = {"NEW ORDERS": True}
    manager.get_by_name = lambda name: stratagem if str(name or "").upper() == "NEW ORDERS" else None

    assert manager._queue_new_orders_decision(phase_name="Command phase") is False
    assert list(decision_queue.list() or []) == []


def test_apply_discard_secondary_uses_new_orders_stratagem() -> None:
    card = SimpleNamespace(name="Cleanse")
    calls: list[tuple[str, dict]] = []
    manager = SimpleNamespace(
        use=lambda name, **kwargs: calls.append((name, dict(kwargs))) or True,
        _dequeue_reaction_by_name=lambda *_args, **_kwargs: None,
    )
    player = SimpleNamespace(id="player:new-orders", active_secondaries=[card], stratagems=manager)
    game = SimpleNamespace(players=[player])
    request = _new_orders_request(player_id=player.id, card_name=card.name)
    choice = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("card_name", "") or "") == card.name
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=choice.option_id,
        payload={},
    )

    assert _validate_discard_secondary(game, request, result) == ()
    assert _apply_discard_secondary(game, request, result) is card
    assert calls == [
        (
            "NEW ORDERS",
            {
                "secondary_card": card,
                "phase_name": "Command phase",
                "dequeue": True,
            },
        )
    ]


def test_validate_discard_secondary_rejects_unavailable_new_orders() -> None:
    card = SimpleNamespace(name="Cleanse")
    manager = SimpleNamespace(can_use=lambda *_args, **_kwargs: False)
    player = SimpleNamespace(id="player:new-orders", active_secondaries=[card], stratagems=manager)
    game = SimpleNamespace(players=[player])
    request = _new_orders_request(player_id=player.id, card_name=card.name)
    choice = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("card_name", "") or "") == card.name
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=choice.option_id,
        payload={},
    )

    assert _validate_discard_secondary(game, request, result) == ("New Orders stratagem is not available.",)


def test_apply_discard_secondary_skip_clears_pending_new_orders_reaction() -> None:
    dequeued: list[str] = []
    manager = SimpleNamespace(
        use=lambda *_args, **_kwargs: True,
        _dequeue_reaction_by_name=lambda name: dequeued.append(str(name)),
    )
    player = SimpleNamespace(
        id="player:new-orders",
        active_secondaries=[SimpleNamespace(name="Cleanse")],
        stratagems=manager,
    )
    game = SimpleNamespace(players=[player])
    request = _new_orders_request(player_id=player.id)
    skip_option = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("action", "") or "") == "skip"
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=skip_option.option_id,
        payload={"skipped": True},
    )

    assert _validate_discard_secondary(game, request, result) == ()
    assert _apply_discard_secondary(game, request, result) is None
    assert dequeued == ["NEW ORDERS"]
