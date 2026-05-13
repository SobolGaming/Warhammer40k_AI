from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT, DECISION_SELECT_MOVEMENT_ACTION
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionRequest
from warhammer40k_ai.engine.movement_intent import MovementIntent
from warhammer40k_ai.engine.movement_solver import generate_move_unit_candidates, generate_select_movement_action_candidates
from warhammer40k_ai.engine.path_witness import PathWitnessStore
from warhammer40k_ai.engine.time_manager import TimeManager


class _BaseStub:
    has_circular_base = True

    def __init__(self, x: float, y: float, *, radius: float = 0.5, z: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.facing = 0.0
        self._radius = float(radius)

    def get_radius(self) -> float:
        return self._radius

    def get_longest_radius(self) -> float:
        return self._radius


class _ModelStub:
    def __init__(self, model_id: str, *, x: float, y: float) -> None:
        self.id = model_id
        self._id = model_id
        self.model_base = _BaseStub(x, y)
        self.is_alive = True

    def get_location(self) -> tuple[float, float, float, float]:
        return (float(self.model_base.x), float(self.model_base.y), float(self.model_base.z), 0.0)

    def set_location(self, x: float, y: float, z: float, facing: float) -> None:
        self.model_base.x = float(x)
        self.model_base.y = float(y)
        self.model_base.z = float(z)
        self.model_base.facing = float(facing)


class _ArmyStub:
    def __init__(self, player: object | None = None) -> None:
        self.player = player
        self.units: list[object] = []


class _PlayerStub:
    def __init__(self, player_id: str, army: _ArmyStub) -> None:
        self.id = player_id
        self.army = army

    def get_army(self):
        return self.army


class _UnitStub:
    def __init__(self, unit_id: str, *, army: _ArmyStub, reserve_status: str) -> None:
        self.id = unit_id
        self._id = unit_id
        self.parent_army = army
        self.reserve_status = reserve_status
        self.deployed = reserve_status == "deployed"
        self.embarked_in = None
        self.is_embarked = False
        self.movement = 12
        self.models = [_ModelStub(f"{unit_id}:model-1", x=0.0, y=0.0)]

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_models(self):
        return list(self.models)

    def is_in_reserves(self) -> bool:
        return str(self.reserve_status or "").strip().lower() != "deployed"

    def can_arrive_from_reserves(self, _turn: int) -> bool:
        return True

    def is_in_strategic_reserves(self) -> bool:
        return False

    def has_deep_strike(self) -> bool:
        return True

    def is_alive(self) -> bool:
        return True

    def _create_potential_base(
        self,
        x: float,
        y: float,
        z: float,
        facing: float,
        *,
        model: _ModelStub | None = None,
    ) -> _BaseStub:
        radius = float(model.model_base.get_radius()) if model is not None else 0.5
        base = _BaseStub(float(x), float(y), radius=radius, z=float(z))
        base.facing = float(facing)
        return base


class _MapStub:
    width = 60.0
    height = 44.0

    def __init__(self, units: list[object]) -> None:
        self.units = list(units)
        self.terrain_features: list[object] = []

    @staticmethod
    def get_height_at_point(_x: float, _y: float) -> float:
        return 0.0

    @staticmethod
    def is_within_boundary(_model: object, destination: tuple[float, float]) -> bool:
        x, y = destination
        return 0.0 <= float(x) <= 60.0 and 0.0 <= float(y) <= 44.0

    @staticmethod
    def check_collision_with_obstacles(_model: object, destination: tuple[float, float]) -> bool:
        del destination
        return False


class _GameStub:
    def __init__(self) -> None:
        arriving_army = _ArmyStub()
        enemy_army = _ArmyStub()
        self.arriving = _UnitStub("unit:arriving", army=arriving_army, reserve_status="reserves")
        self.enemy = _UnitStub("unit:enemy", army=enemy_army, reserve_status="deployed")
        self.enemy.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        arriving_army.units = [self.arriving]
        enemy_army.units = [self.enemy]
        self.players = [
            _PlayerStub("player:arriving", arriving_army),
            _PlayerStub("player:enemy", enemy_army),
        ]
        arriving_army.player = self.players[0]
        enemy_army.player = self.players[1]
        self.turn = 2
        self.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        self.current_player_index = 0
        self.time_manager = TimeManager()
        self.path_witness_store = PathWitnessStore()
        self.objectives: list[object] = []
        self.battlefield = SimpleNamespace(width=60.0, height=44.0)
        self.map = _MapStub([self.arriving, self.enemy])

    def _resolve_unit_by_id(self, unit_id: str):
        for player in self.players:
            for unit in list(player.army.units or []):
                if str(getattr(unit, "id", "") or "") == str(unit_id or ""):
                    return unit
        return None

    def get_current_player(self):
        return self.players[self.current_player_index]

    def get_enemy_units(self, player: object):
        if player is self.players[0]:
            return [self.enemy]
        return [self.arriving]


def test_move_solver_replaces_illegal_reserves_arrival_candidate_with_freeform_confirm(monkeypatch) -> None:
    game = _GameStub()
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Arrive from reserves",
        player_id="player:arriving",
        options=[
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": "unit:arriving", "movement_type": "move", "action": "confirm"},
            ),
            DecisionOption.create(
                "Skip",
                payload={"unit_id": "unit:arriving", "movement_type": "move", "action": "skip"},
            ),
        ],
        context={
            "unit_id": "unit:arriving",
            "movement_type": "move",
            "placement_kind": "reserves_arrival",
            "allow_skip": True,
        },
    )
    intent = MovementIntent.from_context(request.context)

    def _invalid_reserves_translation(*_args, **_kwargs):
        return (
            [
                {
                    "model_id": "unit:arriving:model-1",
                    "position": [18.0, 10.0, 0.0],
                    "facing": 0.0,
                }
            ],
            {
                "movement_distance": 6.0,
                "enemy_distance_delta": 1.0,
                "objective_distance_delta": 0.0,
            },
        )

    monkeypatch.setattr(
        "warhammer40k_ai.engine.movement_solver._translate_model_positions",
        _invalid_reserves_translation,
    )

    candidates, mask, _wall_clock_ms, fallback_mode = generate_move_unit_candidates(game, request, intent)

    assert fallback_mode is False
    action_mask = {str(dict(candidate.params or {}).get("action", "") or ""): bool(mask[idx]) for idx, candidate in enumerate(list(candidates or []))}
    assert action_mask == {"confirm": True, "skip": True}
    confirm_candidate = next(
        candidate
        for candidate in list(candidates or [])
        if str(dict(candidate.params or {}).get("action", "") or "") == "confirm"
    )
    assert "model_positions" not in dict(confirm_candidate.params or {})
    assert str(dict(confirm_candidate.metadata or {}).get("candidate_kind", "") or "") == "freeform_confirm"


