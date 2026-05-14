from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.shooting import _validate_declare_shots
from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.decision_requests import queue_declare_shots_request
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionQueue, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.event.system import EventSystem
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController
from warhammer40k_ai.units.unit import Unit


class _MapStub:
    def __init__(self, enemies=None) -> None:
        self.units = list(enemies or [])
        self.state_generation = 0

    def get_enemy_units(self, _unit):
        return list(self.units)


class _RegistryStub:
    def __init__(self, items) -> None:
        self._items = {str(getattr(item, "id", "")): item for item in list(items or [])}

    def get(self, item_id, *, kind=None):
        del kind
        return self._items.get(str(item_id or ""))


def _profile(profile_id: str = "profile-1"):
    return SimpleNamespace(
        id=profile_id,
        _id=profile_id,
        name="default",
        is_plasma_warhead=lambda: False,
    )


def _wargear(wargear_id: str, profile=None):
    profile = profile or _profile(f"{wargear_id}:profile")
    return SimpleNamespace(
        id=wargear_id,
        _id=wargear_id,
        name="Rifle",
        profiles={"default": profile},
        is_ranged=lambda: True,
        is_melee=lambda: False,
    )


def _model(model_id: str, wargear):
    return SimpleNamespace(id=model_id, _id=model_id, is_alive=True, wargear=[wargear])


def _unit(unit_id: str, army, *, model=None, legal_target=None):
    unit = SimpleNamespace(
        id=unit_id,
        _id=unit_id,
        name=f"Unit {unit_id}",
        parent_army=army,
        deployed=True,
        is_embarked=False,
        embarked_in=None,
        models=[model] if model is not None else [],
        round_state=SimpleNamespace(shot_this_round=False, advanced_this_round=False, fell_back_this_round=False),
        special_rules={},
        get_parent_army=lambda: army,
        get_attached_unit_root=lambda: None,
        get_attached_unit_models=lambda: [],
        is_in_reserves=lambda: False,
        is_alive=lambda: True,
    )
    unit.get_attached_unit_root = lambda: unit
    unit.get_attached_unit_models = lambda: list(unit.models)
    unit._validate_shooting_declaration = (
        lambda _profile, target, _models, _game_map, **_kwargs: {
            "valid": target is legal_target,
            "reason": "No models in range or line of sight",
        }
    )
    return unit


def _players_with_units(shooter, *targets):
    p1 = SimpleNamespace(id="player-1", has_control=lambda: False)
    p2 = SimpleNamespace(id="player-2", has_control=lambda: False)
    army1 = SimpleNamespace(player=p1, units=[shooter])
    army2 = SimpleNamespace(player=p2, units=list(targets))
    p1.army = army1
    p2.army = army2
    shooter.parent_army = army1
    shooter.get_parent_army = lambda: army1
    for target in targets:
        target.parent_army = army2
        target.get_parent_army = lambda army=army2: army
    return p1, p2, army1, army2


def _game(players, units, *, enemies=None):
    return SimpleNamespace(
        is_authoritative=True,
        players=list(players),
        map=_MapStub(enemies=enemies),
        entity_registry=_RegistryStub(units),
        decision_queue=DecisionQueue(),
        request_decision=lambda request: None,
        turn=1,
    )


def test_declare_shots_request_does_not_precompute_expensive_target_candidates() -> None:
    profile = _profile()
    wargear = _wargear("weapon-1", profile)
    model = _model("model-1", wargear)
    legal_target = _unit("target-legal", None)
    illegal_target = _unit("target-illegal", None)
    shooter = _unit("shooter", None, model=model, legal_target=legal_target)
    calls = {"count": 0}

    def _validate(_profile, target, _models, _game_map, **_kwargs):
        calls["count"] += 1
        return {
            "valid": target is legal_target,
            "reason": "No models in range or line of sight",
        }

    shooter._validate_shooting_declaration = _validate
    p1, p2, _army1, _army2 = _players_with_units(shooter, legal_target, illegal_target)
    game = _game([p1, p2], [shooter, model, wargear, legal_target, illegal_target], enemies=[legal_target, illegal_target])
    queued: list[DecisionRequest] = []
    game.request_decision = lambda request: queued.append(request)

    request = queue_declare_shots_request(game, shooter, player_id=p1.id)

    assert request is queued[0]
    assert "allowed_target_unit_ids" not in request.context
    assert "shooting_target_candidates" not in request.context
    assert calls["count"] == 0


