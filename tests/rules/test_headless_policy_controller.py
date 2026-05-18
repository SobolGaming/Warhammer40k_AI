from __future__ import annotations

from dataclasses import dataclass
import time

from shapely.geometry import Point

import warhammer40k_ai.engine.headless_policy_controller as headless_policy_module
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_ATTACH_LEADER,
    DECISION_ATTACH_SUPPORT_ARTILLERY,
    DECISION_ASSIGN_TRANSPORT,
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_CHOOSE_MISSION,
    DECISION_CHOOSE_PLAYER_COLOR,
    DECISION_CHOOSE_SETUP_REACTIVE_ACTION,
    DECISION_CHOOSE_START_OF_BATTLE_KEYWORD,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_RESERVES,
    DECISION_DECLARE_SHOTS,
    DECISION_DISCARD_SECONDARY,
    DECISION_MOVE_UNIT,
    DECISION_REQUEST_DICE_ROLL,
    DECISION_RESOLVE_COHERENCY,
    DECISION_SCOUT_MOVE,
    DECISION_SELECT_REALM_OF_CHAOS_UNITS,
    DECISION_SELECT_SETUP_REACTIVE_TARGET,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
    DECISION_SELECT_UNIT,
    DECISION_SHADOW_ASSIGNMENT,
)
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionQueue, DecisionRequest
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


class _QueuePoppingFakeGame:
    def __init__(self, request: DecisionRequest) -> None:
        self.is_authoritative = True
        self.commands = []
        self.decision_queue = DecisionQueue()
        self.decision_queue.add(request)

    def apply_command(self, command):
        self.commands.append(command)
        payload = dict(getattr(command, "payload", {}) or {})
        self.decision_queue.pop(str(payload.get("decision_id", "") or ""))
        return _ApplyResult(ok=False)


def test_headless_policy_stops_retrying_when_apply_side_effect_removes_request() -> None:
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Choose once",
        player_id="p1",
        options=[
            DecisionOption.create("Alpha", payload={"action_id": "TEST:alpha", "choice": True}),
            DecisionOption.create("Beta", payload={"action_id": "TEST:beta", "choice": False}),
        ],
        candidates=[
            CandidateAction("TEST:alpha", {"choice": True}, metadata={"projected_score_delta_round": 1.0}),
            CandidateAction("TEST:beta", {"choice": False}, metadata={"projected_score_delta_round": 0.0}),
        ],
        mask=[True, True],
    )
    game = _QueuePoppingFakeGame(request)
    controller = HeadlessPolicyDecisionController(auto_attach=False)

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    assert game.decision_queue.get(request.decision_id) is None


class _ReserveSearchBase:
    has_circular_base = True

    def __init__(self, x: float = 0.0, y: float = 0.0, *, radius: float = 0.5, z: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.facing = 0.0
        self._radius = float(radius)

    def get_radius(self) -> float:
        return float(self._radius)

    def get_longest_radius(self) -> float:
        return float(self._radius)

    def get_base_shape(self):
        return Point(float(self.x), float(self.y)).buffer(float(self._radius))


class _ReserveSearchModel:
    def __init__(self, model_id: str, *, x: float = 0.0, y: float = 0.0, radius: float = 0.5) -> None:
        self._id = model_id
        self.id = model_id
        self.model_base = _ReserveSearchBase(x=float(x), y=float(y), radius=radius)
        self.is_alive = True
        self.parent_unit = None

    def get_location(self) -> tuple[float, float, float, float]:
        return (
            float(self.model_base.x),
            float(self.model_base.y),
            float(self.model_base.z),
            float(self.model_base.facing),
        )

    def set_location(self, x: float, y: float, z: float, facing: float) -> None:
        self.model_base.x = float(x)
        self.model_base.y = float(y)
        self.model_base.z = float(z)
        self.model_base.facing = float(facing)


class _ReserveSearchUnit:
    def __init__(
        self,
        unit_id: str,
        *,
        reserve_status: str,
        strategic: bool,
        deep_strike: bool,
        x: float = 0.0,
        y: float = 0.0,
    ) -> None:
        self._id = unit_id
        self.id = unit_id
        self.name = unit_id
        self.reserve_status = reserve_status
        self.deployed = reserve_status == "deployed"
        self.embarked_in = None
        self.is_embarked = False
        self.parent_army = None
        self._strategic = bool(strategic)
        self._deep_strike = bool(deep_strike)
        self.models = [_ReserveSearchModel(f"{unit_id}:model", x=float(x), y=float(y))]
        for model in self.models:
            model.parent_unit = self

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_models(self):
        return list(self.models)

    def is_alive(self) -> bool:
        return True

    def is_in_reserves(self) -> bool:
        return str(self.reserve_status or "").strip().lower() != "deployed"

    def can_arrive_from_reserves(self, _turn: int) -> bool:
        return True

    def is_in_strategic_reserves(self) -> bool:
        return bool(self._strategic)

    def has_deep_strike(self) -> bool:
        return bool(self._deep_strike)

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

    def _create_potential_base(
        self,
        x: float,
        y: float,
        z: float,
        facing: float,
        *,
        model: _ReserveSearchModel | None = None,
    ) -> _ReserveSearchBase:
        radius = float(model.model_base.get_radius()) if model is not None else 0.5
        base = _ReserveSearchBase(float(x), float(y), radius=radius, z=float(z))
        base.facing = float(facing)
        return base


class _ReserveSearchArmy:
    def __init__(self, player, units) -> None:
        self.player = player
        self.units = list(units)


class _ReserveSearchPlayer:
    def __init__(self, player_id: str) -> None:
        self.id = player_id
        self.army = None


class _ReserveSearchMap:
    terrain_features: list[object] = []

    def __init__(self, width: float, height: float, units: list[object]) -> None:
        self.width = float(width)
        self.height = float(height)
        self.units = list(units)

    def get_height_at_point(self, _x: float, _y: float) -> float:
        return 0.0

    def is_within_boundary(self, _model: object, destination: tuple[float, float]) -> bool:
        x, y = destination
        return 0.0 <= float(x) <= float(self.width) and 0.0 <= float(y) <= float(self.height)

    def check_collision_with_obstacles(self, _model: object, destination: tuple[float, float]) -> bool:
        del destination
        return False


class _ReserveSearchGame:
    def __init__(
        self,
        arriving_unit: _ReserveSearchUnit,
        *,
        success_xy: tuple[float, float],
        friendly_units: list[_ReserveSearchUnit] | None = None,
        enemy_units: list[_ReserveSearchUnit] | None = None,
        width: float = 60.0,
        height: float = 44.0,
    ) -> None:
        self.is_authoritative = True
        self.turn = 2
        self.phase = type("Phase", (), {"name": "MOVEMENT_PHASE"})()
        self.current_player_index = 0
        self.commands: list[object] = []
        self._success_xy = (float(success_xy[0]), float(success_xy[1]))

        self.players = [_ReserveSearchPlayer("player:arriving"), _ReserveSearchPlayer("player:enemy")]
        own_units = [arriving_unit] + list(friendly_units or [])
        enemy_pool = list(enemy_units or [])
        own_army = _ReserveSearchArmy(self.players[0], own_units)
        enemy_army = _ReserveSearchArmy(self.players[1], enemy_pool)
        self.players[0].army = own_army
        self.players[1].army = enemy_army
        for unit in own_units:
            unit.parent_army = own_army
        for unit in enemy_pool:
            unit.parent_army = enemy_army

        self.map = _ReserveSearchMap(float(width), float(height), own_units + enemy_pool)
        self.battlefield = type("Battlefield", (), {"width": float(width), "height": float(height)})()

    def _resolve_unit_by_id(self, unit_id: str):
        for player in self.players:
            for candidate in player.army.units:
                if str(getattr(candidate, "id", "")) == str(unit_id):
                    return candidate
        return None

    def get_boundary_repulsors(self, _unit, context=""):
        del context
        return []

    def get_current_player(self):
        return self.players[self.current_player_index]

    def get_enemy_units(self, player):
        if player is self.players[0]:
            return list(self.players[1].army.units)
        return list(self.players[0].army.units)

    def is_valid_strategic_reserves_edge(self, edge: str, *, turn: int | None = None) -> bool:
        del edge, turn
        return True

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


def _build_reserves_search_fixture(
    *,
    strategic: bool,
    deep_strike: bool,
    success_xy: tuple[float, float],
    friendly_positions: tuple[tuple[float, float], ...] = (),
    enemy_positions: tuple[tuple[float, float], ...] = (),
) -> tuple[_ReserveSearchGame, _ReserveSearchUnit, DecisionRequest]:
    arriving = _ReserveSearchUnit(
        "unit:arriving",
        reserve_status="strategic_reserves" if strategic else "reserves",
        strategic=bool(strategic),
        deep_strike=bool(deep_strike),
    )
    friendly_units = [
        _ReserveSearchUnit(
            f"unit:friendly:{idx}",
            reserve_status="deployed",
            strategic=False,
            deep_strike=False,
            x=float(x),
            y=float(y),
        )
        for idx, (x, y) in enumerate(list(friendly_positions or ()))
    ]
    enemy_units = [
        _ReserveSearchUnit(
            f"unit:enemy:{idx}",
            reserve_status="deployed",
            strategic=False,
            deep_strike=False,
            x=float(x),
            y=float(y),
        )
        for idx, (x, y) in enumerate(list(enemy_positions or ()))
    ]
    game = _ReserveSearchGame(
        arriving,
        success_xy=(float(success_xy[0]), float(success_xy[1])),
        friendly_units=friendly_units,
        enemy_units=enemy_units,
    )
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Arrive from Reserves",
        player_id="player:arriving",
        options=[DecisionOption(option_id="confirm", label="Confirm", payload={"action": "confirm", "action_id": "confirm"})],
        context={"placement_kind": "reserves_arrival", "unit_id": arriving.id, "allow_skip": False},
    )
    return game, arriving, request


def test_headless_policy_controller_can_disable_generic_tool_decisions() -> None:
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False, enable_tool_decisions=False)

    assert controller.supports_generic_tool_decisions() is False


def test_headless_policy_synthesizes_required_realm_unit_selection() -> None:
    game = _FakeGame()
    request = DecisionRequest.create(
        DECISION_SELECT_REALM_OF_CHAOS_UNITS,
        "Select one required unit.",
        player_id="player-1",
        options=[DecisionOption.create("Confirm", payload={"action": "confirm"})],
        context={
            "ability": "siege_regiment_creeping_barrage_selection",
            "allowed_unit_ids": ["unit-b", "unit-a"],
            "max_units": 1,
            "required_units": 1,
        },
    )
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    command = game.commands[0]
    assert command.payload["result_payload"]["unit_ids"] == ["unit-b"]


