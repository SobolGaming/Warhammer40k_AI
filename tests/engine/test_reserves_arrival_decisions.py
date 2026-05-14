from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.movement import validate_move_unit_payload
from warhammer40k_ai.engine.reserve_entry_geometry import (
    enemy_deployment_battlefield_edges,
    is_valid_strategic_reserves_edge,
)
from warhammer40k_ai.engine.reserve_entry_rules import evaluate_reserves_arrival_positions
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController
from warhammer40k_ai.engine.missions import DeploymentZone, DeploymentZoneType, MissionRegistry
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.engine.state_blob_units import unit_entries
from warhammer40k_ai.engine import turn_manager
from warhammer40k_ai.engine.game_mixins.missions_scoring_actions_mixin import (
    GameMissionsScoringActionsMixin,
)
from warhammer40k_ai.engine.game_mixins.setup_deployment_reserves_mixin import (
    GameSetupDeploymentReservesMixin,
)
from warhammer40k_ai.utility.model_base import Base, BaseType


class _ReserveRequestGame(GameSetupDeploymentReservesMixin):
    def __init__(self) -> None:
        self.turn = 3
        self.players = []


class _ReserveEnemyDeploymentZoneGame(GameSetupDeploymentReservesMixin):
    def __init__(self, player) -> None:
        self.turn = 2
        self.players = [player]
        self.battlefield = SimpleNamespace(width=60.0, height=44.0)
        self.map = SimpleNamespace(width=60.0, height=44.0)
        self.deployment_zones = {
            str(player.id): {
                "mission_zones": [
                    DeploymentZone(
                        "Own Deployment Zone",
                        DeploymentZoneType.DEFENDER,
                        [(0.0, 0.0), (60.0, 0.0), (60.0, 6.0), (0.0, 6.0)],
                    )
                ]
            },
            "player:enemy": {
                "mission_zones": [
                    DeploymentZone(
                        "Enemy Deployment Zone",
                        DeploymentZoneType.ATTACKER,
                        [(0.0, 38.0), (60.0, 38.0), (60.0, 44.0), (0.0, 44.0)],
                    )
                ]
            },
        }

    def get_current_player(self):
        return self.players[0]


class _ReserveScoringGame(GameMissionsScoringActionsMixin):
    def __init__(self, players) -> None:
        self.turn = 3
        self.players = list(players or [])

    def award_vp(self, *_args, **_kwargs):
        return 0


class _DecisionQueue:
    def __init__(self) -> None:
        self.requests = []

    def list(self):
        return list(self.requests)


class _MandatoryReinforcementsTurnGame(GameSetupDeploymentReservesMixin):
    def __init__(self, player, unit) -> None:
        self.is_authoritative = True
        self.turn = 3
        self.phase = BattleRoundPhases.MOVEMENT_PHASE
        self.players = [player]
        self.current_player_index = 0
        self.reinforcements_step_active = True
        self.reinforcements_step_player_id = str(player.id)
        self.decision_queue = _DecisionQueue()
        self.map = SimpleNamespace(bump_state_generation=lambda _reason: None)
        player.army.units = [unit]

    def get_current_player(self):
        return self.players[self.current_player_index]

    def request_decision(self, request) -> None:
        self.decision_queue.requests.append(request)


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


def test_turn_manager_requeues_unresolved_mandatory_reinforcements_before_phase_end() -> None:
    player, army, unit = _build_reserve_unit()
    player.get_army = lambda: army
    unit.can_arrive_from_reserves = lambda _turn: True
    unit.must_arrive_from_reserves = lambda _turn: True
    game = _MandatoryReinforcementsTurnGame(player, unit)

    turn_manager.next_phase(game)

    assert game.phase == BattleRoundPhases.MOVEMENT_PHASE
    assert game.reinforcements_step_active is True
    assert len(game.decision_queue.requests) == 1
    request = game.decision_queue.requests[0]
    assert request.decision_type == "SELECT_UNIT"
    assert request.context["phase_step"] == "REINFORCEMENTS"
    assert request.context["pending_must_arrival_unit_ids"] == ["unit:one"]


def test_headless_reserves_failure_records_structured_unit_metadata() -> None:
    _player, _army, unit = _build_reserve_unit()
    metric = {
        "anchor_attempts": 12,
        "build_calls": 4,
        "validation_rejects": 3,
        "quick_rejects": 5,
        "timed_out": True,
        "budget_mode": "",
        "work_budget_units": 0,
        "work_units_used": 0,
        "work_budget_exhausted": False,
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
        "budget_mode": "",
        "work_budget_units": 0,
        "work_units_used": 0,
        "work_budget_exhausted": False,
        "elapsed_ms": 250,
    }
    assert unit.reserve_last_arrival_failure == failure


