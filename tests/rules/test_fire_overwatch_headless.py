import logging
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.shooting import (
    _apply_select_overwatch,
    _validate_select_overwatch,
)
from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionQueue, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController
from warhammer40k_ai.rules.stratagems import StratagemManager


def _fire_overwatch_manager(*, apply_info: dict | None = None) -> StratagemManager:
    manager = StratagemManager.__new__(StratagemManager)
    manager.available = [SimpleNamespace(name="FIRE OVERWATCH", cp_cost=1, type="Core")]
    manager._current_phase_name = "Movement phase"
    manager._pending_reactions = []
    manager._used_once_per_battle = {}
    manager._used_stratagems_this_phase = set()
    manager._used_this_turn = {"OVERWATCH": False}
    manager.game = SimpleNamespace(map=object())
    manager.player = SimpleNamespace(
        command_points=1,
        apply_stratagem_cp_cost=lambda *_args, **_kwargs: dict(apply_info or {"cost": 1}),
        spend_command_points=lambda *_args, **_kwargs: True,
    )

    def _unused_faction_handler(*_args, **_kwargs):
        return None

    for name in (
        "_use_grey_knights_warpbane_stratagem",
        "_use_imperial_agents_veiled_blade_stratagem",
        "_use_imperial_agents_imperialis_fleet_stratagem",
        "_use_imperial_agents_ordo_hereticus_stratagem",
        "_use_imperial_agents_ordo_malleus_stratagem",
        "_use_imperial_agents_ordo_xenos_stratagem",
        "_use_chaos_daemons_plague_legion_stratagem",
        "_use_chaos_daemons_shadow_legion_stratagem",
        "_use_chaos_daemons_legion_of_excess_stratagem",
        "_use_chaos_daemons_blood_legion_stratagem",
        "_use_chaos_knights_stratagem",
        "_use_adeptus_custodes_stratagem",
    ):
        setattr(manager, name, _unused_faction_handler)
    return manager


def _fire_overwatch_shooter() -> SimpleNamespace:
    return SimpleNamespace(
        id="unit:shooter",
        name="Shooter",
        is_embarked=False,
        embarked_in=None,
        special_rules={},
        is_battle_shocked=lambda: False,
        can_shoot_out_of_phase_at_target=lambda _enemy, _game_map: True,
    )


def _fire_overwatch_enemy() -> SimpleNamespace:
    enemy = SimpleNamespace(id="unit:enemy", name="Enemy", special_rules={})
    enemy.is_overwatch_prevented_against = lambda _shooter, game=None: False
    return enemy


def _fire_overwatch_request(*, player_id: str, enemy_unit_id: str, shooter_unit_id: str) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_SELECT_OVERWATCH_SHOOTER,
        "FIRE OVERWATCH: select a unit to shoot the enemy mover.",
        player_id=player_id,
        options=[
            DecisionOption.create(
                "Shooter",
                payload={
                    "unit_id": shooter_unit_id,
                    "ability_key": "fire_overwatch",
                    "stratagem_name": "FIRE OVERWATCH",
                },
            ),
            DecisionOption.create(
                "Do not use",
                payload={
                    "action": "skip",
                    "skip": True,
                    "ability_key": "fire_overwatch",
                    "stratagem_name": "FIRE OVERWATCH",
                },
            ),
        ],
        context={
            "ability": "fire_overwatch",
            "phase_name": "Movement phase",
            "enemy_unit_id": enemy_unit_id,
            "stratagem_name": "FIRE OVERWATCH",
            "optional": True,
        },
    )


