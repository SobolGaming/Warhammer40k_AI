from __future__ import annotations

from dataclasses import dataclass
import time

from shapely.geometry import Point

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_CHOOSE_MISSION,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_RESERVES,
    DECISION_DECLARE_SHOTS,
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


def test_headless_policy_controller_skips_driver_managed_mission_selection() -> None:
    game = _FakeGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    combo = {
        "id": "take_and_hold",
        "combination_id": "take_and_hold",
        "pack_id": "chapter_approved_2025_2026",
        "primary": "Take and Hold",
        "deployment": "Crucible of Battle",
        "layouts": [2],
    }
    request = DecisionRequest.create(
        DECISION_CHOOSE_MISSION,
        "Select a mission-pack entry and terrain layout.",
        player_id="p1",
        options=[DecisionOption.create("Take and Hold", payload={"combination": combo})],
    )

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


def test_headless_policy_controller_prunes_structurally_invalid_declare_shots_candidates() -> None:
    class _SkipGame(_FakeGame):
        def apply_command(self, command):
            self.commands.append(command)
            payload = dict(command.payload or {})
            result_payload = dict(payload.get("result_payload", {}) or {})
            return _ApplyResult(ok=bool(result_payload.get("skipped", False)))

    game = _SkipGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    options = [
        DecisionOption(
            option_id="opt:confirm",
            label="Confirm",
            payload={"action": "confirm", "action_id": "shoot:confirm"},
        ),
        DecisionOption(
            option_id="opt:skip",
            label="Skip",
            payload={"action": "skip", "action_id": "shoot:skip"},
        ),
    ]
    request = DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        "Declare shots",
        player_id="p1",
        options=options,
        context={"unit_id": "unit:1"},
        candidates=[
            CandidateAction(
                action_id="shoot:confirm",
                params={"action": "confirm"},
                metadata={"projected_score_delta_next_window": 5.0, "candidate_kind": "confirm"},
            ),
            CandidateAction(
                action_id="shoot:skip",
                params={"action": "skip"},
                metadata={"projected_score_delta_next_window": 0.0, "candidate_kind": "skip"},
            ),
        ],
        mask=[True, True],
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    result_payload = dict(payload.get("result_payload", {}) or {})
    metadata = dict(game.commands[0].metadata or {})
    assert str(payload.get("option_id", "")) == "opt:skip"
    assert result_payload == {"action": "skip", "skipped": True}
    assert metadata["candidate_action_id"] == "shoot:skip"
    assert metadata["candidate_kind"] == "skip"
    assert metadata["resolution_strategy"] == "ranked_candidate"


def test_headless_policy_controller_prunes_move_candidates_without_model_positions() -> None:
    class _SkipGame(_FakeGame):
        def apply_command(self, command):
            self.commands.append(command)
            payload = dict(command.payload or {})
            result_payload = dict(payload.get("result_payload", {}) or {})
            return _ApplyResult(ok=bool(result_payload.get("skipped", False)))

    game = _SkipGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    options = [
        DecisionOption(
            option_id="opt:confirm",
            label="Confirm",
            payload={"action": "confirm", "action_id": "move:confirm"},
        ),
        DecisionOption(
            option_id="opt:skip",
            label="Skip",
            payload={"action": "skip", "action_id": "move:skip"},
        ),
    ]
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move unit",
        player_id="p1",
        options=options,
        context={"unit_id": "unit:1", "allow_skip": True},
        candidates=[
            CandidateAction(
                action_id="move:confirm",
                params={"action": "confirm", "movement_type": "move", "unit_id": "unit:1"},
                metadata={"projected_score_delta_next_window": 5.0, "candidate_kind": "move"},
            ),
            CandidateAction(
                action_id="move:skip",
                params={"action": "skip"},
                metadata={"projected_score_delta_next_window": 0.0, "candidate_kind": "skip"},
            ),
        ],
        mask=[True, True],
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    result_payload = dict(payload.get("result_payload", {}) or {})
    metadata = dict(game.commands[0].metadata or {})
    assert str(payload.get("option_id", "")) == "opt:skip"
    assert result_payload == {"action": "skip", "skipped": True}
    assert metadata["candidate_action_id"] == "move:skip"
    assert metadata["candidate_kind"] == "skip"
    assert metadata["resolution_strategy"] == "ranked_candidate"


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