def test_strategic_reserves_edge_offsets_allow_large_single_model_bases() -> None:
    base = SimpleNamespace(
        has_circular_base=True,
        get_radius=lambda: 5.0,
    )
    unit = SimpleNamespace(models=[SimpleNamespace(model_base=base)])
    controller = HeadlessPolicyDecisionController(auto_attach=False)

    groups = controller._strategic_edge_anchor_groups(unit, width=60.0, height=44.0)
    primary_points = list(groups[0][1])
    sources = [source for source, _anchors in groups]

    assert controller._strategic_edge_offset_preference(unit) == 5.0
    assert "strategic_edge_touch_dense" in sources
    assert any(abs(y - 5.0) < 1e-6 for _x, y in primary_points)
    assert any(abs(x - 5.0) < 1e-6 for x, _y in primary_points)
    assert all(5.0 <= x <= 55.0 for x, _y in primary_points)
    assert all(5.0 <= y <= 39.0 for _x, y in primary_points)


def test_turn_two_strategic_reserves_enemy_edge_is_mission_relative() -> None:
    player, _army, unit = _build_reserve_unit()
    enemy_player = SimpleNamespace(id="player:enemy")
    player.get_army = lambda: player.army
    game = SimpleNamespace(
        turn=2,
        battlefield=SimpleNamespace(width=60.0, height=44.0),
        map=SimpleNamespace(width=60.0, height=44.0, units=[]),
        players=[player, enemy_player],
        deployment_zones={
            player.id: {
                "mission_zones": [
                    DeploymentZone(
                        "Own Hammer and Anvil Zone",
                        DeploymentZoneType.ATTACKER,
                        [(42.0, 0.0), (42.0, 44.0), (60.0, 44.0), (60.0, 0.0)],
                    )
                ]
            },
            enemy_player.id: {
                "mission_zones": [
                    DeploymentZone(
                        "Enemy Hammer and Anvil Zone",
                        DeploymentZoneType.DEFENDER,
                        [(0.0, 0.0), (0.0, 44.0), (18.0, 44.0), (18.0, 0.0)],
                    )
                ]
            },
        },
    )

    assert enemy_deployment_battlefield_edges(game, player.id) == ("left",)
    assert is_valid_strategic_reserves_edge(game, "left", turn=2, unit=unit) is False
    assert is_valid_strategic_reserves_edge(game, "enemy", turn=2, unit=unit) is True
    assert is_valid_strategic_reserves_edge(game, "left", turn=3, unit=unit) is True


def test_turn_two_strategic_reserves_enemy_edges_are_inferred_for_all_registered_missions() -> None:
    expected_edges = {
        "Crucible of Battle": {
            DeploymentZoneType.ATTACKER: ("left", "enemy"),
            DeploymentZoneType.DEFENDER: ("own", "right"),
        },
        "Dawn of War": {
            DeploymentZoneType.ATTACKER: ("enemy",),
            DeploymentZoneType.DEFENDER: ("own",),
        },
        "Hammer and Anvil": {
            DeploymentZoneType.ATTACKER: ("left",),
            DeploymentZoneType.DEFENDER: ("right",),
        },
        "Tipping Point": {
            DeploymentZoneType.ATTACKER: ("left",),
            DeploymentZoneType.DEFENDER: ("right",),
        },
        "Search and Destroy": {
            DeploymentZoneType.ATTACKER: ("left", "enemy"),
            DeploymentZoneType.DEFENDER: ("own", "right"),
        },
        "Sweeping Engagement": {
            DeploymentZoneType.ATTACKER: ("enemy",),
            DeploymentZoneType.DEFENDER: ("own",),
        },
    }

    for mission_name in MissionRegistry.get_available_missions():
        mission = MissionRegistry.get_mission(mission_name)
        attacker_zones = mission.get_attacker_zones()
        defender_zones = mission.get_defender_zones()
        assert attacker_zones
        assert defender_zones
        for owner_type, enemy_type in (
            (DeploymentZoneType.ATTACKER, DeploymentZoneType.DEFENDER),
            (DeploymentZoneType.DEFENDER, DeploymentZoneType.ATTACKER),
        ):
            player = SimpleNamespace(id=f"player:{owner_type.value}")
            enemy_player = SimpleNamespace(id=f"player:{enemy_type.value}")
            game = SimpleNamespace(
                turn=2,
                battlefield=SimpleNamespace(width=60.0, height=44.0),
                map=SimpleNamespace(width=60.0, height=44.0, units=[]),
                players=[player, enemy_player],
                deployment_zones={
                    player.id: {
                        "mission_zones": attacker_zones if owner_type == DeploymentZoneType.ATTACKER else defender_zones
                    },
                    enemy_player.id: {
                        "mission_zones": attacker_zones if enemy_type == DeploymentZoneType.ATTACKER else defender_zones
                    },
                },
            )

            inferred = enemy_deployment_battlefield_edges(game, player.id)

            assert inferred == expected_edges[mission_name][owner_type]


