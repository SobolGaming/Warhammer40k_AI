from __future__ import annotations

from typing import Optional

from ..utility.ability_support import ABILITY_OATH_OF_MOMENT, army_has_ability_id

CODEX_SPACE_MARINES_DETACHMENTS = {
    "gladius task force",
    "anvil siege force",
    "ironstorm spearhead",
    "firestorm assault force",
    "stormlance task force",
    "vanguard spearhead",
    "1st company task force",
    "boarding strike",
    "pilum strike team",
    "terminator assault",
}

DIVERGENT_CHAPTER_KEYWORDS = {
    "black templars",
    "blood angels",
    "dark angels",
    "deathwatch",
    "space wolves",
}


def _norm(text: str) -> str:
    return (text or "").strip().lower()


class OathOfMomentManager:
    """
    Space Marines army rule: Oath of Moment.

    Each Command phase, select one enemy unit as the Oath target until your next Command phase.
    """

    def __init__(self, army=None):
        self.army = army
        self.oathOfMomentTargetUnitId: Optional[str] = None
        self.oathOfMomentTargetName: Optional[str] = None
        if self.army is not None:
            try:
                setattr(self.army, "oathOfMomentTargetUnitId", None)
                setattr(self.army, "oathOfMomentTargetName", None)
            except Exception:
                pass

    def army_has_oath(self) -> bool:
        return self._army_has_oath()

    def _army_has_oath(self) -> bool:
        if self.army is None:
            return False
        if not army_has_ability_id(self.army, ABILITY_OATH_OF_MOMENT):
            return False
        try:
            faction_id = str(getattr(self.army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "SM":
            return False
        # Fallback: if faction id is missing, require at least one ADEPTUS ASTARTES unit.
        if not faction_id:
            try:
                for unit in list(getattr(self.army, "units", []) or []):
                    if self._unit_is_adeptus_astartes(unit):
                        return True
            except Exception:
                return False
            return False
        return True

    def _unit_is_adeptus_astartes(self, unit) -> bool:
        if unit is None:
            return False
        try:
            return unit.has_any_keyword("ADEPTUS ASTARTES")
        except Exception:
            return False

    def _army_is_codex_detachment(self) -> bool:
        if self.army is None:
            return False
        try:
            det = _norm(getattr(self.army, "detachment_type", "") or "")
        except Exception:
            det = ""
        if not det:
            return False
        return det in CODEX_SPACE_MARINES_DETACHMENTS

    def _army_has_divergent_chapter_keywords(self) -> bool:
        if self.army is None:
            return False
        for unit in list(getattr(self.army, "units", []) or []):
            for kw in DIVERGENT_CHAPTER_KEYWORDS:
                try:
                    if unit.has_any_keyword(kw):
                        return True
                except Exception:
                    continue
        return False

    def wound_bonus_enabled(self) -> bool:
        if not self._army_has_oath():
            return False
        if not self._army_is_codex_detachment():
            return False
        if self._army_has_divergent_chapter_keywords():
            return False
        return True

    def clear_target(self) -> None:
        self.oathOfMomentTargetUnitId = None
        self.oathOfMomentTargetName = None
        if self.army is not None:
            try:
                setattr(self.army, "oathOfMomentTargetUnitId", None)
                setattr(self.army, "oathOfMomentTargetName", None)
            except Exception:
                pass

    def set_target(self, unit) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            rid = getattr(root, "_id", None)
        except Exception:
            rid = None
        if not rid:
            return
        self.oathOfMomentTargetUnitId = rid
        try:
            self.oathOfMomentTargetName = str(getattr(root, "name", "") or "")
        except Exception:
            self.oathOfMomentTargetName = None
        if self.army is not None:
            try:
                setattr(self.army, "oathOfMomentTargetUnitId", self.oathOfMomentTargetUnitId)
                setattr(self.army, "oathOfMomentTargetName", self.oathOfMomentTargetName)
            except Exception:
                pass

    def is_oath_target(self, target_unit) -> bool:
        if target_unit is None:
            return False
        if not self.oathOfMomentTargetUnitId:
            return False
        try:
            root = target_unit.get_attached_unit_root()
        except Exception:
            root = target_unit
        try:
            tid = getattr(target_unit, "_id", None)
            rid = getattr(root, "_id", None)
        except Exception:
            tid = getattr(target_unit, "_id", None)
            rid = None
        return bool(self.oathOfMomentTargetUnitId in {tid, rid})

    def can_reroll_hit(self, attacker_unit, target_unit) -> bool:
        if not self._army_has_oath():
            return False
        if not self._unit_is_adeptus_astartes(attacker_unit):
            return False
        return self.is_oath_target(target_unit)

    def wound_bonus_applies(self, attacker_unit, target_unit) -> bool:
        if not self.can_reroll_hit(attacker_unit, target_unit):
            return False
        return self.wound_bonus_enabled()

    def _eligible_enemy_units(self, *, game=None, player=None) -> list:
        if game is None or player is None:
            return []
        try:
            enemy_units = list(game.get_enemy_units(player) or [])
        except Exception:
            enemy_units = []
        if not enemy_units:
            return []
        eligible = []
        seen = set()
        for unit in enemy_units:
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                if bool(getattr(root, "is_embarked", False)):
                    continue
            except Exception:
                pass
            try:
                if getattr(root, "embarked_in", None) is not None:
                    continue
            except Exception:
                pass
            try:
                rid = getattr(root, "_id", None)
            except Exception:
                rid = None
            if not rid or rid in seen:
                continue
            seen.add(rid)
            try:
                if hasattr(root, "is_alive") and callable(root.is_alive) and not root.is_alive():
                    continue
            except Exception:
                pass
            eligible.append(root)
        eligible.sort(key=lambda u: str(getattr(u, "name", "")))
        return eligible

    def get_eligible_enemy_units(self, *, game=None, player=None) -> list:
        return self._eligible_enemy_units(game=game, player=player)

    def _pick_best_target(self, options: list) -> Optional[object]:
        if not options:
            return None

        def _score(u) -> int:
            try:
                return int(u.get_unit_cost())
            except Exception:
                pass
            try:
                return int(getattr(u, "points", 0) or 0)
            except Exception:
                return 0

        return max(options, key=lambda u: (_score(u), str(getattr(u, "name", ""))))

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if self.army is None or player is None:
            return
        try:
            if getattr(player, "get_army", lambda: None)() is not self.army:
                return
        except Exception:
            return

        # Always clear at the start of the Command phase before new selection.
        self.clear_target()

        if not self._army_has_oath():
            return

        options = self._eligible_enemy_units(game=game, player=player)
        if not options:
            return

        is_human = False
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False

        ctx = {
            "ability": "Oath of Moment",
            "options": [str(getattr(u, "name", "") or "") for u in options],
        }
        choice = None
        try:
            choice = player._choose_optional_value("OATH_OF_MOMENT_TARGET", ctx["options"], ctx)
        except Exception:
            choice = None

        selected = None
        if choice in options:
            selected = choice
        elif isinstance(choice, str):
            for u in options:
                if str(getattr(u, "name", "") or "").strip().lower() == choice.strip().lower():
                    selected = u
                    break

        if selected is None:
            if is_human:
                return
            selected = self._pick_best_target(options)

        if selected is not None:
            self.set_target(selected)
