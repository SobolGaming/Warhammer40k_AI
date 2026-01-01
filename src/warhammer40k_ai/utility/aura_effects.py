from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

from .aura_utils import unit_within_range_of_unit


@dataclass(frozen=True)
class AuraAttackModifiers:
    """Aggregated roll modifiers coming from friendly auras."""

    hit: int = 0
    wound: int = 0
    target_toughness_delta: int = 0
    hit_reasons: tuple[str, ...] = ()
    wound_reasons: tuple[str, ...] = ()
    target_toughness_reasons: tuple[str, ...] = ()
    reroll_hit_ones: bool = False
    reroll_wound_ones: bool = False
    reroll_hit_reasons: tuple[str, ...] = ()
    reroll_wound_reasons: tuple[str, ...] = ()

    def merge(self, other: "AuraAttackModifiers") -> "AuraAttackModifiers":
        if other is None:
            return self
        return AuraAttackModifiers(
            hit=int(self.hit) + int(other.hit),
            wound=int(self.wound) + int(other.wound),
            target_toughness_delta=int(self.target_toughness_delta) + int(other.target_toughness_delta),
            hit_reasons=tuple(self.hit_reasons) + tuple(other.hit_reasons),
            wound_reasons=tuple(self.wound_reasons) + tuple(other.wound_reasons),
            target_toughness_reasons=tuple(self.target_toughness_reasons) + tuple(other.target_toughness_reasons),
            reroll_hit_ones=bool(self.reroll_hit_ones or other.reroll_hit_ones),
            reroll_wound_ones=bool(self.reroll_wound_ones or other.reroll_wound_ones),
            reroll_hit_reasons=tuple(self.reroll_hit_reasons) + tuple(other.reroll_hit_reasons),
            reroll_wound_reasons=tuple(self.reroll_wound_reasons) + tuple(other.reroll_wound_reasons),
        )


def _norm(s: str) -> str:
    return (s or "").strip().lower()

def _norm_name(s: str) -> str:
    return _norm((s or "").replace("’", "'"))


def _iter_possible_abilities(unit) -> Iterable[object]:
    for ab in (getattr(unit, "possible_abilities", []) or []):
        yield ab


def _is_aura_ability(ability) -> bool:
    name = str(getattr(ability, "name", "") or "")
    return "(aura)" in _norm(name)


def _get_map_from_attacker_unit(attacker_unit):
    """
    Best-effort map lookup for aura calculations.

    Aura modifiers require access to the current game map. In unit tests and in some isolated
    subsystems, we may be operating on lightweight Unit-like stubs that don't have full Army/Game
    wiring. In those cases, treat "no map" as "no aura modifiers" rather than raising.
    """
    if attacker_unit is None:
        return None
    try:
        get_parent_army = getattr(attacker_unit, "get_parent_army", None)
        if not callable(get_parent_army):
            return None
        army = get_parent_army()
    except Exception:
        return None
    if army is None or getattr(army, "player", None) is None:
        return None
    game = getattr(army.player, "game", None)
    if game is None:
        return None
    return getattr(game, "map", None)

def _get_battle_round_from_unit(unit) -> int:
    try:
        army = unit.get_parent_army()
        game = getattr(getattr(army, "player", None), "game", None)
        return int(getattr(game, "turn", 0) or 0)
    except Exception:
        return 0


def _weapon_is_melee(weapon_profile) -> bool:
    pw = getattr(weapon_profile, "parent_wargear", None)
    if pw is None:
        return False
    return bool(pw.is_melee())


def _excluded_by_target_keywords(target_unit, excluded_keywords: Iterable[str]) -> bool:
    for kw in excluded_keywords:
        k = str(kw or "").strip()
        if not k:
            continue
        if target_unit.has_keyword(k):
            return True
    return False


