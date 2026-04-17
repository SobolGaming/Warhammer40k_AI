from __future__ import annotations

import json
from pathlib import Path

import pytest
from shapely.geometry import Point

from warhammer40k_ai.battlefield.map import Map, TerrainFactory
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionRequest
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_DEPLOYMENT_ZONE, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.deployment_ranker import DEFAULT_DEPLOYMENT_RANKER_FEATURE_KEYS
from warhammer40k_ai.engine.deployment_headless import DeterministicDeploymentDecisionMaker
from warhammer40k_ai.engine.game_mixins.setup_deployment_reserves_mixin import GameSetupDeploymentReservesMixin


class _StubBase:
    has_circular_base = True

    def __init__(self, radius: float = 0.5) -> None:
        self._radius = float(radius)
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.facing = 0.0

    def get_radius(self) -> float:
        return float(self._radius)

    def get_base_shape_at(self, x: float, y: float, facing: float):
        return Point(float(x), float(y)).buffer(self._radius)


class _StubModel:
    def __init__(self, model_id: str) -> None:
        self._id = model_id
        self.id = model_id
        self.model_base = _StubBase(radius=0.5)
        self.is_alive = True

    def set_location(self, x: float, y: float, z: float, facing: float = 0.0) -> None:
        self.model_base.x = float(x)
        self.model_base.y = float(y)
        self.model_base.z = float(z)
        self.model_base.facing = float(facing)

    def get_location(self) -> tuple[float, float, float, float]:
        return (
            float(self.model_base.x),
            float(self.model_base.y),
            float(self.model_base.z),
            float(self.model_base.facing),
        )


class _StubUnit:
    def __init__(
        self,
        unit_id: str,
        *,
        must_start_in_reserves: bool,
        infiltrate: bool = False,
        map_obj: object | None = None,
    ) -> None:
        self._id = unit_id
        self.id = unit_id
        self._must_start_in_reserves = bool(must_start_in_reserves)
        self._infiltrate = bool(infiltrate)
        self._map = map_obj
        self.models = [_StubModel(f"{unit_id}:model")]
        self.name = f"Unit {unit_id}"
        self._army = type("ArmyLink", (), {"player": type("PlayerLink", (), {"id": "player:1"})()})()

    def must_start_in_reserves(self) -> bool:
        return bool(self._must_start_in_reserves)

    def has_infiltrate(self) -> bool:
        return bool(self._infiltrate)

    def get_parent_army(self):
        return self._army

    def calculate_model_positions(
        self,
        x,
        y,
        game_map,
        avoid_friendly_units=False,
        boundary_repulsors=None,
        search_context=None,
    ):
        del search_context
        use_map = self._map if self._map is not None else game_map
        z = float(use_map.get_height_at_point(float(x), float(y))) if use_map is not None else 0.0
        return [(float(x), float(y), z, 0.0)]


class _StubArmy:
    def __init__(self, units) -> None:
        self.units = list(units)
        self.validated_payload = None

    def validate_reserves_decisions(self, decisions):
        self.validated_payload = dict(decisions)
        return {"valid": True}


class _StubPlayer:
    def __init__(self, army, *, player_id: str = "player:1", name: str = "Player One") -> None:
        self.id = player_id
        self.name = name
        self._army = army

    def get_army(self):
        return self._army


class _ZoneStub:
    def __init__(self, min_x: float, max_x: float, min_y: float, max_y: float) -> None:
        self.vertices = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
        self.min_x = float(min_x)
        self.max_x = float(max_x)
        self.min_y = float(min_y)
        self.max_y = float(max_y)

    def contains_point(self, x: float, y: float) -> bool:
        return self.min_x <= float(x) <= self.max_x and self.min_y <= float(y) <= self.max_y


def test_forced_only_reserve_policy_keeps_optional_units_deployed() -> None:
    required = _StubUnit("unit:required", must_start_in_reserves=True)
    optional = _StubUnit("unit:optional", must_start_in_reserves=False)
    army = _StubArmy([required, optional])
    player = _StubPlayer(army)

    maker = DeterministicDeploymentDecisionMaker(game=object(), reserve_policy="forced_only")
    decisions = maker.declare_reserves(player)

    assert decisions == {
        "unit:required": "reserves",
        "unit:optional": "deploy",
    }
    assert army.validated_payload == decisions


