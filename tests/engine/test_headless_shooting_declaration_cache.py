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


def _round_base(x: float, y: float, *, radius: float = 1.0):
    return SimpleNamespace(
        has_circular_base=True,
        x=float(x),
        y=float(y),
        z=0.0,
        facing=0.0,
        get_radius=lambda: float(radius),
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


def test_shooting_select_unit_precheck_reuses_cached_legal_target_context():
    target = _alive_unit("target")
    profile = SimpleNamespace(_id="profile", name="Main", is_plasma_warhead=lambda: False)
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
    unit.round_state = SimpleNamespace(shot_this_round=False)
    unit.get_attached_unit_models = lambda: list(unit.models)
    unit.get_parent_army = lambda: None
    unit.is_in_reserves = lambda: False
    unit._validate_shooting_declaration = validate
    game_map = SimpleNamespace(state_generation=1, get_enemy_units=lambda _unit: [target])
    queued: list[DecisionRequest] = []
    game = SimpleNamespace(
        map=game_map,
        players=[],
        turn=1,
        request_decision=lambda request: queued.append(request),
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

    assert HeadlessPolicyDecisionController._select_unit_option_is_currently_valid(game, request, "unit-option")
    assert calls["validate"] == 1

    declare_request = queue_declare_shots_request(game, unit, player_id="player-1")

    assert declare_request is queued[0]
    assert calls["validate"] == 1
    assert declare_request.context["allowed_target_unit_ids"] == ["target"]


def test_headless_declare_shots_request_is_not_queued_without_legal_targets():
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

    assert request is None
    assert queued == []
    assert calls["validate"] == 2


def test_headless_declare_shots_skips_full_validation_when_longest_model_weapon_out_of_range():
    target = _alive_unit("target")
    target.models = [
        SimpleNamespace(
            _id="target-model",
            is_alive=True,
            model_base=_round_base(31.0, 0.0),
        )
    ]
    profile_short = SimpleNamespace(_id="profile-short", name="Short", range=SimpleNamespace(max=12), is_plasma_warhead=lambda: False)
    profile_long = SimpleNamespace(_id="profile-long", name="Long", range=SimpleNamespace(max=24), is_plasma_warhead=lambda: False)
    wargear = SimpleNamespace(
        _id="wargear",
        name="Rifle",
        is_ranged=lambda: True,
        profiles={"short": profile_short, "long": profile_long},
    )
    model = SimpleNamespace(_id="model", is_alive=True, wargear=[wargear], model_base=_round_base(0.0, 0.0))
    calls = {"validate": 0}

    def validate(_profile, _target, _models, _game_map):
        calls["validate"] += 1
        return {"valid": True}

    unit = _alive_unit("unit")
    unit.models = [model]
    unit.round_state = SimpleNamespace(shot_this_round=False)
    unit.get_attached_unit_models = lambda: list(unit.models)
    unit.get_parent_army = lambda: None
    unit.is_in_reserves = lambda: False
    unit._validate_shooting_declaration = validate
    game_map = SimpleNamespace(state_generation=1, get_enemy_units=lambda _unit: [target])
    queued: list[DecisionRequest] = []
    game = SimpleNamespace(
        map=game_map,
        players=[],
        turn=1,
        _headless_disable_generic_tool_decisions=True,
        request_decision=lambda request: queued.append(request),
    )

    request = queue_declare_shots_request(game, unit, player_id="player-1")

    assert request is None
    assert queued == []
    assert calls["validate"] == 0


def test_headless_declare_shots_applies_lone_operative_range_gate_before_los_validation():
    target = _alive_unit("target")
    target.models = [
        SimpleNamespace(
            _id="target-model",
            is_alive=True,
            model_base=_round_base(18.0, 0.0),
        )
    ]
    target.get_ranged_targeting_restriction = lambda *, game_map=None, ignore_lone_operative=False: (
        None if ignore_lone_operative else 12.0,
        ("Lone Operative",),
    )
    profile = SimpleNamespace(_id="profile", name="Main", range=SimpleNamespace(max=24), is_plasma_warhead=lambda: False)
    wargear = SimpleNamespace(
        _id="wargear",
        name="Rifle",
        is_ranged=lambda: True,
        profiles={"main": profile},
    )
    model = SimpleNamespace(_id="model", is_alive=True, wargear=[wargear], model_base=_round_base(0.0, 0.0))
    calls = {"validate": 0}

    def validate(_profile, _target, _models, _game_map):
        calls["validate"] += 1
        return {"valid": True}

    unit = _alive_unit("unit")
    unit.models = [model]
    unit.round_state = SimpleNamespace(shot_this_round=False)
    unit.get_attached_unit_models = lambda: list(unit.models)
    unit.get_parent_army = lambda: None
    unit.is_in_reserves = lambda: False
    unit._validate_shooting_declaration = validate
    game_map = SimpleNamespace(state_generation=1, get_enemy_units=lambda _unit: [target])
    queued: list[DecisionRequest] = []
    game = SimpleNamespace(
        map=game_map,
        players=[],
        turn=1,
        _headless_disable_generic_tool_decisions=True,
        request_decision=lambda request: queued.append(request),
    )

    request = queue_declare_shots_request(game, unit, player_id="player-1")

    assert request is None
    assert queued == []
    assert calls["validate"] == 0
