from __future__ import annotations

import pytest

from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.dice_rolls import DiceRollState, register_roll_handler
from warhammer40k_ai.engine.decision_kinds import DECISION_REQUEST_DICE_ROLL
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.utility.dice import get_roll, suppress_get_roll_requests
from warhammer40k_ai.utility.game_context import game_context


class _StubRng:
    def __init__(self, values):
        self._it = iter(values)

    def randint(self, _a, _b):
        return next(self._it)


class _StubPlayer:
    def __init__(self, pid: str):
        self.id = str(pid)
        self.name = str(pid)

    def set_game(self, _game):
        return None

    def assign_default_ui_color(self, _idx: int):
        return None

    def get_army(self):
        return None


def _make_game() -> Game:
    battlefield = Battlefield(width=60, height=44)
    return Game(battlefield, players=[])


def _make_game_with_players() -> Game:
    battlefield = Battlefield(width=60, height=44)
    return Game(battlefield, players=[_StubPlayer("p1"), _StubPlayer("p2")])


def test_dice_roll_sum_success_lte():
    game = _make_game()
    game.auto_resolve_dice_rolls = True
    spec = {
        "dice_count": 2,
        "faces": 6,
        "fixed_dice": [3, 4],
        "reason": "Leadership test",
        "roll_type": "battle_shock",
        "show_sum": True,
        "sum_target": 7,
        "sum_op": "lte",
    }
    req = game.request_dice_roll(player_id=None, spec=spec, prompt=spec["reason"])
    roll_id = req.context.get("roll_id")
    state = game.roll_manager.get_roll(int(roll_id))
    assert state is not None
    assert state.status == "rolled"
    assert state.total == 7
    assert state.sum_success is True


def test_headless_auto_roll_callbacks_drain_iteratively_without_truncating_deep_chains():
    state = {"handled": 0}
    handler_key = f"test_headless_auto_roll_chain_{id(state)}"

    def _chain_next_roll(game, roll_state):
        state["handled"] += 1
        remaining = int(roll_state.spec.get("remaining", 0) or 0)
        if remaining <= 0:
            return None
        return game.request_dice_roll(
            player_id=roll_state.player_id,
            spec={
                "dice_count": 1,
                "faces": 6,
                "fixed_dice": [4],
                "reason": f"Auto roll chain {remaining}",
                "roll_type": "test_auto_roll_chain",
                "handler_key": handler_key,
                "remaining": remaining - 1,
            },
            prompt=f"Auto roll chain {remaining}",
        )

    register_roll_handler(handler_key, _chain_next_roll)
    game = _make_game_with_players()
    game.auto_resolve_dice_rolls = True
    game.setup_complete = True
    game.session_id = "test:auto-roll-chain"

    depth = 90
    req = game.request_dice_roll(
        player_id="p1",
        spec={
            "dice_count": 1,
            "faces": 6,
            "fixed_dice": [4],
            "reason": "Auto roll chain",
            "roll_type": "test_auto_roll_chain",
            "handler_key": handler_key,
            "remaining": depth,
        },
        prompt="Auto roll chain",
    )

    assert req.decision_type == DECISION_REQUEST_DICE_ROLL
    assert state["handled"] == depth + 1
    assert game.decision_queue.peek() is None
    assert len(game.decision_record_store.records) == depth + 1


