from __future__ import annotations

from types import MethodType, SimpleNamespace

from warhammer40k_ai.UI.game_ui import (
    GameView,
    _confirm_request_requires_specialized_ui,
    _mark_request_ui_prompted,
    _miracle_request_requires_specialized_ui,
    _request_lookup_context,
)
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.event.system import EventSystem


class _HookHarness:
    def __init__(self, game: object):
        self.game = game
        self._subscribed_event_system = None
        self._subscribed_game = None
        self._ui_event_hook_group = ""
        self._decision_controller = None
        self._optional_decision_hook_handler = self._optional_decision_hook

    def __getattr__(self, name: str):
        if name.startswith("_on_"):
            return lambda **_kwargs: None
        raise AttributeError(name)

    def _optional_decision_hook(self, *_args, **_kwargs):
        return False


def _subscriber_count(event_system: EventSystem) -> int:
    return sum(len(items) for items in list(event_system.subscribers.values()))


def test_subscribe_event_hooks_is_idempotent_for_same_game():
    game = SimpleNamespace(event_system=EventSystem())
    harness = _HookHarness(game)
    harness._unsubscribe_event_hooks = MethodType(GameView._unsubscribe_event_hooks, harness)

    GameView._subscribe_event_hooks(harness)
    first = _subscriber_count(game.event_system)
    assert first > 0

    GameView._subscribe_event_hooks(harness)
    second = _subscriber_count(game.event_system)
    assert second == first


def test_subscribe_event_hooks_detaches_old_game_on_swap():
    game_one = SimpleNamespace(event_system=EventSystem())
    game_two = SimpleNamespace(event_system=EventSystem())
    harness = _HookHarness(game_one)
    harness._unsubscribe_event_hooks = MethodType(GameView._unsubscribe_event_hooks, harness)

    GameView._subscribe_event_hooks(harness)
    first = _subscriber_count(game_one.event_system)
    assert first > 0

    harness.game = game_two
    GameView._subscribe_event_hooks(harness)

    assert _subscriber_count(game_one.event_system) == 0
    assert _subscriber_count(game_two.event_system) == first


def test_subscribe_event_hooks_installs_optional_decision_hook_for_local_players():
    local_player = SimpleNamespace(optional_decision_hook=None, has_control=lambda: True)
    remote_player = SimpleNamespace(optional_decision_hook=None, has_control=lambda: False)
    game = SimpleNamespace(event_system=EventSystem(), players=[local_player, remote_player])
    harness = _HookHarness(game)
    harness._unsubscribe_event_hooks = MethodType(GameView._unsubscribe_event_hooks, harness)

    GameView._subscribe_event_hooks(harness)

    assert local_player.optional_decision_hook is harness._optional_decision_hook_handler
    assert remote_player.optional_decision_hook is None

    GameView._unsubscribe_event_hooks(harness)

    assert local_player.optional_decision_hook is None
    assert remote_player.optional_decision_hook is None


def test_request_lookup_context_strips_ui_only_fields():
    ctx = {
        "ability": "shadow_in_the_warp",
        "unit_id": "u1",
        "message": "Use it now?",
        "ui_prompted": True,
    }

    assert _request_lookup_context(ctx) == {
        "ability": "shadow_in_the_warp",
        "unit_id": "u1",
    }


def test_mark_request_ui_prompted_preserves_existing_message():
    request = DecisionRequest.create(
        "decision.confirm_yes_no",
        "Confirm",
        player_id="p1",
        options=[
            DecisionOption.create("Use", payload={"choice": True}),
            DecisionOption.create("Skip", payload={"choice": False}),
        ],
        context={"ability": "shadow_in_the_warp", "message": "Existing"},
    )

    ctx = _mark_request_ui_prompted(request, message="Replacement")

    assert ctx["message"] == "Existing"
    assert ctx["ui_prompted"] is True
    assert request.context["ui_prompted"] is True


def test_confirm_request_requires_specialized_ui_for_custom_flows():
    request = DecisionRequest.create(
        "decision.confirm_yes_no",
        "Blood Surge",
        player_id="p1",
        options=[
            DecisionOption.create("Move", payload={"choice": True}),
            DecisionOption.create("Skip", payload={"choice": False}),
        ],
        context={"reactive_move_kind": "blood_surge"},
    )
    assert _confirm_request_requires_specialized_ui(request) is True

    request = DecisionRequest.create(
        "decision.confirm_yes_no",
        "Hover Mode",
        player_id="p1",
        options=[
            DecisionOption.create("Hover", payload={"choice": True}),
            DecisionOption.create("Aircraft", payload={"choice": False}),
        ],
        context={"ability": "hover_mode", "unit_id": "u1"},
    )
    assert _confirm_request_requires_specialized_ui(request) is True

    generic = DecisionRequest.create(
        "decision.confirm_yes_no",
        "Generic",
        player_id="p1",
        options=[
            DecisionOption.create("Use", payload={"choice": True}),
            DecisionOption.create("Skip", payload={"choice": False}),
        ],
        context={"ability": "generic_optional"},
    )
    assert _confirm_request_requires_specialized_ui(generic) is False