def test_headless_turn_two_search_keeps_side_edges_for_hammer_and_anvil() -> None:
    player, _army, unit = _build_reserve_unit()
    enemy_player = SimpleNamespace(id="player:enemy")
    player.get_army = lambda: player.army
    game = SimpleNamespace(
        turn=2,
        battlefield=SimpleNamespace(width=60.0, height=44.0),
        map=SimpleNamespace(width=60.0, height=44.0, units=[]),
        players=[player, enemy_player],
        deployment_zones={
            player.id: {
                "mission_zones": [
                    DeploymentZone(
                        "Own Hammer and Anvil Zone",
                        DeploymentZoneType.ATTACKER,
                        [(42.0, 0.0), (42.0, 44.0), (60.0, 44.0), (60.0, 0.0)],
                    )
                ]
            },
            enemy_player.id: {
                "mission_zones": [
                    DeploymentZone(
                        "Enemy Hammer and Anvil Zone",
                        DeploymentZoneType.DEFENDER,
                        [(0.0, 0.0), (0.0, 44.0), (18.0, 44.0), (18.0, 0.0)],
                    )
                ]
            },
        },
    )
    controller = HeadlessPolicyDecisionController(auto_attach=False)

    edges = controller._strategic_reserves_search_edges(game, unit)

    assert "left" not in edges
    assert "enemy" in edges
    assert "own" in edges
    assert "right" in edges


def test_strategic_reserves_edge_offsets_use_oriented_hull_axis_extent() -> None:
    base = Base(BaseType.HULL, (4.0, 1.0))
    model = SimpleNamespace(id="model:hull", _id="model:hull", model_base=base, is_alive=True)
    unit = SimpleNamespace(
        models=[model],
        calculate_strategic_facing=lambda _x, _y, _game_map: 0.0,
    )
    game = SimpleNamespace(map=SimpleNamespace(width=60.0, height=44.0, units=[]))
    controller = HeadlessPolicyDecisionController(auto_attach=False)

    groups = controller._strategic_edge_anchor_groups(unit, width=60.0, height=44.0, game=game)
    primary_points = list(groups[0][1])

    assert any(abs(y - 1.0) < 1e-6 for _x, y in primary_points)
    assert any(abs(y - 43.0) < 1e-6 for _x, y in primary_points)
    assert not any(0.0 <= y < 1.0 - 1e-6 for _x, y in primary_points)


def test_strategic_reserves_edge_touch_candidates_are_exact_for_oriented_large_hull() -> None:
    base = Base(BaseType.HULL, (1.0, 3.5))
    model = SimpleNamespace(id="model:hull", _id="model:hull", model_base=base, is_alive=True)
    unit = SimpleNamespace(
        models=[model],
        calculate_strategic_facing=lambda _x, _y, _game_map: 0.0,
    )
    game = SimpleNamespace(map=SimpleNamespace(width=60.0, height=44.0, units=[]))
    controller = HeadlessPolicyDecisionController(auto_attach=False)

    groups = controller._strategic_edge_anchor_groups(unit, width=60.0, height=44.0, game=game)
    anchors = [
        (float(x), float(y))
        for _source, anchors in groups
        for x, y in anchors
    ]
    own_enemy_edge_points = [
        (x, y)
        for x, y in anchors
        if 3.0 < x < 57.0 and (0.0 <= y < 6.0 or 38.0 < y <= 44.0)
    ]

    assert own_enemy_edge_points
    assert all(abs(y - 3.5) < 1e-6 or abs(y - 40.5) < 1e-6 for _x, y in own_enemy_edge_points)


