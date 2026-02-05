from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set, Tuple


def _ensure_enhancement_fnp_entry(
    unit,
    value: int,
    *,
    condition: str | None = None,
    source: str | None = None,
    tag: str | None = None,
) -> bool:
    if unit is None:
        return False
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    entries = list(sr.get("enhancement_bearer_fnp_entries", []) or [])
    if tag:
        for entry in entries:
            if isinstance(entry, dict) and entry.get("tag") == tag:
                return False
    entry = {
        "value": int(value),
        "condition": str(condition) if condition else None,
        "source": str(source or "Enhancement"),
        "tag": str(tag or ""),
    }
    entries.append(entry)
    sr["enhancement_bearer_fnp_entries"] = entries
    unit.special_rules = sr
    return True


def _current_unit_wounds(unit) -> int:
    total = 0
    for model in list(getattr(unit, "models", []) or []):
        alive = getattr(model, "is_alive", True)
        try:
            alive = alive() if callable(alive) else bool(alive)
        except Exception:
            alive = True
        if not alive:
            continue
        val = getattr(model, "wounds", None)
        if val is None:
            val = getattr(model, "_wounds", 0)
        try:
            total += int(val or 0)
        except Exception:
            continue
    return total


def maybe_upgrade_adaptive_biology(unit) -> bool:
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict) or not sr.get("enhancement_adaptive_biology"):
        return False
    if sr.get("enhancement_adaptive_biology_upgraded"):
        return False
    starting = int(getattr(unit, "starting_total_wounds", 0) or 0)
    if starting <= 0:
        return False
    current = _current_unit_wounds(unit)
    if current >= starting:
        return False
    _ensure_enhancement_fnp_entry(
        unit,
        4,
        source="Adaptive Biology",
        tag="adaptive_biology_upgrade",
    )
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    sr["enhancement_adaptive_biology_upgraded"] = True
    unit.special_rules = sr
    return True