def test_select_movement_action_masks_advance_when_planned_endpoint_is_normal_distance() -> None:
    game = _GameStub()
    game.arriving.reserve_status = "deployed"
    game.arriving.deployed = True
    request = DecisionRequest.create(
        DECISION_SELECT_MOVEMENT_ACTION,
        "Select movement action",
        player_id="player:arriving",
        options=[
            DecisionOption.create(
                "Move",
                payload={
                    "unit_id": "unit:arriving",
                    "action_type": "move",
                    "action_id": "select:move",
                },
            ),
            DecisionOption.create(
                "Advance",
                payload={
                    "unit_id": "unit:arriving",
                    "action_type": "advance",
                    "action_id": "select:advance",
                },
            ),
            DecisionOption.create(
                "Remain Stationary",
                payload={
                    "unit_id": "unit:arriving",
                    "action_type": "stationary",
                    "action_id": "select:stationary",
                },
            ),
        ],
        context={
            "unit_id": "unit:arriving",
            "phase_name": "MOVEMENT_PHASE",
            "phase_step": "MOVE_UNITS",
        },
    )
    intent = MovementIntent.from_context(request.context)

    candidates, mask, mask_reasons = generate_select_movement_action_candidates(game, request, intent)

    mask_by_action = {candidate.action_id: bool(mask[index]) for index, candidate in enumerate(candidates)}
    metadata_by_action = {candidate.action_id: dict(candidate.metadata or {}) for candidate in candidates}
    assert mask_by_action["select:move"] is True
    assert mask_by_action["select:advance"] is True
    assert mask_reasons == [None, None, None]
    assert (
        metadata_by_action["select:advance"]["movement_action_distance_mismatch"]
        == "advance_not_required_for_planned_endpoint"
    )


def _charge_move_game_and_request():
    army = _ArmyStub()
    player = _PlayerStub("player:one", army)
    army.player = player
    charger = _UnitStub("unit:charger", army=army, reserve_status="deployed")
    army.units.append(charger)
    game = SimpleNamespace(players=[player])
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Charge move",
        player_id=player.id,
        options=[
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": charger.id, "movement_type": "charge", "action": "confirm"},
            ),
            DecisionOption.create(
                "Skip",
                payload={"unit_id": charger.id, "movement_type": "charge", "action": "skip"},
            ),
        ],
        context={
            "unit_id": charger.id,
            "movement_type": "charge",
            "target_unit_ids": ["unit:target"],
            "max_distance": 7,
            "allow_skip": True,
        },
    )
    return game, request


def test_charge_move_solver_does_not_offer_skip_when_legal_charge_exists(monkeypatch) -> None:
    import warhammer40k_ai.engine.movement_solver as movement_solver

    game, request = _charge_move_game_and_request()

    def _charge_candidate(_game, *, request, confirm_option, **_kwargs):
        return CandidateAction(
            action_id=request.action_id_for_option_id(confirm_option.option_id),
            params={
                "unit_id": "unit:charger",
                "movement_type": "charge",
                "action": "confirm",
                "model_positions": [],
            },
            metadata={"candidate_kind": "charge"},
        )

    monkeypatch.setattr(movement_solver, "_charge_candidate", _charge_candidate)
    monkeypatch.setattr(movement_solver, "validate_move_unit_payload", lambda *_args, **_kwargs: ())

    candidates, mask = movement_solver._solver_candidates(game, request, MovementIntent())

    assert mask == [True]
    assert [dict(candidate.params or {}).get("action") for candidate in candidates] == ["confirm"]


def test_charge_move_solver_uses_skip_only_for_failed_charge_move(monkeypatch) -> None:
    import warhammer40k_ai.engine.movement_solver as movement_solver

    game, request = _charge_move_game_and_request()

    monkeypatch.setattr(movement_solver, "_charge_candidate", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(movement_solver, "validate_move_unit_payload", lambda *_args, **_kwargs: ())

    candidates, mask = movement_solver._solver_candidates(game, request, MovementIntent())

    assert mask == [True]
    assert len(candidates) == 1
    candidate = candidates[0]
    assert dict(candidate.params or {})["action"] == "skip"
    assert dict(candidate.params or {})["skipped"] is True
    assert dict(candidate.params or {})["charge_move_failed"] is True
    assert dict(candidate.params or {})["failure_reason"] == "no_legal_charge_move"
    assert dict(candidate.metadata or {})["candidate_kind"] == "charge_failed_no_legal_move"
