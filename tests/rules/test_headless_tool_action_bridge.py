from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.decision_handlers.stratagems import (
    _apply_select_tool_action,
    _validate_select_tool_action,
)
from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_TOOL_ACTION
from warhammer40k_ai.engine.decisions import DecisionQueue, DecisionResult
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.rules.stratagems import StratagemManager


def _build_remote_tool_manager():
    decision_queue = DecisionQueue()
    target_unit = SimpleNamespace(id="unit:target", name="Target Unit")
    game = SimpleNamespace(
        is_authoritative=True,
        decision_queue=decision_queue,
        request_decision=decision_queue.add,
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
    diagnostics = manager.get_tool_action_probe_diagnostics()
    assert len(diagnostics) == 1
    assert diagnostics[0]["code"] == "illegal_tool_candidate_filtered_preflight"
    assert diagnostics[0]["missing_keys"] == ["can_use"]


def test_tool_action_provider_records_error_when_all_candidates_are_filtered() -> None:
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
    diagnostics = manager.get_tool_action_probe_diagnostics()
    assert any(entry["code"] == "illegal_tool_candidate_filtered_preflight" for entry in diagnostics)
    provider_errors = [
        entry
        for entry in diagnostics
        if entry["code"] == "tool_action_candidates_all_filtered"
    ]
    assert len(provider_errors) == 1
    assert provider_errors[0]["severity"] == "ERROR"
    assert provider_errors[0]["missing_keys"] == ["valid_tool_action_candidate"]


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


def test_generic_tool_action_requires_support_context_for_paired_unit_targets() -> None:
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
    diagnostics = manager.get_tool_action_probe_diagnostics()
    assert diagnostics
    assert any(entry["code"] == "missing_tool_action_context" for entry in diagnostics)
    provider_errors = [
        entry
        for entry in diagnostics
        if entry["code"] == "tool_action_missing_context"
    ]
    assert len(provider_errors) == 1
    assert provider_errors[0]["severity"] == "ERROR"
    assert "support_unit" in provider_errors[0]["missing_keys"]


def test_tool_action_provider_records_error_when_context_has_no_candidate_source() -> None:
    manager, _player, game, _stratagem = _build_generic_tool_manager(
        stratagem_name="GENERIC MISSING CONTEXT TEST",
        descriptor_target="target_unit",
        context={"phase_name": "Shooting phase"},
        can_use=lambda *_args, **_kwargs: True,
    )

    assert manager.queue_headless_tool_action_decision(reactions_only=True) is False
    assert list(game.decision_queue.list() or []) == []
    diagnostics = manager.get_tool_action_probe_diagnostics()
    provider_errors = [
        entry
        for entry in diagnostics
        if entry["code"] == "tool_action_missing_context"
    ]
    assert len(provider_errors) == 1
    assert provider_errors[0]["severity"] == "ERROR"
    assert "unit" in provider_errors[0]["missing_keys"]


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
