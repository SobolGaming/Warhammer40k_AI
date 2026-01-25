from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.game import Game


class _StubRng:
    def __init__(self, values):
        self._it = iter(values)

    def randint(self, _a, _b):
        return next(self._it)


def _make_game() -> Game:
    battlefield = Battlefield(width=60, height=44)
    return Game(battlefield, players=[])


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
