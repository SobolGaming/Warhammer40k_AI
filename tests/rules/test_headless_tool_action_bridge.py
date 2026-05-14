import logging
from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.decision_handlers.stratagems import (
    _apply_select_tool_action,
    _validate_select_tool_action,
)
from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_TOOL_ACTION
from warhammer40k_ai.engine.decisions import DecisionQueue, DecisionResult
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController
from warhammer40k_ai.rules.stratagems import Stratagem, StratagemManager


def test_tool_action_action_id_ignores_volatile_expiry_fields() -> None:
    base_payload = {
        "tool_family": "stratagem",
        "tool_type": "stratagem",
        "tool_name": "GO TO GROUND",
        "resolved_kwargs": {
            "event": "shooting_targets_selected",
            "expires_at": 123.456,
            "unit": {"__entity_ref__": {"id": "unit:target", "kind": "unit"}},
        },
    }
    later_payload = {
        **base_payload,
        "resolved_kwargs": {
            **base_payload["resolved_kwargs"],
            "expires_at": 999.999,
        },
    }
    different_event = {
        **base_payload,
        "resolved_kwargs": {
            **base_payload["resolved_kwargs"],
            "event": "battle_shock_failed",
            "expires_at": 999.999,
        },
    }

    assert StratagemManager._tool_action_action_id("GO TO GROUND", base_payload) == StratagemManager._tool_action_action_id(
        "GO TO GROUND",
        later_payload,
    )
    assert StratagemManager._tool_action_action_id("GO TO GROUND", base_payload) != StratagemManager._tool_action_action_id(
        "GO TO GROUND",
        different_event,
    )


def _build_remote_tool_manager():
    decision_queue = DecisionQueue()
    target_unit = SimpleNamespace(id="unit:target", name="Target Unit")
    game = SimpleNamespace(
        is_authoritative=True,
        decision_queue=decision_queue,
        request_decision=decision_queue.add,
        get_current_player=lambda: player,
        turn=2,
    )
    player = SimpleNamespace(
        id="player:remote",
        active_secondaries=[],
        has_control=lambda: False,
        _has_attached_decision_controller=lambda: True,
    )
    stratagem = SimpleNamespace(
        id="stratagem:go_to_ground",
        name="GO TO GROUND",
        description="Take cover.",
        tool_descriptor=SimpleNamespace(
            target="target_unit",
            effect="benefit_of_cover",
            effect_params={},
        ),
    )

    manager = StratagemManager.__new__(StratagemManager)
    manager.game = game
    manager.player = player
    manager._current_phase_name = "Shooting phase"
    manager._skipped_tool_action_signatures = set()
    manager.get_phase_stratagem_items = lambda: [
        {
            "name": "GO TO GROUND",
            "available": True,
            "is_reaction": True,
            "context": {
                "phase_name": "Shooting phase",
                "target_unit": target_unit,
            },
        }
    ]
    manager.get_by_name = lambda _name: stratagem
    manager.can_use = lambda name, **kwargs: str(name).upper() == "GO TO GROUND" and kwargs.get("target_unit") is target_unit
    manager._effective_cp_cost = lambda _stratagem, _kwargs=None: 1
    player.stratagems = manager
    return manager, player, game, target_unit


def _build_generic_tool_manager(
    *,
    stratagem_name: str,
    descriptor_target: str,
    context: dict,
    can_use,
    stratagem_id: str | None = None,
    effect_params: dict | None = None,
) -> tuple:
    decision_queue = DecisionQueue()
    game = SimpleNamespace(
        is_authoritative=True,
        decision_queue=decision_queue,
        request_decision=decision_queue.add,
        get_current_player=lambda: player,
        turn=2,
    )
    player = SimpleNamespace(
        id="player:remote",
        active_secondaries=[],
        has_control=lambda: False,
        _has_attached_decision_controller=lambda: True,
    )
    stratagem = SimpleNamespace(
        id=str(stratagem_id or f"stratagem:{stratagem_name.lower().replace(' ', '_')}"),
        name=stratagem_name,
        description=f"{stratagem_name} test",
        tool_descriptor=SimpleNamespace(
            target=descriptor_target,
            effect="test",
            effect_params=dict(effect_params or {}),
        ),
    )
    manager = StratagemManager.__new__(StratagemManager)
    manager.game = game
    manager.player = player
    manager._current_phase_name = str(context.get("phase_name", "Shooting phase") or "Shooting phase")
    manager._skipped_tool_action_signatures = set()
    manager.get_phase_stratagem_items = lambda: [
        {
            "name": stratagem_name,
            "available": True,
            "is_reaction": True,
            "context": dict(context),
        }
    ]
    manager.get_by_name = lambda _name: stratagem
    manager.can_use = can_use
    manager._effective_cp_cost = lambda _stratagem, _kwargs=None: 1
    player.stratagems = manager
    return manager, player, game, stratagem


def _core_stratagem(
    name: str,
    *,
    stratagem_id: str,
    phase: str,
    turn: str = "Your turn",
    cp_cost: int = 1,
) -> Stratagem:
    return Stratagem(
        id=stratagem_id,
        name=name,
        type="Core - Strategic Ploy Stratagem",
        description=f"{name} test",
        cp_cost=cp_cost,
        turn=turn,
        phase=phase,
        detachment="",
        faction_id="",
    )


def _build_headless_core_manager(*, stratagem: Stratagem, player, game, phase_name: str) -> StratagemManager:
    manager = StratagemManager.__new__(StratagemManager)
    manager.player = player
    manager.game = game
    manager.available = [stratagem]
    manager._current_phase_name = phase_name
    manager._pending_reactions = []
    manager._reaction_timeout_s = 5.0
    manager._skipped_tool_action_signatures = set()
    manager._tool_action_probe_diagnostics = []
    manager._tool_action_probe_diagnostic_keys = set()
    manager._used_once_per_battle = {}
    manager._used_battle_round = {}
    manager._used_this_turn = {"OVERWATCH": False}
    manager._used_stratagems_this_phase = set()
    manager._command_reroll_units_this_phase = set()
    manager._grenade_units_this_phase = set()
    manager._heroic_intervention_units_this_phase = set()
    manager._rapid_ingress_units_this_phase = set()
    manager._defensive_reaction_cache = {}
    manager._charge_melee_ap_cache = {}
    manager._consolidate_move_cache = {}
    manager._get_defensive_reaction_spec = lambda _stratagem: None
    manager._get_consolidate_move_spec = lambda _stratagem: None
    manager.get_by_name = lambda name: stratagem if str(name or "").strip().upper() == stratagem.name.upper() else None
    player.stratagems = manager
    return manager


def _tool_payloads(request):
    return [
        dict(getattr(option, "payload", {}) or {})
        for option in list(getattr(request, "options", []) or [])
        if str((getattr(option, "payload", {}) or {}).get("tool_name", "") or "")
    ]


def test_core_stratagems_load_globally_for_headless_army() -> None:
    army = SimpleNamespace(
        faction_id="SM",
        has_detachment_type=lambda *_args, **_kwargs: False,
    )
    player = SimpleNamespace(
        id="player:core",
        game=None,
        get_army=lambda: army,
    )

    manager = StratagemManager(player)

    core_by_name = {
        str(getattr(stratagem, "name", "") or ""): stratagem
        for stratagem in manager.available
        if not str(getattr(stratagem, "faction_id", "") or "").strip()
    }
    assert set(core_by_name) == {
        "COMMAND RE-ROLL",
        "COUNTER-OFFENSIVE",
        "EPIC CHALLENGE",
        "FIRE OVERWATCH",
        "GO TO GROUND",
        "GRENADE",
        "HEROIC INTERVENTION",
        "INSANE BRAVERY",
        "NEW ORDERS",
        "RAPID INGRESS",
        "SMOKESCREEN",
        "TANK SHOCK",
    }
    assert all(manager._is_implemented_stratagem(stratagem) for stratagem in core_by_name.values())
    assert all("Boarding Actions" not in stratagem.type for stratagem in core_by_name.values())
    assert all("Challenger" not in stratagem.type for stratagem in core_by_name.values())


