from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set, Tuple
import re


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


def _normalize_weapon_name_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _weapon_name_matches(unit, expected_name: str, candidate_name: str) -> bool:
    expected = str(expected_name or "").strip()
    candidate = str(candidate_name or "").strip()
    if not expected or not candidate:
        return False
    if unit is not None and hasattr(unit, "_weapon_name_matches"):
        return bool(unit._weapon_name_matches([expected], candidate))
    exp_key = _normalize_weapon_name_key(expected)
    cand_key = _normalize_weapon_name_key(candidate)
    return bool(exp_key and cand_key and (exp_key == cand_key or exp_key in cand_key or cand_key in exp_key))


def _select_bearer_weapon(unit, bearer, *, weapon_name: str, require_ranged: bool) -> tuple[str, int]:
    if bearer is None:
        return "", -1
    desired_name = str(weapon_name or "").strip()
    for idx, wargear in enumerate(list(getattr(bearer, "wargear", []) or [])):
        if wargear is None:
            continue
        if require_ranged:
            is_ranged = getattr(wargear, "is_ranged", None)
            if not callable(is_ranged) or not bool(is_ranged()):
                continue
        name = str(getattr(wargear, "name", "") or "").strip()
        if not name:
            continue
        if desired_name and not _weapon_name_matches(unit, desired_name, name):
            continue
        return name, int(idx)
    return "", -1


