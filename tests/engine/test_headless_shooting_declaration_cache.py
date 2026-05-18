from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS, DECISION_SELECT_UNIT
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.decision_requests import queue_declare_shots_request
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController


def _alive_unit(unit_id: str):
    return SimpleNamespace(
        _id=str(unit_id),
        is_alive=lambda: True,
        deployed=True,
        reserve_status="deployed",
        models=[],
    )


def test_default_shooting_declarations_reuse_validation_until_map_generation_changes():
    target = _alive_unit("target")
    profile = SimpleNamespace(_id="profile", name="Main", skill=3, get_damage_potential=lambda _target: 1.0)
    wargear = SimpleNamespace(
        _id="wargear",
        name="Rifle",
        is_ranged=lambda: True,
        profiles={"main": profile},
    )
    model = SimpleNamespace(_id="model", is_alive=True, wargear=[wargear], model_base=SimpleNamespace(x=0, y=0, z=0, facing=0))
    calls = {"validate": 0}

    def validate(_profile, _target, _models, _game_map):
        calls["validate"] += 1
        return {"valid": True}

    unit = _alive_unit("unit")
    unit.models = [model]
    unit._validate_shooting_declaration = validate
    game_map = SimpleNamespace(state_generation=1, get_enemy_units=lambda _unit: [target])
    game = SimpleNamespace(
        map=game_map,
        turn=1,
        phase=SimpleNamespace(name="SHOOTING_PHASE"),
        _headless_policy_controller_attached=True,
        _resolve_unit_by_id=lambda unit_id: unit if unit_id == "unit" else target if unit_id == "target" else None,
    )
    request = DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        "Declare shots",
        context={"phase_name": "SHOOTING_PHASE", "unit_id": "unit"},
    )
    payload = {"unit_id": "unit", "max_declarations": 1, "max_validation_attempts": 0}

    first = HeadlessPolicyDecisionController._default_shooting_declarations(game, request, payload)
    second = HeadlessPolicyDecisionController._default_shooting_declarations(game, request, payload)
    assert first == second
    assert calls["validate"] == 1

    game_map.state_generation = 2
    third = HeadlessPolicyDecisionController._default_shooting_declarations(game, request, payload)
    assert third == first
    assert calls["validate"] == 2


def test_default_shooting_declarations_probe_only_ranked_target_slice():
    target_a = _alive_unit("target-a")
    target_b = _alive_unit("target-b")
    target_c = _alive_unit("target-c")
    profile = SimpleNamespace(
        _id="profile",
        name="Main",
        skill=3,
        strength=4,
        get_damage_potential=lambda _target: 1.0,
    )
    wargear = SimpleNamespace(
        _id="wargear",
        name="Rifle",
        is_ranged=lambda: True,
        profiles={"main": profile},
    )
    model = SimpleNamespace(_id="model", is_alive=True, wargear=[wargear], model_base=SimpleNamespace(x=0, y=0, z=0, facing=0))
    calls = {"validate": 0}

    def validate(_profile, target, _models, _game_map):
        calls["validate"] += 1
        return {"valid": target is target_c}

    unit = _alive_unit("unit")
    unit.models = [model]
    unit._validate_shooting_declaration = validate
    game_map = SimpleNamespace(state_generation=1, get_enemy_units=lambda _unit: [target_c, target_b, target_a])
    game = SimpleNamespace(
        map=game_map,
        turn=1,
        phase=SimpleNamespace(name="SHOOTING_PHASE"),
        _headless_shooting_target_probe_limit=2,
        _resolve_unit_by_id=lambda unit_id: unit if unit_id == "unit" else None,
    )
    request = DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        "Declare shots",
        context={"phase_name": "SHOOTING_PHASE", "unit_id": "unit"},
    )

    declarations = HeadlessPolicyDecisionController._default_shooting_declarations(
        game,
        request,
        {"unit_id": "unit"},
    )

    assert declarations == []
    assert calls["validate"] == 2


