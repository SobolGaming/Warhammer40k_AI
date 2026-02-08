from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

from .aura_utils import unit_within_range_of_unit
from .entity_ids import get_entity_id


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
    reroll_hit_values: tuple[int, ...] = ()
    reroll_wound_values: tuple[int, ...] = ()
    reroll_hit_full: bool = False
    reroll_wound_full: bool = False
    reroll_hit_reasons: tuple[str, ...] = ()
    reroll_wound_reasons: tuple[str, ...] = ()
    reroll_hit_full_reasons: tuple[str, ...] = ()
    reroll_wound_full_reasons: tuple[str, ...] = ()
    crit_hit_threshold: Optional[int] = None
    crit_wound_threshold: Optional[int] = None
    crit_hit_reasons: tuple[str, ...] = ()
    crit_wound_reasons: tuple[str, ...] = ()

    def merge(self, other: "AuraAttackModifiers") -> "AuraAttackModifiers":
        if other is None:
            return self
        if self.crit_hit_threshold is None:
            crit_hit = other.crit_hit_threshold
        elif other.crit_hit_threshold is None:
            crit_hit = self.crit_hit_threshold
        else:
            crit_hit = min(int(self.crit_hit_threshold), int(other.crit_hit_threshold))
        if self.crit_wound_threshold is None:
            crit_wound = other.crit_wound_threshold
        elif other.crit_wound_threshold is None:
            crit_wound = self.crit_wound_threshold
        else:
            crit_wound = min(int(self.crit_wound_threshold), int(other.crit_wound_threshold))
        return AuraAttackModifiers(
            hit=int(self.hit) + int(other.hit),
            wound=int(self.wound) + int(other.wound),
            target_toughness_delta=int(self.target_toughness_delta) + int(other.target_toughness_delta),
            hit_reasons=tuple(self.hit_reasons) + tuple(other.hit_reasons),
            wound_reasons=tuple(self.wound_reasons) + tuple(other.wound_reasons),
            target_toughness_reasons=tuple(self.target_toughness_reasons) + tuple(other.target_toughness_reasons),
            reroll_hit_ones=bool(self.reroll_hit_ones or other.reroll_hit_ones),
            reroll_wound_ones=bool(self.reroll_wound_ones or other.reroll_wound_ones),
            reroll_hit_values=tuple(sorted({*self.reroll_hit_values, *other.reroll_hit_values})),
            reroll_wound_values=tuple(sorted({*self.reroll_wound_values, *other.reroll_wound_values})),
            reroll_hit_full=bool(self.reroll_hit_full or other.reroll_hit_full),
            reroll_wound_full=bool(self.reroll_wound_full or other.reroll_wound_full),
            reroll_hit_reasons=tuple(self.reroll_hit_reasons) + tuple(other.reroll_hit_reasons),
            reroll_wound_reasons=tuple(self.reroll_wound_reasons) + tuple(other.reroll_wound_reasons),
            reroll_hit_full_reasons=tuple(self.reroll_hit_full_reasons) + tuple(other.reroll_hit_full_reasons),
            reroll_wound_full_reasons=tuple(self.reroll_wound_full_reasons) + tuple(other.reroll_wound_full_reasons),
            crit_hit_threshold=crit_hit,
            crit_wound_threshold=crit_wound,
            crit_hit_reasons=tuple(self.crit_hit_reasons) + tuple(other.crit_hit_reasons),
            crit_wound_reasons=tuple(self.crit_wound_reasons) + tuple(other.crit_wound_reasons),
        )


def _norm(s: str) -> str:
    return (s or "").strip().lower()

def _norm_name(s: str) -> str:
    return _norm((s or "").replace("\u2019", "'"))