def test_headless_policy_skips_optional_realm_selection_without_empty_confirm() -> None:
    game = _FakeGame()
    request = DecisionRequest.create(
        DECISION_SELECT_REALM_OF_CHAOS_UNITS,
        "Select optional units.",
        player_id="player-1",
        options=[
            DecisionOption.create("Confirm", payload={"action": "confirm"}),
            DecisionOption.create("None", payload={"action": "skip"}),
        ],
        context={
            "ability": "deceptors_masters_of_misdirection_selection",
            "allowed_unit_ids": ["unit-1", "unit-2"],
            "max_units": 2,
        },
    )
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    command = game.commands[0]
    assert command.payload["result_payload"]["action"] == "skip"
    assert command.payload["result_payload"]["skipped"] is True


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


def test_headless_policy_controller_can_ignore_ai_orchestrator_for_decision_type() -> None:
    class _PreferFirstOrchestrator:
        def rank_legal_candidates(self, request, *, fallback_order=None):
            del request
            candidates = list(fallback_order or [])
            return sorted(candidates, key=lambda candidate: str(candidate.action_id) != "a")

    game = _FakeGame()
    controller = HeadlessPolicyDecisionController(
        game=None,
        auto_attach=False,
        ai_orchestrator=_PreferFirstOrchestrator(),
        ai_orchestrator_ignored_decision_types=[DECISION_CONFIRM_YES_NO],
    )
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


def test_headless_policy_controller_can_force_skip_for_decision_type() -> None:
    class _PreferDiscardOrchestrator:
        def rank_legal_candidates(self, request, *, fallback_order=None):
            del request
            candidates = list(fallback_order or [])
            return sorted(candidates, key=lambda candidate: str(candidate.action_id) != "discard")

    game = _FakeGame()
    controller = HeadlessPolicyDecisionController(
        game=None,
        auto_attach=False,
        ai_orchestrator=_PreferDiscardOrchestrator(),
        force_skip_decision_types=[DECISION_DISCARD_SECONDARY],
    )
    options = [
        DecisionOption.create("Discard Cleanse", payload={"action_id": "discard", "card_name": "Cleanse"}),
        DecisionOption.create("Do not use", payload={"action_id": "skip", "action": "skip", "skip": True}),
    ]
    request = DecisionRequest.create(
        DECISION_DISCARD_SECONDARY,
        "NEW ORDERS: discard one active Secondary Mission card and draw a new one.",
        player_id="p1",
        options=options,
        context={"ability": "new_orders", "optional": True},
        candidates=[
            CandidateAction(
                action_id="discard",
                params={"card_name": "Cleanse"},
                metadata={"projected_score_delta_next_window": 10.0},
            ),
            CandidateAction(
                action_id="skip",
                params={"action": "skip", "skip": True},
                metadata={"projected_score_delta_next_window": 0.0},
            ),
        ],
        mask=[True, True],
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("option_id", "")) == str(options[1].option_id)
    result_payload = dict(payload.get("result_payload", {}) or {})
    assert result_payload["action"] == "skip"
    assert result_payload["skip"] is True
    assert result_payload["skipped"] is True


def test_headless_policy_controller_can_ignore_ai_orchestrator_for_setup_context() -> None:
    class _PreferFirstOrchestrator:
        def rank_legal_candidates(self, request, *, fallback_order=None):
            del request
            candidates = list(fallback_order or [])
            return sorted(candidates, key=lambda candidate: str(candidate.action_id) != "a")

    game = _FakeGame()
    controller = HeadlessPolicyDecisionController(
        game=None,
        auto_attach=False,
        ai_orchestrator=_PreferFirstOrchestrator(),
        ai_orchestrator_ignore_setup_decisions=True,
    )
    options = [
        DecisionOption.create("Option A", payload={"action_id": "a"}),
        DecisionOption.create("Option B", payload={"action_id": "b"}),
    ]
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Pick one",
        player_id="p1",
        options=options,
        context={"phase": "declare_battle_formations"},
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


def test_headless_policy_controller_treats_start_of_battle_keyword_as_setup() -> None:
    class _PreferFirstOrchestrator:
        def rank_legal_candidates(self, request, *, fallback_order=None):
            del request
            candidates = list(fallback_order or [])
            return sorted(candidates, key=lambda candidate: str(candidate.action_id) != "a")

    game = _FakeGame()
    controller = HeadlessPolicyDecisionController(
        game=None,
        auto_attach=False,
        ai_orchestrator=_PreferFirstOrchestrator(),
        ai_orchestrator_ignore_setup_decisions=True,
    )
    options = [
        DecisionOption.create("Option A", payload={"action_id": "a"}),
        DecisionOption.create("Option B", payload={"action_id": "b"}),
    ]
    request = DecisionRequest.create(
        DECISION_CHOOSE_START_OF_BATTLE_KEYWORD,
        "Pick one",
        player_id="p1",
        options=options,
        context={"selection_kind": "reroll_ones"},
        candidates=[
            CandidateAction(action_id="a", params={"keyword": "A"}, metadata={"projected_score_delta_next_window": 1.0}),
            CandidateAction(action_id="b", params={"keyword": "B"}, metadata={"projected_score_delta_next_window": 3.0}),
        ],
        mask=[True, True],
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("option_id", "")) == str(options[1].option_id)
    assert dict(payload.get("result_payload", {}) or {}) == {"keyword": "B"}


def test_headless_policy_controller_treats_setup_decision_types_as_setup_without_phase_context() -> None:
    class _PreferFirstOrchestrator:
        def rank_legal_candidates(self, request, *, fallback_order=None):
            del request
            candidates = list(fallback_order or [])
            return sorted(candidates, key=lambda candidate: str(candidate.action_id) != "a")

    setup_decision_types = [
        DECISION_ATTACH_LEADER,
        DECISION_ATTACH_SUPPORT_ARTILLERY,
        DECISION_ASSIGN_TRANSPORT,
        DECISION_CHOOSE_DEPLOYMENT_ZONE,
        DECISION_CHOOSE_MISSION,
        DECISION_CHOOSE_PLAYER_COLOR,
        DECISION_CHOOSE_SETUP_REACTIVE_ACTION,
        DECISION_CHOOSE_START_OF_BATTLE_KEYWORD,
        DECISION_DECLARE_RESERVES,
        DECISION_SCOUT_MOVE,
        DECISION_SELECT_NEXT_DEPLOY_UNIT,
        DECISION_SELECT_SETUP_REACTIVE_TARGET,
        DECISION_SHADOW_ASSIGNMENT,
    ]

    controller = HeadlessPolicyDecisionController(
        game=None,
        auto_attach=False,
        ai_orchestrator=_PreferFirstOrchestrator(),
        ai_orchestrator_ignore_setup_decisions=True,
    )
    for decision_type in setup_decision_types:
        options = [
            DecisionOption.create("Option A", payload={"action_id": "a"}),
            DecisionOption.create("Option B", payload={"action_id": "b"}),
        ]
        request = DecisionRequest.create(
            decision_type,
            "Pick one",
            player_id="p1",
            options=options,
            context={"phase": "COMMAND_PHASE"},
            candidates=[
                CandidateAction(
                    action_id="a",
                    params={"choice": "A"},
                    metadata={"projected_score_delta_next_window": 1.0},
                ),
                CandidateAction(
                    action_id="b",
                    params={"choice": "B"},
                    metadata={"projected_score_delta_next_window": 3.0},
                ),
            ],
            mask=[True, True],
        )

        assert not controller._should_use_ai_orchestrator(request, _FakeGame()), decision_type


def test_headless_policy_tie_break_is_independent_of_request_uuid() -> None:
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    candidates = [
        CandidateAction(
            action_id="attach:runtime-a",
            params={"leader_id": "11111111-1111-4111-8111-111111111111", "bodyguard_id": None},
            metadata={"label": "Unattached"},
        ),
        CandidateAction(
            action_id="attach:runtime-b",
            params={
                "leader_id": "22222222-2222-4222-8222-222222222222",
                "bodyguard_id": "33333333-3333-4333-8333-333333333333",
            },
            metadata={"label": "Khorne Berzerkers"},
        ),
    ]
    first = DecisionRequest.create(
        DECISION_ATTACH_LEADER,
        "Attach leader",
        player_id="p1",
        candidates=candidates,
        mask=[True, True],
    )
    second = DecisionRequest.create(
        DECISION_ATTACH_LEADER,
        "Attach leader",
        player_id="p1",
        candidates=candidates,
        mask=[True, True],
    )

    assert first.decision_id != second.decision_id
    assert [candidate.action_id for candidate in controller._rank_legal_candidates(first)] == [
        candidate.action_id for candidate in controller._rank_legal_candidates(second)
    ]


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


def test_headless_policy_controller_forced_only_policy_prefers_forced_reserve_allocation() -> None:
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False, reserve_policy="forced_only")
    request = DecisionRequest.create(
        DECISION_DECLARE_RESERVES,
        "Declare reserves",
        player_id="p1",
        options=[
            DecisionOption.create(
                "Optional pressure",
                payload={
                    "action_id": "reserve:b",
                    "strategy_id": "deep_strike_pressure",
                    "unit_ids_by_bucket": {"deploy": ["unit:1"], "reserves": ["unit:2"]},
                },
            ),
            DecisionOption.create(
                "Forced-only",
                payload={
                    "action_id": "reserve:z",
                    "strategy_id": "forced_only",
                    "unit_ids_by_bucket": {"deploy": ["unit:1", "unit:2"], "reserves": []},
                },
            ),
        ],
    )

    ranked = controller._rank_legal_candidates(request)

    assert ranked
    assert ranked[0].action_id == "reserve:z"