def test_on_decision_requested_skips_optional_confirm_owned_by_optional_hook():
    player = SimpleNamespace(
        id="p1",
        has_control=lambda: True,
        optional_decision_hook=lambda *_args, **_kwargs: True,
    )
    game = SimpleNamespace(event_system=EventSystem(), players=[player], is_authoritative=False)
    harness = _HookHarness(game)

    class _DialogStub:
        def __init__(self):
            self.visible = False
            self.decision_request = None
            self.show_calls = 0

        def show(self, *_args, **_kwargs):
            self.show_calls += 1

    harness.yes_no_dialog = _DialogStub()
    harness.dialog_manager = SimpleNamespace(open=lambda *_args, **_kwargs: None)
    harness._resolve_player_by_id = lambda player_id: player if str(player_id or "") == "p1" else None

    request = DecisionRequest.create(
        "decision.confirm_yes_no",
        "Confirm",
        player_id="p1",
        options=[
            DecisionOption.create("Use", payload={"choice": True}),
            DecisionOption.create("Skip", payload={"choice": False}),
        ],
        context={"ability": "generic_optional", "optional": True, "message": "Use it?"},
    )

    GameView._on_decision_requested(harness, request=request, game=game)

    assert harness.yes_no_dialog.show_calls == 0


def test_miracle_request_requires_specialized_ui_for_provider_owned_flows():
    acts = DecisionRequest.create(
        "decision.use_miracle_die",
        "Select Miracle Die",
        player_id="p1",
        options=[DecisionOption.create("6", payload={"die_value": 6})],
        context={"ability": "acts_of_faith"},
    )
    assert _miracle_request_requires_specialized_ui(acts) is True

    discard = DecisionRequest.create(
        "decision.use_miracle_die",
        "Discard Miracle Die",
        player_id="p1",
        options=[DecisionOption.create("Skip", payload={"action": "skip"})],
        context={"ability": "miracle_pool_discard"},
    )
    assert _miracle_request_requires_specialized_ui(discard) is True

    generic = DecisionRequest.create(
        "decision.use_miracle_die",
        "Generic Miracle",
        player_id="p1",
        options=[DecisionOption.create("Skip", payload={"action": "skip"})],
        context={"ability": "generic"},
    )
    assert _miracle_request_requires_specialized_ui(generic) is False


def test_on_decision_requested_secondary_discard_cancel_resolves_skip() -> None:
    commands = []
    player = SimpleNamespace(id="p1", has_control=lambda: True)
    game = SimpleNamespace(
        event_system=EventSystem(),
        players=[player],
        apply_command=lambda command: commands.append(command) or SimpleNamespace(
            value=SimpleNamespace(ok=True, value=None)
        ),
    )
    harness = _HookHarness(game)

    class _DialogStub:
        def __init__(self):
            self.calls = []

        def show(self, *args, **kwargs):
            self.calls.append((args, kwargs))

        def hide(self):
            return None

    harness.secondary_discard_dialog = _DialogStub()
    harness.dialog_manager = SimpleNamespace(open=lambda *_args, **_kwargs: None)
    harness._resolve_player_by_id = lambda player_id: player if str(player_id or "") == "p1" else None

    request = DecisionRequest.create(
        "DISCARD_SECONDARY",
        "NEW ORDERS",
        player_id="p1",
        options=[
            DecisionOption.create("Cleanse", payload={"card_name": "Cleanse", "card_slot": 0}),
            DecisionOption.create("Do not use", payload={"action": "skip", "skip": True}),
        ],
        context={"ability": "new_orders", "optional": True},
    )

    GameView._on_decision_requested(harness, request=request, game=game)

    assert len(harness.secondary_discard_dialog.calls) == 1
    _, kwargs = harness.secondary_discard_dialog.calls[0]
    on_cancel = kwargs["on_cancel"]
    assert callable(on_cancel)

    on_cancel()

    assert len(commands) == 1
    assert commands[0].kind == "RESOLVE_DECISION"
    assert commands[0].payload["decision_id"] == request.decision_id
    assert commands[0].payload["result_payload"] == {"skipped": True}