def test_headless_default_shooting_declarations_reuse_current_candidate_context() -> None:
    profile = _profile()
    wargear = _wargear("weapon-1", profile)
    model = _model("model-1", wargear)
    legal_target = _unit("target-legal", None)
    shooter = _unit("shooter", None, model=model, legal_target=legal_target)
    p1, p2, _army1, _army2 = _players_with_units(shooter, legal_target)
    game = _game([p1, p2], [shooter, model, wargear, legal_target], enemies=[legal_target])
    request = queue_declare_shots_request(game, shooter, player_id=p1.id)
    request.context.update(
        {
            "allowed_target_unit_ids": ["target-legal"],
            "shooting_target_candidates": [
                {
                    "model_id": "model-1",
                    "wargear_id": "weapon-1",
                    "profile_name": "default",
                    "target_unit_ids": ["target-legal"],
                }
            ],
            "shooting_target_candidates_state_generation": 0,
        }
    )

    def _unexpected_validation(*_args, **_kwargs):
        raise RuntimeError("candidate context should avoid validation replay")

    shooter._validate_shooting_declaration = _unexpected_validation

    declarations = HeadlessPolicyDecisionController._default_shooting_declarations(
        game,
        request,
        {"unit_id": "shooter"},
    )

    assert declarations == [
        {
            "wargear_id": "weapon-1",
            "profile_name": "default",
            "model_ids": ["model-1"],
            "target_unit_id": "target-legal",
        }
    ]


def test_declare_shots_validation_trusts_current_candidate_context() -> None:
    profile = _profile()
    wargear = _wargear("weapon-1", profile)
    model = _model("model-1", wargear)
    legal_target = _unit("target-legal", None)
    shooter = _unit("shooter", None, model=model, legal_target=legal_target)
    p1, p2, _army1, _army2 = _players_with_units(shooter, legal_target)
    game = _game([p1, p2], [shooter, model, wargear, legal_target], enemies=[legal_target])
    request = queue_declare_shots_request(game, shooter, player_id=p1.id)
    request.context.update(
        {
            "allowed_target_unit_ids": ["target-legal"],
            "shooting_target_candidates": [
                {
                    "model_id": "model-1",
                    "wargear_id": "weapon-1",
                    "profile_name": "default",
                    "target_unit_ids": ["target-legal"],
                }
            ],
            "shooting_target_candidates_state_generation": 0,
        }
    )
    calls = {"count": 0}

    def _reject_on_revalidation(*_args, **_kwargs):
        calls["count"] += 1
        return {"valid": False, "reason": "stale validation should not run"}

    shooter._validate_shooting_declaration = _reject_on_revalidation
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=p1.id,
        option_id=request.options[0].option_id,
        payload={
            "declarations": [
                {
                    "wargear_id": "weapon-1",
                    "profile_name": "default",
                    "model_ids": ["model-1"],
                    "target_unit_id": "target-legal",
                }
            ]
        },
    )

    assert list(_validate_declare_shots(game, request, result) or []) == []
    assert calls["count"] == 0