from .enhancement_effects import (
    EnhancementEffectSpec,
    apply_enhancement_effects,
    normalize_enhancement_token,
    parse_enhancement_eligibility,
    parse_enhancement_effects,
)
from .enhancement_descriptors import get_enhancement_tool_descriptor


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
    eligibility_clause: str = ""
    eligibility_keyword_groups: Tuple[frozenset[str], ...] = field(default_factory=tuple)
    eligibility_name_options: Tuple[str, ...] = field(default_factory=tuple)
    _effects: Tuple[EnhancementEffectSpec, ...] = field(default_factory=tuple, repr=False)

    @classmethod
    def from_waha_dict(cls, data: dict) -> "Enhancement":
        # Wahapedia enhancements do not provide a structured eligibility keyword list.
        # We parse simple "model only" clauses into eligibility groups when possible.
        eligibility = parse_enhancement_eligibility(str(data.get("description", "") or ""))
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
            eligibility_clause=str(getattr(eligibility, "clause", "") or ""),
            eligibility_keyword_groups=tuple(getattr(eligibility, "keyword_groups", ()) or ()),
            eligibility_name_options=tuple(getattr(eligibility, "name_options", ()) or ()),
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
            name = (
                str(getattr(self, "name", "") or "")
                .replace("\u2019", "'")
                .replace("\u2018", "'")
                .replace("\u0192?T", "'")
                .strip()
                .lower()
            )
        except Exception:
            name = ""
        try:
            enh_id = str(getattr(self, "id", "") or "").strip()
        except Exception:
            enh_id = ""

        try:
            for eff in self.get_effects():
                if eff.kind == "bearer_fnp" and eff.supported:
                    tag = f"enhancement_fnp_{enh_id or name}"
                    _ensure_enhancement_fnp_entry(
                        unit,
                        int(eff.value),
                        source=str(getattr(self, "name", "") or "Enhancement"),
                        tag=tag,
                    )
        except Exception:
            pass

        try:
            if hasattr(unit, "_refresh_targeted_stratagem_cp_increase_flags"):
                unit._refresh_targeted_stratagem_cp_increase_flags()
        except Exception:
            pass

        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        ae_mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
        dg_mgr = getattr(army, "death_guard_detachments", None) if army is not None else None
        ac_mgr = getattr(army, "adeptus_custodes_detachments", None) if army is not None else None
        orks_mgr = getattr(army, "orks_detachments", None) if army is not None else None
        cd_mgr = getattr(army, "chaos_daemons_detachments", None) if army is not None else None
        try:
            is_berzerker_warband = bool(we_mgr and we_mgr.is_berzerker_warband())
        except Exception:
            is_berzerker_warband = False
        try:
            is_khorne_daemonkin = bool(we_mgr and we_mgr.is_khorne_daemonkin())
        except Exception:
            is_khorne_daemonkin = False
        try:
            is_goretrack_onslaught = bool(we_mgr and we_mgr.is_goretrack_onslaught())
        except Exception:
            is_goretrack_onslaught = False
        try:
            is_warhost = bool(ae_mgr and ae_mgr.is_warhost_detachment())
        except Exception:
            is_warhost = False
        try:
            is_armoured_warhost = bool(ae_mgr and ae_mgr.is_armoured_warhost())
        except Exception:
            is_armoured_warhost = False
        try:
            is_aspect_host = bool(ae_mgr and ae_mgr.is_aspect_host())
        except Exception:
            is_aspect_host = False
        try:
            is_virulent_vectorium = bool(dg_mgr and dg_mgr.is_virulent_vectorium())
        except Exception:
            is_virulent_vectorium = False
        is_lions = bool(ac_mgr and ac_mgr.is_lions_of_the_emperor())
        try:
            is_war_horde = bool(orks_mgr and orks_mgr.is_war_horde())
        except Exception:
            is_war_horde = False
        try:
            is_daemonic_incursion = bool(cd_mgr and cd_mgr.is_daemonic_incursion_detachment())
        except Exception:
            is_daemonic_incursion = False
        try:
            is_plague_legion = bool(cd_mgr and cd_mgr.is_plague_legion_detachment())
        except Exception:
            is_plague_legion = False
        ck_mgr = getattr(army, "chaos_knights_detachments", None) if army is not None else None
        try:
            is_infernal_lance = bool(ck_mgr and ck_mgr.is_infernal_lance())
        except Exception:
            is_infernal_lance = False

        bearer = None
        bearer_id = ""
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            bearer = get_bearer()
            if bearer is not None:
                bearer_id = str(getattr(bearer, "id", getattr(bearer, "_id", "")) or "")

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

        if name == "murderous onslaught" or enh_id == "000010086002":
            if not is_goretrack_onslaught:
                return
            unit.special_rules["enhancement_murderous_onslaught"] = True

        if name == "aggressive deployment" or enh_id == "000010086003":
            if not is_goretrack_onslaught:
                return
            unit.special_rules["enhancement_aggressive_deployment"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            if desc is not None:
                scouts_distance = float(desc.effect_params.get("scouts_distance", 0) or 0)
                if scouts_distance > 0:
                    unit.special_rules["enhancement_aggressive_deployment_scouts_distance"] = scouts_distance

        if name == "unleash hell" or enh_id == "000010086004":
            if not is_goretrack_onslaught:
                return
            unit.special_rules["enhancement_unleash_hell"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "infernal infusion" or enh_id == "000010086005":
            if not is_goretrack_onslaught:
                return
            unit.special_rules["enhancement_infernal_infusion"] = True

        if name == "carmine reliquary" or enh_id == "000010645002":
            unit.special_rules["enhancement_carmine_reliquary"] = True
            unit.special_rules["enhancement_scout_distance"] = max(
                int(unit.special_rules.get("enhancement_scout_distance", 0) or 0),
                6,
            )

        if name == "angel's fang" or enh_id == "000010645005":
            unit.special_rules["enhancement_angels_fang"] = True

        if name == "timeless strategist" or enh_id == "000009899003":
            if not is_warhost:
                return
            unit.special_rules["enhancement_timeless_strategist_battle_focus_bonus"] = int(
                unit.special_rules.get("enhancement_timeless_strategist_battle_focus_bonus", 0) or 0
            ) + 1

        if name == "guiding presence" or enh_id == "000009769002":
            if not is_armoured_warhost:
                return
            unit.special_rules["enhancement_guiding_presence"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "harmonisation matrix" or enh_id == "000009769003":
            if not is_armoured_warhost:
                return
            unit.special_rules["enhancement_harmonisation_matrix"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "spirit stone of raelyth" or enh_id == "000009769004":
            if not is_armoured_warhost:
                return
            unit.special_rules["enhancement_spirit_stone_of_raelyth"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "guileful strategist" or enh_id == "000009769005":
            if not is_armoured_warhost:
                return
            unit.special_rules["enhancement_guileful_strategist"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "aspect of murder" or enh_id == "000009927002":
            if not is_aspect_host:
                return
            unit.special_rules["enhancement_aspect_of_murder"] = True
            unit.special_rules["enhancement_bearer_melee_damage_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_damage_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_melee_precision"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "mantle of wisdom" or enh_id == "000009927003":
            if not is_aspect_host:
                return
            unit.special_rules["enhancement_mantle_of_wisdom"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "shimmerstone" or enh_id == "000009927004":
            if not is_aspect_host:
                return
            unit.special_rules["enhancement_shimmerstone"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "strategic savant" or enh_id == "000009927005":
            if not is_aspect_host:
                return
            unit.special_rules["enhancement_strategic_savant"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "faultless opportunist" or enh_id == "000010002002":
            unit.special_rules["enhancement_faultless_opportunist"] = True

        if name == "rise to the challenge" or enh_id == "000010002005":
            unit.special_rules["enhancement_rise_to_challenge"] = True

        if name == "adaptive biology" or enh_id == "000008348005":
            unit.special_rules["enhancement_adaptive_biology"] = True
            _ensure_enhancement_fnp_entry(
                unit,
                5,
                source="Adaptive Biology",
                tag="adaptive_biology_base",
            )

        if name == "a'rgath, the king of blades" or enh_id == "000008438002":
            if not is_daemonic_incursion:
                return
            unit.special_rules["enhancement_argath_king_of_blades"] = True
            unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_melee_attacks_bonus_shadow_extra"] = int(
                unit.special_rules.get("enhancement_bearer_melee_attacks_bonus_shadow_extra", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_melee_strength_bonus_shadow_extra"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus_shadow_extra", 0) or 0
            ) + 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "soulstealer" or enh_id == "000008438003":
            if not is_daemonic_incursion:
                return
            unit.special_rules["enhancement_soulstealer"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "the endless gift" or enh_id == "000008438004":
            if not is_daemonic_incursion:
                return
            unit.special_rules["enhancement_endless_gift"] = True

        if name == "the everstave" or enh_id == "000008438005":
            if not is_daemonic_incursion:
                return
            unit.special_rules["enhancement_everstave"] = True
            unit.special_rules["enhancement_bearer_ranged_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_ranged_strength_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_ranged_range_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_ranged_range_bonus", 0) or 0
            ) + 3
            unit.special_rules["enhancement_bearer_ranged_strength_bonus_shadow_extra"] = int(
                unit.special_rules.get("enhancement_bearer_ranged_strength_bonus_shadow_extra", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_ranged_range_bonus_shadow_extra"] = int(
                unit.special_rules.get("enhancement_bearer_ranged_range_bonus_shadow_extra", 0) or 0
            ) + 3
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "cankerblight" or enh_id == "000009819002":
            if not is_plague_legion:
                return
            unit.special_rules["enhancement_cankerblight"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "maggot maws" or enh_id == "000009819003":
            if not is_plague_legion:
                return
            unit.special_rules["enhancement_maggot_maws"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "daemon weapon of nurgle" or enh_id == "000010123002":
            if not is_virulent_vectorium:
                return
            unit.special_rules["enhancement_daemon_weapon_of_nurgle"] = True

        if name == "furnace of plagues" or enh_id == "000010123003":
            if not is_virulent_vectorium:
                return
            unit.special_rules["enhancement_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_melee_strength_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_melee_attacks_bonus"] = int(
                unit.special_rules.get("enhancement_melee_attacks_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_furnace_of_plagues"] = True

        if name == "arch contaminator" or enh_id == "000010123004":
            if not is_virulent_vectorium:
                return
            unit.special_rules["enhancement_arch_contaminator"] = True

        if name == "revolting regeneration" or enh_id == "000010123005":
            if not is_virulent_vectorium:
                return
            unit.special_rules["enhancement_revolting_regeneration"] = True
            _ensure_enhancement_fnp_entry(
                unit,
                5,
                source="Revolting Regeneration",
                tag="revolting_regeneration",
            )

        if name == "superior creation" or enh_id == "000009987002":
            if not is_lions:
                return
            unit.special_rules["enhancement_superior_creation"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
            refresh_return = getattr(unit, "_refresh_return_on_death_flags", None)
            if callable(refresh_return):
                refresh_return()

        if name == "praesidius" or enh_id == "000009987003":
            if not is_lions:
                return
            unit.special_rules["enhancement_praesidius_lone_operative"] = True
            unit.special_rules["enhancement_praesidius_stealth"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "fierce conqueror" or enh_id == "000009987004":
            if not is_lions:
                return
            unit.special_rules["enhancement_fierce_conqueror"] = True
            if bearer_id:
                unit.special_rules["enhancement_fierce_conqueror_bearer_id"] = bearer_id
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "admonimortis" or enh_id == "000009987005":
            if not is_lions:
                return
            unit.special_rules["enhancement_admonimortis"] = True
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0
            ) + 3
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_melee_damage_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_damage_bonus", 0) or 0
            ) + 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "follow me ladz" or enh_id == "000008367002":
            if not is_war_horde:
                return
            unit.special_rules["enhancement_follow_me_ladz"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "headwoppa's killchoppa" or enh_id == "000008367003":
            if not is_war_horde:
                return
            unit.special_rules["enhancement_headwoppas_killchoppa"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "kunnin' but brutal" or enh_id == "000008367004":
            if not is_war_horde:
                return
            unit.special_rules["enhancement_kunnin_but_brutal"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "supa-cybork body" or enh_id == "000008367005":
            if not is_war_horde:
                return
            unit.special_rules["enhancement_supa_cybork_body"] = True
            _ensure_enhancement_fnp_entry(
                unit,
                4,
                source="Supa-Cybork Body",
                tag="supa_cybork_body",
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "knight diabolus" or enh_id == "000010304002":
            if not is_infernal_lance:
                return
            unit.special_rules["enhancement_knight_diabolus"] = True
            unit.special_rules["enhancement_knight_diabolus_ws_bonus"] = 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "blasphemous engine" or enh_id == "000010304003":
            if not is_infernal_lance:
                return
            unit.special_rules["enhancement_blasphemous_engine"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "fleshmetal fusion" or enh_id == "000010304004":
            if not is_infernal_lance:
                return
            unit.special_rules["enhancement_fleshmetal_fusion"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
            if bearer is not None:
                try:
                    bearer._base_toughness = int(getattr(bearer, "_base_toughness", 0)) + 1
                    bearer._toughness = int(getattr(bearer, "_toughness", 0)) + 1
                except Exception:
                    pass

        if name == "bestial aspect" or enh_id == "000010304005":
            if not is_infernal_lance:
                return
            unit.special_rules["enhancement_bestial_aspect"] = True
            unit.special_rules["bearer_unit_assault_ranged"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        invalidate_fn = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_fn):
            invalidate_fn()
        refresh_fn = getattr(unit, "_refresh_bearer_unit_common_modifiers", None)
        if callable(refresh_fn):
            refresh_fn()

    def is_unit_eligible(self, unit) -> bool:
        if not self.eligibility_keyword_groups and not self.eligibility_name_options:
            return True
        try:
            unit_name = normalize_enhancement_token(getattr(unit, "name", "") or "")
        except Exception:
            unit_name = ""
        if unit_name and unit_name in set(self.eligibility_name_options or ()):
            return True

        keywords = []
        get_effective = getattr(unit, "get_effective_keywords", None)
        if callable(get_effective):
            keywords.extend(list(get_effective() or []))
        else:
            keywords.extend(list(getattr(unit, "keywords", []) or []))
        get_effective_faction = getattr(unit, "get_effective_faction_keywords", None)
        if callable(get_effective_faction):
            keywords.extend(list(get_effective_faction() or []))
        else:
            keywords.extend(list(getattr(unit, "faction_keywords", []) or []))

        norm_keywords = {normalize_enhancement_token(k) for k in keywords if str(k or "").strip()}
        for group in self.eligibility_keyword_groups or ():
            if not group:
                continue
            if set(group).issubset(norm_keywords):
                return True
        return False

    def __str__(self) -> str:
        return f"{self.name} ({self.points}pts) [{self.faction_id} / {self.detachment}]\n{self.description}"
