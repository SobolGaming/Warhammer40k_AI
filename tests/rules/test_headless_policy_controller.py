from __future__ import annotations

from dataclasses import dataclass
import time

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_RESERVES,
    DECISION_MOVE_UNIT,
    DECISION_REQUEST_DICE_ROLL,
    DECISION_RESOLVE_COHERENCY,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
    DECISION_SELECT_UNIT,
)
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionRequest
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController


@dataclass(frozen=True)
class _ApplyResult:
    ok: bool = True


class _FakeGame:
    def __init__(self) -> None:
        self.is_authoritative = True
        self.commands = []

    def apply_command(self, command):
        self.commands.append(command)
        return _ApplyResult(ok=True)


def test_headless_policy_controller_picks_best_legal_candidate_and_applies_candidate_payload() -> None:
    game = _FakeGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    options = [
        DecisionOption.create("Option A", payload={"action_id": "a"}),
        DecisionOption.create("Option B", payload={"action_id": "b"}),
    ]
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Pick one",
        player_id="p1",
        options=options,
        candidates=[
            CandidateAction(action_id="a", params={"choice": "A"}, metadata={"projected_score_delta_next_window": 1.0}),
            CandidateAction(action_id="b", params={"choice": "B"}, metadata={"projected_score_delta_next_window": 3.0}),
        ],
        mask=[True, True],
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("option_id", "")) == str(options[1].option_id)
    assert dict(payload.get("result_payload", {}) or {}) == {"choice": "B"}


def test_headless_policy_controller_respects_mask_and_skips_illegal_candidates() -> None:
    game = _FakeGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    options = [
        DecisionOption.create("Option A", payload={"action_id": "a"}),
        DecisionOption.create("Option B", payload={"action_id": "b"}),
    ]
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Pick one",
        player_id="p1",
        options=options,
        candidates=[
            CandidateAction(action_id="a", params={"choice": "A"}, metadata={"projected_score_delta_next_window": 5.0}),
            CandidateAction(action_id="b", params={"choice": "B"}, metadata={"projected_score_delta_next_window": 1.0}),
        ],
        mask=[False, True],
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("option_id", "")) == str(options[1].option_id)
    assert dict(payload.get("result_payload", {}) or {}) == {"choice": "B"}


def test_headless_policy_controller_does_not_handle_dice_decisions() -> None:
    game = _FakeGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    request = DecisionRequest.create(
        DECISION_REQUEST_DICE_ROLL,
        "Roll",
        player_id="p1",
        options=[DecisionOption.create("Roll", payload={"action_id": "roll"})],
    )

    controller.on_decision_requested(game, request)

    assert game.commands == []


def test_headless_policy_controller_skips_deployment_manager_owned_setup_requests() -> None:
    game = _FakeGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    requests = [
        DecisionRequest.create(
            DECISION_CHOOSE_DEPLOYMENT_ZONE,
            "Choose zone",
            player_id="p1",
            options=[DecisionOption.create("Zone A", payload={"zone_name": "A"})],
            context={"decision_owner": "deployment_manager"},
        ),
        DecisionRequest.create(
            DECISION_DECLARE_RESERVES,
            "Declare reserves",
            player_id="p1",
            options=[DecisionOption.create("Deploy", payload={"unit_ids_by_bucket": {"deploy": ["unit:1"]}})],
            context={"decision_owner": "deployment_manager"},
        ),
        DecisionRequest.create(
            DECISION_SELECT_NEXT_DEPLOY_UNIT,
            "Choose unit",
            player_id="p1",
            options=[DecisionOption.create("Unit A", payload={"unit_id": "unit:1"})],
            context={"decision_owner": "deployment_manager"},
        ),
        DecisionRequest.create(
            DECISION_MOVE_UNIT,
            "Deploy unit",
            player_id="p1",
            options=[DecisionOption.create("Candidate A", payload={"action": "confirm"})],
            context={"decision_owner": "deployment_manager", "placement_kind": "deployment"},
        ),
    ]

    for request in requests:
        controller.on_decision_requested(game, request)

    assert game.commands == []