def test_invalid_reserve_policy_raises_value_error() -> None:
    with pytest.raises(ValueError):
        DeterministicDeploymentDecisionMaker(game=object(), reserve_policy="unknown_policy")


def test_infiltrators_can_search_outside_assigned_deployment_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FlatMap:
        @staticmethod
        def get_height_at_point(_x: float, _y: float) -> float:
            return 0.0

    unit = _StubUnit("unit:infil", must_start_in_reserves=False, infiltrate=True, map_obj=_FlatMap())

    class _StubGame:
        def __init__(self) -> None:
            self.map = object()
            self.battlefield = type("BF", (), {"width": 60.0, "height": 44.0})()

        def is_valid_deployment_position(self, _unit, x: float, _y: float, _player_id: str) -> bool:
            return float(x) > 20.0

    game = _StubGame()
    maker = DeterministicDeploymentDecisionMaker(game=game)
    zone = {"name": "assigned", "mission_zones": [_ZoneStub(0.0, 10.0, 0.0, 44.0)]}

    # Isolate candidate-generation behavior from the full movement/deployment validator stack.
    monkeypatch.setattr("warhammer40k_ai.engine.deployment_headless.validate_decision", lambda *_args, **_kwargs: ())

    x, y = maker.choose_unit_deployment_position(unit, zone, already_deployed=[])
    assert float(x) > 20.0
    assert 0.0 <= float(y) <= 44.0


def test_headless_builder_prefers_upper_ruins_floor_for_single_model() -> None:
    game_map = Map(width=60, height=44)
    ruins = TerrainFactory.create_ruins(
        [(3.0, 18.0), (9.0, 18.0), (9.0, 26.0), (3.0, 26.0)],
        wall_height=4.0,
        num_floors=2,
    )
    game_map.add_terrain_feature(ruins)

    unit = _StubUnit("unit:ruins", must_start_in_reserves=False, infiltrate=False, map_obj=game_map)

    class _StubGame:
        def __init__(self, map_obj: Map) -> None:
            self.map = map_obj
            self.battlefield = type("BF", (), {"width": 60.0, "height": 44.0})()

    maker = DeterministicDeploymentDecisionMaker(game=_StubGame(game_map))
    payload = maker.build_deployment_model_positions(unit, (6.0, 22.0))

    assert payload
    pos = list(payload[0].get("position", []) or [])
    assert len(pos) >= 3
    # Ground floor in this engine is 0.12"; upper floors are 4.12" and 8.12".
    assert float(pos[2]) >= 4.12


def test_chosen_floor_payload_is_cached_for_deployment_manager_consumption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game_map = Map(width=60, height=44)
    ruins = TerrainFactory.create_ruins(
        [(3.0, 18.0), (9.0, 18.0), (9.0, 26.0), (3.0, 26.0)],
        wall_height=4.0,
        num_floors=2,
    )
    game_map.add_terrain_feature(ruins)

    unit = _StubUnit("unit:cached", must_start_in_reserves=False, infiltrate=False, map_obj=game_map)
    zone = {"name": "assigned", "mission_zones": [_ZoneStub(0.0, 10.0, 0.0, 44.0)]}

    class _StubGame:
        def __init__(self, map_obj: Map) -> None:
            self.map = map_obj
            self.battlefield = type("BF", (), {"width": 60.0, "height": 44.0})()

        def is_valid_deployment_position(self, _unit, _x: float, _y: float, _player_id: str) -> bool:
            return True

    # Force acceptance only for elevated placements so choose() must cache an upper-floor payload.
    def _validate_floor_only(_game, _request, result):
        model_positions = list((result.payload or {}).get("model_positions", []) or [])
        if not model_positions:
            return ("missing model_positions",)
        pos = list(model_positions[0].get("position", []) or [])
        if len(pos) < 3:
            return ("missing z",)
        return () if float(pos[2]) >= 4.12 else ("ground floor rejected for test",)

    monkeypatch.setattr("warhammer40k_ai.engine.deployment_headless.validate_decision", _validate_floor_only)

    maker = DeterministicDeploymentDecisionMaker(game=_StubGame(game_map))
    anchor = maker.choose_unit_deployment_position(unit, zone, already_deployed=[])
    payload = maker.build_deployment_model_positions(unit, anchor)
    assert payload
    pos = list(payload[0].get("position", []) or [])
    assert len(pos) >= 3
    assert float(pos[2]) >= 4.12