def test_queue_fire_overwatch_decision_publishes_select_shooter_request() -> None:
    manager = StratagemManager.__new__(StratagemManager)
    decision_queue = DecisionQueue()
    game = SimpleNamespace(
        is_authoritative=True,
        decision_queue=decision_queue,
        request_decision=decision_queue.add,
    )
    player = SimpleNamespace(id="player:overwatch")
    moving_unit = SimpleNamespace(id="unit:enemy", name="Enemy Movers")
    candidates = [
        SimpleNamespace(id="unit:shooter-b", name="Shooter B"),
        SimpleNamespace(id="unit:shooter-a", name="Shooter A"),
    ]
    stratagem = SimpleNamespace(name="FIRE OVERWATCH", cp_cost=1)
    manager.game = game
    manager.player = player

    assert manager._queue_overwatch_decision(
        moving_unit=moving_unit,
        action="normal_move",
        when="start",
        phase_name="Movement phase",
        candidates=candidates,
        stratagem=stratagem,
    ) is True
    pending = list(decision_queue.list() or [])
    assert len(pending) == 1

    request = pending[0]
    assert request.decision_type == DECISION_SELECT_OVERWATCH_SHOOTER
    assert request.context["ability"] == "fire_overwatch"
    assert request.context["enemy_unit_id"] == "unit:enemy"
    assert request.context["tool_id"] == "stratagem:fire_overwatch"
    assert request.context["dispatch_mode"] == "interrupt"
    assert request.context["interrupt_window"] == "start_normal_move"
    assert request.context["out_of_phase"] is True
    assert request.context["blocking_parent"] is True
    assert request.context["resume_parent_after_resolution"] is True
    assert request.context["limited_use"] is True
    assert request.context["limited_use_scope"] == "turn"
    assert request.context["limited_use_key"] == "fire_overwatch"
    assert request.context["once_per_turn"] is True
    assert request.context["once_per_turn_key"] == "fire_overwatch"
    payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    assert [payload.get("unit_id") for payload in payloads[:-1]] == ["unit:shooter-a", "unit:shooter-b"]
    assert str(payloads[-1].get("action", "")) == "skip"

    assert manager._queue_overwatch_decision(
        moving_unit=moving_unit,
        action="normal_move",
        when="start",
        phase_name="Movement phase",
        candidates=candidates,
        stratagem=stratagem,
    ) is False
    assert len(list(decision_queue.list() or [])) == 1


def test_queue_fire_overwatch_decision_uses_unique_shooter_labels_for_duplicate_unit_names() -> None:
    manager = StratagemManager.__new__(StratagemManager)
    decision_queue = DecisionQueue()
    game = SimpleNamespace(
        is_authoritative=True,
        decision_queue=decision_queue,
        request_decision=decision_queue.add,
    )
    player = SimpleNamespace(id="player:overwatch")
    moving_unit = SimpleNamespace(id="unit:enemy", name="Enemy Movers")
    candidates = [
        SimpleNamespace(id="unit:rangers-2", name="Rangers"),
        SimpleNamespace(id="unit:rangers-1", name="Rangers"),
    ]
    stratagem = SimpleNamespace(name="FIRE OVERWATCH", cp_cost=1)
    manager.game = game
    manager.player = player

    assert manager._queue_overwatch_decision(
        moving_unit=moving_unit,
        action="normal_move",
        when="start",
        phase_name="Movement phase",
        candidates=candidates,
        stratagem=stratagem,
    ) is True

    request = list(decision_queue.list() or [])[0]
    assert [option.label for option in list(request.options or [])[:-1]] == ["Rangers #1", "Rangers #2"]
    assert [option.payload.get("unit_label") for option in list(request.options or [])[:-1]] == [
        "Rangers #1",
        "Rangers #2",
    ]


def test_apply_select_overwatch_uses_fire_overwatch_stratagem() -> None:
    calls: list[tuple[str, dict]] = []
    manager = SimpleNamespace(
        use=lambda name, **kwargs: calls.append((name, dict(kwargs))) or True,
        _dequeue_reaction_by_name_and_context=lambda *_args, **_kwargs: None,
    )
    shooter = SimpleNamespace(id="unit:shooter", name="Shooter")
    enemy = SimpleNamespace(id="unit:enemy", name="Enemy")
    player = SimpleNamespace(id="player:overwatch", stratagems=manager)
    game = SimpleNamespace(players=[player], entity_registry=None)
    request = _fire_overwatch_request(player_id=player.id, enemy_unit_id=enemy.id, shooter_unit_id=shooter.id)
    choice = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("unit_id", "") or "") == shooter.id
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=choice.option_id,
        payload={},
    )

    player_lookup = {player.id: player}
    unit_lookup = {shooter.id: shooter, enemy.id: enemy}
    game.entity_registry = SimpleNamespace(get=lambda entity_id, kind=None: player_lookup.get(entity_id) if kind == "player" else unit_lookup.get(entity_id))

    assert _validate_select_overwatch(game, request, result) == ()
    assert _apply_select_overwatch(game, request, result) is shooter
    assert calls == [
        (
            "FIRE OVERWATCH",
            {
                "shooter_unit": shooter,
                "enemy_unit": enemy,
                "phase_name": "Movement phase",
                "dequeue": True,
            },
        )
    ]