def test_headless_policy_controller_forced_only_policy_prefers_teacher_duplicate_of_forced_allocation() -> None:
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False, reserve_policy="forced_only")
    request = DecisionRequest.create(
        DECISION_DECLARE_RESERVES,
        "Declare reserves",
        player_id="p1",
        options=[
            DecisionOption.create(
                "Optional pressure",
                payload={
                    "action_id": "reserve:a",
                    "strategy_id": "deep_strike_pressure",
                    "reserve_units": 3,
                    "reserve_points_ratio": 0.45,
                    "strategic_points_ratio": 0.62,
                    "unit_ids_by_bucket": {"deploy": ["unit:1"], "reserves": ["unit:2"], "strategic_reserves": ["unit:3"]},
                },
            ),
            DecisionOption.create(
                "Teacher allocation",
                payload={
                    "action_id": "reserve:z",
                    "strategy_id": "teacher",
                    "reserve_units": 0,
                    "reserve_points_ratio": 0.0,
                    "strategic_points_ratio": 0.0,
                    "unit_ids_by_bucket": {"deploy": ["unit:1", "unit:2", "unit:3"], "reserves": []},
                },
            ),
        ],
    )

    ranked = controller._rank_legal_candidates(request)

    assert ranked
    assert ranked[0].action_id == "reserve:z"


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


