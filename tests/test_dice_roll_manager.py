from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.decision_kinds import DECISION_REQUEST_DICE_ROLL
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.utility.dice import get_roll
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


def test_legacy_get_roll_uses_request_roll_with_modifier():
    game = _make_game_with_players()
    game.auto_resolve_dice_rolls = False
    game.random_source = _StubRng([4])
    requested = []

    def _capture_request(request=None, **_kwargs):
        if request is not None:
            requested.append(request)

    game.event_system.subscribe("decision_requested", _capture_request, group="test:legacy_get_roll")
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
    assert str((state.spec or {}).get("roll_type", "") or "") == "legacy_get_roll"
    explanation = dict((state.spec or {}).get("roll_explanation", {}) or {})
    sum_modifier = dict(explanation.get("sum_modifier", {}) or {})
    assert int(sum_modifier.get("total", 0) or 0) == 2
    assert game.decision_queue.get(req.decision_id) is None


def test_legacy_get_roll_d33_uses_request_roll():
    game = _make_game_with_players()
    game.auto_resolve_dice_rolls = False
    game.random_source = _StubRng([5, 6])
    with game_context(game):
        value = get_roll("D33")
    assert value == 33


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
