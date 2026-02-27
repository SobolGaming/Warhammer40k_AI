from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.dice_rolls import DiceRollState
from warhammer40k_ai.engine.roll_handlers import handle_advance_roll
from warhammer40k_ai.utility.event_bus import get_recent_dice


class _UnitRegistry:
    def __init__(self, unit) -> None:
        self._unit = unit

    def get(self, entity_id: str, *, kind: str | None = None):
        if kind == "unit" and str(entity_id) == str(getattr(self._unit, "id", "")):
            return self._unit
        return None


class _DummyUnit:
    def __init__(self, player) -> None:
        self.id = "unit-shalaxi"
        self.name = "Shalaxi Helbane"
        self.round_state = SimpleNamespace(advance_roll=None)
        self._army = SimpleNamespace(player=player)

    def get_parent_army(self):
        return self._army

    def _apply_advance_roll_modifiers(self, roll_val: int) -> int:
        return int(roll_val)

    def _collect_advance_roll_modifiers(self):
        return []


def test_handle_advance_roll_appends_player_dice_log() -> None:
    player = SimpleNamespace(id="player-advance-log")
    unit = _DummyUnit(player)
    game = SimpleNamespace(
        entity_registry=_UnitRegistry(unit),
        map=None,
        players=[],
        is_authoritative=True,
    )
    state = DiceRollState(
        roll_id=1,
        player_id=player.id,
        spec={"unit_id": unit.id, "roll_type": "advance"},
        status="rolled",
        dice=[{"die_id": "d0", "value": 5, "faces": 6, "is_derived": False}],
        total=5,
    )

    before = list(get_recent_dice(player, limit=200))
    value = handle_advance_roll(game, state)
    after = list(get_recent_dice(player, limit=200))

    assert int(value or 0) == 5
    assert int(getattr(unit.round_state, "advance_roll", 0) or 0) == 5
    assert len(after) == len(before) + 1
    assert "Advance roll: 5" in str(after[-1])
    assert "Shalaxi Helbane" in str(after[-1])