def test_zone_choice_uses_pregame_teacher_when_player_context_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _StubGame:
        def __init__(self, players: list[_StubPlayer]) -> None:
            self.players = list(players)

    army = _StubArmy([])
    player = _StubPlayer(army, player_id="player:test")
    game = _StubGame([player])
    maker = DeterministicDeploymentDecisionMaker(game=game)
    maker.build_deployment_intent(decision_kind="zone_choice", player=player)

    zones = [
        {"name": "A", "zone_type": "attacker", "x_range": [0.0, 10.0], "y_range": [0.0, 10.0]},
        {"name": "B", "zone_type": "defender", "x_range": [10.0, 20.0], "y_range": [0.0, 10.0]},
    ]
    preferred = dict(zones[0])

    monkeypatch.setattr(
        maker._pregame_agent,  # type: ignore[arg-type]
        "choose_deployment_zone",
        lambda **_kwargs: dict(preferred),
    )

    chosen = maker.choose_deployment_zone(list(zones))
    assert chosen == preferred


def test_next_deploy_unit_uses_teacher_ordering(monkeypatch: pytest.MonkeyPatch) -> None:
    class _StubGame:
        def __init__(self, players: list[_StubPlayer]) -> None:
            self.players = list(players)

    unit_a = _StubUnit("unit:a", must_start_in_reserves=False)
    unit_b = _StubUnit("unit:b", must_start_in_reserves=False)
    army = _StubArmy([unit_a, unit_b])
    player = _StubPlayer(army, player_id="player:test")
    army.player = player
    unit_a._army = army
    unit_b._army = army

    maker = DeterministicDeploymentDecisionMaker(game=_StubGame([player]))

    monkeypatch.setattr(
        maker._pregame_agent,  # type: ignore[arg-type]
        "ordered_deploy_units",
        lambda **_kwargs: [unit_b, unit_a],
    )

    chosen = maker.choose_next_deploy_unit(
        [unit_a, unit_b],
        {"name": "zone", "x_range": [0.0, 10.0], "y_range": [0.0, 10.0]},
        [],
    )
    assert chosen is unit_b


def test_build_deployment_context_includes_teacher_features() -> None:
    class _FlatMap:
        width = 60.0
        height = 44.0
        terrain_features: list[object] = []

    class _StubGame:
        def __init__(self, players: list[_StubPlayer]) -> None:
            self.players = list(players)
            self.map = _FlatMap()
            self.objectives = []

    unit = _StubUnit("unit:ctx", must_start_in_reserves=False)
    army = _StubArmy([unit])
    player = _StubPlayer(army, player_id="player:test")
    army.player = player
    unit._army = army
    maker = DeterministicDeploymentDecisionMaker(game=_StubGame([player]))

    zone = {"name": "zone", "zone_type": "defender", "x_range": [0.0, 20.0], "y_range": [0.0, 22.0]}
    intent = maker.build_deployment_intent(
        decision_kind="placement",
        player=player,
        deployment_zone=zone,
        unit=unit,
        deployable_units=[unit],
        already_deployed=[],
    )
    context = maker.build_deployment_decision_context(
        decision_kind="placement",
        player=player,
        deployment_zone=zone,
        unit=unit,
        deployable_units=[unit],
        already_deployed=[],
    )

    assert "desired_affordances" in intent
    assert "weights" in intent
    assert "board_affordances" in context
    assert "army_role_summary" in context
    assert "deployment_lookahead" in context
    board_affordances = dict(context.get("board_affordances", {}) or {})
    lookahead = dict(context.get("deployment_lookahead", {}) or {})
    assert bool(lookahead.get("enabled", False)) is True
    assert int(lookahead.get("depth", 0) or 0) >= 1
    assert isinstance(list(lookahead.get("candidate_kinds", []) or []), list)
    assert "los_tunnel_count" in board_affordances
    assert "infantry_objective_approach_quality" in board_affordances