def test_declare_shots_validation_rechecks_stale_candidate_context() -> None:
    profile = _profile()
    wargear = _wargear("weapon-1", profile)
    model = _model("model-1", wargear)
    legal_target = _unit("target-legal", None)
    shooter = _unit("shooter", None, model=model, legal_target=legal_target)
    p1, p2, _army1, _army2 = _players_with_units(shooter, legal_target)
    game = _game([p1, p2], [shooter, model, wargear, legal_target], enemies=[legal_target])
    request = queue_declare_shots_request(game, shooter, player_id=p1.id)
    request.context.update(
        {
            "allowed_target_unit_ids": ["target-legal"],
            "shooting_target_candidates": [
                {
                    "model_id": "model-1",
                    "wargear_id": "weapon-1",
                    "profile_name": "default",
                    "target_unit_ids": ["target-legal"],
                }
            ],
            "shooting_target_candidates_state_generation": 0,
        }
    )
    game.map.state_generation += 1
    calls = {"count": 0}

    def _reject_on_revalidation(*_args, **_kwargs):
        calls["count"] += 1
        return {"valid": False, "reason": "candidate context is stale"}

    shooter._validate_shooting_declaration = _reject_on_revalidation
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=p1.id,
        option_id=request.options[0].option_id,
        payload={
            "declarations": [
                {
                    "wargear_id": "weapon-1",
                    "profile_name": "default",
                    "model_ids": ["model-1"],
                    "target_unit_id": "target-legal",
                }
            ]
        },
    )

    assert list(_validate_declare_shots(game, request, result) or []) == ["candidate context is stale"]
    assert calls["count"] == 1


def test_declare_shots_validation_trusts_current_headless_validated_declaration() -> None:
    profile = _profile()
    wargear = _wargear("weapon-1", profile)
    model = _model("model-1", wargear)
    legal_target = _unit("target-legal", None)
    shooter = _unit("shooter", None, model=model, legal_target=legal_target)
    p1, p2, _army1, _army2 = _players_with_units(shooter, legal_target)
    game = _game([p1, p2], [shooter, model, wargear, legal_target], enemies=[legal_target])
    request = queue_declare_shots_request(game, shooter, player_id=p1.id)

    declarations = HeadlessPolicyDecisionController._default_shooting_declarations(
        game,
        request,
        {"unit_id": "shooter"},
    )
    HeadlessPolicyDecisionController._mark_validated_shooting_declarations(
        request,
        declarations,
        game_map=game.map,
    )
    calls = {"count": 0}

    def _reject_on_revalidation(*_args, **_kwargs):
        calls["count"] += 1
        return {"valid": False, "reason": "stale validation should not run"}

    shooter._validate_shooting_declaration = _reject_on_revalidation
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=p1.id,
        option_id=request.options[0].option_id,
        payload={"declarations": declarations},
    )

    assert list(_validate_declare_shots(game, request, result) or []) == []
    assert calls["count"] == 0


def test_declare_shots_rejects_target_outside_candidate_context() -> None:
    profile = _profile()
    wargear = _wargear("weapon-1", profile)
    model = _model("model-1", wargear)
    legal_target = _unit("target-legal", None)
    illegal_target = _unit("target-illegal", None)
    shooter = _unit("shooter", None, model=model, legal_target=legal_target)
    p1, p2, _army1, _army2 = _players_with_units(shooter, legal_target, illegal_target)
    game = _game([p1, p2], [shooter, model, wargear, legal_target, illegal_target], enemies=[legal_target, illegal_target])
    option = DecisionOption.create("Confirm", payload={"action": "confirm", "unit_id": "shooter"})
    request = DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        "Declare shots",
        player_id=p1.id,
        options=[option],
        context={
            "unit_id": "shooter",
            "allowed_model_ids": ["model-1"],
            "allowed_wargear_ids": ["weapon-1"],
            "allowed_target_unit_ids": ["target-legal"],
            "shooting_target_candidates": [
                {
                    "model_id": "model-1",
                    "wargear_id": "weapon-1",
                    "profile_name": "default",
                    "target_unit_ids": ["target-legal"],
                }
            ],
        },
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=p1.id,
        option_id=option.option_id,
        payload={
            "declarations": [
                {
                    "wargear_id": "weapon-1",
                    "profile_name": "default",
                    "model_ids": ["model-1"],
                    "target_unit_id": "target-illegal",
                }
            ]
        },
    )

    errors = list(_validate_declare_shots(game, request, result) or [])

    assert errors == ["Declaration target is not an eligible shooting target."]


