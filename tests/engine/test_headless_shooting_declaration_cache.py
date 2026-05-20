from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS, DECISION_SELECT_TOOL_ACTION, DECISION_SELECT_UNIT
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionRequest
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


def _shooting_game_with_profile(*, wargear_name: str = "Rifle", profile_name: str = "main"):
    target_a = _alive_unit("target-a")
    target_a.toughness = 10
    target_b = _alive_unit("target-b")
    target_b.toughness = 3
    profile = SimpleNamespace(
        _id=f"profile:{profile_name}",
        name=profile_name,
        skill=3,
        strength=4,
        get_damage_potential=lambda _target: 1.0,
    )
    wargear = SimpleNamespace(
        _id="wargear",
        name=wargear_name,
        is_ranged=lambda: True,
        profiles={profile_name: profile},
    )
    model = SimpleNamespace(_id="model", is_alive=True, wargear=[wargear], model_base=SimpleNamespace(x=0, y=0, z=0, facing=0))
    unit = _alive_unit("unit")
    unit.models = [model]
    game_map = SimpleNamespace(state_generation=1, get_enemy_units=lambda _unit: [target_a, target_b])

    def resolve(unit_id: str):
        return {
            "unit": unit,
            "target-a": target_a,
            "target-b": target_b,
        }.get(unit_id)

    game = SimpleNamespace(
        map=game_map,
        turn=1,
        phase=SimpleNamespace(name="SHOOTING_PHASE"),
        _headless_policy_controller_attached=True,
        _resolve_unit_by_id=resolve,
    )
    return game, unit, profile_name


def _target_candidate_row(target_ids: list[str], *, profile_name: str = "main") -> dict[str, object]:
    return {
        "unit_id": "unit",
        "model_id": "model",
        "wargear_id": "wargear",
        "profile_name": profile_name,
        "target_unit_ids": list(target_ids),
    }


def test_default_shooting_declarations_prefer_commander_primary_target_from_legal_candidates():
    game, _unit, profile_name = _shooting_game_with_profile()
    request = DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        "Declare shots",
        context={
            "phase_name": "SHOOTING_PHASE",
            "unit_id": "unit",
            "shooting_target_generation": 1,
            "shooting_target_candidates": [_target_candidate_row(["target-a", "target-b"], profile_name=profile_name)],
            "preferred_target_unit_ids": ["target-a", "target-b"],
            "commander_fire_assignment": {
                "unit_id": "unit",
                "primary_target_unit_id": "target-a",
                "backup_target_unit_ids": ["target-b"],
            },
        },
    )

    declarations = HeadlessPolicyDecisionController._default_shooting_declarations(
        game,
        request,
        {"unit_id": "unit", "max_declarations": 1},
    )

    assert declarations[0]["target_unit_id"] == "target-a"


def test_default_shooting_declarations_fall_back_when_commander_target_is_stale():
    game, _unit, profile_name = _shooting_game_with_profile()
    request = DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        "Declare shots",
        context={
            "phase_name": "SHOOTING_PHASE",
            "unit_id": "unit",
            "shooting_target_generation": 1,
            "shooting_target_candidates": [_target_candidate_row(["target-b"], profile_name=profile_name)],
            "preferred_target_unit_ids": ["target-a"],
            "commander_fire_assignment": {
                "unit_id": "unit",
                "primary_target_unit_id": "target-a",
                "backup_target_unit_ids": ["target-b"],
            },
        },
    )

    declarations = HeadlessPolicyDecisionController._default_shooting_declarations(
        game,
        request,
        {"unit_id": "unit", "max_declarations": 1},
    )

    assert declarations[0]["target_unit_id"] == "target-b"


def test_default_shooting_declarations_try_valid_preferred_declarations_first():
    game, _unit, profile_name = _shooting_game_with_profile()
    request = DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        "Declare shots",
        context={
            "phase_name": "SHOOTING_PHASE",
            "unit_id": "unit",
            "shooting_target_generation": 1,
            "shooting_target_candidates": [_target_candidate_row(["target-a", "target-b"], profile_name=profile_name)],
            "preferred_target_unit_ids": ["target-b"],
            "preferred_declarations": [
                {
                    "wargear_id": "wargear",
                    "profile_name": profile_name,
                    "target_unit_id": "target-a",
                    "model_ids": ["model"],
                }
            ],
        },
    )

    declarations = HeadlessPolicyDecisionController._default_shooting_declarations(
        game,
        request,
        {"unit_id": "unit", "max_declarations": 1},
    )

    assert declarations == [
        {
            "wargear_id": "wargear",
            "profile_name": profile_name,
            "target_unit_id": "target-a",
            "model_ids": ["model"],
        }
    ]