def test_queue_headless_tool_action_decision_builds_select_tool_action_request() -> None:
    manager, _player, game, target_unit = _build_remote_tool_manager()

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_SELECT_TOOL_ACTION
    assert request.context["ability"] == "tool_action"
    assert request.context["reactions_only"] is True

    payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    assert len(payloads) == 2
    assert payloads[0]["tool_name"] == "GO TO GROUND"
    assert payloads[0]["ability_key"] == "go_to_ground"
    assert payloads[0]["ability_name"] == "GO TO GROUND"
    assert payloads[0]["tool_family"] == "stratagem"
    assert payloads[0]["tool_id"] == "stratagem:go_to_ground"
    assert payloads[0]["stratagem_id"] == "stratagem:go_to_ground"
    assert payloads[0]["resolved_kwargs"]["target_unit"]["__entity_ref__"]["id"] == target_unit.id
    assert payloads[1]["action"] == "skip"


def test_headless_policy_prefers_skip_for_optional_tool_actions() -> None:
    manager, _player, game, _target_unit = _build_remote_tool_manager()

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    controller = HeadlessPolicyDecisionController(auto_attach=False)
    ranked = controller._rank_legal_candidates(request)

    assert ranked
    assert dict(ranked[0].params or {}).get("action") == "skip"


def test_queue_headless_tool_action_decision_normalizes_generic_stratagem_identity_payload() -> None:
    target_unit = SimpleNamespace(id="unit:target", name="Target Unit")
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="SOULSIGHT",
        stratagem_id="000009770006",
        descriptor_target="target_unit",
        context={
            "phase_name": "Shooting phase",
            "target_unit": target_unit,
        },
        can_use=lambda _name, **kwargs: kwargs.get("target_unit") is target_unit,
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    payload = dict(getattr(request.options[0], "payload", {}) or {})
    assert payload["ability_key"] == "soulsight"
    assert payload["ability_name"] == "SOULSIGHT"
    assert payload["tool_id"] == "stratagem:soulsight"
    assert payload["stratagem_id"] == "000009770006"
    assert payload["tool_descriptor_id"] == "tool_descriptor:stratagem:000009770006"


def test_normalize_phase_context_accepts_structured_singleton_candidate() -> None:
    manager = StratagemManager.__new__(StratagemManager)
    target_unit = SimpleNamespace(id="unit:target", name="Target Unit")
    enemy_unit = SimpleNamespace(id="unit:enemy", name="Enemy Unit")

    context = manager._normalize_phase_item_context(
        {
            "candidates": [{"target_unit": target_unit, "target_unit_id": target_unit.id}],
            "enemy_candidates_by_unit": {target_unit.id: [enemy_unit]},
        }
    )

    assert context["unit"] is target_unit
    assert context["target_unit"] is target_unit
    assert context["enemy_unit"] is enemy_unit
    assert context["target_enemy_unit"] is enemy_unit


def test_queue_headless_tool_action_decision_preserves_structured_order_the_advance_context() -> None:
    officer = SimpleNamespace(id="unit:officer", name="Tank Commander")
    target = SimpleNamespace(id="unit:target", name="Cadian Shock Troops")
    candidate = {
        "officer_unit": officer,
        "officer_unit_id": officer.id,
        "target_units": [target],
        "target_unit_ids": [target.id],
    }

    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="ORDER THE ADVANCE",
        descriptor_target="astra_militarum_officer_and_one_or_more_friendly_astra_militarum_units_within_6",
        context={
            "phase_name": "Movement phase",
            "candidates": [candidate],
        },
        can_use=lambda name, **kwargs: (
            str(name).upper() == "ORDER THE ADVANCE"
            and kwargs.get("officer_unit") is officer
            and kwargs.get("source_unit") is officer
            and list(kwargs.get("target_units") or []) == [target]
        ),
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    payload = _tool_payloads(request)[0]
    resolved = dict(payload["resolved_kwargs"])
    assert resolved["officer_unit"]["__entity_ref__"]["id"] == officer.id
    assert resolved["source_unit"]["__entity_ref__"]["id"] == officer.id
    assert resolved["target_units"][0]["__entity_ref__"]["id"] == target.id
    assert manager.get_tool_action_probe_diagnostics() == []


def test_queue_headless_tool_action_decision_pairs_unit_objective_candidates() -> None:
    unit = SimpleNamespace(id="unit:cybernetica", name="Kastelan Robots")
    objective = SimpleNamespace(id="objective:alpha", name="Objective Alpha")

    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="AUTO-DIVINATORY TARGETING",
        descriptor_target="friendly_unit_and_objective_marker",
        context={
            "phase_name": "Command phase",
            "candidates": [unit],
            "objective_candidates": [objective],
            "objective_candidates_by_unit": {unit.id: [objective]},
        },
        can_use=lambda name, **kwargs: (
            str(name).upper() == "AUTO-DIVINATORY TARGETING"
            and kwargs.get("unit") is unit
            and kwargs.get("objective") is objective
        ),
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    payloads = _tool_payloads(request)
    assert len(payloads) == 1
    resolved = dict(payloads[0]["resolved_kwargs"])
    assert resolved["unit"]["__entity_ref__"]["id"] == unit.id
    assert resolved["objective"]["__entity_ref__"]["id"] == objective.id
    assert manager.get_tool_action_probe_diagnostics() == []


def test_queue_headless_tool_action_decision_uses_passenger_map_for_mount_up_ladz() -> None:
    transport = SimpleNamespace(id="unit:trukk", name="Trukk")
    passenger = SimpleNamespace(id="unit:boyz", name="Boyz")

    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="MOUNT UP, LADZ",
        descriptor_target="friendly_transport_with_eligible_orks_infantry_unit",
        context={
            "phase_name": "Fight phase",
            "transport_candidates": [transport],
            "passenger_candidates_by_transport": {transport.id: [passenger]},
        },
        can_use=lambda name, **kwargs: (
            str(name).upper() == "MOUNT UP, LADZ"
            and kwargs.get("transport_unit") is transport
            and kwargs.get("passenger_unit") is passenger
        ),
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    payload = _tool_payloads(request)[0]
    resolved = dict(payload["resolved_kwargs"])
    assert resolved["transport_unit"]["__entity_ref__"]["id"] == transport.id
    assert resolved["passenger_unit"]["__entity_ref__"]["id"] == passenger.id
    assert manager.get_tool_action_probe_diagnostics() == []


def test_queue_headless_tool_action_decision_skips_explicit_command_reroll_bridge() -> None:
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="COMMAND RE-ROLL",
        descriptor_target="target_unit",
        context={"phase_name": "Fight phase"},
        can_use=lambda *_args, **_kwargs: True,
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is False
    assert list(game.decision_queue.list() or []) == []


@pytest.mark.parametrize(
    "stratagem_name",
    [
        "DUTY AND HONOUR",
        "ETHEREAL PHANTASM",
        "FRACTAL DISJUNCTION",
        "HEROES OF THE CHAPTER",
        "LEGENDARY FORTITUDE",
        "ORBITAL TELEPORTARIUM",
        "TERRIFYING PROFICIENCY",
    ],
)
def test_queue_headless_tool_action_decision_skips_bespoke_context_stratagems(stratagem_name: str) -> None:
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name=stratagem_name,
        descriptor_target="target_unit",
        context={"phase_name": "Shooting phase"},
        can_use=lambda *_args, **_kwargs: True,
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is False
    assert list(game.decision_queue.list() or []) == []


