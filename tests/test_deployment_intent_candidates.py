from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_MOVE_UNIT,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
)
from warhammer40k_ai.engine.decision_requests import (
    build_deployment_zone_request,
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

    def has_infiltrate(self) -> bool:
        return bool(self._infiltrate)

    def has_deep_strike(self) -> bool:
        return bool(self._deep_strike)


class _DummyModel:
    def __init__(self, model_id: str) -> None:
        self.id = model_id
        self._id = model_id
        self.is_alive = True


class _DummyArmy:
    def __init__(self, army_id: str, units: list[object]) -> None:
        self._id = army_id
        self.id = army_id
        self.units = list(units)
        self.player = None
        for unit in self.units:
            setattr(unit, "parent_army", self)

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