def test_headless_policy_controller_records_bounded_non_exhaustive_deep_strike_search() -> None:
    class _Base:
        has_circular_base = True

        def __init__(self, x: float, y: float, radius: float = 0.5) -> None:
            self.x = float(x)
            self.y = float(y)
            self.z = 0.0
            self._radius = float(radius)

        def get_radius(self) -> float:
            return float(self._radius)

        def get_longest_radius(self) -> float:
            return float(self._radius)

        def get_base_shape(self):
            return Point(float(self.x), float(self.y)).buffer(float(self._radius))

    class _Model:
        def __init__(self, model_id: str, *, x: float, y: float) -> None:
            self._id = model_id
            self.id = model_id
            self.model_base = _Base(x=float(x), y=float(y))
            self.is_alive = True

        def get_location(self) -> tuple[float, float, float, float]:
            return (float(self.model_base.x), float(self.model_base.y), 0.0, 0.0)

    class _Unit:
        def __init__(self, unit_id: str, *, reserve_status: str, x: float = 0.0, y: float = 0.0) -> None:
            self._id = unit_id
            self.id = unit_id
            self.name = unit_id
            self.reserve_status = reserve_status
            self.deployed = reserve_status == "deployed"
            self.embarked_in = None
            self.is_embarked = False
            self.models = [_Model(f"{unit_id}:model", x=float(x), y=float(y))]

        def get_parent_army(self):
            return self.parent_army

        def is_alive(self) -> bool:
            return True

        def is_in_strategic_reserves(self) -> bool:
            return False

        def calculate_model_positions(
            self,
            x: float,
            y: float,
            _game_map: object,
            *,
            avoid_friendly_units: bool = False,
            boundary_repulsors: object | None = None,
            search_context: object | None = None,
        ) -> list[tuple[float, float, float, float]]:
            del avoid_friendly_units, boundary_repulsors, search_context
            return [(float(x), float(y), 0.0, 0.0)]

    class _Army:
        def __init__(self, player, units) -> None:
            self.player = player
            self.units = list(units)

    class _Player:
        def __init__(self, player_id: str) -> None:
            self.id = player_id
            self.army = None

    class _Game:
        def __init__(self, arriving, enemies, *, success_xy: tuple[float, float]) -> None:
            self.is_authoritative = True
            self.turn = 2
            self.phase = type("Phase", (), {"name": "MOVEMENT_PHASE"})()
            self.ruleset_bundle = None
            self.map = type("Map", (), {"width": 60.0, "height": 44.0})()
            self.battlefield = type("Battlefield", (), {"width": 60.0, "height": 44.0})()
            self.players = [arriving.parent_army.player, enemies[0].parent_army.player]
            self.commands = []
            self._success_xy = (float(success_xy[0]), float(success_xy[1]))

        def _resolve_unit_by_id(self, unit_id: str):
            for player in self.players:
                for unit in player.army.units:
                    if str(getattr(unit, "id", "")) == str(unit_id):
                        return unit
            return None

        def get_boundary_repulsors(self, _unit, context=""):
            del context
            return []

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
            return _ApplyResult(
                ok=(
                    abs(float(pos[0]) - self._success_xy[0]) < 1e-6
                    and abs(float(pos[1]) - self._success_xy[1]) < 1e-6
                )
            )

    arriving_player = _Player("player:arriving")
    enemy_player = _Player("player:enemy")
    arriving = _Unit("unit:deep", reserve_status="reserves")
    enemies = [
        _Unit("enemy:center", reserve_status="deployed", x=30.0, y=22.0),
        _Unit("enemy:left", reserve_status="deployed", x=15.0, y=11.0),
        _Unit("enemy:right", reserve_status="deployed", x=15.0, y=33.0),
    ]
    arriving.parent_army = _Army(arriving_player, [arriving])
    arriving_player.army = arriving.parent_army
    enemy_army = _Army(enemy_player, enemies)
    enemy_player.army = enemy_army
    for enemy in enemies:
        enemy.parent_army = enemy_army

    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Arrive from Reserves",
        player_id="player:arriving",
        options=[DecisionOption(option_id="confirm", label="Confirm", payload={"action": "confirm", "action_id": "confirm"})],
        context={"placement_kind": "reserves_arrival", "unit_id": "unit:deep", "allow_skip": False},
    )
    game = _Game(arriving, enemies, success_xy=(45.0, 22.0))

    resolved = controller._try_resolve_reserves_arrival_bruteforce(game, request)

    assert resolved is True
    metric = controller.get_reserves_arrival_search_metrics()[-1]
    assert str(metric.get("first_valid_source", "") or "") == "board_landmarks"
    assert bool(metric.get("exhaustive_fallback_used", False)) is False
    assert int(metric.get("build_calls", 0) or 0) < 10