def test_validate_select_overwatch_rejects_stale_once_used_choice() -> None:
    manager = SimpleNamespace(
        can_use=lambda *_args, **_kwargs: False,
        _dequeue_reaction_by_name_and_context=lambda *_args, **_kwargs: None,
    )
    shooter = SimpleNamespace(id="unit:shooter", name="Shooter")
    enemy = SimpleNamespace(id="unit:enemy", name="Enemy")
    player = SimpleNamespace(id="player:overwatch", stratagems=manager)
    game = SimpleNamespace(players=[player], entity_registry=None)
    request = _fire_overwatch_request(player_id=player.id, enemy_unit_id=enemy.id, shooter_unit_id=shooter.id)
    choice = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("unit_id", "") or "") == shooter.id
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=choice.option_id,
        payload={},
    )

    player_lookup = {player.id: player}
    unit_lookup = {shooter.id: shooter, enemy.id: enemy}
    game.entity_registry = SimpleNamespace(
        get=lambda entity_id, kind=None: player_lookup.get(entity_id) if kind == "player" else unit_lookup.get(entity_id)
    )

    assert _validate_select_overwatch(game, request, result) == (
        "Fire Overwatch is no longer legal for the selected unit.",
    )


def test_headless_precheck_rejects_stale_fire_overwatch_choice_before_apply() -> None:
    manager = SimpleNamespace(
        can_use=lambda *_args, **_kwargs: False,
        _dequeue_reaction_by_name_and_context=lambda *_args, **_kwargs: None,
    )
    shooter = SimpleNamespace(id="unit:shooter", name="Shooter")
    enemy = SimpleNamespace(id="unit:enemy", name="Enemy")
    player = SimpleNamespace(id="player:overwatch", stratagems=manager)
    game = SimpleNamespace(players=[player], entity_registry=None)
    request = _fire_overwatch_request(player_id=player.id, enemy_unit_id=enemy.id, shooter_unit_id=shooter.id)
    shooter_choice = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("unit_id", "") or "") == shooter.id
    )
    skip_choice = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("action", "") or "") == "skip"
    )

    player_lookup = {player.id: player}
    unit_lookup = {shooter.id: shooter, enemy.id: enemy}
    game.entity_registry = SimpleNamespace(
        get=lambda entity_id, kind=None: player_lookup.get(entity_id) if kind == "player" else unit_lookup.get(entity_id)
    )

    assert (
        HeadlessPolicyDecisionController._candidate_passes_current_game_precheck(
            game,
            request,
            shooter_choice.option_id,
        )
        is False
    )
    assert (
        HeadlessPolicyDecisionController._candidate_passes_current_game_precheck(
            game,
            request,
            skip_choice.option_id,
        )
        is True
    )


def test_apply_select_overwatch_purges_other_same_phase_overwatch_requests() -> None:
    manager = SimpleNamespace(
        use=lambda *_args, **_kwargs: True,
        _dequeue_reaction_by_name_and_context=lambda *_args, **_kwargs: None,
    )
    shooter = SimpleNamespace(id="unit:shooter", name="Shooter")
    enemy = SimpleNamespace(id="unit:enemy", name="Enemy")
    player = SimpleNamespace(id="player:overwatch", stratagems=manager)
    queue = DecisionQueue()
    game = SimpleNamespace(players=[player], entity_registry=None, decision_queue=queue)
    request = _fire_overwatch_request(player_id=player.id, enemy_unit_id=enemy.id, shooter_unit_id=shooter.id)
    stale = _fire_overwatch_request(player_id=player.id, enemy_unit_id=enemy.id, shooter_unit_id=shooter.id)
    queue.add(request)
    queue.add(stale)
    choice = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("unit_id", "") or "") == shooter.id
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=choice.option_id,
        payload={},
    )

    player_lookup = {player.id: player}
    unit_lookup = {shooter.id: shooter, enemy.id: enemy}
    game.entity_registry = SimpleNamespace(
        get=lambda entity_id, kind=None: player_lookup.get(entity_id) if kind == "player" else unit_lookup.get(entity_id)
    )

    assert _apply_select_overwatch(game, request, result) is shooter
    assert queue.get(request.decision_id) is request
    assert queue.get(stale.decision_id) is None