def test_headless_tank_shock_is_available_after_vehicle_charge_with_cp() -> None:
    stratagem = _core_stratagem(
        "TANK SHOCK",
        stratagem_id="000008335007",
        phase="Charge phase",
    )
    player = SimpleNamespace(id="player:tank", command_points=1)
    enemy_player = SimpleNamespace(id="player:enemy")
    army = SimpleNamespace(id="army:tank", units=[], player=player)
    enemy_army = SimpleNamespace(id="army:enemy", units=[], player=enemy_player)
    player.get_army = lambda: army
    enemy_player.get_army = lambda: enemy_army
    player.has_control = lambda: False
    player._has_attached_decision_controller = lambda: True
    player.active_secondaries = []

    charger = SimpleNamespace(
        id="unit:charger",
        name="Impulsor",
        is_vehicle=True,
        deployed=True,
        is_alive=lambda: True,
    )
    charger.get_parent_army = lambda: army
    charger.get_attached_unit_root = lambda: charger
    enemy_a = SimpleNamespace(id="unit:enemy-a", name="Enemy A", is_alive=lambda: True)
    enemy_b = SimpleNamespace(id="unit:enemy-b", name="Enemy B", is_alive=lambda: True)
    army.units = [charger]
    enemy_army.units = [enemy_a, enemy_b]

    game_map = SimpleNamespace(
        units=[charger, enemy_a, enemy_b],
        get_enemy_units=lambda unit: [enemy_a, enemy_b] if unit is charger else [],
        is_within_engagement_range=lambda left, right: left is charger and right in (enemy_a, enemy_b),
    )
    decision_queue = DecisionQueue()
    game = SimpleNamespace(
        is_authoritative=True,
        decision_queue=decision_queue,
        request_decision=decision_queue.add,
        get_current_player=lambda: player,
        map=game_map,
        players=[player, enemy_player],
        turn=1,
    )
    manager = _build_headless_core_manager(
        stratagem=stratagem,
        player=player,
        game=game,
        phase_name="Charge phase",
    )

    manager._on_unit_move_ended(charger, "charge")

    tank_item = next(item for item in manager.get_phase_stratagem_items() if item["name"] == "TANK SHOCK")
    assert tank_item["available"] is True
    assert tank_item["is_reaction"] is True
    assert tank_item["context"]["eligible_enemy_units"] == [enemy_a, enemy_b]

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True
    request = next(iter(game.decision_queue.list() or []))
    payloads = _tool_payloads(request)
    assert [payload["tool_name"] for payload in payloads] == ["TANK SHOCK", "TANK SHOCK"]
    assert [
        payload["resolved_kwargs"]["enemy_unit"]["__entity_ref__"]["id"]
        for payload in payloads
    ] == [enemy_a.id, enemy_b.id]
    assert all(
        payload["resolved_kwargs"]["target_unit"]["__entity_ref__"]["id"] == charger.id
        for payload in payloads
    )


def test_headless_grenade_is_available_in_shooting_phase_with_cp_and_targets() -> None:
    stratagem = _core_stratagem(
        "GRENADE",
        stratagem_id="000008335006",
        phase="Shooting phase",
    )
    player = SimpleNamespace(id="player:grenade", command_points=1)
    enemy_player = SimpleNamespace(id="player:enemy")
    army = SimpleNamespace(id="army:grenade", units=[], player=player)
    enemy_army = SimpleNamespace(id="army:enemy", units=[], player=enemy_player)
    player.get_army = lambda: army
    enemy_player.get_army = lambda: enemy_army
    player.has_control = lambda: False
    player._has_attached_decision_controller = lambda: True
    player.active_secondaries = []

    grenadier_model = SimpleNamespace(id="model:grenadier", name="Grenadier", is_alive=True)
    enemy_model_a = SimpleNamespace(id="model:enemy-a", name="Enemy A Model", is_alive=True)
    enemy_model_b = SimpleNamespace(id="model:enemy-b", name="Enemy B Model", is_alive=True)
    grenadier = SimpleNamespace(
        id="unit:grenadier",
        name="Intercessors",
        deployed=True,
        is_alive=lambda: True,
        models=[grenadier_model],
        round_state=SimpleNamespace(
            advanced_this_round=False,
            fell_back_this_round=False,
            shot_this_round=False,
        ),
        special_rules={},
    )
    grenadier.get_parent_army = lambda: army
    grenadier.get_attached_unit_root = lambda: grenadier
    grenadier.has_keyword = lambda keyword: str(keyword or "").strip().upper() == "GRENADES"
    enemy_a = SimpleNamespace(id="unit:enemy-a", name="Enemy A", models=[enemy_model_a], is_alive=lambda: True)
    enemy_b = SimpleNamespace(id="unit:enemy-b", name="Enemy B", models=[enemy_model_b], is_alive=lambda: True)
    army.units = [grenadier]
    enemy_army.units = [enemy_a, enemy_b]

    game_map = SimpleNamespace(
        units=[grenadier, enemy_a, enemy_b],
        get_enemy_units=lambda unit: [enemy_a, enemy_b] if unit is grenadier else [],
        is_within_engagement_range=lambda _left, _right: False,
        get_distance_between_units=lambda _left, _right: 6.0,
        can_model_see_model=lambda _source, _target: True,
    )
    decision_queue = DecisionQueue()
    game = SimpleNamespace(
        is_authoritative=True,
        decision_queue=decision_queue,
        request_decision=decision_queue.add,
        get_current_player=lambda: player,
        map=game_map,
        players=[player, enemy_player],
        turn=1,
    )
    manager = _build_headless_core_manager(
        stratagem=stratagem,
        player=player,
        game=game,
        phase_name="Shooting phase",
    )

    grenade_item = next(item for item in manager.get_phase_stratagem_items() if item["name"] == "GRENADE")
    assert grenade_item["available"] is True
    assert grenade_item["is_reaction"] is False
    assert grenade_item["context"]["candidates"] == [grenadier]
    assert grenade_item["context"]["enemy_candidates"] == [enemy_a, enemy_b]

    assert manager.queue_headless_tool_action_decision(reactions_only=False) is True
    request = next(iter(game.decision_queue.list() or []))
    payloads = _tool_payloads(request)
    assert [payload["tool_name"] for payload in payloads] == ["GRENADE", "GRENADE"]
    assert [
        payload["resolved_kwargs"]["enemy_unit"]["__entity_ref__"]["id"]
        for payload in payloads
    ] == [enemy_a.id, enemy_b.id]
    assert all(
        payload["resolved_kwargs"]["target_unit"]["__entity_ref__"]["id"] == grenadier.id
        for payload in payloads
    )