def _coerce_int(value, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _descriptor_params(desc) -> dict:
    raw_params = getattr(desc, "effect_params", {}) if desc is not None else {}
    if isinstance(raw_params, dict):
        return dict(raw_params)
    try:
        return dict(raw_params or {})
    except (TypeError, ValueError):
        return {}


def _apply_selected_ranged_weapon_bonus_enhancement(
    unit,
    *,
    special_rule_flag: str,
    descriptor_params: dict,
    bearer,
    bearer_id: str,
    default_weapon_name: str,
    default_attacks_bonus: int,
    default_strength_bonus: int,
    default_ap_bonus: int,
    default_damage_bonus: int,
    source_name: str,
) -> None:
    unit.special_rules[str(special_rule_flag)] = True
    selected_weapon_name = str(descriptor_params.get("weapon_name", default_weapon_name) or default_weapon_name).strip()
    selected_weapon_slot = -1
    if bearer is not None:
        chosen_name, chosen_slot = _select_bearer_weapon(
            unit,
            bearer,
            weapon_name=selected_weapon_name,
            require_ranged=True,
        )
        if chosen_name:
            selected_weapon_name = chosen_name
        selected_weapon_slot = int(chosen_slot)
    attacks_bonus = _coerce_int(
        descriptor_params.get("attacks_bonus", default_attacks_bonus) or default_attacks_bonus,
        default=default_attacks_bonus,
    )
    strength_bonus = _coerce_int(
        descriptor_params.get("strength_bonus", default_strength_bonus) or default_strength_bonus,
        default=default_strength_bonus,
    )
    ap_bonus = _coerce_int(
        descriptor_params.get("ap_bonus", default_ap_bonus) or default_ap_bonus,
        default=default_ap_bonus,
    )
    damage_bonus = _coerce_int(
        descriptor_params.get("damage_bonus", default_damage_bonus) or default_damage_bonus,
        default=default_damage_bonus,
    )

    prefix = str(special_rule_flag)
    unit.special_rules[f"{prefix}_weapon_name"] = selected_weapon_name
    unit.special_rules[f"{prefix}_weapon_slot_index"] = int(selected_weapon_slot)
    unit.special_rules[f"{prefix}_attacks_bonus"] = int(max(0, attacks_bonus))
    unit.special_rules[f"{prefix}_strength_bonus"] = int(max(0, strength_bonus))
    unit.special_rules[f"{prefix}_ap_bonus"] = int(max(0, ap_bonus))
    unit.special_rules[f"{prefix}_damage_bonus"] = int(max(0, damage_bonus))
    unit.special_rules[f"{prefix}_source"] = str(source_name or "Enhancement").strip() or "Enhancement"
    if bearer_id:
        unit.special_rules["enhancement_bearer_model_id"] = bearer_id

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
        as_mgr = getattr(army, "adepta_sororitas_detachments", None) if army is not None else None
        orks_mgr = getattr(army, "orks_detachments", None) if army is not None else None
        cd_mgr = getattr(army, "chaos_daemons_detachments", None) if army is not None else None
        csm_mgr = getattr(army, "chaos_space_marines_detachments", None) if army is not None else None
        lov_mgr = getattr(army, "leagues_of_votann_detachments", None) if army is not None else None
        tau_mgr = getattr(army, "tau_empire_detachments", None) if army is not None else None
        ec_mgr = getattr(army, "emperors_children_detachments", None) if army is not None else None
        if ec_mgr is None and army is not None:
            ec_mgr = getattr(army, "emperors_children", None)
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
            is_cult_of_blood = bool(we_mgr and we_mgr.is_cult_of_blood())
        except Exception:
            is_cult_of_blood = False
        try:
            is_possessed_slaughterband = bool(we_mgr and we_mgr.is_possessed_slaughterband())
        except Exception:
            is_possessed_slaughterband = False
        try:
            is_vessels_of_wrath = bool(we_mgr and we_mgr.is_vessels_of_wrath())
        except Exception:
            is_vessels_of_wrath = False
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
            is_guardian_battlehost = bool(ae_mgr and ae_mgr.is_guardian_battlehost())
        except Exception:
            is_guardian_battlehost = False
        try:
            is_virulent_vectorium = bool(dg_mgr and dg_mgr.is_virulent_vectorium())
        except Exception:
            is_virulent_vectorium = False
        try:
            is_hallowed_martyrs = bool(as_mgr and as_mgr.is_hallowed_martyrs())
        except Exception:
            is_hallowed_martyrs = False
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
        try:
            is_scintillating_legion = bool(cd_mgr and cd_mgr.is_scintillating_legion_detachment())
        except Exception:
            is_scintillating_legion = False
        try:
            is_cabal_of_chaos = bool(csm_mgr and csm_mgr.is_cabal_of_chaos())
        except Exception:
            is_cabal_of_chaos = False
        try:
            is_hearthband = bool(lov_mgr and lov_mgr.is_hearthband())
        except Exception:
            is_hearthband = False
        try:
            is_needgaard_oathband = bool(lov_mgr and lov_mgr.is_needgaard_oathband())
        except Exception:
            is_needgaard_oathband = False
        try:
            is_experimental_prototype_cadre = bool(tau_mgr and tau_mgr.is_experimental_prototype_cadre())
        except Exception:
            is_experimental_prototype_cadre = False
        try:
            is_coterie_of_conceited = bool(ec_mgr and ec_mgr.is_coterie_of_conceited())
        except Exception:
            is_coterie_of_conceited = False
        try:
            is_carnival_of_excess = bool(ec_mgr and ec_mgr.is_carnival_of_excess())
        except Exception:
            is_carnival_of_excess = False
        try:
            is_court_of_the_phoenician = bool(ec_mgr and ec_mgr.is_court_of_the_phoenician())
        except Exception:
            is_court_of_the_phoenician = False
        try:
            is_mercurial_host = bool(ec_mgr and ec_mgr.is_mercurial_host())
        except Exception:
            is_mercurial_host = False
        try:
            is_rapid_evisceration = bool(ec_mgr and ec_mgr.is_rapid_evisceration())
        except Exception:
            is_rapid_evisceration = False
        try:
            is_slaaneshs_chosen = bool(ec_mgr and ec_mgr.is_slaaneshs_chosen())
        except Exception:
            is_slaaneshs_chosen = False
        is_court_or_mercurial_host = bool(is_court_of_the_phoenician or is_mercurial_host)
        am_mgr = getattr(army, "astra_militarum_detachments", None) if army is not None else None
        try:
            is_grizzled_company = bool(am_mgr and am_mgr.is_grizzled_company())
        except Exception:
            is_grizzled_company = False
        ck_mgr = getattr(army, "chaos_knights_detachments", None) if army is not None else None
        try:
            is_infernal_lance = bool(ck_mgr and ck_mgr.is_infernal_lance())
        except Exception:
            is_infernal_lance = False
        gk_mgr = getattr(army, "grey_knights_detachments", None) if army is not None else None
        try:
            is_warpbane_task_force = bool(gk_mgr and gk_mgr.is_warpbane_task_force())
        except Exception:
            is_warpbane_task_force = False
        dru_mgr = getattr(army, "drukhari_detachments", None) if army is not None else None
        try:
            is_spectacle_of_spite = bool(dru_mgr and dru_mgr.is_spectacle_of_spite())
        except Exception:
            is_spectacle_of_spite = False
        ts_mgr = getattr(army, "thousand_sons_detachments", None) if army is not None else None
        try:
            is_grand_coven = bool(ts_mgr and ts_mgr.is_grand_coven())
        except Exception:
            is_grand_coven = False
        try:
            is_rubricae_phalanx = bool(ts_mgr and ts_mgr.is_rubricae_phalanx())
        except Exception:
            is_rubricae_phalanx = False

        bearer = None
        bearer_id = ""
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            bearer = get_bearer()
            if bearer is not None:
                bearer_id = str(getattr(bearer, "id", getattr(bearer, "_id", "")) or "")

        if name == "supernova launcher" or enh_id == "000009983002":
            if not is_experimental_prototype_cadre:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            _apply_selected_ranged_weapon_bonus_enhancement(
                unit,
                special_rule_flag="enhancement_supernova_launcher",
                descriptor_params=params,
                bearer=bearer,
                bearer_id=bearer_id,
                default_weapon_name="airbursting fragmentation projector",
                default_attacks_bonus=0,
                default_strength_bonus=3,
                default_ap_bonus=1,
                default_damage_bonus=1,
                source_name="Supernova Launcher",
            )

        if name == "thermoneutronic projector" or enh_id == "000009983003":
            if not is_experimental_prototype_cadre:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            _apply_selected_ranged_weapon_bonus_enhancement(
                unit,
                special_rule_flag="enhancement_thermoneutronic_projector",
                descriptor_params=params,
                bearer=bearer,
                bearer_id=bearer_id,
                default_weapon_name="t'au flamer",
                default_attacks_bonus=0,
                default_strength_bonus=2,
                default_ap_bonus=1,
                default_damage_bonus=1,
                source_name="Thermoneutronic Projector",
            )

        if name == "plasma accelerator rifle" or enh_id == "000009983004":
            if not is_experimental_prototype_cadre:
                return
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            params = _descriptor_params(desc)
            _apply_selected_ranged_weapon_bonus_enhancement(
                unit,
                special_rule_flag="enhancement_plasma_accelerator_rifle",
                descriptor_params=params,
                bearer=bearer,
                bearer_id=bearer_id,
                default_weapon_name="plasma rifle",
                default_attacks_bonus=1,
                default_strength_bonus=2,
                default_ap_bonus=1,
                default_damage_bonus=1,
                source_name="Plasma Accelerator Rifle",
            )

        if name == "saintly example" or enh_id == "000008470002":
            if not is_hallowed_martyrs:
                return
            unit.special_rules["enhancement_saintly_example"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "through suffering, strength" or enh_id == "000008470003":
            if not is_hallowed_martyrs:
                return
            unit.special_rules["enhancement_through_suffering_strength"] = True
            unit.special_rules["enhancement_through_suffering_base_bonus"] = 1
            unit.special_rules["enhancement_through_suffering_wounded_bonus"] = 2
            # Generic parser support applies a unit-wide +1 A/S/D for this text; replace that
            # with bearer-specific runtime handling for the conditional +1/+2 effect.
            for key in (
                "enhancement_melee_attacks_bonus",
                "enhancement_melee_strength_bonus",
                "enhancement_melee_damage_bonus",
            ):
                current = int(unit.special_rules.get(key, 0) or 0)
                if current > 0:
                    unit.special_rules[key] = current - 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "chaplet of sacrifice" or enh_id == "000008470004":
            if not is_hallowed_martyrs:
                return
            unit.special_rules["enhancement_chaplet_of_sacrifice"] = True
            unit.special_rules["enhancement_chaplet_of_sacrifice_max_rerolls"] = 1
            unit.special_rules["enhancement_chaplet_of_sacrifice_max_rerolls_damaged"] = 3
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "mantle of ophelia" or enh_id == "000008470005":
            if not is_hallowed_martyrs:
                return
            unit.special_rules["enhancement_mantle_of_ophelia"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "abhuman detail" or enh_id == "000010637002":
            if not is_grizzled_company:
                return
            unit.special_rules["enhancement_abhuman_detail"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            extra_keywords = [
                str(v or "").strip().upper()
                for v in list(params.get("order_target_keyword_add", ("OGRYN",)) or ())
                if str(v or "").strip()
            ]
            extra_names = [
                str(v or "").strip()
                for v in list(params.get("attachment_override_unit_names_any", ("Ogryn Squad", "Bullgryn Squad")) or ())
                if str(v or "").strip()
            ]
            if extra_keywords:
                unit.special_rules["enhancement_abhuman_detail_order_target_keywords"] = extra_keywords
            if extra_names:
                unit.special_rules["enhancement_abhuman_detail_attach_unit_names"] = extra_names
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "aquilan eye" or enh_id == "000010637003":
            if not is_grizzled_company:
                return
            unit.special_rules["enhancement_aquilan_eye"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            order_key = str(params.get("extra_order_key", "TARGET_WEAK_SPOT") or "TARGET_WEAK_SPOT").strip().upper()
            try:
                ap_bonus = int(params.get("extra_order_ap_bonus", 1) or 1)
            except Exception:
                ap_bonus = 1
            try:
                order_range = float(params.get("extra_order_range", 12.0) or 12.0)
            except Exception:
                order_range = 12.0
            unit.special_rules["enhancement_aquilan_eye_order_key"] = order_key
            unit.special_rules["enhancement_aquilan_eye_ap_bonus"] = int(max(0, ap_bonus))
            unit.special_rules["enhancement_aquilan_eye_order_range"] = float(max(0.0, order_range))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "spec ops veteran" or enh_id == "000010637004":
            if not is_grizzled_company:
                return
            unit.special_rules["enhancement_spec_ops_veteran"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            order_key = str(params.get("extra_order_key", "MOVE_TO_SHADOWS") or "MOVE_TO_SHADOWS").strip().upper()
            unit.special_rules["enhancement_spec_ops_veteran_order_key"] = order_key
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "laud hailer" or enh_id == "000010637005":
            if not is_grizzled_company:
                return
            unit.special_rules["enhancement_laud_hailer"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            try:
                order_range = float(params.get("order_range", 12.0) or 12.0)
            except Exception:
                order_range = 12.0
            unit.special_rules["enhancement_laud_hailer_order_range"] = float(max(0.0, order_range))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

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

        if name == "craftworld's champion" or enh_id == "000009911002":
            if not is_guardian_battlehost:
                return
            unit.special_rules["enhancement_craftworlds_champion"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            try:
                oc_value = int(params.get("objective_control", 5) or 5)
            except Exception:
                oc_value = 5
            unit.special_rules["enhancement_craftworlds_champion_objective_control"] = int(max(1, oc_value))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "ethereal pathway" or enh_id == "000009911003":
            if not is_guardian_battlehost:
                return
            unit.special_rules["enhancement_ethereal_pathway"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "protector of the paths" or enh_id == "000009911004":
            if not is_guardian_battlehost:
                return
            unit.special_rules["enhancement_protector_of_paths"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            try:
                base_threshold = int(params.get("base_overwatch_hit_threshold", 5) or 5)
            except Exception:
                base_threshold = 5
            try:
                controlled_threshold = int(params.get("controlled_objective_hit_threshold", 4) or 4)
            except Exception:
                controlled_threshold = 4
            unit.special_rules["enhancement_protector_of_paths_base_threshold"] = int(max(2, base_threshold))
            unit.special_rules["enhancement_protector_of_paths_controlled_threshold"] = int(max(2, controlled_threshold))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "breath of vaul" or enh_id == "000009911005":
            if not is_guardian_battlehost:
                return
            unit.special_rules["enhancement_breath_of_vaul"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            flamer_names = tuple(str(v or "").strip() for v in list(params.get("flamer_weapon_names", ("flamer",))) if str(v or "").strip())
            fusion_names = tuple(str(v or "").strip() for v in list(params.get("fusion_weapon_names", ("fusion gun",))) if str(v or "").strip())
            if flamer_names:
                unit.special_rules["enhancement_breath_of_vaul_flamer_weapon_names"] = list(flamer_names)
            if fusion_names:
                unit.special_rules["enhancement_breath_of_vaul_fusion_weapon_names"] = list(fusion_names)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "lord of forbidden lore" or enh_id == "000010193002":
            if not is_grand_coven:
                return
            unit.special_rules["enhancement_lord_of_forbidden_lore"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "incandaeum" or enh_id == "000010193003":
            if not is_grand_coven:
                return
            unit.special_rules["enhancement_incandaeum"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "umbralefic crystal" or enh_id == "000010193004":
            if not is_grand_coven:
                return
            unit.special_rules["enhancement_umbralefic_crystal"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "eldritch vortex of e'taph" or enh_id == "000010193005":
            if not is_grand_coven:
                return
            unit.special_rules["enhancement_eldritch_vortex_of_etaph"] = True
            unit.special_rules["enhancement_bearer_psychic_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_psychic_strength_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_psychic_damage_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_psychic_damage_bonus", 0) or 0
            ) + 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "risen rubricae" or enh_id == "000010205002":
            if not is_rubricae_phalanx:
                return
            unit.special_rules["enhancement_risen_rubricae"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "arcane thralls (aura)" or enh_id == "000010205003":
            if not is_rubricae_phalanx:
                return
            unit.special_rules["enhancement_arcane_thralls"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "lord of the rubricae" or enh_id == "000010205004":
            if not is_rubricae_phalanx:
                return
            unit.special_rules["enhancement_lord_of_the_rubricae"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "the stave abominus" or enh_id == "000010205005":
            if not is_rubricae_phalanx:
                return
            unit.special_rules["enhancement_the_stave_abominus"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "pharmacophex" or enh_id == "000010580002":
            if not is_spectacle_of_spite:
                return
            unit.special_rules["enhancement_pharmacophex"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "chronoshard" or enh_id == "000010580003":
            if not is_spectacle_of_spite:
                return
            unit.special_rules["enhancement_chronoshard"] = True
            unit.special_rules["enhancement_fight_first_once_per_battle"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "periapt of torments" or enh_id == "000010580004":
            if not is_spectacle_of_spite:
                return
            unit.special_rules["enhancement_periapt_of_torments"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "morghenna's curse" or enh_id == "000010580005":
            if not is_spectacle_of_spite:
                return
            unit.special_rules["enhancement_morghennas_curse"] = True
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_melee_damage_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_damage_bonus", 0) or 0
            ) + 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "touched by the warp" or enh_id == "000010151002":
            if not is_cabal_of_chaos:
                return
            unit.special_rules["enhancement_touched_by_the_warp"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
            if bearer is not None:
                try:
                    keywords = list(getattr(bearer, "keywords", []) or [])
                    if "psyker" not in {str(k or "").strip().lower() for k in keywords}:
                        keywords.append("PSYKER")
                        bearer.keywords = keywords
                except Exception:
                    pass

        if name == "eyes of z'desh" or name == "eyes of z’desh" or enh_id == "000010151003":
            if not is_cabal_of_chaos:
                return
            unit.special_rules["enhancement_eyes_of_zdesh"] = True
            unit.special_rules["enhancement_scout_distance"] = max(
                int(unit.special_rules.get("enhancement_scout_distance", 0) or 0),
                6,
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "mind blade" or enh_id == "000010151004":
            if not is_cabal_of_chaos:
                return
            unit.special_rules["enhancement_mind_blade"] = True
            unit.special_rules["enhancement_mind_blade_source"] = "Mind Blade"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "infernal avatar" or enh_id == "000010151005":
            if not is_cabal_of_chaos:
                return
            unit.special_rules["enhancement_infernal_avatar"] = True
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0
            ) + 2
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0) or 0
            ) + 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

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

        if name == "chosen of the blood god" or enh_id == "000010074002":
            if not is_cult_of_blood:
                return
            unit.special_rules["enhancement_chosen_of_blood_god"] = True
            unit.special_rules["enhancement_chosen_of_blood_god_aura_range_bonus"] = int(
                unit.special_rules.get("enhancement_chosen_of_blood_god_aura_range_bonus", 0) or 0
            ) + 3
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "butcher lord" or enh_id == "000010074003":
            if not is_cult_of_blood:
                return
            unit.special_rules["enhancement_butcher_lord"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "brazen form" or enh_id == "000010074004":
            if not is_cult_of_blood:
                return
            unit.special_rules["enhancement_brazen_form"] = True
            _ensure_enhancement_fnp_entry(
                unit,
                5,
                source="Brazen Form",
                tag="brazen_form",
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
            if bearer is not None:
                try:
                    bearer._base_toughness = int(getattr(bearer, "_base_toughness", 0)) + 1
                    bearer._toughness = int(getattr(bearer, "_toughness", 0)) + 1
                except Exception:
                    pass

        if name == "strategic slaughter" or enh_id == "000010074005":
            if not is_cult_of_blood:
                return
            unit.special_rules["enhancement_strategic_slaughter"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "malicious vigour" or enh_id == "000010082002":
            if not is_possessed_slaughterband:
                return
            unit.special_rules["enhancement_malicious_vigour"] = True
            unit.special_rules["enhancement_malicious_vigour_brazen_fury_distance"] = int(
                unit.special_rules.get("enhancement_malicious_vigour_brazen_fury_distance", 0) or 6
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "killing clarity" or enh_id == "000010082003":
            if not is_possessed_slaughterband:
                return
            unit.special_rules["enhancement_killing_clarity"] = True
            unit.special_rules["enhancement_killing_clarity_success_on"] = int(
                unit.special_rules.get("enhancement_killing_clarity_success_on", 0) or 4
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "frenzied focus" or enh_id == "000010082004":
            if not is_possessed_slaughterband:
                return
            unit.special_rules["enhancement_frenzied_focus"] = True
            unit.special_rules["enhancement_frenzied_focus_crit_hit_threshold"] = int(
                unit.special_rules.get("enhancement_frenzied_focus_crit_hit_threshold", 0) or 5
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "violent demise" or enh_id == "000010082005":
            if not is_possessed_slaughterband:
                return
            unit.special_rules["enhancement_violent_demise"] = True
            unit.special_rules["enhancement_violent_demise_trigger_threshold"] = int(
                unit.special_rules.get("enhancement_violent_demise_trigger_threshold", 0) or 2
            )
            unit.special_rules["enhancement_violent_demise_damage_dice"] = str(
                unit.special_rules.get("enhancement_violent_demise_damage_dice", "") or "D3+1"
            )
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "archslaughterer" or enh_id == "000009847002":
            if not is_vessels_of_wrath:
                return
            unit.special_rules["enhancement_archslaughterer"] = True
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_archslaughterer_vessel_melee_damage_bonus"] = 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "vox-diabolus" or enh_id == "000009847003":
            if not is_vessels_of_wrath:
                return
            unit.special_rules["enhancement_vox_diabolus"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "avenger's crown" or enh_id == "000009847004":
            if not is_vessels_of_wrath:
                return
            unit.special_rules["enhancement_avengers_crown"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "gateways to glory" or enh_id == "000009847005":
            if not is_vessels_of_wrath:
                return
            unit.special_rules["enhancement_gateways_to_glory"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "bastion shield" or enh_id == "000009823002":
            if not is_hearthband:
                return
            unit.special_rules["enhancement_bastion_shield"] = True
            unit.special_rules["enhancement_bastion_shield_base_range"] = 12
            unit.special_rules["enhancement_bastion_shield_extended_range"] = 18
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "quake multigenerator" or enh_id == "000009823003":
            if not is_hearthband:
                return
            unit.special_rules["enhancement_quake_multigenerator"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "high kahl" or enh_id == "000009823005":
            if not is_hearthband:
                return
            unit.special_rules["enhancement_high_kahl"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "oathbound speculator" or enh_id == "000010435002":
            if not is_needgaard_oathband:
                return
            unit.special_rules["enhancement_oathbound_speculator"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "dead reckoning" or enh_id == "000010435003":
            if not is_needgaard_oathband:
                return
            unit.special_rules["enhancement_dead_reckoning"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "iron ambassador" or enh_id == "000010435004":
            if not is_needgaard_oathband:
                return
            unit.special_rules["enhancement_iron_ambassador"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "ancestral crest" or enh_id == "000010435005":
            if not is_needgaard_oathband:
                return
            unit.special_rules["enhancement_ancestral_crest"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

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

        if name == "pledge of eternal servitude" or enh_id == "000010014002":
            if not is_coterie_of_conceited:
                return
            unit.special_rules["enhancement_pledge_of_eternal_servitude"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id
            refresh_return = getattr(unit, "_refresh_return_on_death_flags", None)
            if callable(refresh_return):
                refresh_return()

        if name == "pledge of dark glory" or enh_id == "000010014003":
            if not is_coterie_of_conceited:
                return
            unit.special_rules["enhancement_pledge_of_dark_glory"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "pledge of mortal pain" or enh_id == "000010014004":
            if not is_coterie_of_conceited:
                return
            unit.special_rules["enhancement_pledge_of_mortal_pain"] = True
            unit.special_rules["enhancement_pledge_of_mortal_pain_range"] = 12
            unit.special_rules["enhancement_pledge_of_mortal_pain_fail_mortal_wounds"] = 3
            unit.special_rules["enhancement_pledge_of_mortal_pain_battleshocked_test_modifier"] = -2
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "pledge of unholy fortune" or enh_id == "000010014005":
            if not is_coterie_of_conceited:
                return
            unit.special_rules["enhancement_pledge_of_unholy_fortune"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "steeped in suffering" or enh_id == "000009998002":
            if not is_court_or_mercurial_host:
                return
            unit.special_rules["enhancement_steeped_in_suffering"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "intoxicating musk" or enh_id == "000009998003":
            if not is_court_or_mercurial_host:
                return
            unit.special_rules["enhancement_intoxicating_musk"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "tactical perfection" or enh_id == "000009998004":
            if not is_court_or_mercurial_host:
                return
            unit.special_rules["enhancement_tactical_perfection"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "loathsome dexterity" or enh_id == "000009998005":
            if not is_court_or_mercurial_host:
                return
            unit.special_rules["enhancement_loathsome_dexterity"] = True
            unit.special_rules["enhancement_loathsome_dexterity_move_types"] = ["move", "advance", "fall_back"]
            unit.special_rules["enhancement_loathsome_dexterity_auto_pass_desperate_escape"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "tears of the phoenix" or enh_id == "000010654002":
            if not is_court_of_the_phoenician:
                return
            unit.special_rules["enhancement_tears_of_the_phoenix"] = True
            unit.special_rules["enhancement_tears_of_the_phoenix_ignore_weapon_skill_modifiers"] = True
            unit.special_rules["enhancement_tears_of_the_phoenix_ignore_hit_roll_modifiers"] = True
            unit.special_rules["enhancement_tears_of_the_phoenix_ignore_wound_roll_modifiers"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "exalted patron" or enh_id == "000010654003":
            if not is_court_of_the_phoenician:
                return
            unit.special_rules["enhancement_exalted_patron"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "soulstain made manifest" or enh_id == "000010654004":
            if not is_court_of_the_phoenician:
                return
            unit.special_rules["enhancement_soulstain_made_manifest"] = True
            unit.special_rules["enhancement_soulstain_battleshock_test_modifier"] = -1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "spiritsliver" or enh_id == "000010654005":
            if not is_court_of_the_phoenician:
                return
            unit.special_rules["enhancement_spiritsliver"] = True
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0
            ) + 1
            unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0
            ) + 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "empyric suffusion" or enh_id == "000010010002":
            if not is_carnival_of_excess:
                return
            unit.special_rules["enhancement_empyric_suffusion"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "dark blessings" or enh_id == "000010010003":
            if not is_carnival_of_excess:
                return
            unit.special_rules["enhancement_dark_blessings"] = True
            unit.special_rules["enhancement_dark_blessings_invulnerable_save"] = 3
            unit.special_rules["enhancement_dark_blessings_once_key"] = "dark_blessings"
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "possessed blade" or enh_id == "000010010004":
            if not is_carnival_of_excess:
                return
            unit.special_rules["enhancement_possessed_blade"] = True
            unit.special_rules["enhancement_possessed_blade_attacks_bonus"] = 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "warp walker" or enh_id == "000010010005":
            if not is_carnival_of_excess:
                return
            unit.special_rules["enhancement_warp_walker"] = True
            unit.special_rules["enhancement_warp_walker_advance_distance"] = 6
            unit.special_rules["enhancement_warp_walker_move_types"] = ["move", "advance", "fall_back"]
            unit.special_rules["enhancement_warp_walker_auto_pass_desperate_escape"] = True
            existing_effects = list(unit.special_rules.get("advance_no_roll_effects", []) or [])
            existing_effects = [
                entry
                for entry in existing_effects
                if not (isinstance(entry, dict) and str(entry.get("tag", "") or "") == "enhancement:warp_walker")
            ]
            existing_effects.append(
                {
                    "distance": 6,
                    "source": "Warp Walker",
                    "tag": "enhancement:warp_walker",
                }
            )
            unit.special_rules["advance_no_roll_effects"] = existing_effects
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "sublime prescience" or enh_id == "000010006002":
            if not is_rapid_evisceration:
                return
            unit.special_rules["enhancement_sublime_prescience"] = True
            unit.special_rules["enhancement_sublime_prescience_round_bonus"] = 1
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "spearhead striker" or enh_id == "000010006003":
            if not is_rapid_evisceration:
                return
            unit.special_rules["enhancement_spearhead_striker"] = True
            # Keep reroll conditional on disembark trigger; parser may set an unconditional flag.
            unit.special_rules.pop("enhancement_charge_reroll", None)
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "accomplished tactician" or enh_id == "000010006004":
            if not is_rapid_evisceration:
                return
            unit.special_rules["enhancement_accomplished_tactician"] = True
            unit.special_rules["enhancement_accomplished_tactician_range"] = 9
            unit.special_rules["enhancement_accomplished_tactician_embark_range"] = 6
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "heretek adept" or enh_id == "000010006005":
            if not is_rapid_evisceration:
                return
            unit.special_rules["enhancement_heretek_adept"] = True
            unit.special_rules["enhancement_heretek_adept_range"] = 6
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "eager to prove" or enh_id == "000010018002":
            if not is_slaaneshs_chosen:
                return
            unit.special_rules["enhancement_eager_to_prove"] = True
            unit.special_rules["enhancement_charge_reroll"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            try:
                move_bonus = int(params.get("favoured_move_bonus", 2) or 2)
            except Exception:
                move_bonus = 2
            unit.special_rules["enhancement_eager_to_prove_favoured_move_bonus"] = int(max(0, move_bonus))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "repulsed by weakness" or enh_id == "000010018003":
            if not is_slaaneshs_chosen:
                return
            unit.special_rules["enhancement_repulsed_by_weakness"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            exclude_mv = bool(params.get("exclude_monsters_vehicles", True))
            try:
                favoured_penalty = int(params.get("favoured_desperate_escape_penalty", 1) or 1)
            except Exception:
                favoured_penalty = 1
            if exclude_mv:
                unit.special_rules["enhancement_repulsed_by_weakness_exclude_monster_vehicle"] = True
                # Keep the generic desperate-escape marker for existing movement hooks.
                unit.special_rules["enemy_fallback_desperate_escape_exclude_monster_vehicle"] = True
            unit.special_rules["enhancement_repulsed_by_weakness_favoured_penalty"] = int(max(0, favoured_penalty))
            # Keep the generic desperate-escape marker for existing movement hooks.
            unit.special_rules["enemy_fallback_desperate_escape"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "proud and vainglorious" or enh_id == "000010018004":
            if not is_slaaneshs_chosen:
                return
            unit.special_rules["enhancement_proud_and_vainglorious"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            try:
                oc_bonus = int(params.get("favoured_objective_control_bonus", 1) or 1)
            except Exception:
                oc_bonus = 1
            unit.special_rules["enhancement_proud_and_vainglorious_oc_bonus"] = int(max(0, oc_bonus))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "slayer of champions" or enh_id == "000010018005":
            if not is_slaaneshs_chosen:
                return
            unit.special_rules["enhancement_slayer_of_champions"] = True
            unit.special_rules["enhancement_bearer_melee_precision"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = dict(getattr(desc, "effect_params", {}) or {})
            except Exception:
                params = {}
            try:
                s_bonus = int(params.get("character_target_strength_bonus", 1) or 1)
            except Exception:
                s_bonus = 1
            try:
                ap_bonus = int(params.get("character_target_ap_bonus", 1) or 1)
            except Exception:
                ap_bonus = 1
            unit.special_rules["enhancement_slayer_of_champions_character_strength_bonus"] = int(max(0, s_bonus))
            unit.special_rules["enhancement_slayer_of_champions_character_ap_bonus"] = int(max(0, ap_bonus))
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "adaptive biology" or enh_id == "000008348005":
            unit.special_rules["enhancement_adaptive_biology"] = True
            _ensure_enhancement_fnp_entry(
                unit,
                5,
                source="Adaptive Biology",
                tag="adaptive_biology_base",
            )

        if name == "perfectly adapted" or enh_id == "000008348003":
            unit.special_rules["enhancement_perfectly_adapted"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "synaptic linchpin" or enh_id == "000008348004":
            unit.special_rules["enhancement_synaptic_linchpin"] = True
            unit.special_rules["enhancement_synaptic_linchpin_range"] = 9.0
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

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

        if name == "inescapable eye" or enh_id == "000009810002":
            if not is_scintillating_legion:
                return
            unit.special_rules["enhancement_inescapable_eye"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "infernal puppeteer" or enh_id == "000009810003":
            if not is_scintillating_legion:
                return
            unit.special_rules["enhancement_infernal_puppeteer"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "neverblade" or enh_id == "000009810004":
            if not is_scintillating_legion:
                return
            unit.special_rules["enhancement_neverblade"] = True
            desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
            try:
                params = getattr(desc, "effect_params", {}) if desc is not None else {}
            except Exception:
                params = {}
            try:
                s_bonus = int(params.get("strength_bonus", 2) or 2)
            except Exception:
                s_bonus = 2
            try:
                a_bonus = int(params.get("attacks_bonus", 1) or 1)
            except Exception:
                a_bonus = 1
            try:
                ap_bonus = int(params.get("ap_bonus", 1) or 1)
            except Exception:
                ap_bonus = 1
            try:
                hit_bonus = int(params.get("hit_bonus", 1) or 1)
            except Exception:
                hit_bonus = 1
            unit.special_rules["enhancement_bearer_melee_strength_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0
            ) + s_bonus
            unit.special_rules["enhancement_bearer_melee_attacks_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_attacks_bonus", 0) or 0
            ) + a_bonus
            unit.special_rules["enhancement_bearer_melee_ap_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0) or 0
            ) + ap_bonus
            unit.special_rules["enhancement_bearer_melee_hit_bonus"] = int(
                unit.special_rules.get("enhancement_bearer_melee_hit_bonus", 0) or 0
            ) + hit_bonus
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "improbable shield (aura)" or enh_id == "000009810005":
            if not is_scintillating_legion:
                return
            unit.special_rules["enhancement_improbable_shield"] = True
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

        if name == "mandulian reliquary" or enh_id == "000009777002":
            if not is_warpbane_task_force:
                return
            unit.special_rules["enhancement_mandulian_reliquary"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "radiant champion" or enh_id == "000009777003":
            if not is_warpbane_task_force:
                return
            unit.special_rules["enhancement_radiant_champion"] = True
            unit.special_rules["enhancement_bearer_melee_precision"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "phial of the abyss" or enh_id == "000009777004":
            if not is_warpbane_task_force:
                return
            unit.special_rules["enhancement_phial_of_the_abyss"] = True
            if bearer_id:
                unit.special_rules["enhancement_bearer_model_id"] = bearer_id

        if name == "paragon of sanctity" or enh_id == "000009777005":
            if not is_warpbane_task_force:
                return
            unit.special_rules["enhancement_paragon_of_sanctity"] = True
            unit.special_rules["enhancement_paragon_of_sanctity_once_key"] = "paragon_of_sanctity"
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