def test_selected_target_reactions_resolve_before_ranged_attacks() -> None:
    order: list[tuple[str, object]] = []
    game = SimpleNamespace(
        is_authoritative=True,
        players=[],
        event_system=EventSystem(),
        auto_resolve_dice_rolls=True,
        map=SimpleNamespace(),
        turn=1,
    )
    attacker_player = SimpleNamespace(id="attacker")
    defender_manager = SimpleNamespace(
        queue_headless_tool_action_decision=lambda *, reactions_only=False: order.append(
            ("reaction", bool(reactions_only), int(getattr(game, "_pre_attack_reaction_window_depth", 0) or 0))
        )
        or False
    )
    defender_player = SimpleNamespace(id="defender", stratagems=defender_manager)
    game.players = [attacker_player, defender_player]
    attacker_player.game = game
    defender_player.game = game

    attacker_army = SimpleNamespace(player=attacker_player)
    attacker = Unit.__new__(Unit)
    attacker._id = "attacker-unit"
    attacker.name = "Attacker"
    attacker.keywords = []
    attacker.models = [_model("attacker-model", _wargear("attacker-weapon"))]
    attacker.parent_army = attacker_army
    attacker.get_parent_army = lambda: attacker_army
    attacker.round_state = SimpleNamespace(
        action_locked_until_turn_end=False,
        shot_this_round=False,
        fell_back_this_round=False,
        advanced_this_round=False,
    )
    attacker._validate_shooting_declaration = lambda *_args, **_kwargs: {"valid": True, "reason": "ok"}
    attacker._execute_weapon_attacks = lambda *_args, **_kwargs: order.append(("attack", None)) or 1
    attacker._expand_tau_droneport_shooting_declarations = lambda declarations, **_kwargs: declarations
    attacker.validate_ctan_power_selection = lambda _declarations: (True, "")
    attacker._is_locked_in_combat = lambda _game_map: False
    attacker._ignore_engagement_for_ranged_targeting_active = lambda: False
    attacker._death_guard_all_is_rot_active = lambda: False
    attacker.weapon_profile_counts_as_pistol = lambda *_args, **_kwargs: False
    attacker._is_controlling_players_shooting_phase = lambda: True
    attacker.get_selected_to_shoot_charge_reroll_rule = lambda: None
    attacker.grant_selected_to_shoot_rerolls_for_models = lambda _models: None
    attacker.grant_selected_to_action_reroll_choice_for_models = lambda _models, action=None: None
    attacker._resolve_pending_attack_mortal_wounds = lambda *_args, **_kwargs: None
    attacker._resolve_pending_horrors_split = lambda **_kwargs: None
    attacker.clear_selected_to_shoot_rerolls = lambda: None
    attacker.clear_selected_to_action_reroll_choice = lambda action=None: None

    target_army = SimpleNamespace(player=defender_player)
    target = SimpleNamespace(
        id="target-unit",
        _id="target-unit",
        name="Target",
        parent_army=target_army,
        is_alive=lambda: True,
        get_attached_unit_root=lambda: None,
        begin_attack_resolution=lambda: None,
        end_attack_resolution=lambda **_kwargs: None,
    )
    target.get_attached_unit_root = lambda: target
    target.is_vehicle = False
    target.is_monster = False

    profile = _profile("attacker-profile")
    declarations = [{"weapon_profile": profile, "target_unit": target, "models": list(attacker.models)}]

    assert attacker.execute_shooting_declarations(declarations, game.map) is True
    assert order[0] == ("reaction", True, 1)
    assert order[1] == ("attack", None)