@pytest.mark.parametrize(
    "name,stratagem_id,phase,turn,cp_cost,active_player_is_self,event",
    [
        (
            "COUNTER-OFFENSIVE",
            "000008335003",
            "Fight phase",
            "Either player's turn",
            2,
            False,
            "fight_sequence_complete",
        ),
        (
            "EPIC CHALLENGE",
            "000008335004",
            "Fight phase",
            "Either player's turn",
            1,
            True,
            "fight_unit_selected",
        ),
        (
            "GO TO GROUND",
            "000008335010",
            "Shooting phase",
            "Opponent's turn",
            1,
            False,
            "shooting_targets_selected",
        ),
        (
            "HEROIC INTERVENTION",
            "000008335012",
            "Charge phase",
            "Opponent's turn",
            1,
            False,
            "heroic_intervention",
        ),
        (
            "INSANE BRAVERY",
            "000008335005",
            "Command phase",
            "Your turn",
            1,
            True,
            "battle_shock_test_started",
        ),
        (
            "RAPID INGRESS",
            "000008335008",
            "Movement phase",
            "Opponent's turn",
            1,
            False,
            "phase_end",
        ),
        (
            "SMOKESCREEN",
            "000008335011",
            "Shooting phase",
            "Opponent's turn",
            1,
            False,
            "shooting_targets_selected",
        ),
    ],
)
def test_headless_core_reaction_stratagems_emit_tool_actions_with_cp_and_trigger(
    name: str,
    stratagem_id: str,
    phase: str,
    turn: str,
    cp_cost: int,
    active_player_is_self: bool,
    event: str,
) -> None:
    stratagem = _core_stratagem(
        name,
        stratagem_id=stratagem_id,
        phase=phase,
        turn=turn,
        cp_cost=cp_cost,
    )
    player = SimpleNamespace(id=f"player:{name.lower().replace(' ', '-')}", command_points=cp_cost)
    enemy_player = SimpleNamespace(id="player:enemy")
    army = SimpleNamespace(id="army:core", units=[], player=player)
    enemy_army = SimpleNamespace(id="army:enemy", units=[], player=enemy_player)
    player.get_army = lambda: army
    enemy_player.get_army = lambda: enemy_army
    player.has_control = lambda: False
    player._has_attached_decision_controller = lambda: True
    player.active_secondaries = []

    target_unit = SimpleNamespace(
        id=f"unit:{name.lower().replace(' ', '-')}",
        name=f"{name} Target",
        deployed=True,
        is_infantry=True,
        is_alive=lambda: True,
        is_embarked=False,
        embarked_in=None,
        special_rules={},
    )
    target_unit.get_parent_army = lambda: army
    target_unit.get_attached_unit_root = lambda: target_unit
    target_unit.is_battle_shocked = lambda: name == "INSANE BRAVERY"
    target_unit.has_keyword = lambda keyword: str(keyword or "").strip().upper() in {"SMOKE", "INFANTRY"}
    challenge_model = SimpleNamespace(
        id=f"model:{name.lower().replace(' ', '-')}",
        name=f"{name} Model",
        parent_unit=target_unit,
        is_character=True,
    )
    if name == "EPIC CHALLENGE":
        target_unit.models = [challenge_model]

    enemy_unit = SimpleNamespace(
        id=f"unit:enemy-{name.lower().replace(' ', '-')}",
        name=f"{name} Enemy",
        is_alive=lambda: True,
    )
    enemy_unit.get_parent_army = lambda: enemy_army
    army.units = [target_unit]
    enemy_army.units = [enemy_unit]

    game_map = SimpleNamespace(
        units=[target_unit, enemy_unit],
        get_enemy_units=lambda unit: [enemy_unit] if unit is target_unit else [target_unit],
        is_within_engagement_range=lambda _left, _right: True,
        get_distance_between_units=lambda _left, _right: 3.0,
    )
    decision_queue = DecisionQueue()
    game = SimpleNamespace(
        is_authoritative=True,
        decision_queue=decision_queue,
        request_decision=decision_queue.add,
        get_current_player=lambda: player if active_player_is_self else enemy_player,
        map=game_map,
        players=[player, enemy_player],
        turn=1,
    )
    manager = _build_headless_core_manager(
        stratagem=stratagem,
        player=player,
        game=game,
        phase_name=phase,
    )

    context = {
        "event": event,
        "phase_name": phase,
        "stratagem": stratagem.name,
        "cp_cost": stratagem.cp_cost,
    }
    if name == "EPIC CHALLENGE":
        context.update(
            {
                "unit": target_unit,
                "target_unit": target_unit,
                "eligible_models": [challenge_model],
                "model_candidates": [challenge_model],
            }
        )
    elif name == "INSANE BRAVERY":
        context.update({"unit": target_unit, "target_unit": target_unit})
    else:
        context["candidates"] = [target_unit]
    if name in {"GO TO GROUND", "SMOKESCREEN"}:
        context["attacking_unit"] = enemy_unit
    if name == "HEROIC INTERVENTION":
        context["enemy_unit"] = enemy_unit
    if name == "RAPID INGRESS":
        context["phase"] = "Movement phase"
    manager._pending_reactions = [context]

    item = next(
        item
        for item in manager.get_phase_stratagem_items()
        if item["name"] == name and item["is_reaction"] is True
    )
    assert item["available"] is True

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True
    request = next(iter(game.decision_queue.list() or []))
    payloads = _tool_payloads(request)
    assert [payload["tool_name"] for payload in payloads] == [name]
    assert payloads[0]["resolved_kwargs"]["target_unit"]["__entity_ref__"]["id"] == target_unit.id
    if name == "HEROIC INTERVENTION":
        assert payloads[0]["resolved_kwargs"]["charge_path_direct_only"] is True


def test_tool_action_sort_key_accepts_string_helper_map_keys() -> None:
    assert StratagemManager._tool_action_sort_key("unit:one") == "unit:one"
    assert StratagemManager._tool_action_sort_key({"id": "unit:two"}) == "unit:two"


def test_queue_headless_tool_action_decision_skips_under_specified_base_probe_for_targeted_stratagem() -> None:
    target_unit = SimpleNamespace(id="unit:target", name="Target Unit")
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="DENIZENS OF THE WARP",
        descriptor_target="target_unit",
        context={
            "phase_name": "Movement phase",
            "candidates": [target_unit],
        },
        can_use=lambda *_args, **_kwargs: True,
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    assert len(payloads) == 2
    assert payloads[0]["resolved_kwargs"]["target_unit"]["__entity_ref__"]["id"] == target_unit.id


def test_queue_headless_tool_action_decision_infers_blitzing_firepower_unit_and_phase_from_descriptor() -> None:
    valid_unit = SimpleNamespace(id="unit:valid", name="Dire Avengers")
    invalid_unit = SimpleNamespace(id="unit:invalid", name="Rangers")
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="BLITZING FIREPOWER",
        stratagem_id="000009900005",
        descriptor_target="asuryani_unit_not_yet_shot",
        context={"phase_name": ""},
        can_use=lambda _name, **kwargs: (
            kwargs.get("unit") is valid_unit
            and kwargs.get("target_unit") is valid_unit
            and kwargs.get("phase_name") == "Shooting phase"
        ),
    )
    manager._current_phase_name = ""
    manager._tool_action_friendly_units = lambda: [invalid_unit, valid_unit]
    game.phase = SimpleNamespace(name="SHOOTING_PHASE")

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    assert len(payloads) == 2
    resolved = payloads[0]["resolved_kwargs"]
    assert resolved["phase_name"] == "Shooting phase"
    assert resolved["unit"]["__entity_ref__"]["id"] == valid_unit.id
    assert resolved["target_unit"]["__entity_ref__"]["id"] == valid_unit.id


def test_queue_headless_tool_action_decision_infers_enemy_target_and_phase_from_descriptor() -> None:
    enemy_unit = SimpleNamespace(id="unit:enemy", name="Chaos Marines")
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="GENERIC ENEMY TEST",
        descriptor_target="enemy_unit",
        context={"phase_name": ""},
        can_use=lambda _name, **kwargs: (
            kwargs.get("enemy_unit") is enemy_unit
            and kwargs.get("target_enemy_unit") is enemy_unit
            and kwargs.get("phase_name") == "Fight phase"
        ),
    )
    manager._current_phase_name = ""
    manager._tool_action_enemy_units = lambda: [enemy_unit]
    game.phase = SimpleNamespace(name="FIGHT_PHASE")

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    assert len(payloads) == 2
    resolved = payloads[0]["resolved_kwargs"]
    assert resolved["phase_name"] == "Fight phase"
    assert resolved["enemy_unit"]["__entity_ref__"]["id"] == enemy_unit.id
    assert resolved["target_enemy_unit"]["__entity_ref__"]["id"] == enemy_unit.id


def test_queue_headless_tool_action_decision_builds_model_target_from_reaction_context() -> None:
    unit = SimpleNamespace(id="unit:source", name="Champion Unit")
    model = SimpleNamespace(id="model:hero", name="Hero", parent_unit=unit)
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="EPIC CHALLENGE",
        descriptor_target="target_model",
        context={
            "phase_name": "Fight phase",
            "unit": unit,
            "eligible_models": [model],
        },
        can_use=lambda _name, **kwargs: kwargs.get("unit") is unit and kwargs.get("model") is model,
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    assert len(payloads) == 2
    resolved = payloads[0]["resolved_kwargs"]
    assert resolved["target_unit"]["__entity_ref__"]["id"] == unit.id
    assert resolved["target_model"]["__entity_ref__"]["id"] == model.id


def test_queue_headless_tool_action_decision_does_not_require_model_for_lost_models_descriptor() -> None:
    unit = SimpleNamespace(id="unit:warriors", name="Necron Warriors")
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="PROTOCOL OF THE UNDYING LEGIONS",
        stratagem_id="000008371003",
        descriptor_target="necrons_unit_that_lost_models_to_attacker_with_reanimation_protocols",
        context={
            "phase_name": "Shooting phase",
            "candidates": [unit],
        },
        can_use=lambda _name, **kwargs: kwargs.get("unit") is unit and kwargs.get("target_unit") is unit,
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    assert len(payloads) == 2
    resolved = payloads[0]["resolved_kwargs"]
    assert resolved["unit"]["__entity_ref__"]["id"] == unit.id
    assert resolved["target_unit"]["__entity_ref__"]["id"] == unit.id
    assert "model" not in resolved
    assert "target_model" not in resolved