def _normalize_desc(desc: str) -> str:
    text = str(desc or "")
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = (
        text.replace("\u00a0", " ")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_keyword_phrase(value: str) -> str:
    t = str(value or "").lower()
    t = t.replace("\u2019", "'").replace("\u0192?T", "'")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _unit_matches_keyword_phrase(unit, phrase: str) -> bool:
    key_phrase = _normalize_keyword_phrase(phrase)
    if not key_phrase or unit is None:
        return False
    tokens = key_phrase.split()
    if not tokens:
        return False
    keywords: set[str] = set()
    try:
        kws = list(getattr(unit, "get_effective_keywords")() or [])
    except Exception:
        kws = list(getattr(unit, "keywords", []) or [])
    try:
        kws += list(getattr(unit, "get_effective_faction_keywords")() or [])
    except Exception:
        kws += list(getattr(unit, "faction_keywords", []) or [])
    for kw in kws:
        norm = _normalize_keyword_phrase(kw)
        if norm:
            keywords.add(norm)
    if not keywords:
        return False
    n = len(tokens)
    dp = [False] * (n + 1)
    dp[n] = True
    for i in range(n - 1, -1, -1):
        for j in range(i + 1, n + 1):
            cand = " ".join(tokens[i:j])
            if cand in keywords and dp[j]:
                dp[i] = True
                break
    return dp[0]


def _iter_possible_abilities(unit) -> Iterable[object]:
    is_active = getattr(unit, "_ability_is_active", None)
    for ab in (getattr(unit, "possible_abilities", []) or []):
        if callable(is_active):
            try:
                if not is_active(ab):
                    continue
            except Exception:
                continue
        yield ab
    enh = getattr(unit, "enhancement", None)
    if enh is not None:
        if callable(is_active):
            try:
                if not is_active(enh):
                    return
            except Exception:
                pass
        yield enh


def _is_aura_ability(ability) -> bool:
    name = str(getattr(ability, "name", "") or "")
    return "(aura" in _norm(name)


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


def _attacker_in_own_shooting_phase(attacker_unit) -> bool:
    try:
        fn = getattr(attacker_unit, "_is_controlling_players_shooting_phase", None)
        if callable(fn):
            return bool(fn())
    except Exception:
        pass
    try:
        army = attacker_unit.get_parent_army()
        player = getattr(army, "player", None)
        game = getattr(player, "game", None)
        if game is None or player is None:
            return False
        return bool(getattr(game, "is_shooting_phase", lambda: False)() and getattr(game, "get_current_player", lambda: None)() is player)
    except Exception:
        return False


def _requires_own_shooting_phase(ability) -> bool:
    desc = str(getattr(ability, "description", "") or "")
    if not desc:
        return False
    return bool(re.search(r"\byour shooting phase\b", desc, flags=re.IGNORECASE))


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


def _excluded_by_unit_keywords(unit, excluded_keywords: Iterable[str]) -> bool:
    if unit is None:
        return False
    for kw in excluded_keywords:
        k = str(kw or "").strip()
        if not k:
            continue
        try:
            if unit.has_keyword(k):
                return True
        except Exception:
            try:
                if unit.has_any_keyword(k):
                    return True
            except Exception:
                continue
    return False


def _parse_excluded_keywords(desc: str) -> tuple[str, ...]:
    if not desc:
        return ()
    ex = re.search(r"\(excluding (?P<ex>[^)]+)\)", desc, flags=re.IGNORECASE)
    if not ex:
        return ()
    raw = str(ex.group("ex") or "")
    raw = raw.replace(" and ", ",")
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    excluded: list[str] = []
    for p in parts:
        p = re.sub(r"\bunits?\b", "", p, flags=re.IGNORECASE).strip()
        if not p:
            continue
        up = p.upper()
        if up == "MONSTERS":
            excluded.append("Monster")
        elif up == "VEHICLES":
            excluded.append("Vehicle")
        elif up == "TITANIC":
            excluded.append("Titanic")
        else:
            excluded.append(p)
    return tuple(excluded)

def _target_is_closest_enemy_unit(attacker_unit, target_unit, game_map) -> bool:
    if attacker_unit is None or target_unit is None or game_map is None:
        return False
    try:
        enemies = list(game_map.get_enemy_units(attacker_unit) or [])
    except Exception:
        enemies = []
    if not enemies:
        return False
    try:
        target_root = target_unit.get_attached_unit_root()
    except Exception:
        target_root = target_unit
    target_id = get_entity_id(target_root) if target_root is not None else ""
    closest = None
    target_dist = None
    seen = set()
    for enemy in enemies:
        try:
            root = enemy.get_attached_unit_root()
        except Exception:
            root = enemy
        if root is None:
            continue
        rid = get_entity_id(root)
        if rid in seen:
            continue
        seen.add(rid)
        try:
            if hasattr(root, "is_alive") and callable(root.is_alive) and not root.is_alive():
                continue
        except Exception:
            pass
        try:
            if hasattr(root, "deployed") and not bool(getattr(root, "deployed", True)):
                continue
        except Exception:
            pass
        try:
            dist = float(game_map.get_distance_between_units(attacker_unit, root))
        except Exception:
            continue
        if root is target_root or (target_id and target_id == getattr(root, "_id", None)):
            target_dist = dist
        if closest is None or dist < closest:
            closest = dist
    if closest is None or target_dist is None:
        return False
    return target_dist <= closest + 1e-6


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

    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None

    # Only consider auras that explicitly specify melee or ranged attacks and +1 to Hit roll.
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of (?:this unit|this model|the bearer), '
        r'each time a model in that unit makes a (?P<atype>melee|ranged) attack.*?add 1 to the Hit roll',
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        return None

    faction_kw = str(m.group("faction_kw") or "").strip()
    rng = float(m.group("rng"))
    atype = str(m.group("atype") or "").strip().lower()

    excluded = list(_parse_excluded_keywords(desc))

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
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) (?:unit|model)(?: \((?P<exclude>[^)]+)\))? is within (?P<rng>\d+)" '
        r"of (?:this unit|this model|the bearer)",
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        return None

    attack_type = "any"
    if re.search(r"makes a melee attack", desc, flags=re.IGNORECASE):
        attack_type = "melee"
    elif re.search(r"makes a ranged attack", desc, flags=re.IGNORECASE):
        attack_type = "ranged"

    hit = bool(re.search(r"re-?roll (?:a |any )?hit roll(?:s)? of 1", desc, flags=re.IGNORECASE))
    wound = bool(re.search(r"re-?roll (?:a |any )?wound roll(?:s)? of 1", desc, flags=re.IGNORECASE))
    if not hit and not wound:
        return None

    return {
        "faction_keyword": str(m.group("faction_kw") or "").strip(),
        "range": float(m.group("rng")),
        "reroll_hit": bool(hit),
        "reroll_wound": bool(wound),
        "excluded_keywords": _parse_excluded_keywords(desc),
        "attack_type": attack_type,
    }


def _parse_full_hit_reroll_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X unit is within N\" ... each time a model in that unit makes an attack,
       you can re-roll the Hit roll."
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) (?:unit|model)(?: \((?P<exclude_a>[^)]+)\))? is within (?P<rng>\d+)"(?: \((?P<exclude_b>[^)]+)\))? '
        r"of (?:this unit|this model|the bearer), each time (?:a model in that unit|that model) makes an attack, "
        r"you can re-?roll (?:a|the) Hit roll",
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    return {
        "faction_keyword": str(m.group("faction_kw") or "").strip(),
        "range": float(m.group("rng")),
        "excluded_keywords": _parse_excluded_keywords(desc),
    }


def _parse_add_oc_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X unit is within N\" of this model/unit, add Y to the Objective Control characteristic of models in that unit."
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) (?:unit|model) is within (?P<rng>\d+)" of this (?:unit|model|the bearer), '
        r'add (?P<amt>\d+) to the Objective Control characteristic of (?:(?:models? in that )?(?:unit|model))',
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

def _parse_leadership_oc_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X model/unit is within N\" of this model/unit, improve that X model's Leadership and
       Objective Control characteristics by Y."
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) (?:unit|model) is within (?P<rng>\d+)" of this (?:unit|model|the bearer), '
        r"improve that .*?Leadership and Objective Control characteristics by (?P<amt>\d+)",
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


def _parse_leadership_only_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X model/unit is within N\" (or wholly within N\") of this model/unit/fortification,
       improve that unit/model's Leadership characteristic by Y."
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) (?:unit|model) is (?:(?:wholly )?within) (?P<rng>\d+)" '
        r"of this (?:unit|model|fortification|the bearer), improve that .*? Leadership characteristic by (?P<amt>\d+)",
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


def _parse_battleshock_leadership_test_reroll_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X unit is within N\" ... you can re-roll Leadership and/or Battle-shock tests taken for that unit."
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) (?:unit|model)(?: \((?P<exclude_a>[^)]+)\))? is within (?P<rng>\d+)"(?: \((?P<exclude_b>[^)]+)\))? '
        r"of (?:this unit|this model|the bearer), you can re-?roll (?P<tests>.+?) tests? taken for that unit",
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    tests = str(m.group("tests") or "").lower()
    reroll_battleshock = "battle-shock" in tests or "battle shock" in tests
    reroll_leadership = "leadership" in tests
    if not reroll_battleshock and not reroll_leadership:
        return None
    return {
        "faction_keyword": str(m.group("faction_kw") or "").strip(),
        "range": float(m.group("rng")),
        "excluded_keywords": _parse_excluded_keywords(desc),
        "reroll_battleshock": bool(reroll_battleshock),
        "reroll_leadership": bool(reroll_leadership),
    }


