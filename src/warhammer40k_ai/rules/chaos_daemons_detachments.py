from __future__ import annotations

import re

from .detachment_manager import DetachmentManagerBase


class ChaosDaemonsDetachmentManager(DetachmentManagerBase):
    faction_id = "CD"
    _SHADOW_LEGION_ALLOWED_HERETIC_ASTARTES_NAMES = {
        "chaos lord",
        "chaos lord in terminator armour",
        "chaos lord with jump pack",
        "chaos terminator squad",
        "chosen",
        "dark apostle",
        "havocs",
        "legionaries",
        "master of possession",
        "possessed",
        "raptors",
        "sorcerer",
        "sorcerer in terminator armour",
        "warp talons",
    }

    @staticmethod
    def _normalize_unit_name(name: str) -> str:
        text = re.sub(r"[^a-z0-9 ]+", " ", str(name or "").lower())
        return re.sub(r"\s+", " ", text).strip()

    def _unit_name_normalized(self, unit) -> str:
        return self._normalize_unit_name(getattr(unit, "name", ""))

    def _iter_army_units(self) -> list:
        return list(getattr(self.army, "units", []) or [])

    def _unit_is_belakor(self, unit) -> bool:
        name_norm = self._unit_name_normalized(unit)
        return "be lakor" in name_norm or "belakor" in name_norm

    def _unit_is_daemon_prince(self, unit) -> bool:
        return "daemon prince" in self._unit_name_normalized(unit)

    def _unit_is_heretic_astartes(self, unit) -> bool:
        return self._unit_has_keyword(unit, "HERETIC ASTARTES")

    def _unit_is_damned(self, unit) -> bool:
        return self._unit_has_keyword(unit, "DAMNED")

    def _unit_is_allowed_shadow_legion_heretic_astartes(self, unit) -> bool:
        if self._unit_is_damned(unit):
            return True
        if not self._unit_is_heretic_astartes(unit):
            return False
        return self._unit_name_normalized(unit) in self._SHADOW_LEGION_ALLOWED_HERETIC_ASTARTES_NAMES

    @staticmethod
    def _shadow_legion_heretic_astartes_points_cap(points_limit: int) -> tuple[int, str]:
        if points_limit <= 1000:
            return 500, "Incursion"
        if points_limit <= 2000:
            return 1000, "Strike Force"
        return 1500, "Onslaught"

    @staticmethod
    def _unit_points(unit) -> int:
        get_cost = getattr(unit, "get_unit_cost", None)
        if callable(get_cost):
            try:
                return int(get_cost() or 0)
            except (TypeError, ValueError):
                return 0
            except AttributeError:
                return 0
        raw = getattr(unit, "points", 0)
        try:
            return int(raw or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _ensure_keyword(unit, keyword: str) -> bool:
        token = str(keyword or "").strip()
        if not token:
            return False
        current = list(getattr(unit, "keywords", []) or [])
        token_lower = token.lower()
        if any(str(value or "").strip().lower() == token_lower for value in current):
            return False
        current.append(token)
        unit.keywords = current
        return True

    @staticmethod
    def _clear_unit_ability_cache(unit) -> None:
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            maybe_root = get_root()
            if maybe_root is not None:
                root = maybe_root
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict):
            cache.clear()

    def apply_shadow_legion_keywords(self, unit=None) -> None:
        if not self.is_shadow_legion_detachment():
            return
        units = [unit] if unit is not None else self._iter_army_units()
        for cur in units:
            if cur is None:
                continue
            changed = False
            if self._unit_is_heretic_astartes(cur) or self._unit_is_belakor(cur):
                changed = self._ensure_keyword(cur, "SHADOW LEGION") or changed
                changed = self._ensure_keyword(cur, "UNDIVIDED") or changed
            if self._unit_has_keyword(cur, "LEGIONES DAEMONICA"):
                changed = self._ensure_keyword(cur, "SHADOW LEGION") or changed
            if changed:
                self._clear_unit_ability_cache(cur)

    def _attached_unit_has_keyword(self, unit, keyword: str) -> bool:
        if unit is None:
            return False
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        members = (
            list(root.get_attached_unit_members() or [])
            if hasattr(root, "get_attached_unit_members")
            else [root]
        )
        for member in members:
            if self._unit_has_keyword(member, keyword):
                return True
        return False

    def is_shadow_legion_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Shadow Legion")

    def is_blood_legion_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Blood Legion")

    def is_legion_of_excess_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Legion of Excess")

    def is_daemonic_incursion_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Daemonic Incursion")

    def is_plague_legion_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Plague Legion")

    def is_scintillating_legion_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Scintillating Legion")

    def first_prince_of_chaos_active(self) -> bool:
        return self.is_shadow_legion_detachment()

    def murdercall_applies(self, unit) -> bool:
        if not self.is_blood_legion_detachment():
            return False
        if unit is None:
            return False
        return bool(
            self._attached_unit_has_keyword(unit, "LEGIONES DAEMONICA")
            and self._attached_unit_has_keyword(unit, "KHORNE")
        )

    def blood_tainted_applies(self, unit) -> bool:
        return self.murdercall_applies(unit)

    def beguiling_aura_applies(self, unit) -> bool:
        if not self.is_legion_of_excess_detachment():
            return False
        if unit is None:
            return False
        return bool(
            self._attached_unit_has_keyword(unit, "LEGIONES DAEMONICA")
            and self._attached_unit_has_keyword(unit, "SLAANESH")
        )

    def seductive_gambit_applies(self, unit) -> bool:
        return self.beguiling_aura_applies(unit)

    def melancholic_miasma_source_applies(self, unit) -> bool:
        if not self.is_plague_legion_detachment():
            return False
        if unit is None:
            return False
        return bool(
            self._attached_unit_has_keyword(unit, "LEGIONES DAEMONICA")
            and self._attached_unit_has_keyword(unit, "NURGLE")
        )

    def validate_detachment_rules(self) -> list[str]:
        errors: list[str] = []
        if not self.is_shadow_legion_detachment():
            return errors
        self.apply_shadow_legion_keywords()
        army = self.army
        if army is None:
            return errors
        cap, size_label = self._shadow_legion_heretic_astartes_points_cap(
            int(getattr(army, "points_limit", 0) or 0)
        )
        allied_points = 0
        for unit in self._iter_army_units():
            if unit is None:
                continue
            unit_name = str(getattr(unit, "name", "") or "Unit").strip() or "Unit"
            if self._unit_is_daemon_prince(unit):
                errors.append(
                    f"Shadow Legion: Thralls of the First Prince forbids Daemon Prince units ('{unit_name}')."
                )
            if bool(getattr(unit, "is_epic_hero", False)) and not self._unit_is_belakor(unit):
                errors.append(
                    f"Shadow Legion: only Be'lakor may be an Epic Hero ('{unit_name}' is not allowed)."
                )
            if self._unit_is_heretic_astartes(unit):
                if not self._unit_is_allowed_shadow_legion_heretic_astartes(unit):
                    errors.append(
                        "Shadow Legion: HERETIC ASTARTES selections must be one of the listed Thralls units "
                        f"or have DAMNED ('{unit_name}' is not allowed)."
                    )
                allied_points += self._unit_points(unit)
                continue
            if self._unit_is_damned(unit):
                allied_points += self._unit_points(unit)
        if allied_points > cap:
            errors.append(
                "Shadow Legion: combined HERETIC ASTARTES/DAMNED points "
                f"({allied_points}) exceed the {size_label} cap of {cap}."
            )
        return errors