def test_dice_roll_one_reroll_per_die():
    game = _make_game()
    game.auto_resolve_dice_rolls = False
    spec = {
        "dice_count": 2,
        "faces": 6,
        "fixed_dice": [1, 2],
        "reason": "Hit roll",
        "roll_type": "hit",
        "reroll_rules": [
            {
                "action_id": "reroll_ones",
                "label": "Re-roll ones",
                "mode": "values",
                "eligible_values": [1],
            }
        ],
    }
    req = game.request_dice_roll(player_id=None, spec=spec, prompt=spec["reason"])
    roll_id = req.context.get("roll_id")
    state = game.roll_manager.resolve_roll(game, int(roll_id))
    die_id = None
    for die in list(state.dice or []):
        if int(die.get("value", 0) or 0) == 1:
            die_id = die.get("die_id")
            break
    assert die_id is not None
    game.random_source = _StubRng([6])
    state = game.roll_manager.apply_reroll(
        game,
        int(roll_id),
        action_id="reroll_ones",
        selected_die_ids=[die_id],
    )
    rerolled = next(d for d in state.dice if d.get("die_id") == die_id)
    assert int(rerolled.get("reroll_count", 0) or 0) == 1
    val_after = int(rerolled.get("value", 0) or 0)
    game.random_source = _StubRng([2])
    state = game.roll_manager.apply_reroll(
        game,
        int(roll_id),
        action_id="reroll_ones",
        selected_die_ids=[die_id],
    )
    rerolled_again = next(d for d in state.dice if d.get("die_id") == die_id)
    assert int(rerolled_again.get("value", 0) or 0) == val_after
    assert int(rerolled_again.get("reroll_count", 0) or 0) == 1


def test_get_roll_uses_request_roll_with_modifier():
    game = _make_game_with_players()
    game.auto_resolve_dice_rolls = False
    game.random_source = _StubRng([4])
    requested = []

    def _capture_request(request=None, **_kwargs):
        if request is not None:
            requested.append(request)

    game.event_system.subscribe("decision_requested", _capture_request, group="test:get_roll")
    with game_context(game):
        value = get_roll("D6+2")

    assert value == 6
    req = next(
        req for req in requested
        if str(getattr(req, "decision_type", "") or "") == DECISION_REQUEST_DICE_ROLL
    )
    roll_id = int((req.context or {}).get("roll_id", 0) or 0)
    state = game.roll_manager.get_roll(roll_id)
    assert state is not None
    assert state.final is True
    assert str((state.spec or {}).get("roll_type", "") or "") == "get_roll"
    explanation = dict((state.spec or {}).get("roll_explanation", {}) or {})
    sum_modifier = dict(explanation.get("sum_modifier", {}) or {})
    assert int(sum_modifier.get("total", 0) or 0) == 2
    assert game.decision_queue.get(req.decision_id) is None


def test_auto_pick_reroll_action_uses_decision_port_provider_for_remote_player():
    game = _make_game_with_players()
    game.auto_resolve_dice_rolls = False
    player = game.players[0]
    player.has_control = lambda: False
    provider_calls = []
    game.install_decision_providers(
        roll_reroll_provider=lambda **kwargs: provider_calls.append(dict(kwargs)) or True
    )
    req = game.roll_manager.request_roll(
        game,
        player_id=player.id,
        spec={
            "dice_count": 2,
            "faces": 6,
            "fixed_dice": [1, 2],
            "reason": "Hit roll",
            "roll_type": "hit",
            "reroll_rules": [
                {
                    "action_id": "reroll_ones",
                    "label": "Re-roll ones",
                    "mode": "values",
                    "eligible_values": [1],
                }
            ],
        },
        prompt="Hit roll",
    )
    roll_id = int((req.context or {}).get("roll_id", 0) or 0)
    state = game.roll_manager.resolve_roll(game, roll_id)

    action_id, selected = game.roll_manager._auto_pick_reroll_action(game, state)

    assert action_id == "reroll_ones"
    assert list(selected or [])
    assert provider_calls
    assert str(provider_calls[0].get("roll_type", "") or "") == "hit"