def test_strategic_reserves_large_model_edge_touch_applies_when_base_cannot_fit_wholly_within_six() -> None:
    player, _army, unit = _build_reserve_unit()
    player.get_army = lambda: player.army
    base = SimpleNamespace(
        has_circular_base=True,
        get_radius=lambda: 4.0,
        get_longest_radius=lambda: 4.0,
    )
    unit.models = [SimpleNamespace(id="model:large", _id="model:large", model_base=base, is_alive=True)]
    game = SimpleNamespace(
        turn=2,
        battlefield=SimpleNamespace(width=60.0, height=44.0),
        map=SimpleNamespace(width=60.0, height=44.0),
        players=[player],
        get_enemy_units=lambda _player: [],
        is_valid_strategic_reserves_edge=lambda _edge, turn=None: True,
        get_current_player=lambda: player,
    )

    evaluation = evaluate_reserves_arrival_positions(
        game,
        unit,
        [{"model_id": "model:large", "position": [20.0, 4.0, 0.0], "facing": 0.0}],
        ctx={"placement_kind": "reserves_arrival"},
    )

    assert evaluation.get("errors") == []
    assert evaluation.get("battlefield_edge") == "own"
    assert evaluation.get("edge_touch") is True


def test_strategic_reserves_validation_rejects_oriented_hull_overhanging_edge() -> None:
    player, _army, unit = _build_reserve_unit()
    player.get_army = lambda: player.army
    base = Base(BaseType.HULL, (2.5, 0.75))
    model = SimpleNamespace(id="model:hull", _id="model:hull", model_base=base, is_alive=True)
    unit.models = [model]
    game = SimpleNamespace(
        turn=2,
        battlefield=SimpleNamespace(width=60.0, height=44.0),
        map=SimpleNamespace(width=60.0, height=44.0),
        players=[player],
        get_enemy_units=lambda _player: [],
        is_valid_strategic_reserves_edge=lambda _edge, turn=None: True,
        get_current_player=lambda: player,
    )

    overhanging = evaluate_reserves_arrival_positions(
        game,
        unit,
        [{"model_id": "model:hull", "position": [20.0, 0.5, 0.0], "facing": 0.0}],
        ctx={"placement_kind": "reserves_arrival"},
    )
    touching = evaluate_reserves_arrival_positions(
        game,
        unit,
        [{"model_id": "model:hull", "position": [20.0, 0.75, 0.0], "facing": 0.0}],
        ctx={"placement_kind": "reserves_arrival"},
    )

    assert overhanging.get("errors") == ["Reserves arrival must be within 6\" of a battlefield edge."]
    assert touching.get("errors") == []
    assert touching.get("battlefield_edge") == "own"


def test_headless_quick_rejects_strategic_edge_anchor_when_footprint_overhangs() -> None:
    player, _army, unit = _build_reserve_unit()
    player.get_army = lambda: player.army
    base = Base(BaseType.HULL, (2.5, 0.75))
    model = SimpleNamespace(id="model:hull", _id="model:hull", model_base=base, is_alive=True)
    unit.models = [model]
    unit.calculate_strategic_facing = lambda _x, _y, _game_map: 0.0
    game = SimpleNamespace(
        turn=2,
        battlefield=SimpleNamespace(width=60.0, height=44.0),
        map=SimpleNamespace(width=60.0, height=44.0, units=[]),
        players=[player],
        is_valid_strategic_reserves_edge=lambda _edge, turn=None: True,
    )
    controller = HeadlessPolicyDecisionController(auto_attach=False)

    assert controller._quick_reject_reserves_anchor(
        game,
        unit,
        x=20.0,
        y=0.5,
        _context={"placement_kind": "reserves_arrival"},
    ) is True
    assert controller._quick_reject_reserves_anchor(
        game,
        unit,
        x=20.0,
        y=0.75,
        _context={"placement_kind": "reserves_arrival"},
    ) is False


def test_headless_quick_rejects_large_edge_touch_anchor_when_away_from_edge() -> None:
    player, _army, unit = _build_reserve_unit()
    player.get_army = lambda: player.army
    base = Base(BaseType.HULL, (1.0, 3.5))
    model = SimpleNamespace(id="model:hull", _id="model:hull", model_base=base, is_alive=True)
    unit.models = [model]
    unit.calculate_strategic_facing = lambda _x, _y, _game_map: 0.0
    game = SimpleNamespace(
        turn=2,
        battlefield=SimpleNamespace(width=60.0, height=44.0),
        map=SimpleNamespace(width=60.0, height=44.0, units=[]),
        players=[player],
        is_valid_strategic_reserves_edge=lambda _edge, turn=None: True,
    )
    controller = HeadlessPolicyDecisionController(auto_attach=False)

    assert controller._quick_reject_reserves_anchor(
        game,
        unit,
        x=20.0,
        y=3.25,
        _context={"placement_kind": "reserves_arrival"},
    ) is True
    assert controller._quick_reject_reserves_anchor(
        game,
        unit,
        x=20.0,
        y=3.75,
        _context={"placement_kind": "reserves_arrival"},
    ) is True
    assert controller._quick_reject_reserves_anchor(
        game,
        unit,
        x=20.0,
        y=3.5,
        _context={"placement_kind": "reserves_arrival"},
    ) is False