def test_headless_policy_controller_skips_non_authoritative_game_by_default() -> None:
    class _ObservedGame:
        is_authoritative = False

    game_proxy = _FakeGame()
    controller = HeadlessPolicyDecisionController(game=game_proxy, auto_attach=False)
    options = [
        DecisionOption.create("Option A", payload={"action_id": "a"}),
    ]
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Pick one",
        player_id="p1",
        options=options,
        candidates=[CandidateAction(action_id="a", params={"choice": "A"}, metadata={})],
        mask=[True],
    )

    controller.on_decision_requested(_ObservedGame(), request)

    assert game_proxy.commands == []


def test_headless_policy_controller_can_route_via_bound_game_in_non_authoritative_mode() -> None:
    class _ObservedGame:
        is_authoritative = False

    game_proxy = _FakeGame()
    controller = HeadlessPolicyDecisionController(
        game=game_proxy,
        auto_attach=False,
        require_authoritative=False,
    )
    options = [
        DecisionOption.create("Option A", payload={"action_id": "a"}),
    ]
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Pick one",
        player_id="p1",
        options=options,
        candidates=[CandidateAction(action_id="a", params={"choice": "A"}, metadata={})],
        mask=[True],
    )

    controller.on_decision_requested(_ObservedGame(), request)

    assert len(game_proxy.commands) == 1
    payload = dict(game_proxy.commands[0].payload or {})
    assert str(payload.get("option_id", "")) == str(options[0].option_id)
    assert dict(payload.get("result_payload", {}) or {}) == {"choice": "A"}


def test_headless_policy_controller_marks_skip_payload_when_falling_back_to_skip_option() -> None:
    class _SkipGame(_FakeGame):
        def apply_command(self, command):
            self.commands.append(command)
            payload = dict(command.payload or {})
            result_payload = dict(payload.get("result_payload", {}) or {})
            option_id = str(payload.get("option_id", "") or "")
            if option_id.endswith(":confirm"):
                return _ApplyResult(ok=False)
            return _ApplyResult(ok=bool(result_payload.get("skipped", False)))

    game = _SkipGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    options = [
        DecisionOption(option_id="opt:confirm", label="Confirm", payload={"action": "confirm", "action_id": "confirm"}),
        DecisionOption(option_id="opt:skip", label="Skip", payload={"action": "skip", "action_id": "skip"}),
    ]
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Resolve choice",
        player_id="p1",
        options=options,
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) >= 1
    found_skip = False
    for command in list(game.commands):
        payload = dict(command.payload or {})
        if str(payload.get("option_id", "")) != "opt:skip":
            continue
        result_payload = dict(payload.get("result_payload", {}) or {})
        if bool(result_payload.get("skipped", False)):
            found_skip = True
            break
    assert found_skip


