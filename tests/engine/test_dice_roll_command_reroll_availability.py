from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.decisions import DecisionQueue
from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_DICE_REROLL
from warhammer40k_ai.engine.dice_rolls import DiceRollManager, register_roll_handler


class _EventSystemStub:
    def publish(self, _event_name: str, **_kwargs) -> None:
        return None


class _StratagemStub:
    def __init__(self, name: str) -> None:
        self.name = name
        self.cp_cost = 1


class _StratagemManagerStub:
    def __init__(self, *, available: bool) -> None:
        self._available = bool(available)
        self._used_stratagems_this_phase: set[str] = set()

    def get_by_name(self, name: str):
        if str(name or "").strip().upper() == "COMMAND RE-ROLL":
            return _StratagemStub("COMMAND RE-ROLL")
        return None

    def _evaluate_availability(self, strat, _ctx, *, is_active_turn: bool):
        if not bool(is_active_turn):
            return {"available": False, "reason": "Not active player turn."}
        key = str(getattr(strat, "name", "") or "").strip().upper()
        if key in set(self._used_stratagems_this_phase):
            return {"available": False, "reason": "Already used this phase."}
        if not self._available:
            return {"available": False, "reason": "Insufficient CP."}
        return {"available": True}


class _PlayerStub:
    def __init__(self, player_id: str, *, available: bool) -> None:
        self.id = str(player_id)
        self.stratagems = _StratagemManagerStub(available=available)


class _UnitStub:
    def __init__(self, unit_id: str) -> None:
        self.id = str(unit_id)


class _RegistryStub:
    def __init__(self, player, unit) -> None:
        self._player = player
        self._unit = unit

    def get(self, entity_id: str, *, kind: str | None = None):
        eid = str(entity_id or "")
        if kind == "player" and eid == str(getattr(self._player, "id", "")):
            return self._player
        if kind == "unit" and eid == str(getattr(self._unit, "id", "")):
            return self._unit
        return None


class _GameStub:
    def __init__(self, *, player, unit) -> None:
        self.is_authoritative = True
        self.turn = 1
        self.phase = SimpleNamespace(name="SHOOTING_PHASE")
        self.roll_manager = DiceRollManager()
        self.decision_queue = DecisionQueue()
        self.event_system = _EventSystemStub()
        self.players = [player]
        self.entity_registry = _RegistryStub(player, unit)

    def request_decision(self, request) -> None:
        self.decision_queue.add(request)

    def _current_phase_label(self) -> str:
        return "SHOOTING_PHASE"

    def get_current_player(self):
        return self.players[0]


def _resolve_roll_state(game: _GameStub, player: _PlayerStub, unit: _UnitStub):
    req = game.roll_manager.request_roll(
        game,
        player_id=player.id,
        spec={
            "dice_count": 1,
            "faces": 6,
            "fixed_dice": [2],
            "reason": "Hit roll (1D6)",
            "roll_type": "hit",
            "target": 3,
            "target_op": "gte",
            "unit_id": unit.id,
            "command_reroll_allowed": True,
            "command_reroll_mode": "one",
            "reroll_rules": [],
        },
        prompt="Hit roll (1D6)",
    )
    roll_id = int((req.context or {}).get("roll_id", 0) or 0)
    return game.roll_manager.resolve_roll(game, roll_id)


def test_command_reroll_option_present_when_stratagem_available() -> None:
    player = _PlayerStub("p1", available=True)
    unit = _UnitStub("u1")
    game = _GameStub(player=player, unit=unit)

    state = _resolve_roll_state(game, player, unit)
    action_ids = [str(opt.get("action_id", "")) for opt in list(state.reroll_options or [])]

    assert "command_reroll" in action_ids