def test_auto_pick_charge_reroll_uses_required_charge_total_failure():
    game = _make_game_with_players()
    game.auto_resolve_dice_rolls = False
    req = game.roll_manager.request_roll(
        game,
        player_id="p1",
        spec={
            "dice_count": 2,
            "faces": 6,
            "fixed_dice": [3, 1],
            "roll_sequence": [6, 2],
            "reason": "Charge roll",
            "roll_type": "charge",
            "charge_spec": {"dice_count": 2, "keep_highest": 2},
            "sum_target": 8,
            "sum_op": "gte",
            "reroll_rules": [
                {
                    "action_id": "reroll_charge",
                    "label": "Re-roll Charge roll",
                    "mode": "all",
                    "source": "rule",
                }
            ],
        },
        prompt="Charge roll",
    )
    roll_id = int((req.context or {}).get("roll_id", 0) or 0)
    state = game.roll_manager.resolve_roll(game, roll_id)

    assert state.sum_success is False
    action_id, selected = game.roll_manager._auto_pick_reroll_action(game, state)

    assert action_id == "reroll_charge"
    assert set(selected or []) == {f"{roll_id}:0", f"{roll_id}:1"}

    updated = game.roll_manager.apply_reroll(game, roll_id, action_id=action_id, selected_die_ids=selected)
    assert updated.total == 8
    assert updated.sum_success is True
    assert updated.reroll_history[-1]["action_id"] == "reroll_charge"


def test_auto_pick_charge_command_reroll_when_charge_failed_and_no_rule_reroll():
    game = _make_game_with_players()
    state = DiceRollState(
        roll_id=91,
        player_id="p1",
        spec={"roll_type": "charge", "sum_target": 8, "sum_op": "gte"},
        status="rolled",
        dice=[
            {"die_id": "91:0", "value": 2, "is_derived": False},
            {"die_id": "91:1", "value": 2, "is_derived": False},
        ],
        total=4,
        per_die_success={"91:0": None, "91:1": None},
        sum_success=False,
        reroll_options=[
            {"action_id": "none", "label": "No re-roll", "mode": "none", "source": "none"},
            {
                "action_id": "command_reroll",
                "label": "Command Re-roll",
                "mode": "whole",
                "eligible_die_ids": ["91:0", "91:1"],
                "is_command": True,
                "consume_cp": True,
            },
        ],
    )

    action_id, selected = game.roll_manager._auto_pick_reroll_action(game, state)

    assert action_id == "command_reroll"
    assert set(selected or []) == {"91:0", "91:1"}


@pytest.mark.parametrize("roll_type", ["hit", "wound"])
def test_auto_pick_command_reroll_provider_can_select_failed_attack_roll(roll_type: str):
    game = _make_game_with_players()
    provider_calls = []
    game.install_decision_providers(
        roll_reroll_provider=lambda **kwargs: provider_calls.append(dict(kwargs)) or (not bool(kwargs.get("success")))
    )
    state = DiceRollState(
        roll_id=92,
        player_id="p1",
        spec={"roll_type": roll_type, "target": 3, "target_op": "gte"},
        status="rolled",
        dice=[
            {"die_id": "92:0", "value": 2, "is_derived": False},
        ],
        total=2,
        per_die_success={"92:0": False},
        sum_success=None,
        reroll_options=[
            {"action_id": "none", "label": "No re-roll", "mode": "none", "source": "none"},
            {
                "action_id": "command_reroll",
                "label": "Command Re-roll",
                "mode": "one",
                "eligible_die_ids": ["92:0"],
                "is_command": True,
                "consume_cp": True,
                "cp_cost": 1,
            },
        ],
    )

    action_id, selected = game.roll_manager._auto_pick_reroll_action(game, state)

    assert action_id == "command_reroll"
    assert selected == ["92:0"]
    assert provider_calls
    assert provider_calls[0]["roll_type"] == roll_type
    assert provider_calls[0]["success"] is False
    assert provider_calls[0]["is_command"] is True


