from __future__ import annotations

from types import SimpleNamespace

from shapely.geometry import Point

import warhammer40k_ai.engine.headless_policy_controller as headless_policy_module
from warhammer40k_ai.engine.decision_handlers import movement as movement_handlers
from warhammer40k_ai.engine.decision_handlers._helpers import get_model, get_wargear
from warhammer40k_ai.engine.decision_kinds import DECISION_DISEMBARK, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.fight_move import serialize_attached_unit_positions, validate_fight_move_positions
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController


class _Base:
    def __init__(self, base_type: str = "CIRCULAR", radius: object = 0.5) -> None:
        self.base_type = base_type
        if isinstance(radius, (list, tuple)):
            self.radius = [float(radius[0]), float(radius[1] if len(radius) > 1 else radius[0])]
        else:
            self.radius = [float(radius), float(radius)]
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.facing = 0.0

    def set_position(self, x: float, y: float, z: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def set_facing(self, facing: float) -> None:
        self.facing = float(facing)

    def get_base_shape(self):
        return Point(float(self.x), float(self.y)).buffer(float(self.radius[0]))

    def get_radius(self) -> float:
        return float(self.radius[0])


class _Model:
    def __init__(self, model_id: str, x: float, y: float) -> None:
        self.id = model_id
        self.is_alive = True
        self.model_base = _Base()
        self.set_location(x, y, 0.0, 0.0)
        self.wargear = []

    def set_location(self, x: float, y: float, z: float = 0.0, facing: float = 0.0) -> None:
        self.model_base.set_position(x, y, z)
        self.model_base.set_facing(facing)

    def get_location(self):
        return (self.model_base.x, self.model_base.y, self.model_base.z, self.model_base.facing)


def _attached_unit(*, leader_x: float, leader_y: float = 0.0):
    body_model = _Model("model:body", 0.0, 0.0)
    leader_model = _Model("model:leader", leader_x, leader_y)
    bodyguard = SimpleNamespace(id="unit:bodyguard", name="Bodyguard", models=[body_model], models_lost=[])
    leader = SimpleNamespace(id="unit:leader", name="Leader", models=[leader_model], models_lost=[])
    bodyguard.get_attached_unit_root = lambda: bodyguard
    bodyguard.get_attached_unit_members = lambda: [bodyguard, leader]
    leader.get_attached_unit_root = lambda: bodyguard
    leader.get_attached_unit_members = lambda: [bodyguard, leader]
    return bodyguard, leader, body_model, leader_model


def test_fight_move_coherency_uses_full_attached_unit_models():
    unit, _leader, _body_model, _leader_model = _attached_unit(leader_x=1.5)
    game = SimpleNamespace(map=SimpleNamespace(units=[]))

    errors = validate_fight_move_positions(
        game,
        unit,
        movement_type="pile_in",
        model_positions=serialize_attached_unit_positions(unit),
        max_distance=3.0,
    )

    assert errors == []


def test_fight_move_coherency_rejects_split_attached_unit_models():
    unit, _leader, _body_model, _leader_model = _attached_unit(leader_x=5.0)
    game = SimpleNamespace(map=SimpleNamespace(units=[]))

    errors = validate_fight_move_positions(
        game,
        unit,
        movement_type="pile_in",
        model_positions=serialize_attached_unit_positions(unit),
        max_distance=3.0,
    )

    assert errors == ["Move unit: pile in would break unit coherency."]


def test_reactive_move_validator_uses_attached_unit_members_without_cached_getter(monkeypatch):
    unit, _leader, _body_model, _leader_model = _attached_unit(leader_x=1.5)
    game = SimpleNamespace(map=SimpleNamespace(units=[]))
    calls: list[str] = []

    def fake_validate_final_position(model, _position, _rules, _game_map):
        calls.append(str(model.id))
        if model.id == "model:leader":
            return {"valid": False, "reason": "leader model checked"}
        return {"valid": True}

    from warhammer40k_ai.utility import calcs as calcs_mod

    monkeypatch.setattr(calcs_mod, "validate_final_position", fake_validate_final_position)

    errors = movement_handlers._validate_cursed_circlet_positions(
        game,
        unit,
        serialize_attached_unit_positions(unit),
        ctx={"reactive_move_kind": "cursed_circlet", "max_distance": 3},
    )

    assert "model:body" in calls
    assert "model:leader" in calls
    assert errors == ("Move unit: Cursed Circlet leader model checked.",)


def test_fallback_entity_lookup_resolves_attached_member_model_and_wargear():
    unit, _leader, _body_model, leader_model = _attached_unit(leader_x=1.5)
    wargear = SimpleNamespace(id="wargear:leader-sword")
    leader_model.wargear = [wargear]
    army = SimpleNamespace(units=[unit])
    player = SimpleNamespace(army=army)
    game = SimpleNamespace(players=[player], entity_registry=None)

    assert get_model(game, "model:leader") is leader_model
    assert get_wargear(game, "wargear:leader-sword") is wargear


def test_disembark_validator_requires_positions_for_attached_members():
    unit, _leader, body_model, _leader_model = _attached_unit(leader_x=1.5)
    transport = SimpleNamespace(id="unit:transport", name="Transport", models=[], models_lost=[])
    army = SimpleNamespace(units=[unit, transport])
    player = SimpleNamespace(army=army)
    game = SimpleNamespace(players=[player], entity_registry=None)
    option = DecisionOption.create(
        "Disembark",
        payload={"unit_id": "unit:bodyguard", "transport_id": "unit:transport"},
    )
    request = DecisionRequest.create(
        DECISION_DISEMBARK,
        "Disembark attached unit",
        player_id="player:1",
        options=[option],
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=request.player_id,
        option_id=option.option_id,
        payload={"model_positions": [{"model_id": body_model.id, "position": [0.0, 0.0, 0.0, 0.0]}]},
    )

    errors = movement_handlers._validate_disembark(game, request, result)

    assert errors == ("Disembark requires positions for every alive model in the unit.",)


def test_movement_status_marks_attached_group_when_selected_member_points_to_root():
    bodyguard = SimpleNamespace(
        id="unit:bodyguard",
        round_state=SimpleNamespace(
            moved_this_round=False,
            remained_stationary_this_round=True,
            advanced_this_round=False,
        ),
    )
    leader = SimpleNamespace(
        id="unit:leader",
        round_state=SimpleNamespace(
            moved_this_round=False,
            remained_stationary_this_round=True,
            advanced_this_round=False,
        ),
    )
    bodyguard.get_attached_unit_root = lambda: bodyguard
    bodyguard.get_attached_unit_members = lambda: [bodyguard, leader]
    leader.get_attached_unit_root = lambda: bodyguard

    movement_handlers._mark_move_units_movement_status(leader, "advance")

    assert bodyguard.round_state.moved_this_round is True
    assert bodyguard.round_state.advanced_this_round is True
    assert bodyguard.round_state.remained_stationary_this_round is False
    assert leader.round_state.moved_this_round is True
    assert leader.round_state.advanced_this_round is True
    assert leader.round_state.remained_stationary_this_round is False


def test_headless_move_unit_precheck_rejects_invalid_model_positions(monkeypatch):
    option = DecisionOption.create(
        "Confirm",
        payload={"unit_id": "unit:bodyguard", "movement_type": "move", "action": "confirm"},
    )
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move attached unit",
        player_id="player:1",
        options=[option],
        context={"unit_id": "unit:bodyguard", "movement_type": "move"},
    )
    result_payload = {
        "unit_id": "unit:bodyguard",
        "movement_type": "move",
        "action": "confirm",
        "model_positions": [{"model_id": "model:body", "position": [0.0, 0.0, 0.0]}],
    }

    def fake_validate_move_unit_payload(_game, _request, *, option_payload, result_payload):
        assert option_payload["unit_id"] == "unit:bodyguard"
        assert result_payload["model_positions"]
        return ("stale candidate",)

    monkeypatch.setattr(headless_policy_module, "validate_move_unit_payload", fake_validate_move_unit_payload)

    assert (
        HeadlessPolicyDecisionController._candidate_passes_current_game_precheck(
            None,
            request,
            option.option_id,
            result_payload=result_payload,
        )
        is False
    )