def _parse_enemy_leadership_characteristic_penalty_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While an enemy unit is within N\" of this model/unit/the bearer, worsen the Leadership
       characteristic of models in that unit by X."
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    m = re.search(
        r'While an enemy unit(?: \(excluding [^)]+\))? is within (?P<rng>\d+)" of (?:this model|this unit|the bearer), '
        r"worsen the Leadership characteristic of models in that unit by (?P<amt>\d+)",
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    return {
        "range": float(m.group("rng")),
        "amount": int(m.group("amt")),
        "excluded_keywords": _parse_excluded_keywords(desc),
    }


def _parse_advance_charge_roll_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X unit is within N\" of this model/unit, add Y to Advance and Charge rolls made for that unit."
    """
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) units? is within (?P<rng>\d+)" of this (?:unit|model), '
        r"add (?P<amt>\d+) to Advance and Charge rolls made for (?:that|the) unit",
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


def _parse_strength_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X unit is within N\" of this model/the bearer, add Y to the Strength characteristic
       of weapons equipped by models in that unit."
    Optionally supports "melee weapons" / "ranged weapons" phrasing.
    Also supports:
      "While a friendly X unit is within N\" of this model/the bearer, each time a model in that unit makes a
       melee/ranged attack, add Y to the Strength characteristic of that attack."
    """
    if not _is_aura_ability(ability):
        return None
    text = _normalize_desc(getattr(ability, "description", ""))
    if not text:
        return None
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of (?:this model|this unit|the bearer), '
        r'add (?P<amt>\d+) to the Strength characteristic of (?:(?P<atype>melee|ranged) )?weapons equipped by models in that unit',
        text,
        flags=re.IGNORECASE,
    )
    if m:
        atype = str(m.group("atype") or "").strip().lower()
        if atype not in ("melee", "ranged"):
            atype = "any"
            if re.search(r"\bmelee weapons\b", text, flags=re.IGNORECASE):
                atype = "melee"
            elif re.search(r"\branged weapons\b", text, flags=re.IGNORECASE):
                atype = "ranged"
        return {
            "faction_keyword": str(m.group("faction_kw") or "").strip(),
            "range": float(m.group("rng")),
            "amount": int(m.group("amt")),
            "attack_type": atype,
        }
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of (?:this model|this unit|the bearer), '
        r'each time a model in that unit makes a (?P<atype>melee|ranged) attack, add (?P<amt>\d+) '
        r"to the Strength characteristic of that attack",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    return {
        "faction_keyword": str(m.group("faction_kw") or "").strip(),
        "range": float(m.group("rng")),
        "amount": int(m.group("amt")),
        "attack_type": str(m.group("atype") or "").strip().lower(),
    }


def _parse_melee_ap_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X unit is within N\" of this model/the bearer, improve the Armour Penetration
       characteristic of melee weapons equipped by models in that unit by Y."
      Optional: "if that unit made a Charge move this turn".
    """
    if not _is_aura_ability(ability):
        return None
    text = _normalize_desc(getattr(ability, "description", ""))
    if not text:
        return None
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of (?:this model|this unit|the bearer), '
        r'(?:(?P<charged>if that unit made a Charge move this turn, )?)'
        r'improve the Armou?r Penetration(?: characteristic)? of melee weapons (?:equipped by models )?in that unit by (?P<amt>\d+)',
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    return {
        "faction_keyword": str(m.group("faction_kw") or "").strip(),
        "range": float(m.group("rng")),
        "amount": int(m.group("amt")),
        "requires_charge": bool(m.group("charged")),
    }

def _parse_closest_enemy_ap_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X model/unit is within N\" of this model/unit, each time that X model makes an attack
       that targets the closest enemy unit, improve the Armour Penetration characteristic of that attack by Y."
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) (?:unit|model) is within (?P<rng>\d+)" of this (?:model|unit|the bearer), '
        r"each time that .*?attack that targets the closest enemy unit, improve the Armou?r Penetration "
        r"characteristic of that attack by (?P<amt>\d+)",
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    attack_type = "any"
    if re.search(r"melee attack", desc, flags=re.IGNORECASE):
        attack_type = "melee"
    elif re.search(r"ranged attack", desc, flags=re.IGNORECASE):
        attack_type = "ranged"
    return {
        "faction_keyword": str(m.group("faction_kw") or "").strip(),
        "range": float(m.group("rng")),
        "amount": int(m.group("amt")),
        "attack_type": attack_type,
    }


def _parse_toughness_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X unit is within N\" of this model/the bearer, add Y to the Toughness characteristic
       of models in that unit."
      Accepts "improve the Toughness characteristic ... by Y" as well.
    """
    if not _is_aura_ability(ability):
        return None
    text = _normalize_desc(getattr(ability, "description", ""))
    if not text:
        return None
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of (?:this model|this unit|the bearer), '
        r'add (?P<amt>\d+) to the Toughness characteristic of models in that unit',
        text,
        flags=re.IGNORECASE,
    )
    if m:
        return {
            "faction_keyword": str(m.group("faction_kw") or "").strip(),
            "range": float(m.group("rng")),
            "amount": int(m.group("amt")),
        }
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of (?:this model|this unit|the bearer), '
        r'improve the Toughness characteristic of models in that unit by (?P<amt>\d+)',
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    return {
        "faction_keyword": str(m.group("faction_kw") or "").strip(),
        "range": float(m.group("rng")),
        "amount": int(m.group("amt")),
    }


def _parse_battleshock_leadership_test_aura(ability) -> Optional[dict]:
    """
    Strict parser for enemy-test auras like:
      "While an enemy unit is within N\" of this model, subtract X from Battle-shock tests taken for that unit."
      "While an enemy unit is within N\" of this model, subtract X from Battle-shock and Leadership tests taken for that unit."
    """
    if not _is_aura_ability(ability):
        return None
    text = _normalize_desc(getattr(ability, "description", ""))
    if not text:
        return None
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    if "enemy unit" not in text:
        return None
    if "battle shock" not in text:
        return None
    if "test" not in text:
        return None
    m_range = re.search(r"within\s+(?P<rng>\d+)", text)
    m_val = re.search(r"subtract\s+(?P<val>\d+)\s+from", text)
    if not m_range or not m_val:
        return None
    try:
        rng = float(m_range.group("rng"))
    except Exception:
        return None
    try:
        val = int(m_val.group("val"))
    except Exception:
        return None
    if rng <= 0 or val <= 0:
        return None
    return {
        "range": float(rng),
        "amount": -abs(int(val)),
    }