def test_headless_policy_controller_prefers_strategic_edge_band_before_exhaustive_fallback() -> None:
    class _Base:
        has_circular_base = True

        def __init__(self, radius: float = 0.5) -> None:
            self.x = 0.0
            self.y = 0.0
            self.z = 0.0
            self._radius = float(radius)

        def get_radius(self) -> float:
            return float(self._radius)

        def get_longest_radius(self) -> float:
            return float(self._radius)

    class _Model:
        def __init__(self, model_id: str) -> None:
            self._id = model_id
            self.id = model_id
            self.model_base = _Base()
            self.is_alive = True

    class _Unit:
        def __init__(self) -> None:
            self._id = "unit:strategic"
            self.id = "unit:strategic"
            self.name = "unit:strategic"
            self.reserve_status = "strategic_reserves"
            self.deployed = False
            self.embarked_in = None
            self.is_embarked = False
            self.models = [_Model("model:strategic")]

        def get_parent_army(self):
            return self.parent_army

        def is_alive(self) -> bool:
            return True

        def is_in_strategic_reserves(self) -> bool:
            return True

        def calculate_model_positions(
            self,
            x: float,
            y: float,
            _game_map: object,
            *,
            avoid_friendly_units: bool = False,
            boundary_repulsors: object | None = None,
            search_context: object | None = None,
        ) -> list[tuple[float, float, float, float]]:
            del avoid_friendly_units, boundary_repulsors, search_context
            return [(float(x), float(y), 0.0, 0.0)]

    class _Army:
        def __init__(self, player, units) -> None:
            self.player = player
            self.units = list(units)

    class _Player:
        def __init__(self, player_id: str) -> None:
            self.id = player_id
            self.army = None

    class _Game:
        def __init__(self, unit, *, success_xy: tuple[float, float]) -> None:
            self.is_authoritative = True
            self.turn = 2
            self.phase = type("Phase", (), {"name": "MOVEMENT_PHASE"})()
            self.ruleset_bundle = None
            self.map = type("Map", (), {"width": 60.0, "height": 44.0})()
            self.battlefield = type("Battlefield", (), {"width": 60.0, "height": 44.0})()
            self.players = [unit.parent_army.player]
            self.commands = []
            self._success_xy = (float(success_xy[0]), float(success_xy[1]))

        def _resolve_unit_by_id(self, unit_id: str):
            for player in self.players:
                for candidate in player.army.units:
                    if str(getattr(candidate, "id", "")) == str(unit_id):
                        return candidate
            return None

        def get_boundary_repulsors(self, _unit, context=""):
            del context
            return []

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
            return _ApplyResult(
                ok=(
                    abs(float(pos[0]) - self._success_xy[0]) < 1e-6
                    and abs(float(pos[1]) - self._success_xy[1]) < 1e-6
                )
            )

    player = _Player("player:strategic")
    unit = _Unit()
    unit.parent_army = _Army(player, [unit])
    player.army = unit.parent_army
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    preferred_offset = controller._strategic_edge_offset_preference(unit)
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Arrive from Strategic Reserves",
        player_id="player:strategic",
        options=[DecisionOption(option_id="confirm", label="Confirm", payload={"action": "confirm", "action_id": "confirm"})],
        context={"placement_kind": "reserves_arrival", "unit_id": "unit:strategic", "allow_skip": False},
    )
    game = _Game(unit, success_xy=(0.0, preferred_offset))

    resolved = controller._try_resolve_reserves_arrival_bruteforce(game, request)

    assert resolved is True
    metric = controller.get_reserves_arrival_search_metrics()[-1]
    assert str(metric.get("first_valid_source", "") or "") == "strategic_edge_band"
    assert bool(metric.get("exhaustive_fallback_used", False)) is False