def _parse_simple_plus_one_aura(ability) -> Optional[dict]:
    """
    Parse a strict subset of Wahapedia aura text into a structured spec.

    Supported subset (strict):
    - "While a friendly X unit is within N\" of this unit, each time a model in that unit makes a melee attack ...
       add 1 to the Hit roll."
    - optional: "(excluding MONSTERS and VEHICLES)"
    - optional: "If that attack targets a unit ... that is Below Half-strength, add 1 to the Wound roll as well."
    """
    if not _is_aura_ability(ability):
        return None

    desc = str(getattr(ability, "description", "") or "").strip()
    if not desc:
        return None

    # Only consider auras that explicitly specify melee or ranged attacks and +1 to Hit roll.
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of this unit, each time a model in that unit makes a (?P<atype>melee|ranged) attack.*?add 1 to the Hit roll',
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        return None

    faction_kw = str(m.group("faction_kw") or "").strip()
    rng = float(m.group("rng"))
    atype = str(m.group("atype") or "").strip().lower()

    excluded = []
    ex = re.search(r"\(excluding (?P<ex>[^)]+)\)", desc, flags=re.IGNORECASE)
    if ex:
        raw = str(ex.group("ex") or "")
        raw = raw.replace(" and ", ",")
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        # Normalize common plurals from Wahapedia ("MONSTERS" -> "Monster")
        for p in parts:
            up = p.upper()
            if up == "MONSTERS":
                excluded.append("Monster")
            elif up == "VEHICLES":
                excluded.append("Vehicle")
            else:
                excluded.append(p.title())

    below_half_wound = bool(
        re.search(r"Below Half-strength.*add 1 to the Wound roll as well", desc, flags=re.IGNORECASE)
    )

    return {
        "faction_keyword": faction_kw,
        "range": rng,
        "attack_type": atype,  # "melee" | "ranged"
        "hit_bonus": 1,
        "excluded_keywords": tuple(excluded),
        "below_half_wound_bonus": 1 if below_half_wound else 0,
    }

def _parse_reroll_ones_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X unit is within N\" of this unit, you can re-roll Hit rolls of 1."
      "While a friendly X unit is within N\" of this unit, you can re-roll Wound rolls of 1."
    """
    if not _is_aura_ability(ability):
        return None
    desc = str(getattr(ability, "description", "") or "").strip()
    if not desc:
        return None

    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of this unit, you can re-roll (?P<rtype>Hit|Wound) rolls of 1',
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    return {
        "faction_keyword": str(m.group("faction_kw") or "").strip(),
        "range": float(m.group("rng")),
        "reroll_type": str(m.group("rtype") or "").strip().lower(),  # "hit" | "wound"
    }


def _parse_add_oc_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X unit is within N\" of this model/unit, add Y to the Objective Control characteristic of models in that unit."
    """
    if not _is_aura_ability(ability):
        return None
    desc = str(getattr(ability, "description", "") or "").strip()
    if not desc:
        return None
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of this (?:unit|model), add (?P<amt>\d+) to the Objective Control characteristic of models in that unit',
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    return {
        "faction_keyword": str(m.group("faction_kw") or "").strip(),
        "range": float(m.group("rng")),
        "amount": int(m.group("amt")),
    }


def _nurgles_gift_contagion_range(battle_round: int) -> float:
    # 10e baseline: BR1=3", BR2=6", BR3+=9"
    br = int(battle_round or 0)
    if br <= 1:
        return 3.0
    if br == 2:
        return 6.0
    return 9.0


def _beacons_of_rage(attacker_unit, target_unit, weapon_profile, source_unit) -> AuraAttackModifiers:
    # Applicability: friendly WORLD EATERS within 6" of source; melee; excludes MONSTER/VEHICLE targets.
    if not attacker_unit.has_any_keyword("WORLD EATERS"):
        return AuraAttackModifiers()
    if not _weapon_is_melee(weapon_profile):
        return AuraAttackModifiers()
    if bool(target_unit.is_monster) or bool(target_unit.is_vehicle):
        return AuraAttackModifiers()
    if not unit_within_range_of_unit(source_unit, attacker_unit, 6.0, use_attached_aggregate=True):
        return AuraAttackModifiers()

    hit = 1
    hit_reason = "+1 from Beacons of Rage (Aura)"
    wound = 0
    wound_reason = ()
    if target_unit.is_below_half_strength():
        wound = 1
        wound_reason = ("+1 to wound from Beacons of Rage (Aura) vs Below Half-strength",)
    return AuraAttackModifiers(hit=hit, wound=wound, hit_reasons=(hit_reason,), wound_reasons=wound_reason)