def _parse_enemy_move_oc_penalty_aura(ability) -> Optional[dict]:
    """
    Strict parser for enemy auras like:
      "While an enemy unit is within N\" of this model, subtract X from the Move characteristic and
       subtract Y from the Objective Control characteristic of models in that unit."
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    m = re.search(
        r'While an enemy unit(?: \(excluding [^)]+\))? is within (?P<rng>\d+)" of (?:this model|this unit|the bearer), '
        r"subtract (?P<move>\d+) from the Move characteristic and subtract (?P<oc>\d+) from the Objective Control characteristic of models in that unit",
        desc,
        flags=re.IGNORECASE,
    )
    if m:
        try:
            rng = float(m.group("rng"))
            move = int(m.group("move"))
            oc = int(m.group("oc"))
        except Exception:
            return None
        if rng <= 0 or move <= 0 or oc <= 0:
            return None
        return {
            "range": float(rng),
            "move": -abs(int(move)),
            "oc": -abs(int(oc)),
            "excluded_keywords": _parse_excluded_keywords(desc),
        }

    m = re.search(
        r'While an enemy unit(?: \(excluding [^)]+\))? is within (?P<rng>\d+)" of (?:this model|this unit|the bearer), '
        r"subtract (?P<oc>\d+) from the Objective Control characteristic of models in that enemy unit",
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    try:
        rng = float(m.group("rng"))
        oc = int(m.group("oc"))
    except Exception:
        return None
    if rng <= 0 or oc <= 0:
        return None
    return {
        "range": float(rng),
        "move": 0,
        "oc": -abs(int(oc)),
        "excluded_keywords": _parse_excluded_keywords(desc),
    }


def _parse_enemy_psychic_hazardous_aura(ability) -> Optional[dict]:
    """
    Strict parser for enemy auras like:
      "While an enemy PSYKER unit is within 12\" of this model, Psychic weapons equipped by models in that unit
       have the [HAZARDOUS] ability."
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    text = re.sub(r"[^a-zA-Z0-9]+", " ", desc).strip().lower()
    if "enemy" not in text or "within" not in text:
        return None
    if "psychic weapons" not in text or "hazardous" not in text:
        return None
    m_range = re.search(r"within\s+(?P<rng>\d+)", text)
    if not m_range:
        return None
    try:
        rng = float(m_range.group("rng"))
    except Exception:
        return None
    if rng <= 0:
        return None
    requires_psyker = "psyker unit" in text
    return {"range": float(rng), "requires_psyker_unit": bool(requires_psyker)}