def test_headless_policy_controller_auto_builds_declare_shots_payload_for_confirm() -> None:
    class _Profile:
        name = "Rifle"

        def __init__(self) -> None:
            self.parent_wargear = None

        def is_hazardous(self) -> bool:
            return False

        def get_damage_potential(self, _target) -> float:
            return 4.0

    class _Wargear:
        def __init__(self) -> None:
            self.id = "wargear:rifle"
            self.name = "Rifle"
            self.profile = _Profile()
            self.profile.parent_wargear = self
            self.profiles = {"standard": self.profile}

        def is_ranged(self) -> bool:
            return True

    class _Model:
        def __init__(self) -> None:
            self.id = "model:shooter"
            self.is_alive = True
            self.wargear = [_Wargear()]

    class _Unit:
        def __init__(self, unit_id: str) -> None:
            self.id = unit_id
            self.name = unit_id
            self.deployed = True
            self.is_embarked = False
            self.embarked_in = None
            self.models = [_Model()] if unit_id == "unit:shooter" else []
            self.validate_calls = 0

        def get_attached_unit_root(self):
            return self

        def get_attached_unit_models(self):
            return list(self.models)

        def is_alive(self) -> bool:
            return True

        def is_in_reserves(self) -> bool:
            return False

        def _validate_shooting_declaration(self, _profile, target_unit, models, _game_map):
            self.validate_calls += 1
            return {"valid": bool(target_unit is not None and models)}

    class _Map:
        def __init__(self, target) -> None:
            self._target = target
            self.state_generation = 4

        def get_enemy_units(self, _unit):
            return [self._target]

    class _ShootingGame(_FakeGame):
        def __init__(self) -> None:
            super().__init__()
            self.shooter = _Unit("unit:shooter")
            self.target = _Unit("unit:target")
            self.map = _Map(self.target)

        def _resolve_unit_by_id(self, unit_id: str):
            if unit_id == "unit:shooter":
                return self.shooter
            if unit_id == "unit:target":
                return self.target
            return None

        def apply_command(self, command):
            self.commands.append(command)
            payload = dict(command.payload or {})
            result_payload = dict(payload.get("result_payload", {}) or {})
            return _ApplyResult(ok=bool(result_payload.get("declarations")))

    game = _ShootingGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    options = [
        DecisionOption(
            option_id="opt:confirm",
            label="Confirm",
            payload={"action": "confirm", "unit_id": "unit:shooter", "action_id": "shoot:confirm"},
        ),
        DecisionOption(
            option_id="opt:skip",
            label="Skip",
            payload={"action": "skip", "unit_id": "unit:shooter", "action_id": "shoot:skip"},
        ),
    ]
    request = DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        "Declare shots",
        player_id="p1",
        options=options,
        context={
            "unit_id": "unit:shooter",
            "allowed_model_ids": ["model:shooter"],
            "allowed_wargear_ids": ["wargear:rifle"],
            "allowed_target_unit_ids": ["unit:target"],
            "shooting_target_generation": 4,
            "shooting_target_candidates": [
                {
                    "unit_id": "unit:shooter",
                    "model_id": "model:shooter",
                    "wargear_id": "wargear:rifle",
                    "weapon_instance_id": "wargear:rifle",
                    "profile_name": "standard",
                    "target_unit_ids": ["unit:target"],
                    "is_plasma_warhead": False,
                    "map_state_generation": 4,
                }
            ],
        },
        candidates=[
            CandidateAction(
                action_id="shoot:confirm",
                params={"action": "confirm", "unit_id": "unit:shooter"},
                metadata={"projected_score_delta_next_window": 5.0, "candidate_kind": "confirm"},
            ),
            CandidateAction(
                action_id="shoot:skip",
                params={"action": "skip", "unit_id": "unit:shooter"},
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
    assert str(payload.get("option_id", "")) == "opt:confirm"
    assert result_payload["declarations"] == [
        {
            "wargear_id": "wargear:rifle",
            "profile_name": "standard",
            "model_ids": ["model:shooter"],
            "target_unit_id": "unit:target",
        }
    ]
    assert metadata["candidate_action_id"] == "shoot:confirm"
    assert metadata["candidate_kind"] == "confirm"
    assert metadata["resolution_strategy"] == "ranked_candidate"
    assert game.shooter.validate_calls == 0


def test_headless_policy_controller_ignores_shooting_unit_without_legal_declarations() -> None:
    class _Profile:
        def __init__(self, name: str, *, legal: bool) -> None:
            self.name = name
            self.legal = bool(legal)
            self.parent_wargear = None

        def is_hazardous(self) -> bool:
            return False

        def get_damage_potential(self, _target) -> float:
            return 3.0 if self.legal else 0.0

    class _Wargear:
        def __init__(self, wargear_id: str, *, legal: bool) -> None:
            self.id = wargear_id
            self.name = wargear_id
            self.profile = _Profile("standard", legal=legal)
            self.profile.parent_wargear = self
            self.profiles = {"standard": self.profile}

        def is_ranged(self) -> bool:
            return True

    class _Model:
        def __init__(self, model_id: str, *, legal: bool) -> None:
            self.id = model_id
            self.is_alive = True
            self.wargear = [_Wargear(f"wargear:{model_id}", legal=legal)]

    class _Unit:
        def __init__(self, unit_id: str, *, legal: bool) -> None:
            self.id = unit_id
            self.name = unit_id
            self.deployed = True
            self.is_embarked = False
            self.embarked_in = None
            self.models = [_Model(f"model:{unit_id}", legal=legal)] if unit_id != "unit:target" else []

        def get_attached_unit_root(self):
            return self

        def get_attached_unit_models(self):
            return list(self.models)

        def is_alive(self) -> bool:
            return True

        def is_in_reserves(self) -> bool:
            return False

        def _validate_shooting_declaration(self, profile, target_unit, models, _game_map):
            return {"valid": bool(getattr(profile, "legal", False) and target_unit is not None and models)}

    class _Map:
        def __init__(self, target) -> None:
            self._target = target

        def get_enemy_units(self, _unit):
            return [self._target]

    class _ShootingGame(_FakeGame):
        def __init__(self) -> None:
            super().__init__()
            self.blocked = _Unit("unit:blocked", legal=False)
            self.shooter = _Unit("unit:shooter", legal=True)
            self.target = _Unit("unit:target", legal=False)
            self.map = _Map(self.target)
            self.units = {
                self.blocked.id: self.blocked,
                self.shooter.id: self.shooter,
                self.target.id: self.target,
            }

        def _resolve_unit_by_id(self, unit_id: str):
            return self.units.get(str(unit_id or ""))

    game = _ShootingGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    request = DecisionRequest.create(
        DECISION_SELECT_UNIT,
        "Select shooting unit",
        player_id="p1",
        options=[
            DecisionOption("opt:blocked", "Blocked", {"unit_id": "unit:blocked", "action_id": "select:blocked"}),
            DecisionOption("opt:shooter", "Shooter", {"unit_id": "unit:shooter", "action_id": "select:shooter"}),
            DecisionOption("opt:pass", "Pass", {"action": "pass", "action_id": "select:pass"}),
        ],
        context={
            "phase_name": "SHOOTING_PHASE",
            "phase_step": "SHOOT_UNITS",
            "selection_purpose": "ACTIVATE_SHOOTING_UNIT",
            "allow_pass": True,
        },
        candidates=[
            CandidateAction(
                action_id="select:blocked",
                params={"unit_id": "unit:blocked"},
                metadata={"projected_score_delta_next_window": 100.0},
            ),
            CandidateAction(
                action_id="select:shooter",
                params={"unit_id": "unit:shooter"},
                metadata={"projected_score_delta_next_window": 1.0},
            ),
            CandidateAction(
                action_id="select:pass",
                params={"action": "pass"},
                metadata={"projected_score_delta_next_window": 0.0},
            ),
        ],
        mask=[True, True, True],
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("option_id", "")) == "opt:shooter"


def test_headless_policy_controller_passes_shooting_selection_when_no_unit_can_declare_shots() -> None:
    class _Profile:
        name = "Blocked"
        parent_wargear = None

        def is_hazardous(self) -> bool:
            return False

    class _Wargear:
        id = "wargear:blocked"
        name = "Blocked"

        def __init__(self) -> None:
            self.profile = _Profile()
            self.profile.parent_wargear = self
            self.profiles = {"standard": self.profile}

        def is_ranged(self) -> bool:
            return True

    class _Model:
        id = "model:blocked"
        is_alive = True

        def __init__(self) -> None:
            self.wargear = [_Wargear()]

    class _Unit:
        def __init__(self, unit_id: str) -> None:
            self.id = unit_id
            self.name = unit_id
            self.deployed = True
            self.is_embarked = False
            self.embarked_in = None
            self.models = [_Model()] if unit_id == "unit:blocked" else []

        def get_attached_unit_root(self):
            return self

        def get_attached_unit_models(self):
            return list(self.models)

        def is_alive(self) -> bool:
            return True

        def is_in_reserves(self) -> bool:
            return False

        def _validate_shooting_declaration(self, _profile, _target_unit, _models, _game_map):
            return {"valid": False}

    class _Map:
        def __init__(self, target) -> None:
            self._target = target

        def get_enemy_units(self, _unit):
            return [self._target]

    class _ShootingGame(_FakeGame):
        def __init__(self) -> None:
            super().__init__()
            self.blocked = _Unit("unit:blocked")
            self.target = _Unit("unit:target")
            self.map = _Map(self.target)
            self.units = {self.blocked.id: self.blocked, self.target.id: self.target}

        def _resolve_unit_by_id(self, unit_id: str):
            return self.units.get(str(unit_id or ""))

    game = _ShootingGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    request = DecisionRequest.create(
        DECISION_SELECT_UNIT,
        "Select shooting unit",
        player_id="p1",
        options=[
            DecisionOption("opt:blocked", "Blocked", {"unit_id": "unit:blocked", "action_id": "select:blocked"}),
            DecisionOption("opt:pass", "Pass", {"action": "pass", "action_id": "select:pass"}),
        ],
        context={
            "phase_name": "SHOOTING_PHASE",
            "phase_step": "SHOOT_UNITS",
            "selection_purpose": "ACTIVATE_SHOOTING_UNIT",
            "allow_pass": True,
        },
        candidates=[
            CandidateAction(
                action_id="select:blocked",
                params={"unit_id": "unit:blocked"},
                metadata={"projected_score_delta_next_window": 100.0},
            ),
            CandidateAction(
                action_id="select:pass",
                params={"action": "pass"},
                metadata={"projected_score_delta_next_window": 0.0},
            ),
        ],
        mask=[True, True],
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("option_id", "")) == "opt:pass"


def test_headless_policy_controller_shooting_selection_checks_past_first_invalid_target() -> None:
    class _Profile:
        name = "Standard"
        parent_wargear = None

        def is_hazardous(self) -> bool:
            return False

    class _Wargear:
        id = "wargear:rifle"
        name = "Rifle"

        def __init__(self) -> None:
            self.profile = _Profile()
            self.profile.parent_wargear = self
            self.profiles = {"standard": self.profile}

        def is_ranged(self) -> bool:
            return True

    class _Model:
        id = "model:shooter"
        is_alive = True

        def __init__(self) -> None:
            self.wargear = [_Wargear()]

    class _Unit:
        def __init__(self, unit_id: str) -> None:
            self.id = unit_id
            self.name = unit_id
            self.deployed = True
            self.is_embarked = False
            self.embarked_in = None
            self.models = [_Model()] if unit_id == "unit:shooter" else []
            self.validation_calls = 0

        def get_attached_unit_root(self):
            return self

        def get_attached_unit_models(self):
            return list(self.models)

        def is_alive(self) -> bool:
            return True

        def is_in_reserves(self) -> bool:
            return False

        def _validate_shooting_declaration(self, _profile, target_unit, models, _game_map):
            self.validation_calls += 1
            return {"valid": bool(getattr(target_unit, "id", "") == "unit:z-valid" and models)}

    class _Map:
        def __init__(self, targets) -> None:
            self._targets = list(targets)

        def get_enemy_units(self, _unit):
            return list(self._targets)

    class _ShootingGame(_FakeGame):
        def __init__(self) -> None:
            super().__init__()
            self.shooter = _Unit("unit:shooter")
            self.blocked_target = _Unit("unit:a-blocked")
            self.valid_target = _Unit("unit:z-valid")
            self.map = _Map([self.blocked_target, self.valid_target])
            self.units = {
                self.shooter.id: self.shooter,
                self.blocked_target.id: self.blocked_target,
                self.valid_target.id: self.valid_target,
            }

        def _resolve_unit_by_id(self, unit_id: str):
            return self.units.get(str(unit_id or ""))

    game = _ShootingGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    request = DecisionRequest.create(
        DECISION_SELECT_UNIT,
        "Select shooting unit",
        player_id="p1",
        options=[
            DecisionOption("opt:shooter", "Shooter", {"unit_id": "unit:shooter", "action_id": "select:shooter"}),
            DecisionOption("opt:pass", "Pass", {"action": "pass", "action_id": "select:pass"}),
        ],
        context={
            "phase_name": "SHOOTING_PHASE",
            "phase_step": "SHOOT_UNITS",
            "selection_purpose": "ACTIVATE_SHOOTING_UNIT",
            "allow_pass": True,
        },
        candidates=[
            CandidateAction(
                action_id="select:shooter",
                params={"unit_id": "unit:shooter"},
                metadata={"projected_score_delta_next_window": 1.0},
            ),
            CandidateAction(
                action_id="select:pass",
                params={"action": "pass"},
                metadata={"projected_score_delta_next_window": 0.0},
            ),
        ],
        mask=[True, True],
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("option_id", "")) == "opt:shooter"
    assert game.shooter.validation_calls == 2


def test_headless_policy_controller_caps_shooting_selection_precheck_to_first_valid_declaration() -> None:
    class _Profile:
        name = "Standard"
        parent_wargear = None

        def is_hazardous(self) -> bool:
            return False

    class _Wargear:
        def __init__(self, index: int) -> None:
            self.id = f"wargear:{index}"
            self.name = f"Wargear {index}"
            self.profile = _Profile()
            self.profile.parent_wargear = self
            self.profiles = {"standard": self.profile}

        def is_ranged(self) -> bool:
            return True

    class _Model:
        id = "model:shooter"
        is_alive = True

        def __init__(self) -> None:
            self.wargear = [_Wargear(index) for index in range(20)]

    class _Unit:
        def __init__(self, unit_id: str) -> None:
            self.id = unit_id
            self.name = unit_id
            self.deployed = True
            self.is_embarked = False
            self.embarked_in = None
            self.models = [_Model()] if unit_id == "unit:shooter" else []
            self.validation_calls = 0

        def get_attached_unit_root(self):
            return self

        def get_attached_unit_models(self):
            return list(self.models)

        def is_alive(self) -> bool:
            return True

        def is_in_reserves(self) -> bool:
            return False

        def _validate_shooting_declaration(self, _profile, target_unit, models, _game_map):
            self.validation_calls += 1
            return {"valid": bool(target_unit is not None and models)}

    class _Map:
        def __init__(self, target) -> None:
            self._target = target

        def get_enemy_units(self, _unit):
            return [self._target]

    class _ShootingGame(_FakeGame):
        def __init__(self) -> None:
            super().__init__()
            self.shooter = _Unit("unit:shooter")
            self.target = _Unit("unit:target")
            self.map = _Map(self.target)

        def _resolve_unit_by_id(self, unit_id: str):
            if unit_id == "unit:shooter":
                return self.shooter
            if unit_id == "unit:target":
                return self.target
            return None

    game = _ShootingGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    request = DecisionRequest.create(
        DECISION_SELECT_UNIT,
        "Select shooting unit",
        player_id="p1",
        options=[
            DecisionOption("opt:shooter", "Shooter", {"unit_id": "unit:shooter", "action_id": "select:shooter"}),
            DecisionOption("opt:pass", "Pass", {"action": "pass", "action_id": "select:pass"}),
        ],
        context={
            "phase_name": "SHOOTING_PHASE",
            "phase_step": "SHOOT_UNITS",
            "selection_purpose": "ACTIVATE_SHOOTING_UNIT",
            "allow_pass": True,
        },
        candidates=[
            CandidateAction(action_id="select:shooter", params={"unit_id": "unit:shooter"}, metadata={}),
            CandidateAction(action_id="select:pass", params={"action": "pass"}, metadata={}),
        ],
        mask=[True, True],
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("option_id", "")) == "opt:shooter"
    assert game.shooter.validation_calls == 1


def test_headless_policy_controller_declares_each_ranged_weapon_with_best_profile() -> None:
    class _Profile:
        def __init__(
            self,
            name: str,
            *,
            legal: bool = True,
            hazardous: bool = False,
            damage: float = 1.0,
            skill: int = 3,
            strength: int = 4,
        ) -> None:
            self.name = name
            self.legal = bool(legal)
            self._hazardous = bool(hazardous)
            self._damage = float(damage)
            self.skill = int(skill)
            self.strength = int(strength)
            self.parent_wargear = None

        def is_hazardous(self) -> bool:
            return self._hazardous

        def get_anti_specs(self):
            return []

        def get_damage_potential(self, _target) -> float:
            return self._damage

    class _Wargear:
        def __init__(self, wargear_id: str, profiles: dict[str, _Profile], *, ranged: bool = True) -> None:
            self.id = wargear_id
            self.name = wargear_id
            self.profiles = dict(profiles)
            self._ranged = bool(ranged)
            for profile in self.profiles.values():
                profile.parent_wargear = self

        def is_ranged(self) -> bool:
            return self._ranged

    class _Model:
        id = "model:shooter"
        is_alive = True

        def __init__(self) -> None:
            self.wargear = [
                _Wargear("wargear:launcher", {"frag": _Profile("frag", damage=5.0)}),
                _Wargear("wargear:melee", {"strike": _Profile("strike")}, ranged=False),
                _Wargear(
                    "wargear:multi",
                    {
                        "accurate": _Profile("accurate", damage=1.0, skill=2, strength=5),
                        "clumsy": _Profile("clumsy", damage=6.0, skill=4, strength=10),
                    },
                ),
                _Wargear("wargear:out-of-range", {"short": _Profile("short", legal=False)}),
                _Wargear(
                    "wargear:plasma",
                    {"supercharge": _Profile("supercharge", hazardous=True, damage=4.0, skill=3, strength=8)},
                ),
                _Wargear("wargear:rifle", {"standard": _Profile("standard", damage=3.0)}),
            ]

    class _Unit:
        def __init__(self, unit_id: str) -> None:
            self.id = unit_id
            self.name = unit_id
            self.deployed = True
            self.is_embarked = False
            self.embarked_in = None
            self.models = [_Model()] if unit_id == "unit:shooter" else []
            self.toughness = 4
            self.keywords = ["INFANTRY"]

        def get_attached_unit_root(self):
            return self

        def get_attached_unit_models(self):
            return list(self.models)

        def is_alive(self) -> bool:
            return True

        def is_in_reserves(self) -> bool:
            return False

        def _validate_shooting_declaration(self, profile, target_unit, models, _game_map):
            return {"valid": bool(getattr(profile, "legal", False) and target_unit is not None and models)}

    class _Map:
        def __init__(self, target) -> None:
            self._target = target

        def get_enemy_units(self, _unit):
            return [self._target]

    class _ShootingGame(_FakeGame):
        def __init__(self) -> None:
            super().__init__()
            self.shooter = _Unit("unit:shooter")
            self.target = _Unit("unit:target")
            self.map = _Map(self.target)

        def _resolve_unit_by_id(self, unit_id: str):
            if unit_id == "unit:shooter":
                return self.shooter
            if unit_id == "unit:target":
                return self.target
            return None

    game = _ShootingGame()
    request = DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        "Declare shots",
        player_id="p1",
        options=[DecisionOption.create("Confirm", payload={"action": "confirm", "unit_id": "unit:shooter"})],
        context={"unit_id": "unit:shooter"},
    )

    declarations = HeadlessPolicyDecisionController._default_shooting_declarations(
        game,
        request,
        {"unit_id": "unit:shooter"},
    )

    assert declarations == [
        {
            "wargear_id": "wargear:launcher",
            "profile_name": "frag",
            "model_ids": ["model:shooter"],
            "target_unit_id": "unit:target",
        },
        {
            "wargear_id": "wargear:multi",
            "profile_name": "accurate",
            "model_ids": ["model:shooter"],
            "target_unit_id": "unit:target",
        },
        {
            "wargear_id": "wargear:plasma",
            "profile_name": "supercharge",
            "model_ids": ["model:shooter"],
            "target_unit_id": "unit:target",
        },
        {
            "wargear_id": "wargear:rifle",
            "profile_name": "standard",
            "model_ids": ["model:shooter"],
            "target_unit_id": "unit:target",
        },
    ]


def test_headless_policy_controller_falls_back_to_skip_when_declare_shots_confirm_rejected() -> None:
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
    payload = dict(game.commands[-1].payload or {})
    result_payload = dict(payload.get("result_payload", {}) or {})
    metadata = dict(game.commands[-1].metadata or {})
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


def test_headless_policy_controller_synthesizes_forced_redeploy_model_positions(monkeypatch) -> None:
    class _Model:
        def __init__(self, model_id: str) -> None:
            self.id = model_id
            self._id = model_id

    class _Unit:
        def __init__(self) -> None:
            self.id = "unit:jump"
            self._id = "unit:jump"
            self.name = "Jump Unit"
            self.models = [_Model("model:a"), _Model("model:b")]
            self.deployed = True
            self.reserve_status = "deployed"

        def get_attached_unit_root(self):
            return self

        def get_parent_army(self):
            return army

    class _Map:
        width = 60.0
        height = 44.0
        units = []

    class _Game:
        def __init__(self, unit: _Unit) -> None:
            self.is_authoritative = True
            self.map = _Map()
            self.players = [player]
            self._unit = unit

        def _resolve_unit_by_id(self, unit_id: str):
            if str(unit_id) == str(self._unit.id):
                return self._unit
            return None

    unit = _Unit()
    army = type("Army", (), {})()
    army.units = [unit]
    player = type("Player", (), {})()
    player.army = army
    army.player = player
    game = _Game(unit)

    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Set up Jump Unit",
        player_id="p1",
        options=[
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": unit.id, "movement_type": "move", "action": "confirm"},
            )
        ],
        context={
            "unit_id": unit.id,
            "movement_type": "move",
            "placement_kind": "normal_move_redeploy_9h",
            "allowed_model_ids": ["model:a", "model:b"],
            "allow_skip": False,
            "min_enemy_distance_horiz": 9,
        },
    )
    action_id = request.action_id_for_option_id(request.options[0].option_id)
    request.candidates = [
        CandidateAction(
            action_id=str(action_id),
            params={"unit_id": unit.id, "movement_type": "move", "action": "confirm"},
            metadata={"candidate_kind": "confirm"},
        )
    ]
    request.mask = [True]

    def _fake_build_positions(_game, _unit, *, x, y, avoid_friendly_units, search_context):
        del _game, _unit, avoid_friendly_units, search_context
        return [
            {"model_id": "model:a", "position": [float(x), float(y), 0.0], "facing": 0.0},
            {"model_id": "model:b", "position": [float(x) + 2.0, float(y), 0.0], "facing": 0.0},
        ]

    resolved_payloads: list[dict[str, object]] = []

    def _fake_resolve_decision_command(
        _game,
        _request,
        _option_id,
        *,
        result_payload,
        player_id,
        metadata,
    ):
        del _game, _request, _option_id, player_id, metadata
        resolved_payloads.append(dict(result_payload or {}))
        return _ApplyResult(ok=True)

    monkeypatch.setattr(headless_policy_module, "build_placement_search_context", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(headless_policy_module, "_build_reserves_model_positions_from_anchor", _fake_build_positions)
    monkeypatch.setattr(headless_policy_module, "validate_move_unit_payload", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(headless_policy_module, "resolve_decision_command", _fake_resolve_decision_command)

    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    controller.on_decision_requested(game, request)

    assert len(resolved_payloads) == 1
    resolved = resolved_payloads[0]
    assert resolved["unit_id"] == "unit:jump"
    assert resolved["movement_type"] == "move"
    assert resolved["action"] == "confirm"
    assert [entry["model_id"] for entry in list(resolved["model_positions"] or [])] == ["model:a", "model:b"]


def test_headless_policy_controller_prunes_stale_leader_attachment_candidate() -> None:
    class _Unit:
        def __init__(self, unit_id: str, *, is_leader: bool = False, allowed_targets: set[str] | None = None) -> None:
            self.id = unit_id
            self.is_leader = bool(is_leader)
            self._allowed_targets = set(allowed_targets or set())

        def can_attach_to(self, bodyguard) -> bool:
            return str(getattr(bodyguard, "id", "") or "") in self._allowed_targets

    class _SetupGame(_FakeGame):
        def __init__(self) -> None:
            super().__init__()
            self.leader = _Unit("unit:leader", is_leader=True, allowed_targets={"unit:valid"})
            self.invalid_bodyguard = _Unit("unit:invalid")
            self.valid_bodyguard = _Unit("unit:valid")
            self.units = {
                self.leader.id: self.leader,
                self.invalid_bodyguard.id: self.invalid_bodyguard,
                self.valid_bodyguard.id: self.valid_bodyguard,
            }

        def _resolve_unit_by_id(self, unit_id: str):
            return self.units.get(str(unit_id or ""))

    game = _SetupGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    request = DecisionRequest.create(
        DECISION_ATTACH_LEADER,
        "Attach leader",
        player_id="p1",
        options=[
            DecisionOption.create(
                "Invalid",
                payload={
                    "leader_id": "unit:leader",
                    "bodyguard_id": "unit:invalid",
                    "action_id": "attach:invalid",
                },
            ),
            DecisionOption.create(
                "Valid",
                payload={
                    "leader_id": "unit:leader",
                    "bodyguard_id": "unit:valid",
                    "action_id": "attach:valid",
                },
            ),
            DecisionOption.create(
                "Unattached",
                payload={"leader_id": "unit:leader", "bodyguard_id": None, "action_id": "attach:none"},
            ),
        ],
        candidates=[
            CandidateAction(
                action_id="attach:invalid",
                params={"leader_id": "unit:leader", "bodyguard_id": "unit:invalid"},
                metadata={"projected_score_delta_next_window": 10.0},
            ),
            CandidateAction(
                action_id="attach:valid",
                params={"leader_id": "unit:leader", "bodyguard_id": "unit:valid"},
                metadata={"projected_score_delta_next_window": 1.0},
            ),
            CandidateAction(
                action_id="attach:none",
                params={"leader_id": "unit:leader", "bodyguard_id": None},
                metadata={"projected_score_delta_next_window": 0.0},
            ),
        ],
        mask=[True, True, True],
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("option_id", "")) == str(request.options[1].option_id)


def test_headless_policy_controller_prunes_stale_transport_assignment_candidate() -> None:
    class _Unit:
        def __init__(
            self,
            unit_id: str,
            *,
            is_transport: bool = False,
            allowed_passengers: set[str] | None = None,
        ) -> None:
            self.id = unit_id
            self.is_transport = bool(is_transport)
            self._allowed_passengers = set(allowed_passengers or set())

        def can_transport(self, passenger) -> bool:
            return str(getattr(passenger, "id", "") or "") in self._allowed_passengers

    class _SetupGame(_FakeGame):
        def __init__(self) -> None:
            super().__init__()
            self.passenger = _Unit("unit:passenger")
            self.invalid_transport = _Unit("unit:invalid_transport", is_transport=True)
            self.valid_transport = _Unit(
                "unit:valid_transport",
                is_transport=True,
                allowed_passengers={"unit:passenger"},
            )
            self.units = {
                self.passenger.id: self.passenger,
                self.invalid_transport.id: self.invalid_transport,
                self.valid_transport.id: self.valid_transport,
            }

        def _resolve_unit_by_id(self, unit_id: str):
            return self.units.get(str(unit_id or ""))

    game = _SetupGame()
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    request = DecisionRequest.create(
        DECISION_ASSIGN_TRANSPORT,
        "Assign transport",
        player_id="p1",
        options=[
            DecisionOption.create(
                "Invalid transport",
                payload={
                    "unit_id": "unit:passenger",
                    "transport_id": "unit:invalid_transport",
                    "action_id": "transport:invalid",
                },
            ),
            DecisionOption.create(
                "Valid transport",
                payload={
                    "unit_id": "unit:passenger",
                    "transport_id": "unit:valid_transport",
                    "action_id": "transport:valid",
                },
            ),
            DecisionOption.create(
                "No transport",
                payload={"unit_id": "unit:passenger", "transport_id": None, "action_id": "transport:none"},
            ),
        ],
        candidates=[
            CandidateAction(
                action_id="transport:invalid",
                params={"unit_id": "unit:passenger", "transport_id": "unit:invalid_transport"},
                metadata={"projected_score_delta_next_window": 10.0},
            ),
            CandidateAction(
                action_id="transport:valid",
                params={"unit_id": "unit:passenger", "transport_id": "unit:valid_transport"},
                metadata={"projected_score_delta_next_window": 1.0},
            ),
            CandidateAction(
                action_id="transport:none",
                params={"unit_id": "unit:passenger", "transport_id": None},
                metadata={"projected_score_delta_next_window": 0.0},
            ),
        ],
        mask=[True, True, True],
    )

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("option_id", "")) == str(request.options[1].option_id)


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


def _build_reserves_arrival_controller_fixture(
    *,
    include_skip: bool,
    include_confirm_candidate: bool,
    allow_skip: bool,
) -> tuple[object, DecisionRequest]:
    class _Base:
        has_circular_base = True

        def __init__(self, x: float = 0.0, y: float = 0.0, *, radius: float = 0.5, z: float = 0.0) -> None:
            self.x = float(x)
            self.y = float(y)
            self.z = float(z)
            self.facing = 0.0
            self._radius = float(radius)

        def get_radius(self) -> float:
            return self._radius

        def get_longest_radius(self) -> float:
            return self._radius

    class _Model:
        def __init__(self, model_id: str) -> None:
            self._id = model_id
            self.id = model_id
            self.model_base = _Base()
            self.is_alive = True
            self.parent_unit = None

        def get_location(self) -> tuple[float, float, float, float]:
            return (float(self.model_base.x), float(self.model_base.y), float(self.model_base.z), float(self.model_base.facing))

        def set_location(self, x: float, y: float, z: float, facing: float) -> None:
            self.model_base.x = float(x)
            self.model_base.y = float(y)
            self.model_base.z = float(z)
            self.model_base.facing = float(facing)

    class _Unit:
        def __init__(self, unit_id: str, model_id: str) -> None:
            self._id = unit_id
            self.id = unit_id
            self.models = [_Model(model_id)]
            self.name = unit_id
            self.reserve_status = "strategic_reserves"
            self.deployed = False
            self.embarked_in = None
            self.is_embarked = False
            self.parent_army = None
            for model in self.models:
                model.parent_unit = self

        def get_parent_army(self):
            return self.parent_army

        def get_attached_unit_root(self):
            return self

        def get_attached_unit_models(self):
            return list(self.models)

        def is_in_reserves(self) -> bool:
            return True

        def can_arrive_from_reserves(self, _turn: int) -> bool:
            return True

        def is_in_strategic_reserves(self) -> bool:
            return True

        def has_deep_strike(self) -> bool:
            return False

        def calculate_model_positions(self, x, y, _game_map, avoid_friendly_units=False, boundary_repulsors=None):
            return [(float(x), float(y), 0.0, 0.0)]

        def _create_potential_base(self, x: float, y: float, z: float, facing: float, *, model: _Model | None = None) -> _Base:
            radius = float(model.model_base.get_radius()) if model is not None else 0.5
            base = _Base(float(x), float(y), radius=radius, z=float(z))
            base.facing = float(facing)
            return base

    class _Army:
        def __init__(self, unit) -> None:
            self.player = None
            self.units = [unit]

    class _Player:
        def __init__(self, army, player_id: str = "p1") -> None:
            self.id = player_id
            self.army = army

    class _Map:
        width = 4.0
        height = 4.0
        terrain_features: list[object] = []

        def __init__(self, units) -> None:
            self.units = list(units)

        @staticmethod
        def get_height_at_point(_x: float, _y: float) -> float:
            return 0.0

        @staticmethod
        def is_within_boundary(_model: object, destination: tuple[float, float]) -> bool:
            x, y = destination
            return 0.0 <= float(x) <= 4.0 and 0.0 <= float(y) <= 4.0

        @staticmethod
        def check_collision_with_obstacles(_model: object, destination: tuple[float, float]) -> bool:
            del destination
            return False

    class _Battlefield:
        width = 4.0
        height = 4.0

    class _ReservesGame:
        def __init__(self, unit) -> None:
            self.is_authoritative = True
            self.commands = []
            self.turn = 2
            self.phase = type("Phase", (), {"name": "MOVEMENT_PHASE"})()
            self.current_player_index = 0
            army = _Army(unit)
            self.players = [_Player(army)]
            army.player = self.players[0]
            unit.parent_army = army
            self.map = _Map([unit])
            self.battlefield = _Battlefield()

        def _resolve_unit_by_id(self, unit_id: str):
            for player in self.players:
                for candidate in player.army.units:
                    if str(getattr(candidate, "id", "")) == str(unit_id):
                        return candidate
            return None

        def get_boundary_repulsors(self, _unit, context=""):
            return None

        def get_current_player(self):
            return self.players[self.current_player_index]

        def get_enemy_units(self, _player):
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
            x = float(pos[0])
            y = float(pos[1])
            return _ApplyResult(ok=(abs(x - 0.0) < 1e-6 and abs(y - 0.75) < 1e-6))

    unit = _Unit("unit:1", "model:1")
    game = _ReservesGame(unit)
    options = [
        DecisionOption(option_id="confirm", label="Confirm", payload={"action": "confirm", "action_id": "confirm"}),
    ]
    candidates: list[CandidateAction] = []
    mask: list[bool] = []
    if include_confirm_candidate:
        candidates.append(
            CandidateAction(
                action_id="confirm",
                params={
                    "action": "confirm",
                    "model_positions": [{"model_id": "model:1", "position": [9.0, 9.0, 0.0], "facing": 0.0}],
                },
                metadata={"projected_score_delta_next_window": 1.0},
            )
        )
        mask.append(True)
    if include_skip:
        options.append(DecisionOption(option_id="skip", label="Skip", payload={"action": "skip", "action_id": "skip"}))
        candidates.append(
            CandidateAction(
                action_id="skip",
                params={"action": "skip"},
                metadata={"projected_score_delta_next_window": -1.0},
            )
        )
        mask.append(True)
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Arrive from Reserves",
        player_id="p1",
        options=options,
        context={
            "placement_kind": "reserves_arrival",
            "unit_id": "unit:1",
            "allow_skip": bool(allow_skip),
        },
        candidates=candidates,
        mask=mask,
    )
    return game, request