def _nurgles_gift(attacker_unit, target_unit, source_unit) -> AuraAttackModifiers:
    """
    Nurgle’s Gift (Aura): While an enemy unit is within Contagion Range of this unit, subtract 1 from Toughness.
    We implement the baseline Contagion Range scaling by battle round (3/6/9).
    """
    br = _get_battle_round_from_unit(source_unit) or _get_battle_round_from_unit(attacker_unit)
    rng = _nurgles_gift_contagion_range(br)
    if not unit_within_range_of_unit(source_unit, target_unit, rng, use_attached_aggregate=True):
        return AuraAttackModifiers()
    return AuraAttackModifiers(
        target_toughness_delta=-1,
        target_toughness_reasons=(f"-1T from Nurgle’s Gift (Aura) (Contagion Range {rng}\")",),
    )


def get_aura_attack_modifiers(attacker_unit, target_unit, weapon_profile, *, game_map=None) -> AuraAttackModifiers:
    """
    Return aggregated aura modifiers that apply to this attack.

    This is evaluated on-demand at roll resolution time (pull-based), so it naturally
    updates as units move/die without needing to push buffs onto units.
    """
    if attacker_unit is None or target_unit is None or weapon_profile is None:
        return AuraAttackModifiers()

    if game_map is None:
        game_map = _get_map_from_attacker_unit(attacker_unit)
    if game_map is None:
        return AuraAttackModifiers()

    out = AuraAttackModifiers()
    applied_aura_names: set[str] = set()
    friendly_units = list(game_map.get_friendly_units(attacker_unit))

    for source in friendly_units:
        for ab in _iter_possible_abilities(source):
            if not _is_aura_ability(ab):
                continue

            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            # 10e: the same Aura ability never applies more than once to a unit, even if there are
            # multiple sources (e.g. two identical Captains).
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)

            if _norm_name(ab_name) == _norm_name("Beacons of Rage (Aura)"):
                out = out.merge(_beacons_of_rage(attacker_unit, target_unit, weapon_profile, source))
                continue

            # Nurgle’s Gift (Aura) debuff (enemy-targeted).
            if _norm_name(ab_name) == _norm_name("Nurgle's Gift (Aura)"):
                out = out.merge(_nurgles_gift(attacker_unit, target_unit, source))
                continue

            # Generic strict parser for "+1 to hit" auras (very limited subset).
            spec = _parse_simple_plus_one_aura(ab)
            if not spec:
                spec = None

            if spec:
                # Attack-type restriction
                if spec["attack_type"] == "melee" and not _weapon_is_melee(weapon_profile):
                    continue
                if spec["attack_type"] == "ranged" and _weapon_is_melee(weapon_profile):
                    continue

                # Faction keyword restriction (as a phrase, e.g. "WORLD EATERS")
                if spec["faction_keyword"] and not attacker_unit.has_any_keyword(spec["faction_keyword"]):
                    continue

                # Range restriction (source -> attacker)
                if not unit_within_range_of_unit(source, attacker_unit, float(spec["range"]), use_attached_aggregate=True):
                    continue

                # Keyword exclusions (best-effort)
                if spec["excluded_keywords"] and _excluded_by_target_keywords(target_unit, spec["excluded_keywords"]):
                    continue

                hit_reason = f"+{spec['hit_bonus']} from {ab_name}"
                hit_mods = AuraAttackModifiers(hit=int(spec["hit_bonus"]), hit_reasons=(hit_reason,))
                out = out.merge(hit_mods)

                # Optional: below half-strength wound bonus
                if int(spec.get("below_half_wound_bonus", 0) or 0) and target_unit.is_below_half_strength():
                    wound_reason = f"+1 to wound from {ab_name} vs Below Half-strength"
                    out = out.merge(AuraAttackModifiers(wound=1, wound_reasons=(wound_reason,)))

            # Generic strict parser: reroll 1s (hit/wound), friendly within X.
            rr = _parse_reroll_ones_aura(ab)
            if rr:
                if rr["faction_keyword"] and not attacker_unit.has_any_keyword(rr["faction_keyword"]):
                    continue
                if not unit_within_range_of_unit(source, attacker_unit, float(rr["range"]), use_attached_aggregate=True):
                    continue
                if rr["reroll_type"] == "hit":
                    out = out.merge(
                        AuraAttackModifiers(
                            reroll_hit_ones=True,
                            reroll_hit_reasons=(f"Aura: re-roll Hit rolls of 1 from {ab_name}",),
                        )
                    )
                elif rr["reroll_type"] == "wound":
                    out = out.merge(
                        AuraAttackModifiers(
                            reroll_wound_ones=True,
                            reroll_wound_reasons=(f"Aura: re-roll Wound rolls of 1 from {ab_name}",),
                        )
                    )

    return out