def _parse_enemy_psychic_wound_penalty_aura(ability) -> Optional[dict]:
    """
    Strict parser for enemy auras like:
      "While an enemy unit is within 12\" of this model, each time a model in that unit makes a Psychic Attack,
       subtract 1 from the Wound roll."
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    text = re.sub(r"[^a-zA-Z0-9]+", " ", desc).strip().lower()
    if "enemy unit" not in text:
        return None
    if "psychic attack" not in text:
        return None
    if "wound roll" not in text:
        return None
    m_range = re.search(r"within\s+(?P<rng>\d+)", text)
    m_val = re.search(r"subtract\s+(?P<val>\d+)\s+from\s+the\s+wound\s+roll", text)
    if not m_range or not m_val:
        return None
    try:
        rng = float(m_range.group("rng"))
        val = int(m_val.group("val"))
    except Exception:
        return None
    if rng <= 0 or val <= 0:
        return None
    return {"range": float(rng), "amount": -abs(int(val))}


def _nurgles_gift_contagion_range(battle_round: int) -> float:
    # 10e baseline: BR1=3", BR2=6", BR3+=9"
    br = int(battle_round or 0)
    if br <= 1:
        return 3.0
    if br == 2:
        return 6.0
    return 9.0


def nurgles_gift_contagion_range(battle_round: int) -> float:
    return _nurgles_gift_contagion_range(battle_round)


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
    Nurgle's Gift (Aura): While an enemy unit is within Contagion Range of this unit, subtract 1 from Toughness.
    We implement the baseline Contagion Range scaling by battle round (3/6/9).
    """
    br = _get_battle_round_from_unit(source_unit) or _get_battle_round_from_unit(attacker_unit)
    rng = nurgles_gift_contagion_range(br)
    if not unit_within_range_of_unit(source_unit, target_unit, rng, use_attached_aggregate=True):
        return AuraAttackModifiers()
    return AuraAttackModifiers(
        target_toughness_delta=-1,
        target_toughness_reasons=(f"-1T from Nurgle's Gift (Aura) (Contagion Range {rng}\")",),
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
            if _requires_own_shooting_phase(ab) and not _attacker_in_own_shooting_phase(attacker_unit):
                continue
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

            # Nurgle's Gift (Aura) debuff (enemy-targeted).
            if _norm_name(ab_name) == _norm_name("Nurgle's Gift (Aura)"):
                out = out.merge(_nurgles_gift(attacker_unit, target_unit, source))
                continue

            # Belakor Shadow Form: Shadow Lord (Aura, Psychic) => re-roll Hit rolls of 1.
            if _norm_name(ab_name) == _norm_name("Shadow Lord (Aura, Psychic)"):
                try:
                    from ..rules.shadow_form import unit_has_active_shadow_form, KEY_SHADOW_LORD
                except Exception:
                    continue
                if not unit_has_active_shadow_form(source, KEY_SHADOW_LORD):
                    continue
                try:
                    if not (attacker_unit.has_any_keyword("LEGIONES DAEMONICA") or attacker_unit.has_any_keyword("SHADOW LEGION")):
                        continue
                except Exception:
                    continue
                if not unit_within_range_of_unit(source, attacker_unit, 6.0, use_attached_aggregate=True):
                    continue
                out = out.merge(
                    AuraAttackModifiers(
                        reroll_hit_ones=True,
                        reroll_hit_reasons=("Aura: re-roll Hit rolls of 1",),
                    )
                )
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
                if rr.get("attack_type") == "melee" and not _weapon_is_melee(weapon_profile):
                    continue
                if rr.get("attack_type") == "ranged" and _weapon_is_melee(weapon_profile):
                    continue
                if rr.get("excluded_keywords") and _excluded_by_unit_keywords(attacker_unit, rr.get("excluded_keywords", ())):
                    continue
                if not unit_within_range_of_unit(source, attacker_unit, float(rr["range"]), use_attached_aggregate=True):
                    continue
                if rr.get("reroll_hit"):
                    out = out.merge(
                        AuraAttackModifiers(
                            reroll_hit_ones=True,
                            reroll_hit_reasons=("Aura: re-roll Hit rolls of 1",),
                        )
                    )
                if rr.get("reroll_wound"):
                    out = out.merge(
                        AuraAttackModifiers(
                            reroll_wound_ones=True,
                            reroll_wound_reasons=("Aura: re-roll Wound rolls of 1",),
                        )
                    )

            # Generic strict parser: full Hit re-roll aura.
            full_hit = _parse_full_hit_reroll_aura(ab)
            if full_hit:
                if full_hit["faction_keyword"]:
                    matches = _unit_matches_keyword_phrase(attacker_unit, full_hit["faction_keyword"])
                    if not matches:
                        try:
                            matches = bool(attacker_unit.has_any_keyword(full_hit["faction_keyword"]))
                        except Exception:
                            matches = False
                    if not matches:
                        continue
                if full_hit.get("excluded_keywords") and _excluded_by_unit_keywords(attacker_unit, full_hit.get("excluded_keywords", ())):
                    continue
                if not unit_within_range_of_unit(source, attacker_unit, float(full_hit["range"]), use_attached_aggregate=True):
                    continue
                reason = f"Aura: re-roll Hit roll from {ab_name}"
                out = out.merge(
                    AuraAttackModifiers(
                        reroll_hit_full=True,
                        reroll_hit_full_reasons=(reason,),
                    )
                )

    # World Eaters: Idols of Khorne (Idol of Infinite Rage).
    army = getattr(attacker_unit, "get_parent_army", lambda: None)()
    mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
    if mgr is not None and hasattr(mgr, "idols_of_khorne_infinite_rage_sources_for_unit"):
        sources = mgr.idols_of_khorne_infinite_rage_sources_for_unit(attacker_unit, game_map=game_map)
        if sources:
            from ..rules.world_eaters_detachments import IDOL_OF_INFINITE_RAGE
            aura_name = str(getattr(IDOL_OF_INFINITE_RAGE, "name", "") or "Idol of Infinite Rage (Aura)")
            aura_key = _norm_name(aura_name)
            if not aura_key or aura_key not in applied_aura_names:
                if aura_key:
                    applied_aura_names.add(aura_key)
                out = out.merge(
                    AuraAttackModifiers(
                        hit=1,
                        wound=1,
                        hit_reasons=(f"+1 to hit from {aura_name}",),
                        wound_reasons=(f"+1 to wound from {aura_name}",),
                    )
                )

    return out


def get_enemy_aura_psychic_hazardous(attacker_unit, weapon_profile, *, game_map=None) -> tuple[bool, tuple[str, ...]]:
    """
    Return (is_hazardous, reasons) for enemy auras that make Psychic weapons hazardous.
    Dedupe by Aura name (same aura never double-applies).
    """
    if attacker_unit is None or weapon_profile is None:
        return False, ()
    try:
        if not weapon_profile.is_psychic():
            return False, ()
    except Exception:
        return False, ()
    if game_map is None:
        game_map = _get_map_from_attacker_unit(attacker_unit)
    if game_map is None:
        return False, ()

    reasons: list[str] = []
    applied_aura_names: set[str] = set()
    for source in list(game_map.get_enemy_units(attacker_unit)):
        for ab in _iter_possible_abilities(source):
            spec = _parse_enemy_psychic_hazardous_aura(ab)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if spec.get("requires_psyker_unit"):
                try:
                    if not attacker_unit.has_any_keyword("PSYKER"):
                        continue
                except Exception:
                    continue
            if not unit_within_range_of_unit(source, attacker_unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            reasons.append(f"Aura: {ab_name} (Psychic weapons hazardous)")
    return bool(reasons), tuple(reasons)


def get_enemy_aura_psychic_wound_penalties(attacker_unit, weapon_profile, *, game_map=None) -> list[tuple[int, str]]:
    """
    Return wound roll penalties from enemy auras that affect Psychic attacks.
    Dedupe by Aura name (same aura never double-applies).
    """
    if attacker_unit is None or weapon_profile is None:
        return []
    try:
        if not weapon_profile.is_psychic():
            return []
    except Exception:
        return []
    if game_map is None:
        game_map = _get_map_from_attacker_unit(attacker_unit)
    if game_map is None:
        return []

    penalties: list[tuple[int, str]] = []
    applied_aura_names: set[str] = set()
    for source in list(game_map.get_enemy_units(attacker_unit)):
        for ab in _iter_possible_abilities(source):
            spec = _parse_enemy_psychic_wound_penalty_aura(ab)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if not unit_within_range_of_unit(source, attacker_unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            amt = int(spec.get("amount", 0) or 0)
            if amt:
                penalties.append((amt, f"Aura: {ab_name}"))
    return penalties


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
                spec = _parse_leadership_oc_aura(ab)
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

def get_aura_leadership_bonus(unit, *, game_map=None) -> int:
    """
    Return additive Leadership bonus (negative improves Ld) from friendly auras affecting this unit.
    Only supports strict "improve Leadership and OC by N" patterns to avoid over-applying.
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
            spec = _parse_leadership_oc_aura(ab)
            if not spec:
                spec = _parse_leadership_only_aura(ab)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if spec["faction_keyword"] and not unit.has_any_keyword(spec["faction_keyword"]):
                continue
            if not unit_within_range_of_unit(source, unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            amt = int(spec["amount"])
            if amt:
                total -= abs(amt)
    return int(total)


def get_aura_advance_charge_roll_modifiers(unit, *, game_map=None) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """
    Return (advance_mods, charge_mods) from friendly Advance/Charge roll auras affecting this unit.
    Dedupe by Aura name (same aura never double-applies).
    """
    if unit is None:
        return [], []
    if game_map is None:
        game_map = _get_map_from_attacker_unit(unit)
    if game_map is None:
        return [], []

    advance_mods: list[tuple[int, str]] = []
    charge_mods: list[tuple[int, str]] = []
    applied_aura_names: set[str] = set()

    for source in list(game_map.get_friendly_units(unit)):
        for ab in _iter_possible_abilities(source):
            spec = _parse_advance_charge_roll_aura(ab)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if spec["faction_keyword"] and not unit.has_any_keyword(spec["faction_keyword"]):
                continue
            if not unit_within_range_of_unit(source, unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            amt = int(spec["amount"])
            advance_mods.append((amt, f"Aura: +{amt} to Advance rolls from {ab_name}"))
            charge_mods.append((amt, f"Aura: +{amt} to Charge rolls from {ab_name}"))

    # World Eaters: Idols of Khorne (Idol of Burning Wrath).
    army = getattr(unit, "get_parent_army", lambda: None)()
    mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
    if mgr is not None and hasattr(mgr, "idols_of_khorne_burning_wrath_sources_for_unit"):
        sources = mgr.idols_of_khorne_burning_wrath_sources_for_unit(unit, game_map=game_map)
        if sources:
            from ..rules.world_eaters_detachments import IDOL_OF_BURNING_WRATH
            aura_name = str(getattr(IDOL_OF_BURNING_WRATH, "name", "") or "Idol of Burning Wrath (Aura)")
            aura_key = _norm_name(aura_name)
            if not aura_key or aura_key not in applied_aura_names:
                if aura_key:
                    applied_aura_names.add(aura_key)
                advance_mods.append((1, f"Aura: +1 to Advance rolls from {aura_name}"))
                charge_mods.append((1, f"Aura: +1 to Charge rolls from {aura_name}"))

    return advance_mods, charge_mods


def get_aura_battleshock_test_modifiers(unit, *, game_map=None) -> list[tuple[int, str]]:
    """
    Return roll modifiers from enemy auras that affect Battle-shock and Leadership tests.
    Dedupe by Aura name (same aura never double-applies).
    """
    if unit is None:
        return []
    if game_map is None:
        game_map = _get_map_from_attacker_unit(unit)
    if game_map is None:
        return []

    modifiers: list[tuple[int, str]] = []
    applied_aura_names: set[str] = set()
    for source in list(game_map.get_enemy_units(unit)):
        for ab in _iter_possible_abilities(source):
            spec = _parse_battleshock_leadership_test_aura(ab)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if not unit_within_range_of_unit(source, unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            amt = int(spec["amount"])
            if amt:
                modifiers.append((amt, f"Aura: {ab_name}"))
    return modifiers


def get_enemy_aura_move_oc_penalties(unit, *, game_map=None) -> tuple[int, int]:
    """
    Return (move_penalty, oc_penalty) from enemy auras affecting this unit.
    Dedupe by Aura name (same aura never double-applies).
    """
    if unit is None:
        return 0, 0
    if game_map is None:
        game_map = _get_map_from_attacker_unit(unit)
    if game_map is None:
        return 0, 0

    move_penalty = 0
    oc_penalty = 0
    applied_aura_names: set[str] = set()
    for source in list(game_map.get_enemy_units(unit)):
        for ab in _iter_possible_abilities(source):
            spec = _parse_enemy_move_oc_penalty_aura(ab)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if spec.get("excluded_keywords") and _excluded_by_unit_keywords(unit, spec.get("excluded_keywords", ())):
                continue
            if not unit_within_range_of_unit(source, unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            move_penalty += int(spec["move"])
            oc_penalty += int(spec["oc"])
    return int(move_penalty), int(oc_penalty)


def get_enemy_aura_leadership_characteristic_penalty(unit, *, game_map=None) -> int:
    """
    Return additive Leadership characteristic penalties from enemy auras affecting this unit.
    Positive values worsen Leadership (higher target number to pass tests).
    """
    if unit is None:
        return 0
    if game_map is None:
        game_map = _get_map_from_attacker_unit(unit)
    if game_map is None:
        return 0

    total = 0
    applied_aura_names: set[str] = set()
    for source in list(game_map.get_enemy_units(unit)):
        for ab in _iter_possible_abilities(source):
            spec = _parse_enemy_leadership_characteristic_penalty_aura(ab)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if spec.get("excluded_keywords") and _excluded_by_unit_keywords(unit, spec.get("excluded_keywords", ())):
                continue
            if not unit_within_range_of_unit(source, unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            amt = int(spec.get("amount", 0) or 0)
            if amt:
                total += abs(int(amt))
    return int(total)


def get_aura_battleshock_test_reroll_sources(unit, *, game_map=None) -> list[str]:
    """
    Return reroll sources from friendly auras that allow re-rolling Battle-shock tests.
    Dedupe by Aura name (same aura never double-applies).
    """
    if unit is None:
        return []
    if game_map is None:
        game_map = _get_map_from_attacker_unit(unit)
    if game_map is None:
        return []

    sources: list[str] = []
    applied_aura_names: set[str] = set()
    for source in list(game_map.get_friendly_units(unit)):
        for ab in _iter_possible_abilities(source):
            if not _is_aura_ability(ab):
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)

            # Shadow of Khorne (Aura): friendly KHORNE LEGIONES DAEMONICA within 6" can re-roll Battle-shock tests.
            if _norm_name(ab_name) == _norm_name("Shadow of Khorne (Aura)"):
                try:
                    if not (unit.has_any_keyword("LEGIONES DAEMONICA") and unit.has_any_keyword("KHORNE")):
                        continue
                except Exception:
                    continue
                if not unit_within_range_of_unit(source, unit, 6.0, use_attached_aggregate=True):
                    continue
                sources.append(str(ab_name or "Shadow of Khorne (Aura)"))
                continue

            spec = _parse_battleshock_leadership_test_reroll_aura(ab)
            if not spec:
                continue
            if spec.get("faction_keyword"):
                matches = _unit_matches_keyword_phrase(unit, spec["faction_keyword"])
                if not matches:
                    try:
                        matches = bool(unit.has_any_keyword(spec["faction_keyword"]))
                    except Exception:
                        matches = False
                if not matches:
                    continue
            if spec.get("excluded_keywords") and _excluded_by_unit_keywords(unit, spec.get("excluded_keywords", ())):
                continue
            if not unit_within_range_of_unit(source, unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            if not (spec.get("reroll_battleshock") or spec.get("reroll_leadership")):
                continue
            sources.append(str(ab_name or "Aura"))

    return list(sources)


def _parse_melee_attacks_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X unit is within N\" of this model, add M to the Attacks characteristic of melee weapons equipped by models in that unit."
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
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


def _parse_melee_weapon_sustained_hits_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X unit is within N\" of this model, melee weapons in that unit have the [SUSTAINED HITS Y] ability."
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of this model, melee weapons in that unit have the \[SUSTAINED HITS (?P<val>\d+)\] ability',
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    return {
        "faction_keyword": str(m.group("faction_kw") or "").strip(),
        "range": float(m.group("rng")),
        "value": int(m.group("val")),
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
    if game_map is None or not hasattr(game_map, "get_friendly_units"):
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


def get_aura_weapon_keyword_bonuses(attacker_unit, weapon_profile, *, game_map=None) -> list[dict]:
    """
    Return aura-granted weapon keyword bonuses (e.g., Sustained Hits) affecting attacker_unit.
    """
    if attacker_unit is None or weapon_profile is None:
        return []
    pw = getattr(weapon_profile, "parent_wargear", None)
    if pw is None or not bool(pw.is_melee()):
        return []
    if game_map is None:
        game_map = _get_map_from_attacker_unit(attacker_unit)
    if game_map is None or not hasattr(game_map, "get_friendly_units"):
        return []

    rules: list[dict] = []
    applied_aura_names: set[str] = set()

    for source in list(game_map.get_friendly_units(attacker_unit)):
        for ab in _iter_possible_abilities(source):
            spec = _parse_melee_weapon_sustained_hits_aura(ab)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if spec["faction_keyword"] and not _unit_matches_keyword_phrase(attacker_unit, spec["faction_keyword"]):
                continue
            if not unit_within_range_of_unit(source, attacker_unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            try:
                val = int(spec["value"])
            except Exception:
                val = 0
            if val <= 0:
                continue
            rules.append(
                {
                    "attack_type": "melee",
                    "keyword": f"SUSTAINED HITS {int(val)}",
                    "source": ab_name or "Aura",
                }
            )

    return rules


def _parse_stealth_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X unit is within N\" of this model, models in that unit have the Stealth ability."
    Supports optional exclusion phrases like "(excluding Monsters)" and "this FORTIFICATION".
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    m = re.search(
        r"While a friendly (?P<faction_kw>.+?) unit(?: \(excluding (?P<exclude_kw>.+?)\))? is within (?P<rng>\d+)\" "
        r"of this (?:model|unit|fortification), models in that unit have the Stealth ability",
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    return {
        "faction_keyword": str(m.group("faction_kw") or "").strip(),
        "exclude_keyword": str(m.group("exclude_kw") or "").strip(),
        "range": float(m.group("rng")),
    }

def _parse_benefit_of_cover_aura(ability) -> Optional[dict]:
    """
    Strict parser for:
      "While a friendly X model/unit is within N\" of this model/unit, that X model has the Benefit of Cover."
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    m = re.search(
        r'While a friendly (?P<faction_kw>.+?) (?:unit|model) is within (?P<rng>\d+)" of this (?:model|unit|the bearer), '
        r"that .*? has the Benefit of Cover",
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r'While a friendly (?P<faction_kw>.+?) (?:unit|model) is within (?P<rng>\d+)" of this (?:model|unit|the bearer), '
            r"each time a ranged attack is allocated to a model in that unit, that model has the Benefit of Cover",
            desc,
            flags=re.IGNORECASE,
        )
    if not m:
        return None
    return {
        "faction_keyword": str(m.group("faction_kw") or "").strip(),
        "range": float(m.group("rng")),
    }


def get_aura_stealth(target_unit, *, game_map=None) -> tuple[bool, tuple[str, ...]]:
    """
    Return (has_stealth, reasons) from strict Stealth auras affecting target_unit.
    Dedupe by Aura name (same aura never double-applies).
    """
    if target_unit is None:
        return False, ()
    if game_map is None:
        game_map = _get_map_from_attacker_unit(target_unit)
    if game_map is None or not hasattr(game_map, "get_friendly_units"):
        return False, ()

    applied_aura_names: set[str] = set()
    reasons: list[str] = []

    for source in list(game_map.get_friendly_units(target_unit)):
        for ab in _iter_possible_abilities(source):
            spec = _parse_stealth_aura(ab)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if spec["faction_keyword"] and not target_unit.has_any_keyword(spec["faction_keyword"]):
                continue
            exclude_kw = str(spec.get("exclude_keyword", "") or "").strip()
            if exclude_kw:
                exclude_low = exclude_kw.lower()
                if target_unit.has_any_keyword(exclude_low):
                    continue
                if exclude_low.endswith("s") and target_unit.has_any_keyword(exclude_low[:-1]):
                    continue
            if not unit_within_range_of_unit(source, target_unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            reasons.append(f"Aura: Stealth from {ab_name}")
            return True, tuple(reasons)

    return False, ()

def get_aura_benefit_of_cover(target_unit, *, game_map=None) -> tuple[bool, tuple[str, ...]]:
    """
    Return (has_benefit_of_cover, reasons) from strict Benefit of Cover auras affecting target_unit.
    Dedupe by Aura name (same aura never double-applies).
    """
    if target_unit is None:
        return False, ()
    if game_map is None:
        game_map = _get_map_from_attacker_unit(target_unit)
    if game_map is None or not hasattr(game_map, "get_friendly_units"):
        return False, ()

    applied_aura_names: set[str] = set()
    reasons: list[str] = []

    for source in list(game_map.get_friendly_units(target_unit)):
        for ab in _iter_possible_abilities(source):
            spec = _parse_benefit_of_cover_aura(ab)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if spec["faction_keyword"]:
                matches = _unit_matches_keyword_phrase(target_unit, spec["faction_keyword"])
                if not matches:
                    try:
                        matches = bool(target_unit.has_any_keyword(spec["faction_keyword"]))
                    except Exception:
                        matches = False
                if not matches:
                    continue
            if not unit_within_range_of_unit(source, target_unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            reasons.append(f"Aura: Benefit of Cover from {ab_name}")
            return True, tuple(reasons)

    return False, ()


def get_aura_strength_bonus(attacker_unit, weapon_profile, *, game_map=None) -> tuple[int, tuple[str, ...]]:
    """
    Return (bonus_strength, reasons) from strict "Strength characteristic" auras affecting attacker_unit.
    Dedupe by Aura name (same aura never double-applies).
    """
    if attacker_unit is None or weapon_profile is None:
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
            spec = _parse_strength_aura(ab)
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
            if spec.get("attack_type") == "melee" and not _weapon_is_melee(weapon_profile):
                continue
            if spec.get("attack_type") == "ranged" and _weapon_is_melee(weapon_profile):
                continue
            if not unit_within_range_of_unit(source, attacker_unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            amt = int(spec["amount"])
            total += amt
            reasons.append(f"Aura: +{amt}S from {ab_name}")

    return int(total), tuple(reasons)


def get_aura_toughness_bonus(unit, *, game_map=None) -> tuple[int, tuple[str, ...]]:
    """
    Return (bonus_toughness, reasons) from strict "Toughness characteristic" auras affecting unit.
    Dedupe by Aura name (same aura never double-applies).
    """
    if unit is None:
        return 0, ()
    if game_map is None:
        game_map = _get_map_from_attacker_unit(unit)
    if game_map is None or not hasattr(game_map, "get_friendly_units"):
        return 0, ()

    total = 0
    reasons: list[str] = []
    applied_aura_names: set[str] = set()

    for source in list(game_map.get_friendly_units(unit)):
        for ab in _iter_possible_abilities(source):
            spec = _parse_toughness_aura(ab)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if spec["faction_keyword"] and not unit.has_any_keyword(spec["faction_keyword"]):
                continue
            if not unit_within_range_of_unit(source, unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            amt = int(spec["amount"])
            total += amt
            reasons.append(f"Aura: +{amt}T from {ab_name}")

    return int(total), tuple(reasons)


def get_aura_melee_ap_bonus(attacker_unit, weapon_profile, *, game_map=None) -> tuple[int, tuple[str, ...]]:
    """
    Return (ap_bonus, reasons) from strict "melee AP" auras affecting attacker_unit.
    Dedupe by Aura name (same aura never double-applies).
    """
    if attacker_unit is None or weapon_profile is None:
        return 0, ()
    pw = getattr(weapon_profile, "parent_wargear", None)
    if pw is None or not bool(pw.is_melee()):
        return 0, ()
    if game_map is None:
        game_map = _get_map_from_attacker_unit(attacker_unit)
    if game_map is None or not hasattr(game_map, "get_friendly_units"):
        return 0, ()

    total = 0
    reasons: list[str] = []
    applied_aura_names: set[str] = set()
    charged = bool(getattr(getattr(attacker_unit, "round_state", None), "charged_this_round", False))

    for source in list(game_map.get_friendly_units(attacker_unit)):
        for ab in _iter_possible_abilities(source):
            spec = _parse_melee_ap_aura(ab)
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
            if spec.get("requires_charge") and not charged:
                continue
            if not unit_within_range_of_unit(source, attacker_unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            amt = int(spec["amount"])
            total += amt
            suffix = " after charge" if spec.get("requires_charge") else ""
            reasons.append(f"Aura: +{amt} AP (melee) from {ab_name}{suffix}")

    return int(total), tuple(reasons)

def get_aura_ap_bonus(attacker_model, weapon_profile, target_unit, *, game_map=None) -> tuple[int, tuple[str, ...]]:
    """
    Return (ap_bonus, reasons) from strict "closest enemy" AP auras affecting attacker_model.
    Dedupe by Aura name (same aura never double-applies).
    """
    if attacker_model is None or weapon_profile is None or target_unit is None:
        return 0, ()
    try:
        attacker_unit = getattr(attacker_model, "parent_unit", None)
    except Exception:
        attacker_unit = None
    if attacker_unit is None:
        return 0, ()
    if game_map is None:
        game_map = _get_map_from_attacker_unit(attacker_unit)
    if game_map is None or not hasattr(game_map, "get_friendly_units"):
        return 0, ()

    is_melee = False
    is_ranged = False
    try:
        if weapon_profile.parent_wargear is not None:
            is_melee = bool(weapon_profile.parent_wargear.is_melee())
            is_ranged = bool(weapon_profile.parent_wargear.is_ranged())
    except Exception:
        is_melee = False
        is_ranged = False
    if not is_melee and not is_ranged:
        try:
            is_ranged = bool(getattr(weapon_profile, "range", None) and int(getattr(weapon_profile.range, "max", 0) or 0) > 0)
        except Exception:
            is_ranged = False

    total = 0
    reasons: list[str] = []
    applied_aura_names: set[str] = set()

    for source in list(game_map.get_friendly_units(attacker_unit)):
        for ab in _iter_possible_abilities(source):
            spec = _parse_closest_enemy_ap_aura(ab)
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
            atype = spec.get("attack_type") or "any"
            if atype == "melee" and not is_melee:
                continue
            if atype == "ranged" and not is_ranged:
                continue
            if not unit_within_range_of_unit(source, attacker_unit, float(spec["range"]), use_attached_aggregate=True):
                continue
            target_is_closest = False
            if is_ranged and hasattr(attacker_unit, "is_target_closest_eligible"):
                try:
                    target_is_closest = bool(attacker_unit.is_target_closest_eligible(attacker_model, weapon_profile, target_unit, game_map))
                except Exception:
                    target_is_closest = False
            if not target_is_closest:
                target_is_closest = _target_is_closest_enemy_unit(attacker_unit, target_unit, game_map)
            if not target_is_closest:
                continue
            amt = int(spec["amount"])
            if amt:
                total += amt
                reasons.append(f"Aura: +{amt} AP (closest enemy) from {ab_name}")

    return int(total), tuple(reasons)


def get_enemy_engagement_oc_divisors(unit, *, game_map=None) -> tuple[str, ...]:
    """
    Return source-reason strings for each enemy ability that causes:
      "While an enemy unit is within Engagement Range of this unit, halve the Objective Control
       characteristic of models in that enemy unit"

    This is used to build DIV 2 modifiers for OC, and is intentionally strict to avoid
    over-applying unsupported rules text.
    """
    if unit is None:
        return ()
    if game_map is None:
        game_map = _get_map_from_attacker_unit(unit)
    if game_map is None:
        return ()

    reasons: list[str] = []
    applied_keys: set[str] = set()

    try:
        enemies = list(game_map.get_enemy_units(unit))
    except Exception:
        enemies = []

    for enemy in enemies:
        try:
            if not bool(getattr(enemy, "is_alive", lambda: True)()):
                continue
        except Exception:
            pass

        try:
            if not game_map.is_within_engagement_range(enemy, unit):
                continue
        except Exception:
            continue

        for ab in (getattr(enemy, "possible_abilities", []) or []):
            try:
                name = str(getattr(ab, "name", "") or "")
                desc = str(getattr(ab, "description", "") or "")
                if not desc:
                    continue
                # Strict match on the canonical phrasing (covers the example "Chitinous Horrors").
                if re.search(
                    r"While an enemy unit is within Engagement Range of this unit, halve the Objective Control characteristic of models in that enemy unit",
                    desc,
                    flags=re.IGNORECASE,
                ):
                    key = _norm_name(name) or _norm_name(desc)
                    if key and key in applied_keys:
                        continue
                    if key:
                        applied_keys.add(key)
                    reasons.append(f"enemy_engagement_oc_halve:{name or 'ability'}")
            except Exception:
                continue

    return tuple(reasons)