def test_headless_policy_controller_resolves_coherency_with_model_ids_payload() -> None:
    class _CoherencyGame(_FakeGame):
        def apply_command(self, command):
            self.commands.append(command)
            payload = dict(command.payload or {})
            result_payload = dict(payload.get("result_payload", {}) or {})
            return _ApplyResult(ok=list(result_payload.get("model_ids", []) or []) == ["model:1"])

    game = _CoherencyGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    request = DecisionRequest.create(
        DECISION_RESOLVE_COHERENCY,
        "Remove one model",
        player_id="p1",
        options=[
            DecisionOption.create(
                "Model 1",
                payload={"model_id": "model:1", "model_ids": ["model:1"], "action_id": "cohere:model:1"},
            )
        ],
        context={"unit_id": "unit:1", "coherency_failure_reason": "post_casualty"},
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert dict(payload.get("result_payload", {}) or {})["model_ids"] == ["model:1"]


def test_headless_policy_controller_deprioritizes_move_units_pass_option() -> None:
    game = _FakeGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    request = DecisionRequest.create(
        DECISION_SELECT_UNIT,
        "Select a unit to act in Movement Phase / Move Units.",
        player_id="p1",
        options=[
            DecisionOption.create("Unit A", payload={"unit_id": "unit-a", "action_id": "select:unit-a"}),
            DecisionOption.create("Pass", payload={"action": "pass", "action_id": "select:pass"}),
        ],
        context={"phase_name": "MOVEMENT_PHASE", "phase_step": "MOVE_UNITS", "allow_pass": True},
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("option_id", "")) == str(request.options[0].option_id)
    assert dict(payload.get("result_payload", {}) or {}) == {"unit_id": "unit-a"}


def test_headless_policy_controller_deprioritizes_reinforcements_pass_option() -> None:
    game = _FakeGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    request = DecisionRequest.create(
        DECISION_SELECT_UNIT,
        "Select a unit to act in Movement Phase / Reinforcements.",
        player_id="p1",
        options=[
            DecisionOption.create("Unit A", payload={"unit_id": "unit-a", "action_id": "select:unit-a"}),
            DecisionOption.create("Pass", payload={"action": "pass", "action_id": "select:pass"}),
        ],
        context={"phase_name": "MOVEMENT_PHASE", "phase_step": "REINFORCEMENTS", "allow_pass": True},
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("option_id", "")) == str(request.options[0].option_id)
    assert dict(payload.get("result_payload", {}) or {}) == {"unit_id": "unit-a"}


def test_headless_policy_controller_bruteforces_reserves_arrival_when_solver_candidate_is_invalid() -> None:
    class _Base:
        def get_radius(self) -> float:
            return 0.5

    class _Model:
        def __init__(self, model_id: str) -> None:
            self._id = model_id
            self.id = model_id
            self.model_base = _Base()

    class _Unit:
        def __init__(self, unit_id: str, model_id: str) -> None:
            self._id = unit_id
            self.id = unit_id
            self.models = [_Model(model_id)]

        def is_in_strategic_reserves(self) -> bool:
            return True

        def calculate_model_positions(self, x, y, _game_map, avoid_friendly_units=False, boundary_repulsors=None):
            return [(float(x), float(y), 0.0, 0.0)]

    class _Army:
        def __init__(self, unit) -> None:
            self.units = [unit]

    class _Player:
        def __init__(self, army) -> None:
            self.army = army

    class _Map:
        width = 4.0
        height = 4.0

    class _Battlefield:
        width = 4.0
        height = 4.0

    class _ReservesGame:
        def __init__(self, unit) -> None:
            self.is_authoritative = True
            self.commands = []
            self.players = [_Player(_Army(unit))]
            self.map = _Map()
            self.battlefield = _Battlefield()

        def _resolve_unit_by_id(self, unit_id: str):
            for player in self.players:
                for candidate in player.army.units:
                    if str(getattr(candidate, "id", "")) == str(unit_id):
                        return candidate
            return None

        def get_boundary_repulsors(self, _unit, context=""):
            return None

        def apply_command(self, command):
            self.commands.append(command)
            payload = dict(command.payload or {})
            result_payload = dict(payload.get("result_payload", {}) or {})
            model_positions = list(result_payload.get("model_positions", []) or [])
            if not model_positions:
                return _ApplyResult(ok=False)
            pos = list(model_positions[0].get("position", []) or [])
            if len(pos) < 2:
                return _ApplyResult(ok=False)
            x = float(pos[0])
            y = float(pos[1])
            return _ApplyResult(ok=(abs(x - 0.0) < 1e-6 and abs(y - 0.0) < 1e-6))

    unit = _Unit("unit:1", "model:1")
    game = _ReservesGame(unit)
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    options = [
        DecisionOption(option_id="confirm", label="Confirm", payload={"action": "confirm", "action_id": "confirm"}),
    ]
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Arrive from Reserves",
        player_id="p1",
        options=options,
        context={
            "placement_kind": "reserves_arrival",
            "unit_id": "unit:1",
            "allow_skip": False,
        },
        candidates=[
            CandidateAction(
                action_id="confirm",
                params={
                    "action": "confirm",
                    "model_positions": [{"model_id": "model:1", "position": [9.0, 9.0, 0.0], "facing": 0.0}],
                },
                metadata={"projected_score_delta_next_window": 1.0},
            )
        ],
        mask=[True],
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) >= 2
    last_payload = dict(game.commands[-1].payload or {})
    last_result_payload = dict(last_payload.get("result_payload", {}) or {})
    pos = list(last_result_payload.get("model_positions", [{}])[0].get("position", []) or [])
    assert len(pos) >= 2
    assert abs(float(pos[0]) - 0.0) < 1e-6
    assert abs(float(pos[1]) - 0.0) < 1e-6


