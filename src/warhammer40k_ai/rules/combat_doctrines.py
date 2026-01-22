from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CombatDoctrine:
    key: str
    name: str
    summary: str


DEVASTATOR_DOCTRINE = CombatDoctrine(
    key="DEVASTATOR",
    name="Devastator Doctrine",
    summary="Eligible to shoot in a turn in which it Advanced.",
)
TACTICAL_DOCTRINE = CombatDoctrine(
    key="TACTICAL",
    name="Tactical Doctrine",
    summary="Eligible to shoot and declare a charge in a turn in which it Fell Back.",
)
ASSAULT_DOCTRINE = CombatDoctrine(
    key="ASSAULT",
    name="Assault Doctrine",
    summary="Eligible to declare a charge in a turn in which it Advanced.",
)

COMBAT_DOCTRINE_OPTIONS: tuple[CombatDoctrine, ...] = (
    DEVASTATOR_DOCTRINE,
    TACTICAL_DOCTRINE,
    ASSAULT_DOCTRINE,
)
COMBAT_DOCTRINE_BY_KEY = {d.key: d for d in COMBAT_DOCTRINE_OPTIONS}


class CombatDoctrinesManager:
    """
    Space Marines detachment ability: Combat Doctrines (Gladius Task Force).

    At the start of your Command phase, you can select one Combat Doctrine.
    Each doctrine can only be selected once per battle. The selected doctrine
    is active until the start of your next Command phase.
    """

    def __init__(self, army=None):
        self.army = army
        self.active_doctrine_key: Optional[str] = None
        self.active_round: Optional[int] = None
        self.used_doctrine_keys: list[str] = []

    def _army_has_combat_doctrines(self) -> bool:
        if self.army is None:
            return False
        try:
            faction_id = str(getattr(self.army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "SM":
            return False
        try:
            mgr = getattr(self.army, "space_marines_detachments", None)
            if mgr is not None and getattr(mgr, "is_gladius_task_force", None):
                if mgr.is_gladius_task_force():
                    return True
        except Exception:
            pass
        det = str(getattr(self.army, "detachment_type", "") or "").strip().lower()
        if "gladius" in det and "task force" in det:
            return True
        if not faction_id:
            try:
                for unit in list(getattr(self.army, "units", []) or []):
                    if self._unit_is_adeptus_astartes(unit):
                        return True
            except Exception:
                return False
        return False

    def _unit_is_adeptus_astartes(self, unit) -> bool:
        if unit is None:
            return False
        try:
            return bool(unit.has_any_keyword("ADEPTUS ASTARTES"))
        except Exception:
            return False

    def _is_active_round(self, game=None) -> bool:
        if self.active_round is None:
            return False
        if game is None:
            return True
        try:
            return int(getattr(game, "turn", 0) or 0) == int(self.active_round)
        except Exception:
            return False

    def get_active_doctrine(self, *, game=None) -> Optional[CombatDoctrine]:
        if not self._army_has_combat_doctrines():
            return None
        if not self.active_doctrine_key:
            return None
        if not self._is_active_round(game=game):
            return None
        return COMBAT_DOCTRINE_BY_KEY.get(self.active_doctrine_key)

    def get_active_doctrine_for_unit(self, unit, *, game=None) -> Optional[CombatDoctrine]:
        if not self._unit_is_adeptus_astartes(unit):
            return None
        return self.get_active_doctrine(game=game)

    def get_available_doctrines(self) -> list[CombatDoctrine]:
        if not self._army_has_combat_doctrines():
            return []
        used = {str(k or "").strip().upper() for k in (self.used_doctrine_keys or []) if str(k or "").strip()}
        return [d for d in COMBAT_DOCTRINE_OPTIONS if d.key not in used]

    def can_select_now(self, *, game=None) -> bool:
        if not self._army_has_combat_doctrines():
            return False
        if self.active_round is not None and self._is_active_round(game=game) and self.active_doctrine_key:
            return False
        return bool(self.get_available_doctrines())

    def select_doctrine(self, doctrine, *, battle_round: Optional[int] = None) -> bool:
        if not self._army_has_combat_doctrines():
            return False
        key = getattr(doctrine, "key", doctrine)
        key = str(key or "").strip().upper()
        if key not in COMBAT_DOCTRINE_BY_KEY:
            return False
        used = {str(k or "").strip().upper() for k in (self.used_doctrine_keys or []) if str(k or "").strip()}
        if key in used:
            return False
        self.active_doctrine_key = key
        if battle_round is not None:
            try:
                self.active_round = int(battle_round)
            except Exception:
                pass
        self.used_doctrine_keys.append(key)
        return True

    def can_shoot_after_advance(self, unit, profile=None, *, game=None) -> bool:
        if unit is None:
            return False
        if not self._unit_is_adeptus_astartes(unit):
            return False
        active = self.get_active_doctrine_for_unit(unit, game=game)
        if active is None or active.key != DEVASTATOR_DOCTRINE.key:
            return False
        try:
            if profile is not None and getattr(profile, "parent_wargear", None) is not None:
                return bool(profile.parent_wargear.is_ranged())
        except Exception:
            pass
        return True

    def can_shoot_after_fall_back(self, unit, profile=None, *, game=None) -> bool:
        if unit is None:
            return False
        if not self._unit_is_adeptus_astartes(unit):
            return False
        active = self.get_active_doctrine_for_unit(unit, game=game)
        if active is None or active.key != TACTICAL_DOCTRINE.key:
            return False
        try:
            if profile is not None and getattr(profile, "parent_wargear", None) is not None:
                return bool(profile.parent_wargear.is_ranged())
        except Exception:
            pass
        return True

    def can_charge_after_advance(self, unit, *, game=None) -> bool:
        if unit is None:
            return False
        if not self._unit_is_adeptus_astartes(unit):
            return False
        active = self.get_active_doctrine_for_unit(unit, game=game)
        if active is None:
            return False
        return active.key == ASSAULT_DOCTRINE.key

    def can_charge_after_fall_back(self, unit, *, game=None) -> bool:
        if unit is None:
            return False
        if not self._unit_is_adeptus_astartes(unit):
            return False
        active = self.get_active_doctrine_for_unit(unit, game=game)
        if active is None:
            return False
        return active.key == TACTICAL_DOCTRINE.key