def test_command_reroll_option_hidden_when_unavailable_or_used() -> None:
    player = _PlayerStub("p1", available=False)
    unit = _UnitStub("u1")
    game = _GameStub(player=player, unit=unit)

    state = _resolve_roll_state(game, player, unit)
    action_ids = [str(opt.get("action_id", "")) for opt in list(state.reroll_options or [])]
    assert "command_reroll" not in action_ids

    player_enabled = _PlayerStub("p2", available=True)
    unit_enabled = _UnitStub("u2")
    game_enabled = _GameStub(player=player_enabled, unit=unit_enabled)
    state_enabled = _resolve_roll_state(game_enabled, player_enabled, unit_enabled)
    action_ids_enabled = [str(opt.get("action_id", "")) for opt in list(state_enabled.reroll_options or [])]
    assert "command_reroll" in action_ids_enabled

    player_enabled.stratagems._used_stratagems_this_phase.add("COMMAND RE-ROLL")
    recomputed = game_enabled.roll_manager._compute_reroll_options(game_enabled, state_enabled)
    recomputed_ids = [str(opt.get("action_id", "")) for opt in list(recomputed or [])]
    assert "command_reroll" not in recomputed_ids


def test_command_reroll_request_payload_carries_tool_metadata() -> None:
    player = _PlayerStub("p3", available=True)
    unit = _UnitStub("u3")
    game = _GameStub(player=player, unit=unit)

    _resolve_roll_state(game, player, unit)
    reroll_request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_DICE_REROLL
    )
    payload = next(
        dict(getattr(option, "payload", {}) or {})
        for option in list(getattr(reroll_request, "options", []) or [])
        if str(getattr(option, "payload", {}).get("action_id", "") or "") == "command_reroll"
    )

    assert payload["cp_cost"] == 1
    assert payload["tool_id"] == "stratagem:command_reroll"
    assert payload["tool_type"] == "stratagem"
    assert payload["stratagem_name"] == "COMMAND RE-ROLL"
    assert payload["ability_key"] == "command_reroll"
    assert payload["ability_name"] == "COMMAND RE-ROLL"


@pytest.mark.parametrize("roll_type", ["hit", "wound"])
def test_command_reroll_attack_handler_receives_final_rerolled_hit_or_wound(roll_type: str) -> None:
    player = _PlayerStub("p4", available=True)
    unit = _UnitStub("u4")
    game = _GameStub(player=player, unit=unit)
    handled: list[dict] = []
    handler_key = f"test_command_reroll_final_{roll_type}_{id(handled)}"

    def _capture_handler(_game, state) -> None:
        handled.append(
            {
                "roll_type": str(state.spec.get("roll_type", "") or ""),
                "dice": [
                    int(die.get("value", 0) or 0)
                    for die in list(state.dice or [])
                    if not bool(die.get("is_derived", False))
                ],
                "success": list(dict(state.per_die_success or {}).values()),
                "final": bool(state.final),
            }
        )

    register_roll_handler(handler_key, _capture_handler)
    req = game.roll_manager.request_roll(
        game,
        player_id=player.id,
        spec={
            "dice_count": 1,
            "faces": 6,
            "fixed_dice": [2],
            "roll_sequence": [5],
            "reason": f"{roll_type.title()} roll (1D6)",
            "roll_type": roll_type,
            "target": 3,
            "target_op": "gte",
            "unit_id": unit.id,
            "handler_key": handler_key,
            "command_reroll_allowed": True,
            "command_reroll_mode": "one",
            "reroll_rules": [],
        },
        prompt=f"{roll_type.title()} roll (1D6)",
    )
    roll_id = int((req.context or {}).get("roll_id", 0) or 0)

    state = game.roll_manager.resolve_roll(game, roll_id)
    assert state.final is False
    assert handled == []

    command_option = next(
        opt
        for opt in list(state.reroll_options or [])
        if str(opt.get("action_id", "") or "") == "command_reroll"
    )
    updated = game.roll_manager.apply_reroll(
        game,
        roll_id,
        action_id="command_reroll",
        selected_die_ids=list(command_option.get("eligible_die_ids", []) or []),
    )

    assert updated.final is True
    assert handled == [
        {
            "roll_type": roll_type,
            "dice": [5],
            "success": [True],
            "final": True,
        }
    ]