def test_semantic_anchor_candidates_are_used_for_placement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FlatMap:
        @staticmethod
        def get_height_at_point(_x: float, _y: float) -> float:
            return 0.0

    class _StubGame:
        def __init__(self, players: list[_StubPlayer]) -> None:
            self.players = list(players)
            self.map = _FlatMap()
            self.battlefield = type("BF", (), {"width": 60.0, "height": 44.0})()

        def is_valid_deployment_position(self, _unit, x: float, y: float, _player_id: str) -> bool:
            return abs(float(x) - 24.0) < 0.2 and abs(float(y) - 12.0) < 0.2

    unit = _StubUnit("unit:anchor", must_start_in_reserves=False, map_obj=_FlatMap())
    army = _StubArmy([unit])
    player = _StubPlayer(army, player_id="player:test")
    army.player = player
    unit._army = army
    maker = DeterministicDeploymentDecisionMaker(game=_StubGame([player]))

    monkeypatch.setattr(
        maker._pregame_agent,  # type: ignore[arg-type]
        "anchor_candidates_for_unit",
        lambda **_kwargs: [(24.0, 12.0)],
    )
    monkeypatch.setattr("warhammer40k_ai.engine.deployment_headless.validate_decision", lambda *_args, **_kwargs: ())

    zone = {"name": "zone", "x_range": [0.0, 30.0], "y_range": [0.0, 20.0]}
    x, y = maker.choose_unit_deployment_position(unit, zone, already_deployed=[])
    assert x == pytest.approx(24.0, abs=0.2)
    assert y == pytest.approx(12.0, abs=0.2)


def test_headless_builds_multiple_runtime_deployment_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FlatMap:
        @staticmethod
        def get_height_at_point(_x: float, _y: float) -> float:
            return 0.0

    class _StubGame:
        def __init__(self, players: list[_StubPlayer]) -> None:
            self.players = list(players)
            self.map = _FlatMap()
            self.battlefield = type("BF", (), {"width": 60.0, "height": 44.0})()

        def is_valid_deployment_position(self, _unit, _x: float, _y: float, _player_id: str) -> bool:
            return True

    unit = _StubUnit("unit:multi", must_start_in_reserves=False, map_obj=_FlatMap())
    army = _StubArmy([unit])
    player = _StubPlayer(army, player_id="player:test")
    army.player = player
    unit._army = army
    maker = DeterministicDeploymentDecisionMaker(game=_StubGame([player]))
    monkeypatch.setattr("warhammer40k_ai.engine.deployment_headless.validate_decision", lambda *_args, **_kwargs: ())

    zone = {"name": "zone", "x_range": [0.0, 30.0], "y_range": [0.0, 20.0]}
    candidates = maker.build_deployment_move_candidates(unit, zone, already_deployed=[], max_candidates=4)
    assert len(candidates) >= 2
    first = dict(candidates[0] or {})
    assert isinstance(first.get("anchor"), list)
    assert isinstance(first.get("model_positions"), list)
    assert str(first.get("source", "") or "")


