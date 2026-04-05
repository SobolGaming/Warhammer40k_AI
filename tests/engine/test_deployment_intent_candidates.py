from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_DECLARE_RESERVES,
    DECISION_MOVE_UNIT,
    DECISION_SCOUT_MOVE,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
)
from warhammer40k_ai.engine.decision_requests import (
    build_deployment_zone_request,
    build_reserves_allocation_request,
    build_scout_move_request,
    build_select_next_deploy_unit_request,
)
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.player import Player


class _DummyUnit:
    def __init__(
        self,
        unit_id: str,
        name: str,
        *,
        infiltrate: bool = False,
        deep_strike: bool = False,
        scout_distance: float = 0.0,
        is_leader: bool = False,
        is_transport: bool = False,
        is_titanic: bool = False,
        model_count: int = 5,
        keywords: list[str] | None = None,
    ) -> None:
        self.id = unit_id
        self._id = unit_id
        self.name = name
        self._infiltrate = bool(infiltrate)
        self._deep_strike = bool(deep_strike)
        self.scout_move_distance = float(scout_distance)
        self.is_leader = bool(is_leader)
        self.is_transport = bool(is_transport)
        self.is_titanic = bool(is_titanic)
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.models = [_DummyModel(f"{unit_id}:model:{idx}") for idx in range(max(1, int(model_count)))]
        self.parent_army = None
        self.deployed = True
        self.reserve_status = "deployed"

    def has_infiltrate(self) -> bool:
        return bool(self._infiltrate)

    def has_deep_strike(self) -> bool:
        return bool(self._deep_strike)

    def has_scout(self):
        if self.scout_move_distance > 0.0:
            return (True, float(self.scout_move_distance))
        return (False, 0.0)

    def get_unit_cost(self) -> int:
        return 100


class _DummyModel:
    def __init__(self, model_id: str) -> None:
        self.id = model_id
        self._id = model_id
        self.is_alive = True
        self._location = (10.0, 10.0, 0.0, 0.0)

    def get_location(self):
        return self._location


class _DummyArmy:
    def __init__(self, army_id: str, units: list[object]) -> None:
        self._id = army_id
        self.id = army_id
        self.units = list(units)
        self.player = None
        for unit in self.units:
            setattr(unit, "parent_army", self)

    def get_reserve_limits(self) -> dict:
        return {
            "max_units": max(1, len(list(self.units or []))),
            "max_points": 1000,
            "max_strategic_points": 500,
        }

    def validate_reserves_decisions(self, reserves_decisions: dict) -> dict:
        reserve_units = 0
        reserve_points = 0
        strategic_points = 0
        for unit in list(self.units or []):
            unit_id = str(getattr(unit, "id", "") or getattr(unit, "_id", "") or "")
            status = str(dict(reserves_decisions or {}).get(unit_id, "deploy") or "deploy")
            if status in ("reserves", "strategic_reserves"):
                reserve_units += 1
                reserve_points += int(getattr(unit, "get_unit_cost", lambda: 0)() or 0)
                if status == "strategic_reserves":
                    strategic_points += int(getattr(unit, "get_unit_cost", lambda: 0)() or 0)
        limits = self.get_reserve_limits()
        valid = (
            reserve_units <= int(limits["max_units"])
            and reserve_points <= int(limits["max_points"])
            and strategic_points <= int(limits["max_strategic_points"])
        )
        return {
            "valid": bool(valid),
            "errors": [] if valid else ["reserve limits exceeded"],
            "reserve_units": int(reserve_units),
            "reserve_points": int(reserve_points),
            "strategic_points": int(strategic_points),
            "limits": dict(limits),
        }

    def enforce_reserves_limits(self, reserves_decisions: dict) -> dict:
        return dict(reserves_decisions or {})

    def set_player(self, player: object) -> None:
        self.player = player


def _build_game() -> tuple[Game, Player, _DummyUnit, _DummyUnit]:
    p1 = Player("P1")
    p2 = Player("P2")
    infiltrator = _DummyUnit(
        "unit:infiltrator",
        "Forward Screen",
        infiltrate=True,
        model_count=10,
        keywords=["INFILTRATORS"],
    )
    hammer = _DummyUnit(
        "unit:hammer",
        "Hammer Brick",
        deep_strike=True,
        model_count=5,
        keywords=["DEEP STRIKE"],
    )
    p1.army = _DummyArmy("army-1", [infiltrator, hammer])
    p2.army = _DummyArmy("army-2", [])
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
    game.deployment_zones = {
        p1.id: {"name": "Left Zone", "zone_type": "defender", "x_range": [0.0, 30.0], "y_range": [0.0, 44.0]},
        p2.id: {"name": "Right Zone", "zone_type": "attacker", "x_range": [30.0, 60.0], "y_range": [0.0, 44.0]},
    }
    return game, p1, infiltrator, hammer