def test_headless_policy_controller_bruteforces_reserves_arrival_when_solver_candidate_is_invalid() -> None:
    game, request = _build_reserves_arrival_controller_fixture(
        include_skip=False,
        include_confirm_candidate=False,
        allow_skip=False,
    )
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    last_payload = dict(game.commands[0].payload or {})
    assert str(last_payload.get("option_id", "")) == "confirm"
    last_result_payload = dict(last_payload.get("result_payload", {}) or {})
    pos = list(last_result_payload.get("model_positions", [{}])[0].get("position", []) or [])
    assert len(pos) >= 2
    assert abs(float(pos[0]) - 0.0) < 1e-6
    assert abs(float(pos[1]) - 0.75) < 1e-6


def test_headless_policy_controller_bruteforces_reserves_arrival_before_skip_fallback() -> None:
    game, request = _build_reserves_arrival_controller_fixture(
        include_skip=True,
        include_confirm_candidate=False,
        allow_skip=True,
    )
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("option_id", "")) == "confirm"
    result_payload = dict(payload.get("result_payload", {}) or {})
    assert bool(result_payload.get("skipped", False)) is False
    pos = list(result_payload.get("model_positions", [{}])[0].get("position", []) or [])
    assert len(pos) >= 2
    assert abs(float(pos[0]) - 0.0) < 1e-6
    assert abs(float(pos[1]) - 0.75) < 1e-6