def get_aura_objective_control_bonus(unit, *, game_map=None) -> int:
    """
    Return additive OC bonus from friendly OC auras affecting this unit.
    Only supports strict "add N to OC while within X" patterns to avoid over-applying.
    """
    if unit is None:
        return 0
    if game_map is None:
        game_map = _get_map_from_attacker_unit(unit)
    if game_map is None:
        return 0
    total = 0
    applied_aura_names: set[str] = set()
    for source in list(game_map.get_friendly_units(unit)):
        for ab in _iter_possible_abilities(source):
            spec = _parse_add_oc_aura(ab)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            # Same Aura name never double-applies.
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if spec["faction_keyword"] and not unit.has_any_keyword(spec["faction_keyword"]):
                continue
            if not unit_within_range_of_unit(source, unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            total += int(spec["amount"])
    return int(total)


def _parse_melee_attacks_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X unit is within N\" of this model, add M to the Attacks characteristic of melee weapons equipped by models in that unit."
    """
    if not _is_aura_ability(ability):
        return None
    desc = str(getattr(ability, "description", "") or "").strip()
    if not desc:
        return None
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of this model, add (?P<amt>\d+) to the Attacks characteristic of melee weapons equipped by models in that unit',
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    return {
        "faction_keyword": str(m.group("faction_kw") or "").strip(),
        "range": float(m.group("rng")),
        "amount": int(m.group("amt")),
    }


def get_aura_melee_attacks_bonus(attacker_unit, weapon_profile, *, game_map=None) -> tuple[int, tuple[str, ...]]:
    """
    Return (bonus_attacks, reasons) from strict "melee Attacks characteristic" auras affecting attacker_unit.
    Dedupe by Aura name (same aura never double-applies).
    """
    if attacker_unit is None or weapon_profile is None:
        return 0, ()
    pw = getattr(weapon_profile, "parent_wargear", None)
    if pw is None or not bool(pw.is_melee()):
        return 0, ()
    if game_map is None:
        game_map = _get_map_from_attacker_unit(attacker_unit)
    if game_map is None:
        return 0, ()

    total = 0
    reasons: list[str] = []
    applied_aura_names: set[str] = set()

    for source in list(game_map.get_friendly_units(attacker_unit)):
        for ab in _iter_possible_abilities(source):
            spec = _parse_melee_attacks_aura(ab)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if spec["faction_keyword"] and not attacker_unit.has_any_keyword(spec["faction_keyword"]):
                continue
            if not unit_within_range_of_unit(source, attacker_unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            amt = int(spec["amount"])
            total += amt
            reasons.append(f"Aura: +{amt}A (melee) from {ab_name}")

    return int(total), tuple(reasons)