def test_maybe_queue_overwatch_filters_units_without_legal_out_of_phase_shots() -> None:
    valid_shooter = SimpleNamespace(
        id="unit:valid",
        name="Valid Shooter",
        is_alive=lambda: True,
        deployed=True,
        is_titanic=False,
        is_embarked=False,
        embarked_in=None,
        special_rules={},
        is_battle_shocked=lambda: False,
        can_shoot_out_of_phase_at_target=lambda _enemy, _game_map: True,
    )
    invalid_shooter = SimpleNamespace(
        id="unit:invalid",
        name="Invalid Shooter",
        is_alive=lambda: True,
        deployed=True,
        is_titanic=False,
        is_embarked=False,
        embarked_in=None,
        special_rules={},
        is_battle_shocked=lambda: False,
        can_shoot_out_of_phase_at_target=lambda _enemy, _game_map: False,
    )
    defender_player = SimpleNamespace(
        id="player:defender",
        command_points=1,
        get_army=lambda: SimpleNamespace(units=[invalid_shooter, valid_shooter]),
    )
    attacker_player = SimpleNamespace(id="player:attacker")
    moving_unit = SimpleNamespace(
        id="unit:enemy",
        name="Enemy",
        get_parent_army=lambda: SimpleNamespace(player=attacker_player),
        special_rules={},
    )
    moving_unit.is_overwatch_prevented_against = lambda _target, game=None: False

    queued_candidates: list[object] = []
    manager = StratagemManager.__new__(StratagemManager)
    manager.player = defender_player
    manager.game = SimpleNamespace(
        get_current_player=lambda: attacker_player,
        map=SimpleNamespace(get_distance_between_units=lambda _u1, _u2: 10.0),
    )
    manager._used_this_turn = {"OVERWATCH": False}
    manager._used_stratagems_this_phase = set()
    manager._current_phase_name = "Movement phase"
    manager._pending_reactions = []
    manager._queue_reaction = lambda reaction: manager._pending_reactions.append(reaction)
    manager._queue_overwatch_decision = lambda **kwargs: queued_candidates.extend(list(kwargs.get("candidates", []) or [])) or True
    manager.get_by_name = lambda _name: SimpleNamespace(
        name="FIRE OVERWATCH",
        is_phase_allowed=lambda _phase: True,
        is_turn_allowed=lambda _is_active: True,
        cp_cost=1,
    )

    manager._maybe_queue_overwatch(moving_unit, action="move", when="start")

    assert queued_candidates == [valid_shooter]
    assert len(manager._pending_reactions) == 1
    assert list(manager._pending_reactions[0].get("candidates", []) or []) == [valid_shooter]


def test_fire_overwatch_registers_charge_declared_handler() -> None:
    manager = StratagemManager.__new__(StratagemManager)
    manager.available = [SimpleNamespace(name="FIRE OVERWATCH")]

    handlers = manager._compute_required_handlers()

    assert any(
        getattr(handler, "__name__", "") == "_on_charge_declared"
        for handler in list(handlers.get("charge_declared", []) or [])
    )


def test_charge_declared_opens_fire_overwatch_window_not_charge_end() -> None:
    valid_shooter = SimpleNamespace(
        id="unit:valid",
        name="Valid Shooter",
        is_alive=lambda: True,
        deployed=True,
        is_titanic=False,
        is_embarked=False,
        embarked_in=None,
        special_rules={},
        is_battle_shocked=lambda: False,
        can_shoot_out_of_phase_at_target=lambda _enemy, _game_map: True,
    )
    defender_player = SimpleNamespace(
        id="player:defender",
        command_points=1,
        get_army=lambda: SimpleNamespace(units=[valid_shooter]),
    )
    attacker_player = SimpleNamespace(id="player:attacker")
    charging_unit = SimpleNamespace(
        id="unit:charging",
        name="Charging Unit",
        get_parent_army=lambda: SimpleNamespace(player=attacker_player),
        special_rules={},
    )
    charging_unit.is_overwatch_prevented_against = lambda _target, game=None: False

    queued_contexts: list[dict] = []
    manager = StratagemManager.__new__(StratagemManager)
    manager.player = defender_player
    manager.game = SimpleNamespace(
        get_current_player=lambda: attacker_player,
        map=SimpleNamespace(get_distance_between_units=lambda _u1, _u2: 10.0),
    )
    manager._used_this_turn = {"OVERWATCH": False}
    manager._used_stratagems_this_phase = set()
    manager._current_phase_name = "Charge phase"
    manager._pending_reactions = []
    manager._queue_reaction = lambda reaction: manager._pending_reactions.append(reaction)
    manager._queue_overwatch_decision = lambda **kwargs: queued_contexts.append(dict(kwargs)) or True
    manager.get_by_name = lambda _name: SimpleNamespace(
        name="FIRE OVERWATCH",
        is_phase_allowed=lambda phase: str(phase or "") == "Charge phase",
        is_turn_allowed=lambda is_active: not bool(is_active),
        cp_cost=1,
    )

    manager._maybe_queue_overwatch(charging_unit, action="charge", when="end")

    assert queued_contexts == []
    assert manager._pending_reactions == []

    manager._on_charge_declared(charging_unit, target_units=[])

    assert len(queued_contexts) == 1
    assert queued_contexts[0]["action"] == "charge"
    assert queued_contexts[0]["when"] == "declare"
    assert queued_contexts[0]["candidates"] == [valid_shooter]
    assert len(manager._pending_reactions) == 1
    assert manager._pending_reactions[0]["action"] == "charge"
    assert manager._pending_reactions[0]["when"] == "declare"


