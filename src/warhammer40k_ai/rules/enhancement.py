from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set, Tuple

from .enhancement_effects import (
    EnhancementEffectSpec,
    apply_enhancement_effects,
    parse_enhancement_effects,
)


@dataclass(slots=True)
class Enhancement:
    """
    Rules/metadata container for a Detachment Enhancement (10e).

    Current engine usage:
    - Stored on a Character unit (`Unit.enhancement`)
    - Included in points cost (`Unit.get_unit_cost()`)
    - Displayed in UI panels

    Important: enhancement *rules effects* are not generally executed by the engine yet.
    """

    id: str
    name: str
    faction_id: str
    detachment: str
    detachment_id: str = ""
    points: int = 0
    legend: str = ""
    description: str = ""
    eligible_keywords: Set[str] = field(default_factory=set)
    _effects: Tuple[EnhancementEffectSpec, ...] = field(default_factory=tuple, repr=False)

    @classmethod
    def from_waha_dict(cls, data: dict) -> "Enhancement":
        # Wahapedia enhancements do not provide a structured eligibility keyword list.
        # We keep `eligible_keywords` empty to avoid enforcing incorrect restrictions.
        return cls(
            id=str(data.get("id", "") or ""),
            name=str(data.get("name", "") or ""),
            faction_id=str(data.get("faction_id", "") or ""),
            detachment=str(data.get("detachment", "") or ""),
            detachment_id=str(data.get("detachment_id", "") or ""),
            points=int(data.get("cost", 0) or 0),
            legend=str(data.get("legend", "") or ""),
            description=str(data.get("description", "") or ""),
            eligible_keywords=set(),
            _effects=tuple(parse_enhancement_effects(str(data.get("description", "") or ""))),
        )

    def get_effects(self) -> Tuple[EnhancementEffectSpec, ...]:
        if self._effects:
            return self._effects
        return tuple(parse_enhancement_effects(self.description))

    def apply_to_unit(self, unit) -> None:
        """
        Apply supported enhancement effects to the bearer unit.

        This is intentionally narrow/safe: only a few common patterns are supported,
        and everything else remains "Partial" support.
        """
        try:
            apply_enhancement_effects(unit, list(self.get_effects()))
        except Exception:
            # Never hard-fail list loading / army parsing due to a rules parsing miss.
            pass

        # Custom enhancement hooks (small, explicit support for known rules).
        try:
            if getattr(unit, "special_rules", None) is None:
                unit.special_rules = {}
        except Exception:
            return

        try:
            name = str(getattr(self, "name", "") or "").replace("\u0192?T", "'").strip().lower()
        except Exception:
            name = ""
        try:
            enh_id = str(getattr(self, "id", "") or "").strip()
        except Exception:
            enh_id = ""

        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        ae_mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
        try:
            is_berzerker_warband = bool(we_mgr and we_mgr.is_berzerker_warband())
        except Exception:
            is_berzerker_warband = False
        try:
            is_khorne_daemonkin = bool(we_mgr and we_mgr.is_khorne_daemonkin())
        except Exception:
            is_khorne_daemonkin = False
        try:
            is_warhost = bool(ae_mgr and ae_mgr.is_warhost_detachment())
        except Exception:
            is_warhost = False

        if name == "berzerker glaive" or enh_id == "000008432002":
            if not is_berzerker_warband:
                return
            unit.special_rules["enhancement_melee_attacks_bonus_no_extra_attacks"] = int(
                unit.special_rules.get("enhancement_melee_attacks_bonus_no_extra_attacks", 0) or 0
            ) + 1
            unit.special_rules["enhancement_melee_damage_bonus_no_extra_attacks"] = int(
                unit.special_rules.get("enhancement_melee_damage_bonus_no_extra_attacks", 0) or 0
            ) + 1

        if name == "battle-lust" or enh_id == "000008432005":
            if not is_berzerker_warband:
                return
            unit.special_rules["enhancement_charge_reroll"] = True
            unit.special_rules["enhancement_battle_lust_bonus_if_unbridled"] = 1

        if name == "favoured of khorne" or enh_id == "000008432004":
            if not is_berzerker_warband:
                return
            unit.special_rules["enhancement_favoured_of_khorne_rerolls"] = 2

        if name == "gift of foresight" and enh_id == "000009899004":
            if not is_warhost:
                return
            unit.special_rules["enhancement_free_command_reroll_once_per_battle_round"] = True

        if name == "phoenix gem" or enh_id == "000009899002":
            if not is_warhost:
                return
            unit.special_rules["enhancement_phoenix_gem"] = True

        if name == "psychic destroyer" or enh_id == "000009899005":
            if not is_warhost:
                return
            unit.special_rules["enhancement_psychic_destroyer_damage_bonus"] = int(
                unit.special_rules.get("enhancement_psychic_destroyer_damage_bonus", 0) or 0
            ) + 1

        if name == "blood-forged armour" or enh_id == "000010078003":
            if not is_khorne_daemonkin:
                return
            unit.special_rules["enhancement_blood_forged_armour"] = True

        if name == "icon of war" or enh_id == "000010078002":
            if not is_khorne_daemonkin:
                return
            unit.special_rules["enhancement_icon_of_war"] = True

        if name == "blade of endless bloodshed" or enh_id == "000010078005":
            if not is_khorne_daemonkin:
                return
            unit.special_rules["enhancement_blade_of_endless_bloodshed"] = True

        if name == "disciple of khorne" or enh_id == "000010078004":
            if not is_khorne_daemonkin:
                return
            unit.special_rules["enhancement_disciple_of_khorne"] = True

        if name == "timeless strategist" or enh_id == "000009899003":
            if not is_warhost:
                return
            unit.special_rules["enhancement_timeless_strategist_battle_focus_bonus"] = int(
                unit.special_rules.get("enhancement_timeless_strategist_battle_focus_bonus", 0) or 0
            ) + 1

        if name == "faultless opportunist" or enh_id == "000010002002":
            unit.special_rules["enhancement_faultless_opportunist"] = True

    def __str__(self) -> str:
        return f"{self.name} ({self.points}pts) [{self.faction_id} / {self.detachment}]\n{self.description}"
