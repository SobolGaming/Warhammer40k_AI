from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.movement import validate_move_unit_payload
from warhammer40k_ai.engine.game_mixins.setup_deployment_reserves_mixin import (
    GameSetupDeploymentReservesMixin,
)


class _ReserveRequestGame(GameSetupDeploymentReservesMixin):
    def __init__(self) -> None:
        self.turn = 3
        self.players = []


def _build_reserve_unit():
    player = SimpleNamespace(id="player:one")
    army = SimpleNamespace(player=player, units=[])
    model = SimpleNamespace(id="model:one", _id="model:one")
    unit = SimpleNamespace(
        id="unit:one",
        _id="unit:one",
        name="Stormraven Gunship",
        models=[model],
        reserve_status="strategic_reserves",
        get_parent_army=lambda: army,
        has_deep_strike=lambda: False,
        is_in_strategic_reserves=lambda: True,
    )
    army.units = [unit]
    player.army = army
    return player, army, unit


def test_forced_reserves_arrival_request_has_non_voluntary_failure_option() -> None:
    player, _army, unit = _build_reserve_unit()
    game = _ReserveRequestGame()
    game.players = [player]

    request = game._build_reserves_arrival_request(unit, allow_skip=False)

    assert request is not None
    assert request.context["allow_skip"] is False
    assert request.context["allow_forced_arrival_failure"] is True
    payloads = [dict(option.payload or {}) for option in list(request.options or [])]
    assert any(payload.get("action") == "confirm" for payload in payloads)
    assert any(
        payload.get("action") == "skip" and payload.get("forced_arrival_failed") is True
        for payload in payloads
    )


def test_forced_reserves_arrival_failure_skip_validates_only_with_failure_flag() -> None:
    player, army, unit = _build_reserve_unit()
    game = SimpleNamespace(players=[player], map=SimpleNamespace(units=[]))
    player.army = army

    request = _ReserveRequestGame()._build_reserves_arrival_request(unit, allow_skip=False)
    assert request is not None
    failure_option = next(
        option
        for option in list(request.options or [])
        if dict(option.payload or {}).get("forced_arrival_failed") is True
    )

    errors = validate_move_unit_payload(
        game,
        request,
        option_payload=dict(failure_option.payload or {}),
        result_payload={"skipped": True, "forced_arrival_failed": True},
    )

    assert errors == ()

    blocked_errors = validate_move_unit_payload(
        game,
        request,
        option_payload={"unit_id": unit.id, "movement_type": "deploy", "action": "skip"},
        result_payload={"skipped": True},
    )

    assert blocked_errors == ("Move unit: skipping is not allowed for this placement.",)