def test_headless_deployment_candidate_probe_restores_unit_state(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FlatMap:
        terrain_features: list[object] = []

        @staticmethod
        def get_height_at_point(_x: float, _y: float) -> float:
            return 0.0

    class _MutatingUnit(_StubUnit):
        def __init__(self, unit_id: str) -> None:
            super().__init__(unit_id, must_start_in_reserves=False, map_obj=_FlatMap())
            self.models = [_StubModel(f"{unit_id}:model:0"), _StubModel(f"{unit_id}:model:1")]
            self.reserve_status = "deployed"
            self.reserve_status = "deployed"

        def calculate_model_positions(
            self,
            x,
            y,
            game_map,
            avoid_friendly_units=False,
            boundary_repulsors=None,
            search_context=None,
        ):
            del game_map, avoid_friendly_units, boundary_repulsors, search_context
            positions = [
                (float(x), float(y), 0.0, 0.0),
                (float(x) + 1.0, float(y), 0.0, 0.0),
            ]
            for model, pos in zip(self.models, positions):
                model.set_location(*pos)
            return positions

    class _ProbeGame(GameSetupDeploymentReservesMixin):
        def __init__(self) -> None:
            self.map = _FlatMap()
            self.battlefield = type("BF", (), {"width": 60.0, "height": 44.0})()

        def get_boundary_repulsors(self, unit, context="deployment"):
            del unit, context
            return []

        def is_position_wholly_in_deployment_zone(self, x: float, y: float, base: object, player_id: str) -> bool:
            del x, y, base, player_id
            return True

        def is_position_in_enemy_deployment_zone(self, x: float, y: float, player_id: str) -> bool:
            del x, y, player_id
            return False

        def get_distance_to_enemy_deployment_zone(self, x: float, y: float, player_id: str) -> float:
            del x, y, player_id
            return 999.0

        def get_distance_to_enemy_models(self, x: float, y: float, player_id: str) -> float:
            del x, y, player_id
            return 999.0

    monkeypatch.setattr("warhammer40k_ai.engine.deployment_headless.validate_decision", lambda *_args, **_kwargs: ())

    game = _ProbeGame()
    unit = _MutatingUnit("unit:probe")
    army = _StubArmy([unit])
    player = _StubPlayer(army, player_id="player:test")
    army.player = player
    unit._army = army
    maker = DeterministicDeploymentDecisionMaker(game=game)

    zone = {"name": "zone", "x_range": [0.0, 30.0], "y_range": [0.0, 20.0]}
    initial_positions = [model.get_location() for model in list(unit.models)]

    candidates = maker.build_deployment_move_candidates(unit, zone, already_deployed=[], max_candidates=2)

    assert candidates
    assert [model.get_location() for model in list(unit.models)] == initial_positions


def test_deployment_headless_uses_ranker_model_for_option_selection(tmp_path: Path) -> None:
    class _StubGame:
        players: list[object] = []

    feature_keys = list(DEFAULT_DEPLOYMENT_RANKER_FEATURE_KEYS)
    model_payload = {
        "model_type": "deployment_linear_ranker_v1",
        "feature_keys": feature_keys,
        "weights": [1.0] + [0.0 for _ in feature_keys[1:]],
        "bias": 0.0,
        "normalization": {
            "mean": [0.0 for _ in feature_keys],
            "scale": [1.0 for _ in feature_keys],
        },
        "decision_types": [DECISION_CHOOSE_DEPLOYMENT_ZONE],
        "candidate_kinds": ["deployment_zone"],
        "created_at_utc": "2026-03-08T00:00:00Z",
        "training_metrics": {},
    }
    model_path = tmp_path / "deployment_ranker_model.json"
    model_path.write_text(json.dumps(model_payload, sort_keys=True), encoding="utf-8")
    maker = DeterministicDeploymentDecisionMaker(game=_StubGame(), ranker_model_path=str(model_path))

    request = DecisionRequest.create(
        DECISION_CHOOSE_DEPLOYMENT_ZONE,
        "Choose deployment zone",
        player_id="player:test",
        options=[
            DecisionOption.create("Zone A", payload={"zone_name": "A"}),
            DecisionOption.create("Zone B", payload={"zone_name": "B"}),
        ],
        context={},
    )
    assert request is not None
    action_a = request.action_id_for_option_id(request.options[0].option_id)
    action_b = request.action_id_for_option_id(request.options[1].option_id)
    low = {
        "candidate_kind": "deployment_zone",
        "projected_score_delta_next_window": 0.1,
    }
    high = {
        "candidate_kind": "deployment_zone",
        "projected_score_delta_next_window": 1.2,
    }
    request.candidates = [
        CandidateAction(action_id=action_a, params={}, metadata=low),
        CandidateAction(action_id=action_b, params={}, metadata=high),
    ]
    request.mask = [True, True]
    option_id = maker.choose_deployment_zone_option(request, [])
    assert str(option_id or "") == str(request.options[1].option_id)


def test_deployment_headless_uses_ranker_model_for_deployment_move_option_selection(tmp_path: Path) -> None:
    class _StubGame:
        players: list[object] = []

    feature_keys = list(DEFAULT_DEPLOYMENT_RANKER_FEATURE_KEYS)
    model_payload = {
        "model_type": "deployment_linear_ranker_v1",
        "feature_keys": feature_keys,
        "weights": [1.0] + [0.0 for _ in feature_keys[1:]],
        "bias": 0.0,
        "normalization": {
            "mean": [0.0 for _ in feature_keys],
            "scale": [1.0 for _ in feature_keys],
        },
        "decision_types": [DECISION_MOVE_UNIT],
        "candidate_kinds": ["deployment_move"],
        "created_at_utc": "2026-03-08T00:00:00Z",
        "training_metrics": {},
    }
    model_path = tmp_path / "deployment_move_ranker_model.json"
    model_path.write_text(json.dumps(model_payload, sort_keys=True), encoding="utf-8")
    maker = DeterministicDeploymentDecisionMaker(game=_StubGame(), ranker_model_path=str(model_path))

    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Deploy unit",
        player_id="player:test",
        options=[
            DecisionOption.create(
                "Candidate A",
                payload={"unit_id": "unit:test", "movement_type": "deploy", "action": "confirm"},
            ),
            DecisionOption.create(
                "Candidate B",
                payload={"unit_id": "unit:test", "movement_type": "deploy", "action": "confirm"},
            ),
        ],
        context={"placement_kind": "deployment"},
    )
    action_a = request.action_id_for_option_id(request.options[0].option_id)
    action_b = request.action_id_for_option_id(request.options[1].option_id)
    request.candidates = [
        CandidateAction(
            action_id=action_a,
            params={},
            metadata={"candidate_kind": "deployment_move", "projected_score_delta_next_window": 0.2},
        ),
        CandidateAction(
            action_id=action_b,
            params={},
            metadata={"candidate_kind": "deployment_move", "projected_score_delta_next_window": 1.3},
        ),
    ]
    request.mask = [True, True]
    option_id = maker.choose_deployment_move_option(request, object(), {}, [])
    assert str(option_id or "") == str(request.options[1].option_id)


