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
    Space Marines detachment abilities: Combat Doctrines and Mastered Doctrines.

    Gladius Task Force (Combat Doctrines):
    - At the start of your Command phase, you can select one Combat Doctrine.
    - Each doctrine can only be selected once per battle.

    Blade of Ultramar (Mastered Doctrines):
    - At the start of up to three Command phases, you can select one doctrine.
    - Doctrines cannot be re-selected unless a friendly Marneus Calgar model
      is on the battlefield.

    The selected doctrine is active until the start of your next Command phase.
    """

    def __init__(self, army=None):
        self.army = army
        self.active_doctrine_key: Optional[str] = None
        self.active_round: Optional[int] = None
        self.used_doctrine_keys: list[str] = []
        self.selection_count: int = 0
        self.selection_rounds: list[int] = []

    def _space_marines_mgr(self):
        if self.army is None:
            return None
        return getattr(self.army, "space_marines_detachments", None)

    def _is_gladius_task_force(self) -> bool:
        mgr = self._space_marines_mgr()
        if mgr is not None:
            is_gladius = getattr(mgr, "is_gladius_task_force", None)
            if callable(is_gladius) and is_gladius():
                return True
        army = self.army
        if army is None:
            return False
        has_detachment = getattr(army, "has_detachment_type", None)
        if callable(has_detachment):
            return bool(has_detachment("Gladius Task Force"))
        det = str(getattr(army, "detachment_type", "") or "").strip().lower()
        return "gladius" in det and "task force" in det

    def _is_mastered_doctrines(self) -> bool:
        mgr = self._space_marines_mgr()
        if mgr is not None:
            is_blade = getattr(mgr, "is_blade_of_ultramar", None)
            if callable(is_blade) and is_blade():
                return True
        army = self.army
        if army is None:
            return False
        has_detachment = getattr(army, "has_detachment_type", None)
        if callable(has_detachment):
            return bool(has_detachment("Blade of Ultramar"))
        det = str(getattr(army, "detachment_type", "") or "").strip().lower()
        return "blade of ultramar" in det

    def _army_has_combat_doctrines(self) -> bool:
        if self.army is None:
            return False
        try:
            faction_id = str(getattr(self.army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "SM":
            return False
        if self._is_gladius_task_force() or self._is_mastered_doctrines():
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
        mgr = self._space_marines_mgr()
        if mgr is not None:
            override_fn = getattr(mgr, "blade_of_ultramar_student_of_the_codex_active_doctrine", None)
            if callable(override_fn):
                override_key = str(override_fn(unit, game=game) or "").strip().upper()
                doctrine = COMBAT_DOCTRINE_BY_KEY.get(override_key)
                if doctrine is not None:
                    return doctrine
        return self.get_active_doctrine(game=game)

    def _doctrine_selection_limit(self) -> Optional[int]:
        if self._is_mastered_doctrines():
            return 3
        return None

    def _selection_limit_reached(self) -> bool:
        limit = self._doctrine_selection_limit()
        if limit is None:
            return False
        return int(self.selection_count) >= int(limit)

    def _doctrine_reuse_allowed(self) -> bool:
        if not self._is_mastered_doctrines():
            return False
        mgr = self._space_marines_mgr()
        if mgr is None:
            return False
        has_calgar = getattr(mgr, "has_marneus_calgar_on_battlefield", None)
        if not callable(has_calgar):
            return False
        return bool(has_calgar())

    def get_available_doctrines(self) -> list[CombatDoctrine]:
        if not self._army_has_combat_doctrines():
            return []
        if self._selection_limit_reached():
            return []
        if self._doctrine_reuse_allowed():
            return list(COMBAT_DOCTRINE_OPTIONS)
        used = {str(k or "").strip().upper() for k in (self.used_doctrine_keys or []) if str(k or "").strip()}
        return [d for d in COMBAT_DOCTRINE_OPTIONS if d.key not in used]

    def can_select_now(self, *, game=None) -> bool:
        if not self._army_has_combat_doctrines():
            return False
        if self._selection_limit_reached():
            return False
        if self.active_round is not None and self._is_active_round(game=game) and self.active_doctrine_key:
            return False
        return bool(self.get_available_doctrines())

    def select_doctrine(self, doctrine, *, battle_round: Optional[int] = None) -> bool:
        if not self._army_has_combat_doctrines():
            return False
        if self._selection_limit_reached():
            return False
        key = getattr(doctrine, "key", doctrine)
        key = str(key or "").strip().upper()
        if key not in COMBAT_DOCTRINE_BY_KEY:
            return False
        if battle_round is not None and self.active_round is not None and self.active_doctrine_key:
            try:
                if int(battle_round) == int(self.active_round):
                    return False
            except Exception:
                return False
        used = {str(k or "").strip().upper() for k in (self.used_doctrine_keys or []) if str(k or "").strip()}
        if key in used and not self._doctrine_reuse_allowed():
            return False
        self.active_doctrine_key = key
        if battle_round is not None:
            try:
                self.active_round = int(battle_round)
            except Exception:
                pass
        if key not in used:
            self.used_doctrine_keys.append(key)
        self.selection_count = int(self.selection_count) + 1
        if battle_round is not None:
            try:
                self.selection_rounds.append(int(battle_round))
            except Exception:
                pass
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