def _candidate_view(request: DecisionRequest) -> list[tuple[str, dict, dict]]:
    normalized: list[tuple[str, dict, dict]] = []
    for candidate in list(request.candidates or []):
        metadata = dict(candidate.metadata or {})
        metadata.pop("solver_ms", None)
        normalized.append((str(candidate.action_id), dict(candidate.params or {}), metadata))
    return normalized


def test_deployment_zone_candidates_include_solver_metadata_and_are_deterministic() -> None:
    game, player, _screen, _hammer = _build_game()
    zones = [
        {"name": "Left Zone", "zone_type": "defender", "x_range": [0.0, 24.0], "y_range": [0.0, 44.0]},
        {"name": "Right Zone", "zone_type": "attacker", "x_range": [36.0, 60.0], "y_range": [0.0, 44.0]},
    ]
    first = build_deployment_zone_request(game, player, zones, queue_requests=True)
    second = build_deployment_zone_request(game, player, zones, queue_requests=True)
    assert first is not None
    assert second is not None
    assert first.decision_type == DECISION_CHOOSE_DEPLOYMENT_ZONE
    assert "deployment_intent" in first.context

    first_candidates = list(first.candidates or [])
    assert first_candidates
    for candidate in first_candidates:
        metadata = dict(candidate.metadata or {})
        assert metadata.get("candidate_kind") == "deployment_zone"
        assert "reserve_denial_delta" in metadata
        assert "screen_integrity_delta" in metadata
        assert "projected_exposure_delta_if_enemy_goes_first" in metadata
        assert "los_tunnel_count" in metadata
        assert "infantry_objective_approach_quality" in metadata
        assert metadata.get("semantic_projection_kind") == "generic"

    assert _candidate_view(first) == _candidate_view(second)


def test_select_next_deploy_unit_candidates_include_unit_profile_and_screen_delta() -> None:
    game, player, screen_unit, hammer_unit = _build_game()
    request = build_select_next_deploy_unit_request(
        game,
        player,
        [hammer_unit, screen_unit],
        deployment_zone={"name": "Left Zone", "zone_type": "defender"},
        already_deployed_units=[hammer_unit],
        queue_requests=True,
    )
    assert request is not None
    assert request.decision_type == DECISION_SELECT_NEXT_DEPLOY_UNIT
    assert int(request.context.get("already_deployed_count", 0) or 0) == 1
    assert "deployment_intent" in request.context

    by_unit_id = {
        str(candidate.params.get("unit_id", "") or ""): candidate
        for candidate in list(request.candidates or [])
    }
    assert "unit:infiltrator" in by_unit_id
    assert "unit:hammer" in by_unit_id

    screen_metadata = dict(by_unit_id["unit:infiltrator"].metadata or {})
    hammer_metadata = dict(by_unit_id["unit:hammer"].metadata or {})
    assert screen_metadata.get("candidate_kind") == "deployment_commit_order"
    assert isinstance(screen_metadata.get("unit_profile"), dict)
    assert float(screen_metadata.get("screen_integrity_delta", 0.0)) > float(hammer_metadata.get("screen_integrity_delta", 0.0))


def test_deployment_move_request_uses_deployment_solver_candidate_payload() -> None:
    game, player, screen_unit, _hammer = _build_game()
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Deploy Forward Screen",
        player_id=player.id,
        options=[
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": screen_unit.id, "movement_type": "deploy", "action": "confirm"},
            )
        ],
        context={
            "unit_id": screen_unit.id,
            "movement_type": "deploy",
            "placement_kind": "deployment",
            "deployment_model_positions": [
                {
                    "model_id": "m1",
                    "position": [10.0, 10.0, 0.0],
                    "facing": 0.0,
                }
            ],
            "deployment_intent": {
                "desired_affordances": ["SAFE_STAGING", "SCREEN_DEPTH"],
                "weights": {
                    "score": 0.3,
                    "deny": 0.22,
                    "safety": 0.28,
                    "staging": 0.2,
                    "reserve_deny": 0.24,
                    "screen": 0.25,
                    "countercharge": 0.15,
                    "cover": 0.2,
                    "los": 0.1,
                    "aura": 0.1,
                },
            },
        },
    )

    game.request_decision(request)
    assert request.candidates
    candidate = request.candidates[0]
    metadata = dict(candidate.metadata or {})
    assert metadata.get("candidate_kind") == "deployment_move"
    assert "model_positions" in dict(candidate.params or {})