def test_round_two_strategic_reserves_rejects_base_overlap_with_enemy_deployment_zone() -> None:
    player, _army, unit = _build_reserve_unit()
    player.get_army = lambda: player.army
    base = SimpleNamespace(
        base_type=SimpleNamespace(name="CIRCULAR"),
        has_circular_base=True,
        radius=2.0,
        get_radius=lambda: 2.0,
        get_longest_radius=lambda: 2.0,
    )
    unit.models = [SimpleNamespace(id="model:large", _id="model:large", model_base=base, is_alive=True)]
    game = _ReserveEnemyDeploymentZoneGame(player)

    assert game.is_position_in_enemy_deployment_zone(2.0, 37.0, player.id) is False
    assert game.does_position_base_overlap_enemy_deployment_zone(2.0, 37.0, base, player.id) is True

    evaluation = evaluate_reserves_arrival_positions(
        game,
        unit,
        [{"model_id": "model:large", "position": [2.0, 37.0, 0.0], "facing": 0.0}],
        ctx={"placement_kind": "reserves_arrival"},
    )

    assert evaluation.get("errors") == [
        "Strategic Reserves units cannot arrive in the enemy deployment zone during battle round 2."
    ]
    assert evaluation.get("battlefield_edge") is None


def test_aircraft_reserve_arrival_skips_ruins_surface_validation_but_keeps_reserve_rules() -> None:
    player, army, unit = _build_reserve_unit()
    player.get_army = lambda: army
    unit.can_arrive_from_reserves = lambda _turn: True
    unit.must_arrive_from_reserves = lambda _turn: True
    unit.has_any_keyword = lambda keyword: str(keyword or "").strip().upper() == "AIRCRAFT"
    unit.is_aircraft = True
    unit.has_deep_strike = lambda: False
    unit.get_parent_army = lambda: army
    base = SimpleNamespace(
        has_circular_base=True,
        get_radius=lambda: 0.5,
        get_longest_radius=lambda: 0.5,
        x=10.0,
        y=1.0,
        z=0.0,
        facing=0.0,
    )
    model = SimpleNamespace(
        id="model:aircraft",
        _id="model:aircraft",
        model_base=base,
        is_alive=True,
        get_location=lambda: (10.0, 1.0, 0.0, 0.0),
    )
    model.parent_unit = unit
    unit.models = [model]
    game = SimpleNamespace(
        turn=2,
        battlefield=SimpleNamespace(width=60.0, height=44.0),
        map=SimpleNamespace(
            width=60.0,
            height=44.0,
            units=[],
            terrain_features=[SimpleNamespace()],
            is_within_boundary=lambda _model, destination: True,
            check_collision_with_obstacles=lambda _model, destination: False,
            validate_model_surface_placement=lambda _model, position: {
                "valid": False,
                "reason": "surface blocked",
            },
        ),
        players=[player],
        get_enemy_units=lambda _player: [],
        is_valid_strategic_reserves_edge=lambda _edge, turn=None: True,
        get_current_player=lambda: player,
    )
    request = _ReserveRequestGame()._build_reserves_arrival_request(unit, allow_skip=False)
    assert request is not None

    errors = validate_move_unit_payload(
        game,
        request,
        option_payload={"unit_id": unit.id, "movement_type": "deploy", "action": "confirm"},
        result_payload={
            "model_positions": [
                {"model_id": "model:aircraft", "position": [10.0, 1.0, 0.0], "facing": 0.0}
            ]
        },
    )

    assert errors == ()


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


def test_round_three_reserve_destruction_fixes_blank_metadata_before_diagnostic() -> None:
    player, army, unit = _build_reserve_unit()
    player.get_army = lambda: army
    unit.special_rules.pop("reserve_source", None)
    unit.special_rules.pop("reserve_latest_arrival_round", None)
    unit.reserve_source = ""
    unit.reserve_latest_arrival_round = 0
    game = _ReserveScoringGame([player])

    game.end_of_battle_round_scoring()

    diagnostic = game.reserve_arrival_diagnostics[0]
    assert diagnostic["reserve_source"] == "deployment_choice"
    assert diagnostic["reserve_mandatory_start"] is False
    assert diagnostic["reserve_latest_arrival_round"] == 3


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