def test_general_resource_policy_reserves_one_shot_profiles_until_commander_authorizes_current_round():
    game, _unit, profile_name = _shooting_game_with_profile(
        wargear_name="Hunter-killer missile",
        profile_name="hunter-killer",
    )
    base_context = {
        "phase_name": "SHOOTING_PHASE",
        "unit_id": "unit",
        "shooting_target_generation": 1,
        "shooting_target_candidates": [_target_candidate_row(["target-a"], profile_name=profile_name)],
        "general_limited_resource_policy": [
            {
                "resource_id": "unit:one_shot_weapon",
                "resource_kind": "one_shot_weapon",
                "status": "reserved",
                "owner_unit_id": "unit",
                "authorization_threshold": 0.8,
            }
        ],
    }
    reserved_request = DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        "Declare shots",
        context={
            **base_context,
            "target_fire_plan_summary": {
                "target_unit_id": "target-a",
                "threat_score": 0.9,
            },
        },
    )
    authorized_request = DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        "Declare shots",
        context={
            **base_context,
            "commander_resource_authorizations": [
                {
                    "resource_id": "unit:one_shot_weapon",
                    "resource_kind": "one_shot_weapon",
                    "status": "conditionally_authorized",
                    "owner_unit_id": "unit",
                    "allowed_target_unit_ids": ["target-a"],
                    "authorization_threshold": 0.8,
                }
            ],
            "target_fire_plan_summary": {
                "target_unit_id": "target-a",
                "threat_score": 0.9,
            },
        },
    )

    reserved = HeadlessPolicyDecisionController._default_shooting_declarations(
        game,
        reserved_request,
        {"unit_id": "unit", "max_declarations": 1},
    )
    authorized = HeadlessPolicyDecisionController._default_shooting_declarations(
        game,
        authorized_request,
        {"unit_id": "unit", "max_declarations": 1},
    )

    assert reserved == []
    assert authorized[0]["target_unit_id"] == "target-a"


def test_commander_resource_authorization_blocks_wrong_one_shot_target():
    game, _unit, profile_name = _shooting_game_with_profile(
        wargear_name="Hunter-killer missile",
        profile_name="hunter-killer",
    )
    request = DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        "Declare shots",
        context={
            "phase_name": "SHOOTING_PHASE",
            "unit_id": "unit",
            "shooting_target_generation": 1,
            "shooting_target_candidates": [_target_candidate_row(["target-b"], profile_name=profile_name)],
            "commander_resource_authorizations": [
                {
                    "resource_id": "unit:one_shot_weapon",
                    "resource_kind": "one_shot_weapon",
                    "status": "conditionally_authorized",
                    "owner_unit_id": "unit",
                    "allowed_target_unit_ids": ["target-a"],
                    "authorization_threshold": 0.8,
                }
            ],
        },
    )

    declarations = HeadlessPolicyDecisionController._default_shooting_declarations(
        game,
        request,
        {"unit_id": "unit", "max_declarations": 1},
    )

    assert declarations == []


def test_tool_action_cp_reserve_penalty_preserves_unless_commander_authorizes():
    controller = HeadlessPolicyDecisionController(auto_attach=False)
    spend = CandidateAction(
        action_id="spend-cp",
        params={"action": "use", "cp_cost": 1},
        metadata={"projected_score_delta_round": 500.0},
    )
    context = {
        "general_cp_policy": {
            "reserve_for_interrupt_or_overwatch": 1,
            "reserve_for_defensive_reaction": 1,
        },
        "current_command_points": 1,
    }
    reserved_request = DecisionRequest.create(
        DECISION_SELECT_TOOL_ACTION,
        "Use tool?",
        context=context,
        candidates=[spend],
        mask=[True],
    )
    authorized_request = DecisionRequest.create(
        DECISION_SELECT_TOOL_ACTION,
        "Use tool?",
        context={
            **context,
            "commander_resource_authorizations": [
                {
                    "resource_id": "stratagem:commit",
                    "resource_kind": "stratagem",
                    "status": "authorized",
                }
            ],
        },
        candidates=[spend],
        mask=[True],
    )

    assert controller._semantic_score(reserved_request, spend) < controller._semantic_score(authorized_request, spend)
    assert HeadlessPolicyDecisionController._cp_reserve_penalty(
        reserved_request.context,
        spend.params,
        spend.metadata,
    ) > 0.0
    assert HeadlessPolicyDecisionController._cp_reserve_penalty(
        authorized_request.context,
        spend.params,
        spend.metadata,
    ) == 0.0


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