def test_headless_policy_controller_prevalidates_reserves_bruteforce_candidates_before_submit() -> None:
    game, request = _build_reserves_arrival_controller_fixture(
        include_skip=False,
        include_confirm_candidate=False,
        allow_skip=False,
    )
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    controller._reserves_arrival_anchor_candidate_groups = lambda *_args, **_kwargs: [("test", [(0.0, 0.0), (1.0, 1.0)])]  # type: ignore[method-assign]
    built_positions = iter(
        [
            [{"model_id": "model:1", "position": [9.0, 9.0, 0.0], "facing": 0.0}],
            [{"model_id": "model:1", "position": [0.0, 0.75, 0.0], "facing": 0.0}],
        ]
    )
    controller._build_model_positions_from_anchor = lambda *_args, **_kwargs: next(built_positions)  # type: ignore[method-assign]

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    result_payload = dict(payload.get("result_payload", {}) or {})
    pos = list(result_payload.get("model_positions", [{}])[0].get("position", []) or [])
    assert len(pos) >= 2
    assert abs(float(pos[0]) - 0.0) < 1e-6
    assert abs(float(pos[1]) - 0.75) < 1e-6
    metric = controller.get_reserves_arrival_search_metrics()[-1]
    assert int(metric.get("validation_rejects", 0) or 0) == 1
    assert int(metric.get("resolve_attempts", 0) or 0) == 1


def test_headless_policy_controller_discards_failed_speculative_reserves_commands() -> None:
    game, request = _build_reserves_arrival_controller_fixture(
        include_skip=False,
        include_confirm_candidate=False,
        allow_skip=False,
    )
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)

    def _anchor_groups(*_args, **_kwargs):
        return [("test", [(1.0, 1.0), (0.0, 0.75)])]

    controller._reserves_arrival_anchor_candidate_groups = _anchor_groups  # type: ignore[method-assign]

    controller.on_decision_requested(game, request)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    result_payload = dict(payload.get("result_payload", {}) or {})
    pos = list(result_payload.get("model_positions", [{}])[0].get("position", []) or [])
    assert len(pos) >= 2
    assert abs(float(pos[0]) - 0.0) < 1e-6
    assert abs(float(pos[1]) - 0.75) < 1e-6
    metric = controller.get_reserves_arrival_search_metrics()[-1]
    assert int(metric.get("resolve_attempts", 0) or 0) == 2


