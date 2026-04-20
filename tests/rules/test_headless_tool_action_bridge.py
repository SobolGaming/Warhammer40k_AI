from types import SimpleNamespace

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
    assert payloads[0]["tool_family"] == "stratagem"
    assert payloads[0]["resolved_kwargs"]["target_unit"]["__entity_ref__"]["id"] == target_unit.id
    assert payloads[1]["action"] == "skip"


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