def test_tool_action_firewall_filters_emitted_spec_that_fails_can_use() -> None:
    valid_unit = SimpleNamespace(id="unit:valid", name="Valid Unit")
    invalid_unit = SimpleNamespace(id="unit:invalid", name="Invalid Unit")
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="GENERIC FIREWALL TEST",
        descriptor_target="target_unit",
        context={"phase_name": "Shooting phase"},
        can_use=lambda _name, **kwargs: kwargs.get("unit") is valid_unit,
    )
    game.entity_registry = SimpleNamespace(
        get=lambda entity_id, kind=None: (
            valid_unit
            if kind == "unit" and entity_id == valid_unit.id
            else invalid_unit
            if kind == "unit" and entity_id == invalid_unit.id
            else None
        )
    )

    def _spec_for(unit):
        return {
            "label": unit.name,
            "payload": {
                "tool_family": "stratagem",
                "tool_type": "stratagem",
                "tool_name": "GENERIC FIREWALL TEST",
                "resolved_kwargs": manager._serialize_tool_action_value(
                    {
                        "phase_name": "Shooting phase",
                        "unit": unit,
                        "target_unit": unit,
                    }
                ),
            },
        }

    manager._build_tool_action_specs_for_item = lambda _item: [_spec_for(invalid_unit), _spec_for(valid_unit)]

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    tool_payloads = [payload for payload in payloads if str(payload.get("tool_name", "") or "")]
    assert len(tool_payloads) == 1
    assert tool_payloads[0]["resolved_kwargs"]["unit"]["__entity_ref__"]["id"] == valid_unit.id
    assert manager.get_tool_action_probe_diagnostics() == []


def test_tool_action_firewall_suppresses_speculative_can_use_error_logs(caplog) -> None:
    probe_logger = logging.getLogger("tests.tool_action_probe")
    valid_unit = SimpleNamespace(id="unit:valid", name="Valid Unit")
    invalid_unit = SimpleNamespace(id="unit:invalid", name="Invalid Unit")

    def _noisy_can_use(_name, **kwargs):
        if kwargs.get("unit") is invalid_unit:
            probe_logger.error("ERROR: speculative false candidate")
            return False
        return True

    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="GENERIC QUIET FIREWALL TEST",
        descriptor_target="target_unit",
        context={"phase_name": "Shooting phase"},
        can_use=_noisy_can_use,
    )
    game.entity_registry = SimpleNamespace(
        get=lambda entity_id, kind=None: (
            valid_unit
            if kind == "unit" and entity_id == valid_unit.id
            else invalid_unit
            if kind == "unit" and entity_id == invalid_unit.id
            else None
        )
    )

    def _spec_for(unit):
        return {
            "label": unit.name,
            "payload": {
                "tool_family": "stratagem",
                "tool_type": "stratagem",
                "tool_name": "GENERIC QUIET FIREWALL TEST",
                "resolved_kwargs": manager._serialize_tool_action_value(
                    {
                        "phase_name": "Shooting phase",
                        "unit": unit,
                        "target_unit": unit,
                    }
                ),
            },
        }

    manager._build_tool_action_specs_for_item = lambda _item: [_spec_for(invalid_unit), _spec_for(valid_unit)]

    with caplog.at_level(logging.ERROR):
        assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    assert "speculative false candidate" not in caplog.text
    assert manager.get_tool_action_probe_diagnostics() == []


def test_stratagem_availability_probe_suppresses_false_can_use_error_logs(caplog) -> None:
    probe_logger = logging.getLogger("tests.stratagem_availability_probe")
    manager = StratagemManager.__new__(StratagemManager)

    def _noisy_can_use(_name, **_kwargs):
        probe_logger.error("ERROR: noisy availability miss")
        return False

    manager.can_use = _noisy_can_use

    with caplog.at_level(logging.ERROR):
        assert manager._quiet_can_use_probe("NOISY TEST", {"phase_name": "Shooting phase"}) is False

    assert "noisy availability miss" not in caplog.text


def test_tool_action_provider_skips_silently_when_all_candidates_are_filtered() -> None:
    invalid_a = SimpleNamespace(id="unit:invalid-a", name="Invalid A")
    invalid_b = SimpleNamespace(id="unit:invalid-b", name="Invalid B")
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="GENERIC ALL FILTERED TEST",
        descriptor_target="target_unit",
        context={"phase_name": "Shooting phase", "candidates": [invalid_a, invalid_b]},
        can_use=lambda *_args, **_kwargs: False,
    )
    game.entity_registry = SimpleNamespace(
        get=lambda entity_id, kind=None: (
            invalid_a
            if kind == "unit" and entity_id == invalid_a.id
            else invalid_b
            if kind == "unit" and entity_id == invalid_b.id
            else None
        )
    )

    def _spec_for(unit):
        return {
            "label": unit.name,
            "payload": {
                "tool_family": "stratagem",
                "tool_type": "stratagem",
                "tool_name": "GENERIC ALL FILTERED TEST",
                "resolved_kwargs": manager._serialize_tool_action_value(
                    {
                        "phase_name": "Shooting phase",
                        "unit": unit,
                        "target_unit": unit,
                    }
                ),
            },
        }

    manager._build_tool_action_specs_for_item = lambda _item: [_spec_for(invalid_a), _spec_for(invalid_b)]

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is False
    assert list(game.decision_queue.list() or []) == []
    assert manager.get_tool_action_probe_diagnostics() == []


def test_tool_action_firewall_filters_unresolvable_emitted_entity_ref() -> None:
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="GENERIC MALFORMED TEST",
        descriptor_target="target_unit",
        context={"phase_name": "Shooting phase"},
        can_use=lambda *_args, **_kwargs: True,
    )
    game.entity_registry = SimpleNamespace(get=lambda _entity_id, kind=None: None)
    manager._build_tool_action_specs_for_item = lambda _item: [
        {
            "label": "Missing Unit",
            "payload": {
                "tool_family": "stratagem",
                "tool_type": "stratagem",
                "tool_name": "GENERIC MALFORMED TEST",
                "resolved_kwargs": {
                    "phase_name": "Shooting phase",
                    "unit": {"__entity_ref__": {"id": "unit:missing", "kind": "unit"}},
                    "target_unit": {"__entity_ref__": {"id": "unit:missing", "kind": "unit"}},
                },
            },
        }
    ]

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is False
    assert list(game.decision_queue.list() or []) == []
    diagnostics = manager.get_tool_action_probe_diagnostics()
    assert len(diagnostics) == 1
    assert diagnostics[0]["code"] == "malformed_tool_candidate_filtered_preflight"
    assert diagnostics[0]["severity"] == "ERROR"
    assert "resolved_kwargs.unit" in diagnostics[0]["missing_keys"]


def test_generic_tool_action_descriptor_filters_invalid_unit_keywords_before_emit() -> None:
    aspect = SimpleNamespace(
        id="unit:aspect",
        name="Dire Avengers",
        keywords=["ASPECT WARRIORS", "INFANTRY"],
        faction_keywords=["AELDARI"],
        round_state=SimpleNamespace(shot_this_round=False),
    )
    guardians = SimpleNamespace(
        id="unit:guardians",
        name="Guardian Defenders",
        keywords=["GUARDIANS", "INFANTRY"],
        faction_keywords=["AELDARI"],
        round_state=SimpleNamespace(shot_this_round=False),
    )
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="GENERIC ASPECT TEST",
        descriptor_target="aspect_warriors_unit_not_yet_shot",
        context={
            "phase_name": "Shooting phase",
            "candidates": [guardians, aspect],
        },
        can_use=lambda *_args, **_kwargs: True,
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    tool_payloads = [payload for payload in payloads if str(payload.get("tool_name", "") or "")]
    assert len(tool_payloads) == 1
    assert tool_payloads[0]["resolved_kwargs"]["unit"]["__entity_ref__"]["id"] == aspect.id
    assert manager.get_tool_action_probe_diagnostics() == []