def test_headless_policy_controller_reserves_bruteforce_respects_work_budget() -> None:
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

    def _fail(_game, _unit, *, x, y):
        return []

    controller._build_model_positions_from_anchor = _fail  # type: ignore[method-assign]

    started = time.perf_counter()
    resolved = controller._try_resolve_reserves_arrival_bruteforce(game, request)
    elapsed = time.perf_counter() - started

    assert resolved is False
    assert elapsed < 0.5
    metric = controller.get_reserves_arrival_search_metrics()[-1]
    assert metric["budget_mode"] == "work_units"
    assert metric["work_budget_exhausted"] is True
    assert int(metric["anchor_attempts"]) == int(metric["work_budget_units"])


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
            for model in self.models:
                model.parent_unit = self

        def get_parent_army(self):
            return self.parent_army

        def get_attached_unit_root(self):
            return self

        def get_attached_unit_models(self):
            return list(self.models)

        def is_alive(self) -> bool:
            return True

        def is_in_reserves(self) -> bool:
            return str(self.reserve_status or "").strip().lower() != "deployed"

        def can_arrive_from_reserves(self, _turn: int) -> bool:
            return True

        def is_in_strategic_reserves(self) -> bool:
            return False

        def has_deep_strike(self) -> bool:
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

        def _create_potential_base(self, x: float, y: float, z: float, _facing: float, *, model: _Model | None = None) -> _Base:
            radius = float(model.model_base.get_radius()) if model is not None else 0.5
            return _Base(x=float(x), y=float(y), radius=radius)

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
            self.current_player_index = 0
            self.map = type(
                "Map",
                (),
                {
                    "width": 60.0,
                    "height": 44.0,
                    "units": [arriving] + list(enemies),
                    "terrain_features": [],
                    "is_within_boundary": staticmethod(lambda _model, destination: 0.0 <= float(destination[0]) <= 60.0 and 0.0 <= float(destination[1]) <= 44.0),
                    "check_collision_with_obstacles": staticmethod(lambda _model, destination: False),
                },
            )()
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

        def get_current_player(self):
            return self.players[self.current_player_index]

        def get_enemy_units(self, player):
            if player is self.players[0]:
                return list(self.players[1].army.units)
            return list(self.players[0].army.units)

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
            for model in self.models:
                model.parent_unit = self

        def get_parent_army(self):
            return self.parent_army

        def get_attached_unit_root(self):
            return self

        def get_attached_unit_models(self):
            return list(self.models)

        def is_alive(self) -> bool:
            return True

        def is_in_reserves(self) -> bool:
            return True

        def can_arrive_from_reserves(self, _turn: int) -> bool:
            return True

        def is_in_strategic_reserves(self) -> bool:
            return True

        def has_deep_strike(self) -> bool:
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

        def _create_potential_base(self, x: float, y: float, z: float, _facing: float, *, model: _Model | None = None) -> _Base:
            radius = float(model.model_base.get_radius()) if model is not None else 0.5
            base = _Base(radius=radius)
            base.x = float(x)
            base.y = float(y)
            base.z = float(z)
            return base

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
            self.current_player_index = 0
            self.map = type(
                "Map",
                (),
                {
                    "width": 60.0,
                    "height": 44.0,
                    "units": [unit],
                    "terrain_features": [],
                    "is_within_boundary": staticmethod(lambda _model, destination: 0.0 <= float(destination[0]) <= 60.0 and 0.0 <= float(destination[1]) <= 44.0),
                    "check_collision_with_obstacles": staticmethod(lambda _model, destination: False),
                },
            )()
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

        def get_current_player(self):
            return self.players[self.current_player_index]

        def get_enemy_units(self, _player):
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


def test_headless_policy_controller_uses_zone_packer_rows_for_deep_strike_before_coarse_scan() -> None:
    game, unit, request = _build_reserves_search_fixture(
        strategic=False,
        deep_strike=True,
        success_xy=(0.75, 0.75),
    )
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)

    sources = [
        source
        for source, _anchors in controller._reserves_arrival_anchor_candidate_groups(
            game,
            unit,
            context={"placement_kind": "reserves_arrival"},
        )
    ]

    assert "zone_packer_rows:upper_half" in sources
    assert sources.index("zone_packer_rows:upper_half") < sources.index("deep_strike_coarse")

    resolved = controller._try_resolve_reserves_arrival_bruteforce(game, request)

    assert resolved is True
    metric = controller.get_reserves_arrival_search_metrics()[-1]
    assert str(metric.get("first_valid_source", "") or "") == "zone_packer_rows:upper_half"
    assert int(metric.get("build_calls", 0) or 0) < 20


def test_headless_deep_strike_candidate_positions_do_not_use_strategic_edge_search(monkeypatch) -> None:
    game, unit, _request = _build_reserves_search_fixture(
        strategic=False,
        deep_strike=True,
        success_xy=(0.75, 0.75),
    )
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)

    def _fail_strategic_edge_search(_game, _unit):
        raise AssertionError("Deep Strike candidate generation must not use Strategic Reserves edge inference.")

    monkeypatch.setattr(controller, "_strategic_reserves_search_edges", _fail_strategic_edge_search)

    sources = [
        source
        for source, _anchors in controller._reserves_arrival_anchor_candidate_groups(
            game,
            unit,
            context={"placement_kind": "reserves_arrival"},
        )
    ]

    assert "zone_packer_rows:upper_half" in sources
    assert "zone_packer_rows:lower_half" in sources
    assert "zone_packer_rows:own_half" not in sources
    assert "zone_packer_rows:enemy_half" not in sources
    assert "deep_strike_coarse" in sources


def test_headless_policy_controller_places_strategic_zone_packers_after_primary_edge_band() -> None:
    game, unit, request = _build_reserves_search_fixture(
        strategic=True,
        deep_strike=False,
        success_xy=(0.75, 0.75),
    )
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)

    sources = [
        source
        for source, _anchors in controller._reserves_arrival_anchor_candidate_groups(
            game,
            unit,
            context={"placement_kind": "reserves_arrival"},
        )
    ]

    assert sources[0] == "strategic_edge_band"
    assert "zone_packer_rows:edge_own" in sources
    assert sources.index("zone_packer_rows:edge_own") < sources.index("strategic_edge_staggered")

    resolved = controller._try_resolve_reserves_arrival_bruteforce(game, request)

    assert resolved is True
    metric = controller.get_reserves_arrival_search_metrics()[-1]
    assert str(metric.get("first_valid_source", "") or "") == "zone_packer_rows:edge_own"
    assert int(metric.get("build_calls", 0) or 0) < 600


def test_headless_policy_controller_synthesizes_reanimation_placement_payload(monkeypatch) -> None:
    class _Base:
        has_circular_base = True

        def __init__(self, x: float, y: float, *, radius: float = 0.5) -> None:
            self.x = float(x)
            self.y = float(y)
            self.z = 0.0
            self.facing = 0.0
            self._radius = float(radius)

        def get_radius(self) -> float:
            return float(self._radius)

        def get_longest_radius(self) -> float:
            return float(self._radius)

    class _Model:
        def __init__(self, model_id: str, *, x: float, y: float) -> None:
            self._id = model_id
            self.id = model_id
            self.model_base = _Base(x=float(x), y=float(y))
            self.is_alive = True

        def get_location(self) -> tuple[float, float, float, float]:
            return (
                float(self.model_base.x),
                float(self.model_base.y),
                float(self.model_base.z),
                float(self.model_base.facing),
            )

        def set_location(self, x: float, y: float, z: float, facing: float) -> None:
            self.model_base.x = float(x)
            self.model_base.y = float(y)
            self.model_base.z = float(z)
            self.model_base.facing = float(facing)

    class _Unit:
        def __init__(self) -> None:
            self._id = "unit:reanimation"
            self.id = "unit:reanimation"
            self.name = "Immortals"
            anchor = _Model("model:anchor", x=1.0, y=1.0)
            returned = _Model("model:return", x=-1.0, y=-1.0)
            returned.is_alive = False
            returned._pending_placement = True
            returned._pending_placement_source = "reanimation"
            self.models = [anchor, returned]
            self.calls: list[tuple[str, list[str], int, object]] = []

        def get_attached_unit_root(self):
            return self

        def get_attached_unit_models(self):
            return list(self.models)

        def _find_reanimation_position(self, model, alive_models, *, game_map, required_neighbors):
            self.calls.append(
                (
                    str(model.id),
                    [str(other.id) for other in list(alive_models or [])],
                    int(required_neighbors),
                    game_map,
                )
            )
            return (3.0, 4.0, 0.0, 90.0)

    class _Game:
        def __init__(self, unit: _Unit) -> None:
            self.is_authoritative = True
            self.map = object()
            self._unit = unit

        def _resolve_unit_by_id(self, unit_id: str):
            if str(unit_id) == str(self._unit.id):
                return self._unit
            return None

    unit = _Unit()
    game = _Game(unit)
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Place models for Immortals",
        player_id="player:necrons",
        options=[
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": unit.id, "movement_type": "deploy", "action": "confirm"},
            )
        ],
        context={
            "unit_id": unit.id,
            "movement_type": "deploy",
            "placement_kind": "reanimation",
            "allowed_model_ids": ["model:return"],
            "allow_skip": False,
        },
    )

    resolved_payloads: list[dict[str, object]] = []

    def _fake_resolve_decision_command(
        _game,
        _request,
        _option_id,
        *,
        result_payload,
        player_id,
        metadata,
    ):
        del _game, _request, _option_id, player_id, metadata
        resolved_payloads.append(dict(result_payload or {}))
        return _ApplyResult(ok=True)

    monkeypatch.setattr(headless_policy_module, "resolve_decision_command", _fake_resolve_decision_command)

    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    controller.on_decision_requested(game, request)

    assert resolved_payloads == [
        {
            "unit_id": "unit:reanimation",
            "movement_type": "deploy",
            "action": "confirm",
            "model_positions": [
                {
                    "model_id": "model:return",
                    "position": [3.0, 4.0, 0.0],
                    "facing": 90.0,
                }
            ],
        }
    ]
    assert unit.calls == [("model:return", ["model:anchor"], 1, game.map)]
    assert unit.models[1].get_location() == (-1.0, -1.0, 0.0, 0.0)


