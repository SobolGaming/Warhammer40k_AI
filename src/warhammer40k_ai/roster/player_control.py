from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .army import Army
    from ..units.unit import Unit


class PlayerControl(Enum):
    LOCAL = auto()
    REMOTE = auto()


class PlayerControlMixin:
    def has_control(self) -> bool:
        return self.control == PlayerControl.LOCAL

    def set_army(self, army: Army) -> None:
        self.army = army
        army.set_player(self)
        stratagems = getattr(self, "stratagems", None)
        if stratagems is not None:
            stratagems.refresh_available()
        game = getattr(self, "game", None)
        refresh_fn = getattr(game, "refresh_rule_subscribers", None) if game is not None else None
        if callable(refresh_fn):
            refresh_fn()

    def set_game(self, game) -> None:
        """Set the game reference for this player."""
        self.game = game
        from ..rules.stratagems import StratagemManager

        self.stratagems = StratagemManager(self)
        event_system = getattr(game, "event_system", None)
        if event_system is not None:
            self.stratagems.enable_event_subscriptions(event_system=event_system, group="rule:stratagems")

    def get_army(self) -> Army | None:
        return self.army

    def has_unit(self, unit: Unit) -> bool:
        return unit in self.army.units

    def has_units(self) -> bool:
        return len(self.army.units) > 0