def test_deployment_move_candidates_vary_by_runtime_placement_option() -> None:
    game, player, screen_unit, _hammer = _build_game()
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Deploy Forward Screen",
        player_id=player.id,
        options=[
            DecisionOption.create(
                "Forward Candidate",
                payload={
                    "unit_id": screen_unit.id,
                    "movement_type": "deploy",
                    "action": "confirm",
                    "placement_candidate_id": "cand:forward",
                    "placement_candidate_index": 0,
                    "deployment_anchor": [12.0, 10.0],
                    "model_positions": [
                        {
                            "model_id": "m1",
                            "position": [12.0, 10.0, 0.0],
                            "facing": 0.0,
                        }
                    ],
                },
            ),
            DecisionOption.create(
                "Back Candidate",
                payload={
                    "unit_id": screen_unit.id,
                    "movement_type": "deploy",
                    "action": "confirm",
                    "placement_candidate_id": "cand:back",
                    "placement_candidate_index": 1,
                    "deployment_anchor": [6.0, 10.0],
                    "model_positions": [
                        {
                            "model_id": "m1",
                            "position": [6.0, 10.0, 0.0],
                            "facing": 0.0,
                        }
                    ],
                },
            ),
        ],
        context={
            "unit_id": screen_unit.id,
            "movement_type": "deploy",
            "placement_kind": "deployment",
            "deployment_candidate_count": 2,
            "deployment_intent": {
                "desired_affordances": ["LOS_TUNNEL_ADVANCE", "SCREEN_DEPTH"],
                "anchors": {
                    "deployment_center_x": "8.0",
                    "deployment_center_y": "10.0",
                },
                "weights": {
                    "score": 0.32,
                    "deny": 0.22,
                    "safety": 0.26,
                    "staging": 0.22,
                    "reserve_deny": 0.24,
                    "screen": 0.25,
                    "countercharge": 0.15,
                    "cover": 0.2,
                    "los": 0.12,
                    "aura": 0.1,
                },
            },
        },
    )

    game.request_decision(request)
    assert len(list(request.candidates or [])) == 2
    by_candidate_id = {
        str(dict(candidate.params or {}).get("placement_candidate_id", "") or ""): candidate
        for candidate in list(request.candidates or [])
    }
    assert "cand:forward" in by_candidate_id
    assert "cand:back" in by_candidate_id
    forward_meta = dict(by_candidate_id["cand:forward"].metadata or {})
    back_meta = dict(by_candidate_id["cand:back"].metadata or {})
    assert forward_meta.get("candidate_kind") == "deployment_move"
    assert float(forward_meta.get("forward_progress_norm", 0.0) or 0.0) != float(back_meta.get("forward_progress_norm", 0.0) or 0.0)
    assert float(forward_meta.get("projected_score_delta_next_window", 0.0) or 0.0) != float(
        back_meta.get("projected_score_delta_next_window", 0.0) or 0.0
    )