def test_headless_policy_controller_synthesizes_reanimation_from_attached_members(monkeypatch) -> None:
    class _Base:
        has_circular_base = True

        def __init__(self, x: float, y: float, *, radius: float = 0.5) -> None:
            self.x = float(x)
            self.y = float(y)
            self.z = 0.0
            self.facing = 0.0
            self._radius = float(radius)

        def get_radius(self) -> float:
            return float(self._radius)

        def get_longest_radius(self) -> float:
            return float(self._radius)

    class _Model:
        def __init__(self, model_id: str, *, x: float, y: float, alive: bool = True) -> None:
            self._id = model_id
            self.id = model_id
            self.model_base = _Base(x=float(x), y=float(y))
            self.is_alive = bool(alive)

        def get_location(self) -> tuple[float, float, float, float]:
            return (
                float(self.model_base.x),
                float(self.model_base.y),
                float(self.model_base.z),
                float(self.model_base.facing),
            )

        def set_location(self, x: float, y: float, z: float, facing: float) -> None:
            self.model_base.x = float(x)
            self.model_base.y = float(y)
            self.model_base.z = float(z)
            self.model_base.facing = float(facing)

    class _Root:
        def __init__(self) -> None:
            self._id = "unit:root"
            self.id = "unit:root"
            self.name = "Attached Root"
            self.calls: list[tuple[str, list[str], int, object]] = []
            self.members = []

        def get_attached_unit_root(self):
            return self

        def get_attached_unit_members(self):
            return list(self.members)

        def get_attached_unit_models(self):
            return []

        def _find_reanimation_position(self, model, alive_models, *, game_map, required_neighbors):
            self.calls.append(
                (
                    str(model.id),
                    [str(other.id) for other in list(alive_models or [])],
                    int(required_neighbors),
                    game_map,
                )
            )
            return (6.0, 7.0, 0.0, 45.0)

    class _MemberUnit:
        def __init__(self, unit_id: str, root: _Root, models: list[_Model]) -> None:
            self._id = unit_id
            self.id = unit_id
            self.name = unit_id
            self._root = root
            self.models = list(models)

        def get_attached_unit_root(self):
            return self._root

    class _Game:
        def __init__(self, member: _MemberUnit) -> None:
            self.is_authoritative = True
            self.map = object()
            self._member = member

        def _resolve_unit_by_id(self, unit_id: str):
            if str(unit_id) == str(self._member.id):
                return self._member
            return None

    root = _Root()
    anchor_member = _MemberUnit("unit:leader", root, [_Model("model:anchor", x=2.0, y=2.0, alive=True)])
    pending_model = _Model("model:return", x=-2.0, y=-2.0, alive=False)
    pending_model._pending_placement = True
    pending_model._pending_placement_source = "reanimation"
    target_member = _MemberUnit("unit:bodyguard", root, [pending_model])
    root.members = [anchor_member, target_member]
    game = _Game(target_member)
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Place models for Necron Warriors",
        player_id="player:necrons",
        options=[
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": target_member.id, "movement_type": "deploy", "action": "confirm"},
            )
        ],
        context={
            "unit_id": target_member.id,
            "movement_type": "deploy",
            "placement_kind": "reanimation",
            "allowed_model_ids": ["model:return"],
            "allow_skip": False,
        },
    )

    resolved_payloads: list[dict[str, object]] = []

    def _fake_resolve_decision_command(
        _game,
        _request,
        _option_id,
        *,
        result_payload,
        player_id,
        metadata,
    ):
        del _game, _request, _option_id, player_id, metadata
        resolved_payloads.append(dict(result_payload or {}))
        return _ApplyResult(ok=True)

    monkeypatch.setattr(headless_policy_module, "resolve_decision_command", _fake_resolve_decision_command)

    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    controller.on_decision_requested(game, request)

    assert resolved_payloads == [
        {
            "unit_id": "unit:bodyguard",
            "movement_type": "deploy",
            "action": "confirm",
            "model_positions": [
                {
                    "model_id": "model:return",
                    "position": [6.0, 7.0, 0.0],
                    "facing": 45.0,
                }
            ],
        }
    ]
    assert root.calls == [("model:return", ["model:anchor"], 1, game.map)]
    assert pending_model.get_location() == (-2.0, -2.0, 0.0, 0.0)


def test_headless_policy_controller_backtracks_reanimation_positions_to_restore_coherency(monkeypatch) -> None:
    from warhammer40k_ai.utility.calcs import validate_unit_coherency_after_movement

    class _Base:
        has_circular_base = True

        def __init__(self, base_type: str = "circular", radius: float = 0.6299) -> None:
            self.base_type = str(base_type)
            self.radius = float(radius)
            self.x = 0.0
            self.y = 0.0
            self.z = 0.0
            self.facing = 0.0

        def set_position(self, x: float, y: float, z: float) -> None:
            self.x = float(x)
            self.y = float(y)
            self.z = float(z)

        def set_facing(self, facing: float) -> None:
            self.facing = float(facing)

        def get_radius(self) -> float:
            return float(self.radius)

        def get_longest_radius(self) -> float:
            return float(self.radius)

        def get_base_shape(self):
            return Point(float(self.x), float(self.y)).buffer(float(self.radius))

        def collides_with(self, other: "_Base") -> bool:
            return bool(self.get_base_shape().distance(other.get_base_shape()) <= 1e-6)

    class _Model:
        def __init__(
            self,
            model_id: str,
            *,
            x: float,
            y: float,
            z: float = 0.0,
            facing: float = 1.6671,
            alive: bool = True,
        ) -> None:
            self._id = model_id
            self.id = model_id
            self.model_base = _Base()
            self.model_base.set_position(float(x), float(y), float(z))
            self.model_base.set_facing(float(facing))
            self.is_alive = bool(alive)
            self._pending_placement = False
            self._pending_placement_source = ""

        def get_location(self) -> tuple[float, float, float, float]:
            return (
                float(self.model_base.x),
                float(self.model_base.y),
                float(self.model_base.z),
                float(self.model_base.facing),
            )

        def set_location(self, x: float, y: float, z: float, facing: float) -> None:
            self.model_base.set_position(float(x), float(y), float(z))
            self.model_base.set_facing(float(facing))

    class _Map:
        def is_within_boundary(self, _model: object, destination: tuple[float, float]) -> bool:
            x, y = destination
            return 0.0 <= float(x) <= 60.0 and 0.0 <= float(y) <= 44.0

        def check_collision_with_obstacles(self, _model: object, destination: tuple[float, float]) -> bool:
            del destination
            return False

        def check_collision_with_other_friendly_units(self, _model: object, destination: tuple[float, float]) -> bool:
            del destination
            return False

        def check_collision_with_other_enemy_units(self, _model: object, destination: tuple[float, float]) -> bool:
            del destination
            return False

    class _Unit:
        def __init__(self) -> None:
            self._id = "unit:warriors"
            self.id = "unit:warriors"
            self.name = "Necron Warriors"
            facing = 1.6671
            anchored_positions = [
                ("model:a1", 43.026, 22.191, 0.12),
                ("model:a2", 44.534, 22.191, 0.0),
                ("model:a3", 46.042, 22.191, 0.0),
                ("model:a4", 48.050, 22.191, 0.0),
                ("model:a5", 45.034, 23.699, 0.0),
                ("model:a6", 43.254, 20.912, 0.0),
            ]
            pending_positions = [
                ("model:p1", 44.534, 20.683, 0.0),
                ("model:p2", 46.042, 20.683, 0.0),
                ("model:p3", 48.050, 20.683, 0.0),
            ]
            self.models = [
                _Model(model_id, x=x, y=y, z=z, facing=facing, alive=True)
                for model_id, x, y, z in anchored_positions
            ]
            for model_id, x, y, z in pending_positions:
                model = _Model(model_id, x=x, y=y, z=z, facing=facing, alive=True)
                model._pending_placement = True
                model._pending_placement_source = "reanimation"
                self.models.append(model)
            self._greedy_positions = {
                "model:p1": (43.681, 23.325493, 0.12, facing),
                "model:p2": (42.371, 23.325493, 0.12, facing),
                "model:p3": (41.716, 22.191000, 0.12, facing),
            }

        def get_attached_unit_root(self):
            return self

        def get_attached_unit_models(self):
            return list(self.models)

        def _create_potential_base(self, x: float, y: float, z: float, facing: float, *, model: _Model | None = None) -> _Base:
            radius = float(model.model_base.get_radius()) if model is not None else 0.6299
            base = _Base(radius=radius)
            base.set_position(float(x), float(y), float(z))
            base.set_facing(float(facing))
            return base

        def _reanimation_position_valid(
            self,
            x: float,
            y: float,
            z: float,
            facing: float,
            model: _Model,
            alive_models: list[_Model],
            game_map: _Map,
            required_neighbors: int,
        ) -> bool:
            if not game_map.is_within_boundary(model, (x, y)):
                return False
            candidate_base = self._create_potential_base(x, y, z, facing, model=model)
            for other in list(alive_models or []):
                if not getattr(other, "is_alive", True):
                    continue
                if candidate_base.collides_with(other.model_base):
                    return False
            if required_neighbors <= 0:
                return True
            neighbors = 0
            for other in list(alive_models or []):
                if not getattr(other, "is_alive", True):
                    continue
                horizontal = candidate_base.get_base_shape().distance(other.model_base.get_base_shape())
                vertical = abs(float(candidate_base.z) - float(other.model_base.z))
                if horizontal <= 2.0 + 1e-6 and vertical <= 5.0 + 1e-6:
                    neighbors += 1
                    if neighbors >= required_neighbors:
                        return True
            return False

        def _find_reanimation_position(self, model, alive_models, *, game_map, required_neighbors):
            del alive_models, game_map, required_neighbors
            return self._greedy_positions[str(model.id)]

    class _Game:
        def __init__(self, unit: _Unit) -> None:
            self.is_authoritative = True
            self.map = _Map()
            self._unit = unit

        def _resolve_unit_by_id(self, unit_id: str):
            if str(unit_id) == str(self._unit.id):
                return self._unit
            return None

    unit = _Unit()
    game = _Game(unit)
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Place models for Necron Warriors",
        player_id="player:necrons",
        options=[
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": unit.id, "movement_type": "deploy", "action": "confirm"},
            )
        ],
        context={
            "unit_id": unit.id,
            "movement_type": "deploy",
            "placement_kind": "reanimation",
            "allowed_model_ids": ["model:p1", "model:p2", "model:p3"],
            "allow_skip": False,
        },
    )

    resolved_payloads: list[dict[str, object]] = []

    def _payload_is_coherent(model_positions: list[dict[str, object]]) -> bool:
        original_locations = {str(model.id): model.get_location() for model in unit.models}
        try:
            for entry in list(model_positions or []):
                model_id = str(entry.get("model_id", "") or "")
                target = next((model for model in unit.models if str(model.id) == model_id), None)
                if target is None:
                    return False
                position = list(entry.get("position", []) or [])
                if len(position) < 3:
                    return False
                target.set_location(
                    float(position[0]),
                    float(position[1]),
                    float(position[2]),
                    float(entry.get("facing", 0.0) or 0.0),
                )
            coherent, _bad = validate_unit_coherency_after_movement(
                unit,
                [tuple(model.get_location()[:3]) for model in unit.models],
                ignore_pending=False,
            )
            return bool(coherent)
        finally:
            for model in unit.models:
                location = original_locations[str(model.id)]
                model.set_location(*location)

    def _fake_resolve_decision_command(
        _game,
        _request,
        _option_id,
        *,
        result_payload,
        player_id,
        metadata,
    ):
        del _game, _request, _option_id, player_id, metadata
        resolved_payloads.append(dict(result_payload or {}))
        coherent = _payload_is_coherent(list(result_payload.get("model_positions", []) or []))
        return _ApplyResult(ok=coherent)

    monkeypatch.setattr(headless_policy_module, "resolve_decision_command", _fake_resolve_decision_command)

    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)
    controller.on_decision_requested(game, request)

    assert len(resolved_payloads) == 1
    model_positions = list(resolved_payloads[0].get("model_positions", []) or [])
    assert len(model_positions) == 3
    third = next(entry for entry in model_positions if str(entry.get("model_id", "")) == "model:p3")
    assert float(third["position"][0]) > 44.0