def test_generic_tool_action_descriptor_filters_speed_freeks_targets_before_emit() -> None:
    warbikers = SimpleNamespace(
        id="unit:warbikers",
        name="Warbikers",
        keywords=["MOUNTED", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
        round_state=SimpleNamespace(shot_this_round=False, shot_this_phase=False),
    )
    boyz = SimpleNamespace(
        id="unit:boyz",
        name="Boyz",
        keywords=["INFANTRY"],
        faction_keywords=["ORKS"],
        round_state=SimpleNamespace(shot_this_round=False, shot_this_phase=False),
    )
    selected_warbikers = SimpleNamespace(
        id="unit:selected_warbikers",
        name="Selected Warbikers",
        keywords=["MOUNTED", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
        round_state=SimpleNamespace(shot_this_round=True, shot_this_phase=True),
    )
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="BLITZA FIRE",
        descriptor_target="speed_freeks_unit_not_yet_shot",
        context={
            "phase_name": "Shooting phase",
            "candidates": [boyz, selected_warbikers, warbikers],
        },
        can_use=lambda *_args, **_kwargs: True,
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    tool_payloads = [payload for payload in payloads if str(payload.get("tool_name", "") or "")]
    assert len(tool_payloads) == 1
    assert tool_payloads[0]["resolved_kwargs"]["unit"]["__entity_ref__"]["id"] == warbikers.id
    assert manager.get_tool_action_probe_diagnostics() == []


def test_generic_tool_action_descriptor_filters_grey_knights_heal_targets_before_emit() -> None:
    wounded_dreadknight = SimpleNamespace(
        id="unit:wounded_dreadknight",
        name="Grand Master in Nemesis Dreadknight",
        keywords=["VEHICLE", "PSYKER", "CHARACTER"],
        faction_keywords=["GREY KNIGHTS"],
        models=[SimpleNamespace(wounds=9, _base_wounds=12, is_alive=True)],
        round_state=SimpleNamespace(),
    )
    unwounded_dreadknight = SimpleNamespace(
        id="unit:unwounded_dreadknight",
        name="Nemesis Dreadknight",
        keywords=["VEHICLE", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
        models=[SimpleNamespace(wounds=12, _base_wounds=12, is_alive=True)],
        round_state=SimpleNamespace(),
    )
    terminators = SimpleNamespace(
        id="unit:terminators",
        name="Brotherhood Terminator Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
        models=[SimpleNamespace(wounds=2, _base_wounds=3, is_alive=True)],
        round_state=SimpleNamespace(),
    )
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="ARMOURED AEGIS",
        descriptor_target="grey_knights_psyker_vehicle_unit",
        context={
            "phase_name": "Command phase",
            "candidates": [terminators, unwounded_dreadknight, wounded_dreadknight],
        },
        can_use=lambda *_args, **_kwargs: True,
        effect_params={"heal_amount": 3},
    )
    _stratagem.tool_descriptor.effect = "heal_model_in_unit"

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    tool_payloads = [payload for payload in payloads if str(payload.get("tool_name", "") or "")]
    assert len(tool_payloads) == 1
    assert tool_payloads[0]["resolved_kwargs"]["unit"]["__entity_ref__"]["id"] == wounded_dreadknight.id
    assert manager.get_tool_action_probe_diagnostics() == []


def test_generic_tool_action_descriptor_filters_grey_knights_selection_state_before_emit() -> None:
    strike_squad = SimpleNamespace(
        id="unit:strike",
        name="Strike Squad",
        keywords=["INFANTRY"],
        faction_keywords=["GREY KNIGHTS"],
        round_state=SimpleNamespace(shot_this_round=False, shot_this_phase=False),
    )
    selected_terminators = SimpleNamespace(
        id="unit:selected_terminators",
        name="Brotherhood Terminator Squad",
        keywords=["INFANTRY"],
        faction_keywords=["GREY KNIGHTS"],
        round_state=SimpleNamespace(shot_this_round=True, shot_this_phase=True),
    )
    ork_boyz = SimpleNamespace(
        id="unit:ork_boyz",
        name="Boyz",
        keywords=["INFANTRY"],
        faction_keywords=["ORKS"],
        round_state=SimpleNamespace(shot_this_round=False, shot_this_phase=False),
    )
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="ABOMINUS-CLASS TARGETS",
        descriptor_target="grey_knights_unit_not_selected_to_shoot_or_fight",
        context={
            "phase_name": "Shooting phase",
            "candidates": [selected_terminators, ork_boyz, strike_squad],
        },
        can_use=lambda *_args, **_kwargs: True,
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    tool_payloads = [payload for payload in payloads if str(payload.get("tool_name", "") or "")]
    assert len(tool_payloads) == 1
    assert tool_payloads[0]["resolved_kwargs"]["unit"]["__entity_ref__"]["id"] == strike_squad.id
    assert manager.get_tool_action_probe_diagnostics() == []


def test_generic_tool_action_descriptor_enforces_structured_effect_param_filters() -> None:
    valid = SimpleNamespace(
        id="unit:valid",
        name="Infantry Squad",
        keywords=["PLATOON", "INFANTRY"],
        faction_keywords=["ASTRA MILITARUM"],
        round_state=SimpleNamespace(shot_this_round=False, shot_this_phase=False),
    )
    wrong_keyword = SimpleNamespace(
        id="unit:wrong",
        name="Leman Russ",
        keywords=["VEHICLE"],
        faction_keywords=["ASTRA MILITARUM"],
        round_state=SimpleNamespace(shot_this_round=False, shot_this_phase=False),
    )
    excluded = SimpleNamespace(
        id="unit:character",
        name="Command Squad",
        keywords=["PLATOON", "CHARACTER"],
        faction_keywords=["ASTRA MILITARUM"],
        round_state=SimpleNamespace(shot_this_round=False, shot_this_phase=False),
    )
    already_shot = SimpleNamespace(
        id="unit:shot",
        name="Kasrkin",
        keywords=["PLATOON", "INFANTRY"],
        faction_keywords=["ASTRA MILITARUM"],
        round_state=SimpleNamespace(shot_this_round=True, shot_this_phase=True),
    )
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="GENERIC STRUCTURED FILTER TEST",
        descriptor_target="target_unit",
        context={
            "phase_name": "Shooting phase",
            "candidates": [wrong_keyword, excluded, already_shot, valid],
        },
        effect_params={
            "required_keywords_any": ["PLATOON"],
            "excluded_keywords_any": ["CHARACTER"],
            "requires_not_selected_to_shoot": True,
        },
        can_use=lambda *_args, **_kwargs: True,
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    tool_payloads = [payload for payload in payloads if str(payload.get("tool_name", "") or "")]
    assert len(tool_payloads) == 1
    assert tool_payloads[0]["resolved_kwargs"]["unit"]["__entity_ref__"]["id"] == valid.id
    assert manager.get_tool_action_probe_diagnostics() == []


def test_generic_tool_action_descriptor_enforces_target_aliases_on_enemy_units() -> None:
    shooter = SimpleNamespace(
        id="unit:shooter",
        name="Devastator Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    infantry_enemy = SimpleNamespace(
        id="enemy:infantry",
        name="Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    aircraft_enemy = SimpleNamespace(
        id="enemy:aircraft",
        name="Harpy",
        keywords=["MONSTER", "AIRCRAFT"],
        faction_keywords=["TYRANIDS"],
    )
    monster_enemy = SimpleNamespace(
        id="enemy:monster",
        name="Carnifex",
        keywords=["MONSTER"],
        faction_keywords=["TYRANIDS"],
    )
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="GENERIC TARGET ALIAS FILTER TEST",
        descriptor_target="friendly_unit_and_target_enemy_unit",
        context={
            "phase_name": "Shooting phase",
            "unit": shooter,
            "target_unit": shooter,
            "enemy_candidates": [infantry_enemy, aircraft_enemy, monster_enemy],
        },
        effect_params={
            "target_keywords_any": ["MONSTER"],
            "exclude_target_keywords_any": ["AIRCRAFT"],
        },
        can_use=lambda *_args, **_kwargs: True,
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True

    request = next(iter(game.decision_queue.list() or []))
    payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    tool_payloads = [payload for payload in payloads if str(payload.get("tool_name", "") or "")]
    assert len(tool_payloads) == 1
    assert tool_payloads[0]["resolved_kwargs"]["enemy_unit"]["__entity_ref__"]["id"] == monster_enemy.id
    assert manager.get_tool_action_probe_diagnostics() == []


def test_generic_tool_action_skips_paired_unit_targets_without_support_context() -> None:
    regiment = SimpleNamespace(
        id="unit:regiment",
        name="Infantry Squad",
        keywords=["REGIMENT", "INFANTRY"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="GENERIC PAIRED UNIT TEST",
        descriptor_target="regiment_unit_and_squadron_unit_within_6",
        context={
            "phase_name": "Command phase",
            "candidates": [regiment],
        },
        can_use=lambda *_args, **_kwargs: True,
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is False
    assert list(game.decision_queue.list() or []) == []
    assert manager.get_tool_action_probe_diagnostics() == []


def test_tool_action_provider_skips_silently_when_context_has_no_candidate_source() -> None:
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="GENERIC MISSING CONTEXT TEST",
        descriptor_target="target_unit",
        context={"phase_name": "Shooting phase"},
        can_use=lambda *_args, **_kwargs: True,
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is False
    assert list(game.decision_queue.list() or []) == []
    assert manager.get_tool_action_probe_diagnostics() == []


def test_manager_can_use_denizens_requires_selected_unit_context() -> None:
    reserve_unit = SimpleNamespace(id="unit:reserve", name="Reserve Unit")
    reserve_unit.get_attached_unit_root = lambda: reserve_unit
    player = SimpleNamespace(id="player:daemon")
    manager = StratagemManager.__new__(StratagemManager)
    manager.player = player
    manager.game = SimpleNamespace(get_current_player=lambda: player, turn=2)
    manager._current_phase_name = "Movement phase"
    manager._pending_reactions = []
    manager.get_by_name = lambda _name: SimpleNamespace(
        name="DENIZENS OF THE WARP",
        can_use=lambda *_args, **_kwargs: True,
    )
    manager._daemon_incursion_reserve_deep_strike_candidates = lambda: [reserve_unit]

    assert manager.can_use("DENIZENS OF THE WARP", phase_name="Movement phase") is False
    assert manager.can_use("DENIZENS OF THE WARP", phase_name="Movement phase", unit=reserve_unit) is True


def test_manager_can_use_epic_challenge_requires_explicit_model_when_multiple_are_eligible() -> None:
    unit = SimpleNamespace(id="unit:source", name="Champion Unit", models=[])
    model_a = SimpleNamespace(id="model:a", name="Hero A", parent_unit=unit, is_character=True)
    model_b = SimpleNamespace(id="model:b", name="Hero B", parent_unit=unit, is_character=True)
    unit.models = [model_a, model_b]
    manager = StratagemManager.__new__(StratagemManager)
    manager.player = SimpleNamespace(id="player:champion")
    manager.game = SimpleNamespace()
    manager._current_phase_name = "Fight phase"
    manager.get_by_name = lambda _name: SimpleNamespace(
        name="EPIC CHALLENGE",
        can_use=lambda *_args, **_kwargs: True,
    )
    manager._pending_reactions = [
        {
            "stratagem": "EPIC CHALLENGE",
            "phase_name": "Fight phase",
            "unit": unit,
            "target_unit": unit,
            "eligible_models": [model_a, model_b],
            "model_candidates": [model_a, model_b],
        }
    ]

    assert manager.can_use("EPIC CHALLENGE", phase_name="Fight phase") is False
    assert manager.can_use("EPIC CHALLENGE", phase_name="Fight phase", unit=unit, model=model_a) is True


def test_manager_can_use_grenade_requires_unit_and_enemy_context() -> None:
    grenadier = SimpleNamespace(id="unit:grenadier", name="Grenadier")
    enemy = SimpleNamespace(id="unit:enemy", name="Enemy")
    manager = StratagemManager.__new__(StratagemManager)
    manager.player = SimpleNamespace(id="player:grenade")
    manager.game = SimpleNamespace()
    manager._current_phase_name = "Shooting phase"
    manager._pending_reactions = []
    manager.get_by_name = lambda _name: SimpleNamespace(
        name="GRENADE",
        can_use=lambda *_args, **_kwargs: True,
    )
    manager._grenade_phase_action_context = lambda: {
        "candidates": [grenadier],
        "enemy_candidates": [enemy],
        "enemy_candidates_by_unit": {grenadier.id: [enemy]},
    }

    assert manager.can_use("GRENADE", phase_name="Shooting phase") is False
    assert manager.can_use("GRENADE", phase_name="Shooting phase", unit=grenadier) is False
    assert manager.can_use("GRENADE", phase_name="Shooting phase", unit=grenadier, enemy_unit=enemy) is True


def test_grenade_candidate_scan_rejects_out_of_range_before_visibility() -> None:
    grenadier = SimpleNamespace(id="unit:grenadier", name="Grenadier")
    enemy = SimpleNamespace(id="unit:enemy", name="Enemy", is_alive=lambda: True)
    manager = StratagemManager.__new__(StratagemManager)
    manager.game = SimpleNamespace(map=SimpleNamespace(get_enemy_units=lambda _unit: [enemy]))
    manager._grenade_unit_is_eligible = lambda _unit: True
    manager._grenade_extended_range_profile = lambda _unit: (False, 18.0, "")
    manager._grenade_enemy_within_friendly_engagement = lambda _enemy: False
    manager._grenade_enemy_within_range = lambda _unit, _enemy, *, max_range: False

    def _unexpected_visibility_check(_unit, _enemy):
        raise AssertionError("visibility should not be checked for out-of-range grenade targets")

    manager._grenade_enemy_visible_from_unit = _unexpected_visibility_check

    assert manager._grenade_enemy_candidates_for_unit(grenadier) == []


def test_manager_can_use_tank_shock_requires_vehicle_and_enemy_context() -> None:
    charger = SimpleNamespace(id="unit:charger", name="Tank", is_vehicle=True)
    enemy = SimpleNamespace(id="unit:enemy", name="Enemy", is_alive=lambda: True)
    player = SimpleNamespace(id="player:tank")
    manager = StratagemManager.__new__(StratagemManager)
    manager.player = player
    manager.game = SimpleNamespace(
        get_current_player=lambda: player,
        map=SimpleNamespace(is_within_engagement_range=lambda left, right: left is charger and right is enemy),
    )
    manager._current_phase_name = "Charge phase"
    manager._pending_reactions = []
    manager.get_by_name = lambda _name: SimpleNamespace(
        name="TANK SHOCK",
        can_use=lambda *_args, **_kwargs: True,
    )

    assert manager.can_use("TANK SHOCK", phase_name="Charge phase") is False
    assert manager.can_use("TANK SHOCK", phase_name="Charge phase", unit=charger) is False
    assert manager.can_use(
        "TANK SHOCK",
        phase_name="Charge phase",
        unit=charger,
        enemy_unit=enemy,
        eligible_enemy_units=[enemy],
    ) is True


def test_manager_can_use_warp_surge_requires_selected_unit_context() -> None:
    daemon = SimpleNamespace(id="unit:daemon", name="Daemon")
    daemon.get_attached_unit_root = lambda: daemon
    player = SimpleNamespace(id="player:warp")
    manager = StratagemManager.__new__(StratagemManager)
    manager.player = player
    manager.game = SimpleNamespace(get_current_player=lambda: player)
    manager._current_phase_name = "Charge phase"
    manager._pending_reactions = []
    manager.get_by_name = lambda _name: SimpleNamespace(
        name="WARP SURGE",
        can_use=lambda *_args, **_kwargs: True,
    )
    manager._is_legiones_daemonica_unit = lambda unit: unit is daemon
    manager._unit_within_shadow_of_chaos = lambda unit: unit is daemon
    manager._daemon_incursion_battlefield_unit_candidates = lambda: [daemon]

    assert manager.can_use("WARP SURGE", phase_name="Charge phase") is False
    assert manager.can_use("WARP SURGE", phase_name="Charge phase", unit=daemon) is True


def test_apply_select_tool_action_uses_stratagem_and_clears_skip_marker() -> None:
    manager, player, _game, target_unit = _build_remote_tool_manager()
    calls = []
    manager.use = lambda name, **kwargs: calls.append((name, dict(kwargs))) or True

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True
    request = next(iter(player.stratagems.game.decision_queue.list() or []))
    signature = str(request.context["tool_action_signature"])
    manager._skipped_tool_action_signatures.add(signature)

    use_option = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("tool_name", "") or "") == "GO TO GROUND"
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=use_option.option_id,
        payload={},
    )
    entity_registry = SimpleNamespace(
        get=lambda entity_id, kind=None: (
            player
            if kind == "player" and entity_id == player.id
            else target_unit
            if kind == "unit" and entity_id == target_unit.id
            else None
        )
    )
    game = SimpleNamespace(players=[player], entity_registry=entity_registry)

    assert _validate_select_tool_action(game, request, result) == ()
    assert _apply_select_tool_action(game, request, result) == {
        "tool_family": "stratagem",
        "tool_name": "GO TO GROUND",
    }
    assert signature not in manager._skipped_tool_action_signatures
    assert calls == [("GO TO GROUND", {"phase_name": "Shooting phase", "target_unit": target_unit})]


def test_validate_select_tool_action_suppresses_false_can_use_error_logs(caplog) -> None:
    probe_logger = logging.getLogger("tests.select_tool_action_validation")
    manager, player, _game, target_unit = _build_remote_tool_manager()

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True
    request = next(iter(player.stratagems.game.decision_queue.list() or []))
    use_option = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("tool_name", "") or "") == "GO TO GROUND"
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=use_option.option_id,
        payload={},
    )
    entity_registry = SimpleNamespace(
        get=lambda entity_id, kind=None: (
            player
            if kind == "player" and entity_id == player.id
            else target_unit
            if kind == "unit" and entity_id == target_unit.id
            else None
        )
    )
    game = SimpleNamespace(players=[player], entity_registry=entity_registry)

    def _noisy_can_use(_name, **_kwargs):
        probe_logger.error("ERROR: rejected validation probe")
        return False

    manager.can_use = _noisy_can_use

    with caplog.at_level(logging.ERROR):
        errors = _validate_select_tool_action(game, request, result)

    assert errors == ("GO TO GROUND is no longer a valid tool action.",)
    assert "rejected validation probe" not in caplog.text