def test_headless_policy_controller_reserves_bruteforce_respects_timeout_budget() -> None:
    class _Model:
        def __init__(self, model_id: str) -> None:
            self._id = model_id
            self.id = model_id
            self.model_base = object()

    class _Unit:
        def __init__(self, unit_id: str, model_id: str) -> None:
            self._id = unit_id
            self.id = unit_id
            self.models = [_Model(model_id)]

        def is_in_strategic_reserves(self) -> bool:
            return True

    class _ReservesGame:
        def __init__(self, unit) -> None:
            self.is_authoritative = True
            self._unit = unit

        def _resolve_unit_by_id(self, unit_id: str):
            return self._unit if str(unit_id) == str(self._unit.id) else None

    unit = _Unit("unit:timeout", "model:timeout")
    game = _ReservesGame(unit)
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False, max_reserves_arrival_seconds=0.05)
    options = [
        DecisionOption(option_id="confirm", label="Confirm", payload={"action": "confirm", "action_id": "confirm"}),
    ]
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Arrive from Reserves",
        player_id="p1",
        options=options,
        context={"placement_kind": "reserves_arrival", "unit_id": "unit:timeout", "allow_skip": False},
    )

    controller._reserves_arrival_anchor_points = lambda _game, _unit: [(float(i), 0.0) for i in range(10_000)]  # type: ignore[method-assign]

    def _slow_fail(_game, _unit, *, x, y):
        time.sleep(0.01)
        return []

    controller._build_model_positions_from_anchor = _slow_fail  # type: ignore[method-assign]

    started = time.perf_counter()
    resolved = controller._try_resolve_reserves_arrival_bruteforce(game, request)
    elapsed = time.perf_counter() - started

    assert resolved is False
    assert elapsed < 0.5


def test_reserves_anchor_generation_is_bounded_and_deterministic_for_strategic_reserves() -> None:
    class _Base:
        has_circular_base = True

        def get_radius(self) -> float:
            return 0.5

    class _Model:
        def __init__(self, model_id: str) -> None:
            self._id = model_id
            self.id = model_id
            self.model_base = _Base()

    class _Unit:
        def __init__(self) -> None:
            self._id = "unit:strategic"
            self.id = "unit:strategic"
            self.models = [_Model("model:1")]

        def is_in_strategic_reserves(self) -> bool:
            return True

    class _Map:
        width = 60.0
        height = 44.0

    class _Battlefield:
        width = 60.0
        height = 44.0

    class _Game:
        map = _Map()
        battlefield = _Battlefield()

    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False, max_reserves_anchor_points=20000)
    unit = _Unit()
    game = _Game()

    first = controller._reserves_arrival_anchor_points(game, unit, context={"placement_kind": "reserves_arrival"})
    second = controller._reserves_arrival_anchor_points(game, unit, context={"placement_kind": "reserves_arrival"})

    assert first == second
    assert len(first) < 2500
    assert any(abs(x - 0.0) < 1e-6 and abs(y - 0.0) < 1e-6 for x, y in first)