def test_build_fire_overwatch_declarations_prefers_best_valid_profile() -> None:
    invalid_profile = SimpleNamespace(
        name="Heavy Invalid",
        get_damage_potential=lambda _target: 20.0,
    )
    valid_profile = SimpleNamespace(
        name="Pistol Valid",
        get_damage_potential=lambda _target: 3.0,
    )
    model = SimpleNamespace(
        id="model:1",
        is_alive=True,
        wargear=[
            SimpleNamespace(
                id="wargear:1",
                name="Heavy Gun",
                is_ranged=lambda: True,
                profiles={"heavy": invalid_profile},
            ),
            SimpleNamespace(
                id="wargear:2",
                name="Pistol",
                is_ranged=lambda: True,
                profiles={"pistol": valid_profile},
            ),
        ],
    )
    shooter = SimpleNamespace(
        models=[model],
        _validate_shooting_declaration=lambda profile, _enemy, _models, _game_map: {
            "valid": profile is valid_profile,
        },
    )
    enemy = SimpleNamespace(id="unit:enemy")

    manager = StratagemManager.__new__(StratagemManager)
    manager.game = SimpleNamespace(map=object())

    declarations = manager._build_fire_overwatch_declarations(shooter, enemy)

    assert len(declarations) == 1
    assert declarations[0]["weapon_profile"] is valid_profile
    assert declarations[0]["target_unit"] is enemy
    assert declarations[0]["models"] == [model]


def test_fire_overwatch_repeat_denial_logs_info_not_error(caplog) -> None:
    manager = _fire_overwatch_manager(apply_info={"denied": True, "reason": "Overwatch already used this turn"})
    shooter = _fire_overwatch_shooter()
    enemy = _fire_overwatch_enemy()

    with caplog.at_level(logging.INFO, logger="warhammer40k_ai.rules.stratagems"):
        used = manager.use("FIRE OVERWATCH", shooter_unit=shooter, enemy_unit=enemy, phase_name="Movement phase")

    assert used is False
    assert any("Overwatch already used this turn" in record.getMessage() for record in caplog.records)
    assert not [
        record
        for record in caplog.records
        if record.levelno >= logging.ERROR and "Overwatch" in record.getMessage()
    ]


def test_fire_overwatch_no_weapon_declarations_logs_info_not_error(caplog) -> None:
    manager = _fire_overwatch_manager()
    manager._build_fire_overwatch_declarations = lambda _shooter, _enemy: []
    shooter = _fire_overwatch_shooter()
    enemy = _fire_overwatch_enemy()

    with caplog.at_level(logging.INFO, logger="warhammer40k_ai.rules.stratagems"):
        used = manager.use("FIRE OVERWATCH", shooter_unit=shooter, enemy_unit=enemy, phase_name="Movement phase")

    assert used is False
    assert any("no ranged weapons eligible" in record.getMessage() for record in caplog.records)
    assert not [
        record
        for record in caplog.records
        if record.levelno >= logging.ERROR and "Overwatch" in record.getMessage()
    ]


def test_apply_select_overwatch_skip_clears_pending_reaction() -> None:
    dequeued: list[tuple[str, str, str, object]] = []
    manager = SimpleNamespace(
        use=lambda *_args, **_kwargs: True,
        _dequeue_reaction_by_name_and_context=lambda name, event="", phase_name="", enemy_unit=None: dequeued.append(
            (str(name), str(event), str(phase_name), enemy_unit)
        ),
    )
    enemy = SimpleNamespace(id="unit:enemy", name="Enemy")
    player = SimpleNamespace(id="player:overwatch", stratagems=manager)
    game = SimpleNamespace(players=[player], entity_registry=None)
    request = _fire_overwatch_request(player_id=player.id, enemy_unit_id=enemy.id, shooter_unit_id="unit:shooter")
    skip_option = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("action", "") or "") == "skip"
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=skip_option.option_id,
        payload={"skipped": True},
    )

    player_lookup = {player.id: player}
    unit_lookup = {enemy.id: enemy}
    game.entity_registry = SimpleNamespace(get=lambda entity_id, kind=None: player_lookup.get(entity_id) if kind == "player" else unit_lookup.get(entity_id))

    assert _validate_select_overwatch(game, request, result) == ()
    assert _apply_select_overwatch(game, request, result) is None
    assert dequeued == [("FIRE OVERWATCH", "enemy_move", "Movement phase", enemy)]
