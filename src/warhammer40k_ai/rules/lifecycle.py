from __future__ import annotations


class AbilityLifecycle:
    """
    Minimal lifecycle tracker for unit-scoped rules.

    This scaffolding will evolve to attach/detach ability listeners as units
    are set up, destroyed, or move off-board.
    """

    def __init__(self, game: object):
        self.game = game
        self._active_unit_ids: set[str] = set()
        # Events that should only fire for units currently on the battlefield.
        self._active_unit_event_keys: dict[str, tuple[str, ...]] = {
            "unit_set_up": ("unit",),
            "unit_move_started": ("unit",),
            "unit_move_ended": ("unit",),
            "unit_shooting_resolved": ("attacker_unit", "unit"),
            "shooting_targets_selected": ("attacking_unit", "unit"),
            "charge_declared": ("unit",),
            "fight_unit_selected": ("unit",),
            "fight_targets_selected": ("attacking_unit", "unit"),
            "fight_sequence_complete": ("unit",),
            "battle_shock_test_started": ("unit",),
            "battle_shock_test_resolved": ("unit",),
        }
        # Events that should always be dispatched even if the unit is not active.
        self._always_dispatch_events: set[str] = {
            "unit_destroyed",
            "model_destroyed",
            "model_destroyed_before_removal",
            "unit_state_changed",
            "unit_reserve_status_changed",
            "unit_embarked",
            "unit_disembarked",
        }

    def on_unit_set_up(self, unit=None, **_kwargs) -> None:
        uid = self._unit_id(unit)
        if uid:
            self._active_unit_ids.add(uid)

    def on_unit_destroyed(self, unit=None, **_kwargs) -> None:
        uid = self._unit_id(unit)
        if uid:
            self._active_unit_ids.discard(uid)

    def on_unit_state_changed(self, unit=None, **_kwargs) -> None:
        uid = self._unit_id(unit)
        if not uid:
            return
        if self._unit_is_active(unit):
            self._active_unit_ids.add(uid)
        else:
            self._active_unit_ids.discard(uid)

    def refresh(self) -> None:
        """Rebuild the active unit cache from the current game state."""
        self._active_unit_ids = set()
        for unit in self._iter_all_units():
            if self._unit_is_active(unit):
                uid = self._unit_id(unit)
                if uid:
                    self._active_unit_ids.add(uid)

    def should_dispatch(self, event_name: str, kwargs: dict) -> bool:
        if not event_name:
            return True
        if event_name in self._always_dispatch_events:
            return True
        keys = self._active_unit_event_keys.get(event_name)
        if not keys:
            return True
        unit = None
        for key in keys:
            unit = kwargs.get(key)
            if unit is not None:
                break
        if unit is None:
            return True
        return self.is_unit_active(unit)

    def is_unit_active(self, unit) -> bool:
        active = self._unit_is_active(unit)
        uid = self._unit_id(unit)
        if uid:
            if active:
                self._active_unit_ids.add(uid)
            else:
                self._active_unit_ids.discard(uid)
        return active

    def _iter_all_units(self):
        try:
            players = list(getattr(self.game, "players", []) or [])
        except Exception:
            players = []
        for player in players:
            try:
                army = player.get_army()
            except Exception:
                army = getattr(player, "army", None)
            if army is None:
                continue
            try:
                units = list(getattr(army, "units", []) or [])
            except Exception:
                units = []
            for unit in units:
                if unit is not None:
                    yield unit

    def _unit_is_active(self, unit) -> bool:
        if unit is None:
            return False
        try:
            fn = getattr(unit, "is_active_for_rules", None)
            if callable(fn):
                return bool(fn())
        except Exception:
            pass
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive):
                if not unit.is_alive():
                    return False
        except Exception:
            pass
        try:
            if hasattr(unit, "deployed") and not bool(getattr(unit, "deployed", False)):
                return False
        except Exception:
            pass
        try:
            if hasattr(unit, "reserve_status"):
                reserve_status = str(getattr(unit, "reserve_status", "deployed") or "deployed")
                if reserve_status != "deployed":
                    return False
        except Exception:
            pass
        try:
            if bool(getattr(unit, "is_embarked", False)):
                return False
            if getattr(unit, "embarked_in", None):
                return False
        except Exception:
            pass
        return True

    def _unit_id(self, unit) -> str | None:
        if unit is None:
            return None
        try:
            return str(getattr(unit, "_id", "") or "")
        except Exception:
            return None