def test_validate_select_tool_action_rejects_stale_descriptor_candidate() -> None:
    strike_squad = SimpleNamespace(
        id="unit:strike",
        name="Strike Squad",
        keywords=["INFANTRY"],
        faction_keywords=["GREY KNIGHTS"],
        round_state=SimpleNamespace(shot_this_round=False, shot_this_phase=False),
    )
    manager, player, _game, _stratagem = _build_generic_tool_manager(
        stratagem_name="ABOMINUS-CLASS TARGETS",
        descriptor_target="grey_knights_unit_not_selected_to_shoot_or_fight",
        context={
            "phase_name": "Shooting phase",
            "candidates": [strike_squad],
        },
        can_use=lambda *_args, **_kwargs: True,
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True
    request = next(iter(manager.game.decision_queue.list() or []))
    use_option = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("tool_name", "") or "") == "ABOMINUS-CLASS TARGETS"
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=use_option.option_id,
        payload={},
    )
    opponent = SimpleNamespace(id="player:opponent")
    manager.game.get_current_player = lambda: opponent
    entity_registry = SimpleNamespace(
        get=lambda entity_id, kind=None: (
            player
            if kind == "player" and entity_id == player.id
            else strike_squad
            if kind == "unit" and entity_id == strike_squad.id
            else None
        )
    )
    game = SimpleNamespace(players=[player, opponent], entity_registry=entity_registry)

    errors = _validate_select_tool_action(game, request, result)

    assert errors == ("ABOMINUS-CLASS TARGETS is no longer a valid tool action.",)


