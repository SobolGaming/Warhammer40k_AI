from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.movement import validate_move_unit_payload
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController
from warhammer40k_ai.engine.state_blob_units import unit_entries
from warhammer40k_ai.engine.game_mixins.missions_scoring_actions_mixin import (
    GameMissionsScoringActionsMixin,
)
from warhammer40k_ai.engine.game_mixins.setup_deployment_reserves_mixin import (
    GameSetupDeploymentReservesMixin,
)


class _ReserveRequestGame(GameSetupDeploymentReservesMixin):
    def __init__(self) -> None:
        self.turn = 3
        self.players = []


class _ReserveScoringGame(GameMissionsScoringActionsMixin):
    def __init__(self, players) -> None:
        self.turn = 3
        self.players = list(players or [])

    def award_vp(self, *_args, **_kwargs):
        return 0


def _build_reserve_unit():
    player = SimpleNamespace(id="player:one")
    player.name = "Player One"
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
        is_in_reserves=lambda: True,
        is_in_strategic_reserves=lambda: True,
        _started_in_reserves=True,
        special_rules={
            "reserve_source": "deployment_choice",
            "reserve_mandatory_start": False,
            "reserve_latest_arrival_round": 3,
            "reserve_last_arrival_failure": "previous_failure",
        },
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
    assert request.context["reserve_source"] == "deployment_choice"
    assert request.context["reserve_mandatory_start"] is False
    assert request.context["reserve_latest_arrival_round"] == 3
    assert request.context["reserve_last_arrival_failure"] == "previous_failure"


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


def test_headless_reserves_failure_records_structured_unit_metadata() -> None:
    _player, _army, unit = _build_reserve_unit()
    metric = {
        "anchor_attempts": 12,
        "build_calls": 4,
        "validation_rejects": 3,
        "quick_rejects": 5,
        "timed_out": True,
        "elapsed_ms": 250,
    }

    HeadlessPolicyDecisionController._record_reserves_arrival_failure(
        unit,
        reason="timed_out",
        metric=metric,
    )

    failure = unit.special_rules["reserve_last_arrival_failure"]
    assert failure == {
        "reason": "timed_out",
        "anchor_attempts": 12,
        "build_calls": 4,
        "validation_rejects": 3,
        "quick_rejects": 5,
        "timed_out": True,
        "elapsed_ms": 250,
    }
    assert unit.reserve_last_arrival_failure == failure


def test_round_three_reserve_destruction_records_visible_diagnostic() -> None:
    player, army, unit = _build_reserve_unit()
    player.get_army = lambda: army
    unit.reserve_last_arrival_failure = {
        "reason": "no_valid_arrival_position",
        "anchor_attempts": 7,
    }
    unit.special_rules["reserve_last_arrival_failure"] = dict(unit.reserve_last_arrival_failure)
    game = _ReserveScoringGame([player])

    game.end_of_battle_round_scoring()

    assert unit not in army.units
    assert game.reserve_arrival_diagnostics == [
        {
            "code": "reserve_destroyed_round3",
            "severity": "WARNING",
            "unit_id": "unit:one",
            "unit_name": "Stormraven Gunship",
            "player_id": "player:one",
            "battle_round": 3,
            "reserve_source": "deployment_choice",
            "reserve_mandatory_start": False,
            "reserve_latest_arrival_round": 3,
            "last_failed_placement_reason": {
                "reason": "no_valid_arrival_position",
                "anchor_attempts": 7,
            },
        }
    ]


def test_state_blob_units_include_reserve_arrival_metadata_for_owner() -> None:
    player, _army, unit = _build_reserve_unit()
    unit.reserve_last_arrival_failure = {
        "reason": "no_valid_arrival_position",
        "anchor_attempts": 7,
        "build_calls": 2,
        "validation_rejects": 1,
        "quick_rejects": 4,
        "timed_out": False,
        "elapsed_ms": 30,
    }
    unit.special_rules["reserve_last_arrival_failure"] = dict(unit.reserve_last_arrival_failure)
    game = SimpleNamespace(players=[player], map=SimpleNamespace(objectives=[]))

    entries = unit_entries(game, viewer_id=str(player.id), include_hidden=False)

    assert len(entries) == 1
    assert entries[0]["reserve_source"] == "deployment_choice"
    assert entries[0]["reserve_mandatory_start"] is False
    assert entries[0]["reserve_latest_arrival_round"] == 3
    assert entries[0]["reserve_last_arrival_failure"] == {
        "reason": "no_valid_arrival_position",
        "anchor_attempts": 7,
        "build_calls": 2,
        "validation_rejects": 1,
        "quick_rejects": 4,
        "timed_out": False,
        "elapsed_ms": 30,
    }