def test_deployment_headless_falls_back_to_rollout_metadata_when_ranker_missing() -> None:
    class _StubGame:
        players: list[object] = []

    maker = DeterministicDeploymentDecisionMaker(game=_StubGame(), ranker_model_path=None)
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Deploy unit",
        player_id="player:test",
        options=[
            DecisionOption.create(
                "Candidate A",
                payload={"unit_id": "unit:test", "movement_type": "deploy", "action": "confirm"},
            ),
            DecisionOption.create(
                "Candidate B",
                payload={"unit_id": "unit:test", "movement_type": "deploy", "action": "confirm"},
            ),
        ],
        context={
            "placement_kind": "deployment",
            "deployment_lookahead": {"enabled": True},
        },
    )
    action_a = request.action_id_for_option_id(request.options[0].option_id)
    action_b = request.action_id_for_option_id(request.options[1].option_id)
    request.candidates = [
        CandidateAction(
            action_id=action_a,
            params={},
            metadata={"candidate_kind": "deployment_move", "lookahead_total_value": 0.4},
        ),
        CandidateAction(
            action_id=action_b,
            params={},
            metadata={"candidate_kind": "deployment_move", "lookahead_total_value": 1.6},
        ),
    ]
    request.mask = [True, True]

    option_id = maker.choose_deployment_move_option(request, object(), {}, [])
    assert str(option_id or "") == str(request.options[1].option_id)


def test_packability_first_deployment_order_prefers_large_units_over_teacher_tiebreak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _StubGame:
        def __init__(self, players: list[_StubPlayer]) -> None:
            self.players = list(players)

    def _make_unit(unit_id: str, *, radius: float, models: int, scout: bool = False, vehicle: bool = False):
        unit = _StubUnit(unit_id, must_start_in_reserves=False)
        unit.models = [_StubModel(f"{unit_id}:model:{idx}") for idx in range(models)]
        for model in list(unit.models):
            model.model_base = _StubBase(radius=radius)
        unit.is_vehicle = bool(vehicle)
        if scout:
            unit.has_scout = lambda: True  # type: ignore[attr-defined]
        return unit

    large = _make_unit("unit:large", radius=1.5, models=5, vehicle=True)
    small = _make_unit("unit:small", radius=0.5, models=1, scout=True)
    army = _StubArmy([large, small])
    player = _StubPlayer(army, player_id="player:test")
    army.player = player
    large._army = army
    small._army = army

    maker = DeterministicDeploymentDecisionMaker(game=_StubGame([player]))
    monkeypatch.setattr(
        maker._pregame_agent,  # type: ignore[arg-type]
        "ordered_deploy_units",
        lambda **_kwargs: [small, large],
    )

    chosen = maker.choose_next_deploy_unit(
        [small, large],
        {"name": "zone", "x_range": [0.0, 30.0], "y_range": [0.0, 20.0]},
        [],
    )
    assert chosen is large