def test_validate_select_tool_action_skip_is_side_effect_free_until_apply() -> None:
    manager, player, _game, _target_unit = _build_remote_tool_manager()

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is True
    request = next(iter(player.stratagems.game.decision_queue.list() or []))
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
    entity_registry = SimpleNamespace(
        get=lambda entity_id, kind=None: player if kind == "player" and entity_id == player.id else None
    )
    game = SimpleNamespace(players=[player], entity_registry=entity_registry)
    signature = str(request.context["tool_action_signature"])

    assert _validate_select_tool_action(game, request, result) == ()
    assert signature not in manager._skipped_tool_action_signatures
    assert _apply_select_tool_action(game, request, result) is None
    assert signature in manager._skipped_tool_action_signatures


def test_smokescreen_uses_target_unit_for_cp_cost_modifier() -> None:
    target_unit = SimpleNamespace(
        id="unit:smoke",
        name="Smoke Unit",
        special_rules={},
        is_embarked=False,
        embarked_in=None,
        has_keyword=lambda keyword: str(keyword or "").upper() == "SMOKE",
    )
    cp_targets = []

    def _apply_cp_cost(_stratagem, *, target_unit=None):
        cp_targets.append(target_unit)
        return {"cost": 0}

    player = SimpleNamespace(
        command_points=1,
        apply_stratagem_cp_cost=_apply_cp_cost,
        spend_command_points=lambda _cost, **_kwargs: True,
    )
    stratagem = SimpleNamespace(name="SMOKESCREEN", cp_cost=1)
    manager = StratagemManager.__new__(StratagemManager)
    manager.game = SimpleNamespace()
    manager.player = player
    manager._current_phase_name = "Shooting phase"
    manager._pending_reactions = []
    manager._used_stratagems_this_phase = set()
    manager.get_by_name = lambda _name: stratagem

    assert manager.use("SMOKESCREEN", target_unit=target_unit) is True
    assert cp_targets == [target_unit]
    assert target_unit.special_rules["smokescreen_active"] is True


def test_maybe_queue_post_command_tool_decisions_prioritizes_reactions_before_phase_actions() -> None:
    calls: list[tuple[str, bool]] = []
    current_player = SimpleNamespace(
        id="player:current",
        stratagems=SimpleNamespace(
            queue_headless_tool_action_decision=lambda *, reactions_only=False: (
                calls.append(("current", bool(reactions_only))) or (not reactions_only)
            )
        ),
    )
    opponent_player = SimpleNamespace(
        id="player:opponent",
        stratagems=SimpleNamespace(
            queue_headless_tool_action_decision=lambda *, reactions_only=False: (
                calls.append(("opponent", bool(reactions_only))) or False
            )
        ),
    )
    dummy_game = SimpleNamespace(
        is_authoritative=True,
        players=[current_player, opponent_player],
        decision_queue=DecisionQueue(),
        get_current_player=lambda: current_player,
    )

    assert Game._maybe_queue_post_command_tool_decisions(dummy_game, None, SimpleNamespace(ok=True)) is True
    assert calls == [
        ("opponent", True),
        ("current", True),
        ("current", False),
    ]


def test_maybe_queue_post_command_tool_decisions_skips_setup() -> None:
    calls: list[bool] = []
    current_player = SimpleNamespace(
        id="player:current",
        stratagems=SimpleNamespace(
            queue_headless_tool_action_decision=lambda *, reactions_only=False: calls.append(bool(reactions_only))
        ),
    )
    dummy_game = SimpleNamespace(
        is_authoritative=True,
        setup_complete=False,
        players=[current_player],
        decision_queue=DecisionQueue(),
        get_current_player=lambda: current_player,
    )

    assert Game._maybe_queue_post_command_tool_decisions(dummy_game, None, SimpleNamespace(ok=True)) is False
    assert calls == []


def test_tool_action_can_use_filters_stale_once_per_phase_stratagem() -> None:
    stratagem = SimpleNamespace(
        name="PRESENTIMENT OF DREAD",
        can_use=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("stale once-per-phase tool action should be filtered before stratagem.can_use")
        ),
    )
    manager = StratagemManager.__new__(StratagemManager)
    manager.game = SimpleNamespace()
    manager.player = SimpleNamespace()
    manager._current_phase_name = "Command phase"
    manager._used_stratagems_this_phase = {"PRESENTIMENT OF DREAD"}
    manager.get_by_name = lambda _name: stratagem

    assert manager.can_use("PRESENTIMENT OF DREAD", phase_name="Command phase") is False


def test_overwatch_queue_skips_expensive_candidate_scan_without_tool_controller() -> None:
    current_player = SimpleNamespace(
        id="player:current",
        command_points=1,
        get_army=lambda: (_ for _ in ()).throw(AssertionError("candidate scan should not run")),
    )
    moving_owner = SimpleNamespace(id="player:moving")
    moving_unit = SimpleNamespace(
        special_rules={},
        get_parent_army=lambda: SimpleNamespace(player=moving_owner),
    )
    stratagem = SimpleNamespace(
        name="FIRE OVERWATCH",
        cp_cost=1,
        is_phase_allowed=lambda _phase: True,
        is_turn_allowed=lambda _is_active_turn: True,
    )
    manager = StratagemManager.__new__(StratagemManager)
    manager.game = SimpleNamespace(
        get_current_player=lambda: moving_owner,
        _headless_disable_generic_tool_decisions=True,
    )
    manager.player = current_player
    manager._current_phase_name = "Charge phase"
    manager._used_stratagems_this_phase = set()
    manager._used_this_turn = {}
    manager._pending_reactions = []
    manager.get_by_name = lambda _name: stratagem
    manager._player_can_accept_tool_action_decisions = lambda: False

    manager._maybe_queue_overwatch(moving_unit, action="charge", when="declare")

    assert manager._pending_reactions == []