def test_deployment_move_lookahead_layer_adds_runtime_rollout_metadata() -> None:
    game, player, screen_unit, _hammer = _build_game()

    def _request(*, include_lookahead: bool) -> DecisionRequest:
        context = {
            "unit_id": screen_unit.id,
            "movement_type": "deploy",
            "placement_kind": "deployment",
            "deployment_candidate_count": 2,
            "deployment_intent": {
                "desired_affordances": ["LOS_TUNNEL_ADVANCE", "SCREEN_DEPTH"],
                "anchors": {
                    "deployment_center_x": "8.0",
                    "deployment_center_y": "10.0",
                },
                "weights": {
                    "score": 0.32,
                    "deny": 0.22,
                    "safety": 0.26,
                    "staging": 0.22,
                    "reserve_deny": 0.24,
                    "screen": 0.25,
                    "countercharge": 0.15,
                    "cover": 0.2,
                    "los": 0.12,
                    "aura": 0.1,
                },
            },
        }
        if include_lookahead:
            context["deployment_lookahead"] = {
                "enabled": True,
                "depth": 2,
                "branch_count": 3,
                "discount": 0.64,
                "score_blend": 0.22,
                "candidate_kinds": ["deployment_move"],
            }
        return DecisionRequest.create(
            DECISION_MOVE_UNIT,
            "Deploy Forward Screen",
            player_id=player.id,
            options=[
                DecisionOption.create(
                    "Forward Candidate",
                    payload={
                        "unit_id": screen_unit.id,
                        "movement_type": "deploy",
                        "action": "confirm",
                        "placement_candidate_id": "cand:forward",
                        "placement_candidate_index": 0,
                        "deployment_anchor": [12.0, 10.0],
                        "model_positions": [
                            {
                                "model_id": "m1",
                                "position": [12.0, 10.0, 0.0],
                                "facing": 0.0,
                            }
                        ],
                    },
                ),
                DecisionOption.create(
                    "Back Candidate",
                    payload={
                        "unit_id": screen_unit.id,
                        "movement_type": "deploy",
                        "action": "confirm",
                        "placement_candidate_id": "cand:back",
                        "placement_candidate_index": 1,
                        "deployment_anchor": [6.0, 10.0],
                        "model_positions": [
                            {
                                "model_id": "m1",
                                "position": [6.0, 10.0, 0.0],
                                "facing": 0.0,
                            }
                        ],
                    },
                ),
            ],
            context=context,
        )

    without_lookahead = _request(include_lookahead=False)
    with_lookahead = _request(include_lookahead=True)
    game.request_decision(without_lookahead)
    game.request_decision(with_lookahead)

    baseline_by_id = {
        str(dict(candidate.params or {}).get("placement_candidate_id", "") or ""): dict(candidate.metadata or {})
        for candidate in list(without_lookahead.candidates or [])
    }
    rollout_by_id = {
        str(dict(candidate.params or {}).get("placement_candidate_id", "") or ""): dict(candidate.metadata or {})
        for candidate in list(with_lookahead.candidates or [])
    }
    assert "cand:forward" in baseline_by_id
    assert "cand:forward" in rollout_by_id
    rollout_meta = dict(rollout_by_id["cand:forward"] or {})
    baseline_meta = dict(baseline_by_id["cand:forward"] or {})
    assert rollout_meta.get("lookahead_enabled") is True
    assert "lookahead_total_value" in rollout_meta
    assert "lookahead_worst_branch_name" in rollout_meta
    assert "lookahead_adjusted_score_delta_round" in rollout_meta
    assert float(rollout_meta.get("lookahead_base_projected_score_delta_round", 0.0) or 0.0) != float(
        rollout_meta.get("lookahead_adjusted_score_delta_round", 0.0) or 0.0
    )
    assert float(rollout_meta.get("projected_score_delta_round", 0.0) or 0.0) != float(
        baseline_meta.get("projected_score_delta_round", 0.0) or 0.0
    )


def test_reserves_request_generates_rankable_candidates_with_semantic_metadata() -> None:
    game, player, _screen_unit, _hammer = _build_game()
    request = build_reserves_allocation_request(game, player.army, queue_requests=True)
    assert request is not None
    assert request.decision_type == DECISION_DECLARE_RESERVES
    assert len(list(request.options or [])) >= 2
    assert request.candidates
    assert all(
        str(dict(candidate.metadata or {}).get("candidate_kind", "") or "") == "deployment_reserves"
        for candidate in list(request.candidates or [])
    )
    first_metadata = dict(request.candidates[0].metadata or {})
    assert "deep_strike_pressure_delta" in first_metadata
    assert "reserve_entry_lane_delta" in first_metadata
    assert "reserve_denial_delta" in first_metadata


def test_scout_move_request_generates_rankable_destination_candidates() -> None:
    game, _player, screen_unit, _hammer = _build_game()
    request = build_scout_move_request(game, screen_unit)
    assert request is not None
    assert request.decision_type == DECISION_SCOUT_MOVE
    scout_options = [
        option
        for option in list(request.options or [])
        if str(dict(option.payload or {}).get("action", "") or "") == "scout"
    ]
    assert scout_options
    assert any(
        isinstance(dict(option.payload or {}).get("destination"), list)
        for option in scout_options
    )
    scout_candidates = [
        candidate
        for candidate in list(request.candidates or [])
        if str(dict(candidate.params or {}).get("action", "") or "") == "scout"
    ]
    assert scout_candidates
    metadata = dict(scout_candidates[0].metadata or {})
    assert metadata.get("candidate_kind") == "deployment_scout"
    assert "reserve_entry_lane_delta" in metadata