def test_fast_packer_candidate_cap_stops_after_small_candidate_set(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FlatMap:
        @staticmethod
        def get_height_at_point(_x: float, _y: float) -> float:
            return 0.0

    class _StubGame:
        def __init__(self, players: list[_StubPlayer]) -> None:
            self.players = list(players)
            self.map = _FlatMap()
            self.battlefield = type("BF", (), {"width": 60.0, "height": 44.0})()

        def is_valid_deployment_position(self, _unit, _x: float, _y: float, _player_id: str) -> bool:
            return True

    unit = _StubUnit("unit:cap", must_start_in_reserves=False, map_obj=_FlatMap())
    army = _StubArmy([unit])
    player = _StubPlayer(army, player_id="player:test")
    army.player = player
    unit._army = army

    monkeypatch.setattr("warhammer40k_ai.engine.deployment_headless.validate_decision", lambda *_args, **_kwargs: ())

    maker = DeterministicDeploymentDecisionMaker(game=_StubGame([player]), placement_candidate_limit=2)
    candidates = maker.build_deployment_move_candidates(
        unit,
        {"name": "zone", "x_range": [0.0, 30.0], "y_range": [0.0, 20.0]},
        already_deployed=[],
        max_candidates=8,
    )

    assert len(candidates) == 2
    metric = maker.get_deployment_search_metrics()[-1]
    assert int(metric.get("candidate_limit", 0) or 0) == 2
    assert int(metric.get("returned_candidate_count", 0) or 0) == 2
    assert int(metric.get("anchor_attempts", 0) or 0) < 6
    assert int(metric.get("full_validation_calls", 0) or 0) <= 2


def test_cached_search_context_matches_uncached_deployment_validation() -> None:
    class _FlatMap:
        terrain_features: list[object] = []

        @staticmethod
        def get_height_at_point(_x: float, _y: float) -> float:
            return 0.0

    class _ProbeUnit(_StubUnit):
        def __init__(self, unit_id: str) -> None:
            super().__init__(unit_id, must_start_in_reserves=False, map_obj=_FlatMap())
            self.models = [_StubModel(f"{unit_id}:model:0"), _StubModel(f"{unit_id}:model:1")]
            self.reserve_status = "deployed"

        def calculate_model_positions(
            self,
            x,
            y,
            game_map,
            avoid_friendly_units=False,
            boundary_repulsors=None,
            search_context=None,
        ):
            del game_map, avoid_friendly_units, boundary_repulsors, search_context
            return [
                (float(x), float(y), 0.0, 0.0),
                (float(x) + 1.0, float(y), 0.0, 0.0),
            ]

    class _ProbeGame(GameSetupDeploymentReservesMixin):
        def __init__(self) -> None:
            self.map = _FlatMap()
            self.battlefield = type("BF", (), {"width": 60.0, "height": 44.0})()

        def get_boundary_repulsors(self, unit, context="deployment"):
            del unit, context
            return []

        def is_position_wholly_in_deployment_zone(self, x: float, y: float, base: object, player_id: str) -> bool:
            del x, y, base, player_id
            return True

        def is_position_in_enemy_deployment_zone(self, x: float, y: float, player_id: str) -> bool:
            del x, y, player_id
            return False

        def get_distance_to_enemy_deployment_zone(self, x: float, y: float, player_id: str) -> float:
            del x, y, player_id
            return 999.0

        def get_distance_to_enemy_models(self, x: float, y: float, player_id: str) -> float:
            del x, y, player_id
            return 999.0

    game = _ProbeGame()
    unit = _ProbeUnit("unit:cached")
    army = _StubArmy([unit])
    player = _StubPlayer(army, player_id="player:test")
    army.player = player
    unit._army = army
    maker = DeterministicDeploymentDecisionMaker(game=game)

    boundary_repulsors = maker._deployment_boundary_repulsors(unit)
    search_context = maker._build_deployment_search_context(unit, boundary_repulsors=boundary_repulsors)
    uncached = game.is_valid_deployment_position(unit, 5.0, 5.0, player.id)
    cached = game.is_valid_deployment_position(
        unit,
        5.0,
        5.0,
        player.id,
        boundary_repulsors=boundary_repulsors,
        search_context=search_context,
    )
    assert cached is uncached