def test_charge_roll_success_uses_kept_dice_before_reroll_choice():
    game = _make_game_with_players()
    game.auto_resolve_dice_rolls = False
    req = game.roll_manager.request_roll(
        game,
        player_id="p1",
        spec={
            "dice_count": 3,
            "faces": 6,
            "fixed_dice": [6, 5, 1],
            "reason": "Charge roll",
            "roll_type": "charge",
            "charge_spec": {"dice_count": 3, "keep_highest": 2},
            "sum_target": 10,
            "sum_op": "gte",
            "reroll_rules": [
                {
                    "action_id": "reroll_charge",
                    "label": "Re-roll Charge roll",
                    "mode": "all",
                    "source": "rule",
                }
            ],
        },
        prompt="Charge roll",
    )
    roll_id = int((req.context or {}).get("roll_id", 0) or 0)
    state = game.roll_manager.resolve_roll(game, roll_id)

    assert state.total == 11
    assert state.sum_success is True
    assert game.roll_manager._auto_pick_reroll_action(game, state) == ("none", [])


def test_get_roll_d33_uses_request_roll():
    game = _make_game_with_players()
    game.auto_resolve_dice_rolls = False
    game.random_source = _StubRng([5, 6])
    with game_context(game):
        value = get_roll("D33")
    assert value == 33


def test_get_roll_uses_explicit_game_and_player_metadata():
    game = _make_game_with_players()
    game.auto_resolve_dice_rolls = False
    game.random_source = _StubRng([3])
    requested = []

    def _capture_request(request=None, **_kwargs):
        if request is not None:
            requested.append(request)

    game.event_system.subscribe("decision_requested", _capture_request, group="test:get_roll_explicit_game")
    value = get_roll(
        "D6",
        game=game,
        player=game.players[1],
        reason="Determine attacker and defender: p2",
        roll_type="determine_attacker_defender",
    )

    assert value == 3
    req = next(
        req for req in requested
        if str(getattr(req, "decision_type", "") or "") == DECISION_REQUEST_DICE_ROLL
    )
    assert str(getattr(req, "player_id", "") or "") == "p2"

    roll_id = int((req.context or {}).get("roll_id", 0) or 0)
    state = game.roll_manager.get_roll(roll_id)
    assert state is not None
    assert str((state.spec or {}).get("reason", "") or "") == "Determine attacker and defender: p2"
    assert str((state.spec or {}).get("roll_type", "") or "") == "determine_attacker_defender"


def test_suppressed_get_roll_skips_request_roll_emission():
    game = _make_game_with_players()
    game.auto_resolve_dice_rolls = False
    game.random_source = _StubRng([4])
    requested = []

    def _capture_request(request=None, **_kwargs):
        if request is not None:
            requested.append(request)

    game.event_system.subscribe("decision_requested", _capture_request, group="test:get_roll_suppressed")
    with game_context(game):
        with suppress_get_roll_requests():
            value = get_roll("D6")

    assert value == 4
    assert requested == []


def test_request_d3_roll_uses_d6_mapping_and_records_raw_dice():
    game = _make_game_with_players()
    game.auto_resolve_dice_rolls = False
    game.random_source = _StubRng([3])
    spec = {
        "dice_count": 1,
        "faces": 3,
        "reason": "D3 mapping test",
        "roll_type": "d3_mapping_test",
        "show_sum": True,
    }
    req = game.request_dice_roll(player_id="p1", spec=spec, prompt=spec["reason"])
    roll_id = int((req.context or {}).get("roll_id", 0) or 0)
    state = game.roll_manager.resolve_roll(game, roll_id)
    assert state is not None
    assert int(state.total or 0) == 2
    base_die = next(d for d in list(state.dice or []) if not bool(d.get("is_derived", False)))
    assert int(base_die.get("value", 0) or 0) == 2
    assert int(base_die.get("raw_value", 0) or 0) == 3

    events = [e for e in list(game.event_log.events or []) if str(getattr(e, "event_type", "") or "") == "roll_made"]
    assert events
    payload = dict(events[-1].payload or {})
    assert list(payload.get("dice") or []) == [2]
    assert list(payload.get("raw_dice") or []) == [3]
    assert str(payload.get("dice_mapping", "") or "") == "d3_from_d6"