def test_shooting_select_unit_precheck_uses_ranged_potential_without_los_validation(monkeypatch):
    target = _alive_unit("target")
    profile = SimpleNamespace(_id="profile", name="Main")
    wargear = SimpleNamespace(
        _id="wargear",
        name="Rifle",
        is_ranged=lambda: True,
        profiles={"main": profile},
    )
    model = SimpleNamespace(_id="model", is_alive=True, wargear=[wargear], model_base=SimpleNamespace(x=0, y=0, z=0, facing=0))
    unit = _alive_unit("unit")
    unit.models = [model]
    game_map = SimpleNamespace(state_generation=1, get_enemy_units=lambda _unit: [target])
    game = SimpleNamespace(
        map=game_map,
        turn=1,
        phase=SimpleNamespace(name="SHOOTING_PHASE"),
        _headless_policy_controller_attached=True,
        _resolve_unit_by_id=lambda unit_id: unit if unit_id == "unit" else target if unit_id == "target" else None,
    )
    option = DecisionOption(option_id="unit-option", label="Unit", payload={"unit_id": "unit"})
    request = DecisionRequest.create(
        DECISION_SELECT_UNIT,
        "Select unit",
        options=[option],
        context={
            "phase_name": "SHOOTING_PHASE",
            "phase_step": "SHOOT_UNITS",
            "selection_purpose": "ACTIVATE_SHOOTING_UNIT",
        },
    )

    def unexpected_default_declarations(*_args, **_kwargs):
        raise AssertionError("shooting unit precheck should not run full LOS declarations")

    monkeypatch.setattr(
        HeadlessPolicyDecisionController,
        "_default_shooting_declarations",
        unexpected_default_declarations,
    )

    assert HeadlessPolicyDecisionController._select_unit_option_is_currently_valid(game, request, "unit-option")


def test_headless_declare_shots_request_uses_fast_target_context_without_los_validation():
    target_a = _alive_unit("target-a")
    target_b = _alive_unit("target-b")
    profile = SimpleNamespace(_id="profile", name="Main", is_plasma_warhead=lambda: False)
    wargear = SimpleNamespace(
        _id="wargear",
        name="Rifle",
        is_ranged=lambda: True,
        profiles={"main": profile},
    )
    model = SimpleNamespace(_id="model", is_alive=True, wargear=[wargear])
    calls = {"validate": 0}

    def validate(_profile, _target, _models, _game_map):
        calls["validate"] += 1
        return {"valid": False}

    unit = _alive_unit("unit")
    unit.models = [model]
    unit.round_state = SimpleNamespace(shot_this_round=False)
    unit.get_attached_unit_models = lambda: list(unit.models)
    unit.get_parent_army = lambda: None
    unit.is_in_reserves = lambda: False
    unit._validate_shooting_declaration = validate
    game_map = SimpleNamespace(state_generation=1, get_enemy_units=lambda _unit: [target_b, target_a])
    queued: list[DecisionRequest] = []
    game = SimpleNamespace(
        map=game_map,
        players=[],
        turn=1,
        _headless_disable_generic_tool_decisions=True,
        request_decision=lambda request: queued.append(request),
    )

    request = queue_declare_shots_request(game, unit, player_id="player-1")

    assert request is queued[0]
    assert calls["validate"] == 0
    assert request.context["allowed_target_unit_ids"] == ["target-a", "target-b"]
    assert request.context["shooting_target_generation"] == 1
    assert request.context["shooting_target_candidates"] == [
        {
            "unit_id": "unit",
            "model_id": "model",
            "wargear_id": "wargear",
            "weapon_instance_id": "wargear",
            "profile_name": "main",
            "is_plasma_warhead": False,
            "map_state_generation": 1,
            "target_unit_ids": ["target-a", "target-b"],
            "candidate_tags": {"target_count": 2, "forced_target": False},
        }
    ]
