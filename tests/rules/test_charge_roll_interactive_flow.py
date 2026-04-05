from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_REQUEST_DICE_ROLL, DECISION_SELECT_DICE_REROLL
from warhammer40k_ai.engine.decisions import DecisionQueue
from warhammer40k_ai.engine.dice_rolls import DiceRollManager


class _EventSystemStub:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def publish(self, event_name: str, **kwargs) -> None:
        self.events.append((str(event_name), dict(kwargs or {})))


class _UnitRegistry:
    def __init__(self, unit) -> None:
        self._unit = unit

    def get(self, entity_id: str, *, kind: str | None = None):
        if kind == "unit" and str(entity_id) == str(getattr(self._unit, "id", "")):
            return self._unit
        return None


class _DummyUnit:
    def __init__(self, player) -> None:
        self.id = "unit-charge-flow"
        self.name = "Shalaxi Helbane"
        self.round_state = SimpleNamespace(
            charge_roll=0,
            charge_dice=[],
            charge_modifier_choice_pending=False,
            charge_modifier_choice=None,
            charge_modifier_choice_targets=[],
        )
        self._army = SimpleNamespace(player=player)

    def get_parent_army(self):
        return self._army


class _GameStub:
    def __init__(self, *, unit, player) -> None:
        self.is_authoritative = True
        self.decision_queue = DecisionQueue()
        self.roll_manager = DiceRollManager()
        self.event_system = _EventSystemStub()
        self.entity_registry = _UnitRegistry(unit)
        self.players = [player]
        self.phase = SimpleNamespace(name="CHARGE_PHASE")
        self.turn = 1

    def request_decision(self, request) -> None:
        self.decision_queue.add(request)

    def request_dice_roll(self, *, player_id, spec, prompt=None):
        return self.roll_manager.request_roll(self, player_id=player_id, spec=spec, prompt=prompt)


def test_interactive_charge_roll_produces_reroll_decision_and_roll_event() -> None:
    player = SimpleNamespace(id="player-charge-flow")
    unit = _DummyUnit(player)
    game = _GameStub(unit=unit, player=player)

    roll_spec = {
        "dice_count": 2,
        "faces": 6,
        "reason": "Charge roll for Shalaxi Helbane",
        "roll_type": "charge",
        "unit_id": unit.id,
        "target_unit_ids": ["target-1"],
        "handler_key": "charge_roll",
        "charge_spec": {"dice_count": 2, "keep_highest": 2},
        "fixed_dice": [6, 2],
        "reroll_rules": [
            {
                "action_id": "reroll_charge",
                "label": "Re-roll Charge roll",
                "mode": "all",
                "source": "rule",
            }
        ],
        "command_reroll_allowed": True,
        "command_reroll_mode": "whole",
    }

    request = game.request_dice_roll(player_id=player.id, spec=roll_spec, prompt=roll_spec["reason"])

    assert request.decision_type == DECISION_REQUEST_DICE_ROLL
    roll_id = int(request.context.get("roll_id") or 0)
    assert roll_id > 0

    state = game.roll_manager.resolve_roll(game, roll_id)

    assert state is not None
    assert str(state.status) == "rolled"
    assert int(getattr(unit.round_state, "charge_roll", 0) or 0) == 0
    assert list(getattr(unit.round_state, "charge_dice", []) or []) == []

    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "")) == DECISION_SELECT_DICE_REROLL
    ]
    assert pending
    assert int((pending[-1].context or {}).get("roll_id", 0) or 0) == roll_id

    state = game.roll_manager.apply_reroll(
        game,
        roll_id,
        action_id="none",
        selected_die_ids=[],
        actor_player_id=player.id,
    )
    assert state is not None
    assert int(getattr(unit.round_state, "charge_roll", 0) or 0) == 8
    assert list(getattr(unit.round_state, "charge_dice", []) or []) == [6, 2]

    roll_events = [
        payload
        for event_name, payload in game.event_system.events
        if event_name == "roll_made" and str(payload.get("roll_type", "") or "") == "charge"
    ]
    assert roll_events
    assert int(roll_events[-1].get("value", 0) or 0) == 8
