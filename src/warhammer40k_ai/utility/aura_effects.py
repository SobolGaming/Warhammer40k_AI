from __future__ import annotations

import re
import threading
from functools import lru_cache
from dataclasses import dataclass
from typing import Iterable, Optional

from .aura_utils import model_within_range_of_unit, unit_within_range_of_unit
from .entity_ids import get_entity_id
from .regex_hotspot_metrics import increment as increment_regex_hotspot


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


_AURA_SOURCE_PATTERN = r"(?:this unit|this model|this fortification|the bearer|this unit(?:'s| s) [a-z0-9 \-]+ model)"


def _count_regex_hotspot(name: str) -> None:
    increment_regex_hotspot(f"aura_effects:{str(name or '').strip()}")


_AURA_PARSE_CACHE: dict[tuple[str, str, str, str], object] = {}
_AURA_PARSE_CACHE_LOCK = threading.RLock()


def _clone_aura_parse_value(value):
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return value


def _normalize_cache_key_text(value: str) -> str:
    text = str(value or "").lower()
    text = (
        text.replace("\u00a0", " ")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    out_chars: list[str] = []
    prev_space = False
    for ch in text:
        is_ascii_alnum = ("a" <= ch <= "z") or ("0" <= ch <= "9")
        if is_ascii_alnum:
            out_chars.append(ch)
            prev_space = False
            continue
        if not prev_space:
            out_chars.append(" ")
            prev_space = True
    if out_chars and out_chars[-1] == " ":
        out_chars.pop()
    return "".join(out_chars)


def _aura_parse_cache_key(parser_key: str, ability) -> tuple[str, str, str, str]:
    if isinstance(ability, str):
        name = ""
        desc = str(ability or "")
        parameter = ""
    else:
        name = str(getattr(ability, "name", "") or "")
        desc = str(getattr(ability, "description", "") or "")
        parameter = str(getattr(ability, "parameter", "") or "")
    return (
        str(parser_key or "").strip(),
        _normalize_cache_key_text(name),
        _normalize_cache_key_text(desc),
        _normalize_cache_key_text(parameter),
    )


def _cached_parse_aura_spec(parser_key: str, ability, parser):
    key = _aura_parse_cache_key(parser_key, ability)
    with _AURA_PARSE_CACHE_LOCK:
        if key in _AURA_PARSE_CACHE:
            return _clone_aura_parse_value(_AURA_PARSE_CACHE[key])
    parsed = parser(ability)
    with _AURA_PARSE_CACHE_LOCK:
        _AURA_PARSE_CACHE[key] = _clone_aura_parse_value(parsed)
    return _clone_aura_parse_value(parsed)


def clear_aura_parse_cache() -> None:
    with _AURA_PARSE_CACHE_LOCK:
        _AURA_PARSE_CACHE.clear()

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


def _unit_matches_name_phrase(unit, phrase: str) -> bool:
    name_phrase = _normalize_keyword_phrase(phrase)
    if not name_phrase or unit is None:
        return False
    pattern = re.compile(rf"(?:^| ){re.escape(name_phrase)}(?: |$)")
    candidates: list[str] = []

    def _append_candidate(value) -> None:
        norm = _normalize_keyword_phrase(str(value or ""))
        if norm:
            candidates.append(norm)

    _append_candidate(getattr(unit, "name", ""))
    _append_candidate(getattr(unit, "_id", ""))
    datasheet = getattr(unit, "datasheet", None)
    if datasheet is not None:
        _append_candidate(getattr(datasheet, "name", ""))
    try:
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
    except Exception:
        root = unit
    if root is not None and root is not unit:
        _append_candidate(getattr(root, "name", ""))
        _append_candidate(getattr(root, "_id", ""))
        root_datasheet = getattr(root, "datasheet", None)
        if root_datasheet is not None:
            _append_candidate(getattr(root_datasheet, "name", ""))
    for model in list(getattr(unit, "models", []) or []):
        _append_candidate(getattr(model, "name", ""))

    for candidate in candidates:
        if pattern.search(candidate):
            return True
    return False


def _unit_matches_keyword_or_name_phrase(unit, phrase: str) -> bool:
    if _unit_matches_keyword_phrase(unit, phrase):
        return True
    try:
        if bool(unit.has_any_keyword(phrase)):
            return True
    except Exception:
        pass
    return _unit_matches_name_phrase(unit, phrase)


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
    if "(aura" in _norm(name):
        return True
    desc = _normalize_desc(str(getattr(ability, "description", "") or ""))
    if not desc:
        return False
    return bool(re.search(r"\bwhile an? (?:friendly|enemy)\b.*\bwithin\b", desc, flags=re.IGNORECASE))


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


def _chosen_of_blood_god_aura_range_bonus(source_unit, ability) -> float:
    """
    Cult of Blood enhancement: Chosen of the Blood God.
    Add 3" to the range of the bearer's Aura abilities.
    """
    if source_unit is None or ability is None:
        return 0.0
    try:
        name = str(getattr(ability, "name", ability) or "")
    except Exception:
        name = ""
    if "(aura" not in _norm(name):
        return 0.0
    try:
        sr = getattr(source_unit, "special_rules", None)
        if not isinstance(sr, dict) or not sr.get("enhancement_chosen_of_blood_god"):
            return 0.0
    except Exception:
        return 0.0
    try:
        army = source_unit.get_parent_army()
    except Exception:
        army = None
    mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
    if mgr is None:
        return 0.0
    try:
        if not mgr.is_cult_of_blood():
            return 0.0
    except Exception:
        return 0.0
    try:
        return float(sr.get("enhancement_chosen_of_blood_god_aura_range_bonus", 3) or 3)
    except Exception:
        return 3.0


def _aura_anchor_model_for_ability(source_unit, ability):
    if source_unit is None or ability is None:
        return None
    try:
        desc = _normalize_desc(str(getattr(ability, "description", "") or ""))
    except Exception:
        desc = ""
    if not desc:
        return None
    m = re.search(
        r"of this unit(?:'s| s) (?P<model>[a-z0-9 '\-]+?) model",
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    model_phrase = _normalize_keyword_phrase(str(m.group("model") or ""))
    if not model_phrase:
        return None
    for model in list(getattr(source_unit, "models", []) or []):
        try:
            if not bool(getattr(model, "is_alive", True)):
                continue
        except Exception:
            continue
        cand = _normalize_keyword_phrase(str(getattr(model, "name", "") or ""))
        if not cand:
            continue
        if cand == model_phrase or model_phrase in cand or cand in model_phrase:
            return model
    return None


def _unit_within_aura_range(source_unit, target_unit, base_range: float, *, ability=None) -> bool:
    try:
        rng = float(base_range)
    except Exception:
        return False
    rng += float(_chosen_of_blood_god_aura_range_bonus(source_unit, ability))
    anchor_model = _aura_anchor_model_for_ability(source_unit, ability)
    if anchor_model is not None:
        try:
            return model_within_range_of_unit(anchor_model, target_unit, float(rng), use_attached_aggregate=True)
        except Exception:
            pass
    return unit_within_range_of_unit(source_unit, target_unit, float(rng), use_attached_aggregate=True)


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
    _count_regex_hotspot("_requires_own_shooting_phase")
    desc = str(getattr(ability, "description", "") or "")
    if not desc:
        return False
    return _requires_own_shooting_phase_text(_normalize_desc(desc))


@lru_cache(maxsize=4096)
def _requires_own_shooting_phase_text(desc: str) -> bool:
    return bool(re.search(r"\byour shooting phase\b", str(desc or ""), flags=re.IGNORECASE))


def _weapon_is_melee(weapon_profile) -> bool:
    pw = getattr(weapon_profile, "parent_wargear", None)
    if pw is None:
        return False
    return bool(pw.is_melee())


def _legion_of_excess_aura_attacker_valid(attacker_unit) -> bool:
    if attacker_unit is None:
        return False
    try:
        if not bool(attacker_unit.has_any_keyword("LEGIONES DAEMONICA")):
            return False
        if not bool(attacker_unit.has_any_keyword("SLAANESH")):
            return False
        if bool(attacker_unit.has_any_keyword("MONSTER")):
            return False
    except Exception:
        return False
    return True


def _blood_legion_aura_attacker_valid(attacker_unit) -> bool:
    if attacker_unit is None:
        return False
    try:
        if not bool(attacker_unit.has_any_keyword("LEGIONES DAEMONICA")):
            return False
        if not bool(attacker_unit.has_any_keyword("KHORNE")):
            return False
        if bool(attacker_unit.has_any_keyword("MONSTER")):
            return False
    except Exception:
        return False
    return True


def _plague_legion_nurgle_aura_attacker_valid(attacker_unit) -> bool:
    if attacker_unit is None:
        return False
    try:
        if not bool(attacker_unit.has_any_keyword("LEGIONES DAEMONICA")):
            return False
        if not bool(attacker_unit.has_any_keyword("NURGLE")):
            return False
    except Exception:
        return False
    return True


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


def _excluded_by_battleshocked_state(unit, excluded_keywords: Iterable[str]) -> bool:
    if unit is None:
        return False
    has_battleshocked_exclusion = False
    for kw in excluded_keywords:
        token = str(kw or "").strip().lower().replace(" ", "").replace("-", "")
        if token in ("battleshocked",):
            has_battleshocked_exclusion = True
            break
    if not has_battleshocked_exclusion:
        return False
    try:
        fn = getattr(unit, "is_battle_shocked", None)
        if callable(fn):
            return bool(fn())
    except Exception:
        return False
    return bool(getattr(unit, "battle_shocked", False))


@lru_cache(maxsize=4096)
def _parse_excluded_keywords(desc: str) -> tuple[str, ...]:
    _count_regex_hotspot("_parse_excluded_keywords")
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
    _count_regex_hotspot("_parse_simple_plus_one_aura")
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
        rf'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of {_AURA_SOURCE_PATTERN}, '
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
    _count_regex_hotspot("_parse_reroll_ones_aura")
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
        rf"of {_AURA_SOURCE_PATTERN}",
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
    _count_regex_hotspot("_parse_full_hit_reroll_aura")
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
        rf"of {_AURA_SOURCE_PATTERN}, each time (?:a model in that unit|that model) makes an attack, "
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
    _count_regex_hotspot("_parse_add_oc_aura")
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
        rf'While a friendly (?P<faction_kw>.+?) (?:unit|model)(?: \((?P<exclude_a>[^)]+)\))? is within (?P<rng>\d+)"(?: \((?P<exclude_b>[^)]+)\))? of {_AURA_SOURCE_PATTERN}, '
        r'add (?P<amt>\d+) to the Objective Control characteristic of (?:(?:models? in that )?(?:unit|model))',
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    excluded: list[str] = []
    for key in ("exclude_a", "exclude_b"):
        raw = str(m.group(key) or "").strip()
        if not raw:
            continue
        raw = re.sub(r"^\s*excluding\s+", "", raw, flags=re.IGNORECASE).strip()
        excluded.extend(list(_parse_excluded_keywords(f"(excluding {raw})")))
    return {
        "faction_keyword": str(m.group("faction_kw") or "").strip(),
        "range": float(m.group("rng")),
        "amount": int(m.group("amt")),
        "excluded_keywords": tuple(excluded),
    }

def _parse_leadership_oc_aura(ability) -> Optional[dict]:
    _count_regex_hotspot("_parse_leadership_oc_aura")
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
        rf'While a friendly (?P<faction_kw>.+?) (?:unit|model) is within (?P<rng>\d+)" of {_AURA_SOURCE_PATTERN}, '
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
    _count_regex_hotspot("_parse_leadership_only_aura")
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
        rf'While a friendly (?P<faction_kw>.+?) (?:unit|model) is (?:(?:wholly )?within) (?P<rng>\d+)" '
        rf"of {_AURA_SOURCE_PATTERN}, improve that .*? Leadership characteristic by (?P<amt>\d+)",
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
    _count_regex_hotspot("_parse_battleshock_leadership_test_reroll_aura")
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
        rf'While a friendly (?P<faction_kw>.+?) (?:unit|model)(?: \((?P<exclude_a>[^)]+)\))? is within (?P<rng>\d+)"(?: \((?P<exclude_b>[^)]+)\))? '
        rf"of {_AURA_SOURCE_PATTERN}, you can re-?roll (?P<tests>.+?) tests? taken for that unit",
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
    _count_regex_hotspot("_parse_enemy_leadership_characteristic_penalty_aura")
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
    _count_regex_hotspot("_parse_advance_charge_roll_aura")
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


def _parse_charge_reroll_aura(ability) -> Optional[dict]:
    _count_regex_hotspot("_parse_charge_reroll_aura")
    """
    Strict parser for:
      "While a friendly X unit is within N\" of this model/unit, you can re-roll Charge rolls made for that unit."
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    m = re.search(
        rf'While a friendly (?P<faction_kw>.+?) units? is within (?P<rng>\d+)" of {_AURA_SOURCE_PATTERN}, '
        r"you can re-?roll Charge rolls made for (?:that|the) unit",
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


def _parse_move_characteristic_aura(ability) -> Optional[dict]:
    _count_regex_hotspot("_parse_move_characteristic_aura")
    """
    Strict parser for:
      "While a friendly X unit is within N\" of this model/unit, add Y\" to the Move characteristic of models in that unit."
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    m = re.search(
        rf'While a friendly (?P<faction_kw>.+?) units? is within (?P<rng>\d+)" of {_AURA_SOURCE_PATTERN}, '
        r'add (?P<amt>\d+)"? to the Move characteristic of models in that unit',
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    return {
        "faction_keyword": str(m.group("faction_kw") or "").strip(),
        "range": float(m.group("rng")),
        "amount": int(m.group("amt")),
        "excluded_keywords": _parse_excluded_keywords(desc),
    }


def _parse_fnp_aura(ability) -> Optional[dict]:
    _count_regex_hotspot("_parse_fnp_aura")
    """
    Strict parser for:
      "While a friendly X unit is within N\" of this model/unit, that unit/models in that unit have Feel No Pain Y+."
    """
    if not _is_aura_ability(ability):
        return None
    desc = _normalize_desc(getattr(ability, "description", ""))
    if not desc:
        return None
    m = re.search(
        rf'While a friendly (?P<faction_kw>.+?) (?:unit|model)(?: \((?P<exclude_a>[^)]+)\))? is within (?P<rng>\d+)"(?: \((?P<exclude_b>[^)]+)\))? of {_AURA_SOURCE_PATTERN}, '
        r'(?:models in that unit|that unit|that model) (?:has|have) (?:the )?Feel No Pain (?P<val>\d+)\+?\s*ability(?: (?P<cond>against .+))?',
        desc,
        flags=re.IGNORECASE,
    )
    if not m:
        m = re.search(
            rf'While a friendly (?P<faction_kw>.+?) (?:unit|model)(?: \((?P<exclude_a>[^)]+)\))? is within (?P<rng>\d+)"(?: \((?P<exclude_b>[^)]+)\))? of {_AURA_SOURCE_PATTERN}, '
            r'(?:models in that unit|that unit|that model) (?:has|have) (?:the )?Feel No Pain (?P<val>\d+)\+?(?: (?P<cond>against .+))?',
            desc,
            flags=re.IGNORECASE,
        )
    if not m:
        return None
    cond = str(m.group("cond") or "").strip().rstrip(".")
    return {
        "faction_keyword": str(m.group("faction_kw") or "").strip(),
        "range": float(m.group("rng")),
        "value": int(m.group("val")),
        "condition": cond,
        "excluded_keywords": _parse_excluded_keywords(desc),
    }


def _parse_strength_aura(ability) -> Optional[dict]:
    _count_regex_hotspot("_parse_strength_aura")
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
        rf'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of {_AURA_SOURCE_PATTERN}, '
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
        rf'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of {_AURA_SOURCE_PATTERN}, '
        r'(?:you can re-?roll Charge rolls made for (?:that|the) unit and )?'
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
    _count_regex_hotspot("_parse_melee_ap_aura")
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
        rf'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of {_AURA_SOURCE_PATTERN}, '
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
    _count_regex_hotspot("_parse_closest_enemy_ap_aura")
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
        rf'While a friendly (?P<faction_kw>.+?) (?:unit|model) is within (?P<rng>\d+)" of {_AURA_SOURCE_PATTERN}, '
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
    _count_regex_hotspot("_parse_toughness_aura")
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
        rf'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of {_AURA_SOURCE_PATTERN}, '
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
        rf'While a friendly (?P<faction_kw>.+?) unit is within (?P<rng>\d+)" of {_AURA_SOURCE_PATTERN}, '
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
    _count_regex_hotspot("_parse_battleshock_leadership_test_aura")
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
    _count_regex_hotspot("_parse_enemy_move_oc_penalty_aura")
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
        r'While an enemy unit(?: \(excluding [^)]+\))? is within (?P<rng>\d+)" '
        r"of (?:(?:this model|this unit|the bearer)|one or more units with this ability), "
        r"subtract (?P<move>\d+) from the Move characteristic and subtract (?P<oc>\d+) "
        r"from the Objective Control characteristic of models in that (?:enemy unit|unit)",
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
        m_min = re.search(r"to a minimum of (?P<min>\d+)", desc, flags=re.IGNORECASE)
        try:
            oc_minimum = int(m_min.group("min")) if m_min else 0
        except Exception:
            oc_minimum = 0
        return {
            "range": float(rng),
            "move": -abs(int(move)),
            "oc": -abs(int(oc)),
            "oc_minimum": int(max(0, oc_minimum)),
            "excluded_keywords": _parse_excluded_keywords(desc),
        }

    m = re.search(
        r'While an enemy unit(?: \(excluding [^)]+\))? is within (?P<rng>\d+)" '
        r"of (?:(?:this model|this unit|the bearer)|one or more units with this ability), "
        r"subtract (?P<oc>\d+) from the Objective Control characteristic of models in that (?:enemy unit|unit)",
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
    m_min = re.search(r"to a minimum of (?P<min>\d+)", desc, flags=re.IGNORECASE)
    try:
        oc_minimum = int(m_min.group("min")) if m_min else 0
    except Exception:
        oc_minimum = 0
    return {
        "range": float(rng),
        "move": 0,
        "oc": -abs(int(oc)),
        "oc_minimum": int(max(0, oc_minimum)),
        "excluded_keywords": _parse_excluded_keywords(desc),
    }


def _parse_enemy_psychic_hazardous_aura(ability) -> Optional[dict]:
    _count_regex_hotspot("_parse_enemy_psychic_hazardous_aura")
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
    _count_regex_hotspot("_parse_enemy_psychic_wound_penalty_aura")
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

def _source_is_nurgles_gift_source(source_unit, *, game_map=None) -> bool:
    if source_unit is None:
        return False
    has_explicit_nurgles_gift_ability = any(
        _norm_name(str(getattr(ab, "name", "") or "")) == _norm_name("Nurgle's Gift (Aura)")
        for ab in _iter_possible_abilities(source_unit)
    )
    source_army = source_unit.get_parent_army() if hasattr(source_unit, "get_parent_army") else None
    mgr = getattr(source_army, "nurgles_gift", None) if source_army is not None else None
    if mgr is None:
        return bool(has_explicit_nurgles_gift_ability)
    if not bool(getattr(mgr, "_army_has_gift", lambda: False)()):
        return bool(has_explicit_nurgles_gift_ability)
    valid_fn = getattr(mgr, "_unit_is_valid_contagion_source", None)
    if not callable(valid_fn):
        return bool(has_explicit_nurgles_gift_ability)
    return bool(valid_fn(source_unit, game_map=game_map) or has_explicit_nurgles_gift_ability)


def _nurgles_gift(attacker_unit, target_unit, source_unit, *, game_map=None) -> AuraAttackModifiers:
    """
    Nurgle's Gift (Aura): While an enemy unit is within Contagion Range of this unit, subtract 1 from Toughness.
    We implement the baseline Contagion Range scaling by battle round (3/6/9).
    """
    if not _source_is_nurgles_gift_source(source_unit, game_map=game_map):
        return AuraAttackModifiers()
    br = _get_battle_round_from_unit(source_unit) or _get_battle_round_from_unit(attacker_unit)
    rng = float(nurgles_gift_contagion_range(br))
    source_army = source_unit.get_parent_army() if hasattr(source_unit, "get_parent_army") else None
    mgr = getattr(source_army, "nurgles_gift", None) if source_army is not None else None
    if mgr is not None:
        get_range_fn = getattr(mgr, "get_contagion_range", None)
        if callable(get_range_fn):
            rng = float(get_range_fn(br, source_unit=source_unit, game_map=game_map))
    if not unit_within_range_of_unit(source_unit, target_unit, rng, use_attached_aggregate=True):
        return AuraAttackModifiers()
    return AuraAttackModifiers(
        target_toughness_delta=-1,
        target_toughness_reasons=(f"-1T from Nurgle's Gift (Aura) (Contagion Range {rng}\")",),
    )


def get_aura_attack_modifiers(attacker_unit, target_unit, weapon_profile, *, game_map=None) -> AuraAttackModifiers:
    _count_regex_hotspot("get_aura_attack_modifiers")
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
    nurgles_gift_aura_key = _norm_name("Nurgle's Gift (Aura)")
    friendly_units = list(game_map.get_friendly_units(attacker_unit))

    # Chaos Knights (Iconoclast Fiefdom): Dread Tyrants (Aura)
    # While a friendly DAMNED unit is within 9" of a TITANIC CHAOS KNIGHTS source,
    # re-roll Hit rolls of 1 and Wound rolls of 1.
    for source in list(friendly_units or []):
        source_army = source.get_parent_army() if hasattr(source, "get_parent_army") else None
        ck_mgr = getattr(source_army, "chaos_knights_detachments", None) if source_army is not None else None
        applies_fn = getattr(ck_mgr, "iconoclast_dread_tyrants_applies", None) if ck_mgr is not None else None
        if not callable(applies_fn):
            continue
        if not bool(applies_fn(attacker_unit=attacker_unit, source_unit=source)):
            continue
        aura_key = _norm_name("Dread Tyrants (Aura)")
        if aura_key and aura_key in applied_aura_names:
            break
        if aura_key:
            applied_aura_names.add(aura_key)
        out = out.merge(
            AuraAttackModifiers(
                reroll_hit_ones=True,
                reroll_wound_ones=True,
                reroll_hit_reasons=("Aura: re-roll Hit rolls of 1 from Dread Tyrants (Aura)",),
                reroll_wound_reasons=("Aura: re-roll Wound rolls of 1 from Dread Tyrants (Aura)",),
            )
        )
        break

    for source in friendly_units:
        if nurgles_gift_aura_key not in applied_aura_names and _source_is_nurgles_gift_source(source, game_map=game_map):
            ng_mods = _nurgles_gift(attacker_unit, target_unit, source, game_map=game_map)
            if int(getattr(ng_mods, "target_toughness_delta", 0) or 0):
                out = out.merge(ng_mods)
                applied_aura_names.add(nurgles_gift_aura_key)

        source_sr = getattr(source, "special_rules", None)
        if isinstance(source_sr, dict):
            if bool(source_sr.get("enhancement_false_majesty_aura")):
                aura_key = _norm_name("False Majesty (Aura)")
                if not aura_key or aura_key not in applied_aura_names:
                    try:
                        aura_range = float(source_sr.get("enhancement_false_majesty_aura_range", 6.0) or 6.0)
                    except Exception:
                        aura_range = 6.0
                    if (
                        _weapon_is_melee(weapon_profile)
                        and _legion_of_excess_aura_attacker_valid(attacker_unit)
                        and _unit_within_aura_range(source, attacker_unit, float(max(0.0, aura_range)))
                    ):
                        if aura_key:
                            applied_aura_names.add(aura_key)
                        out = out.merge(
                            AuraAttackModifiers(
                                wound=1,
                                wound_reasons=("+1 to wound from False Majesty (Aura)",),
                            )
                        )
            if bool(source_sr.get("enhancement_dreaming_crown_aura")):
                aura_key = _norm_name("Dreaming Crown (Aura)")
                if not aura_key or aura_key not in applied_aura_names:
                    try:
                        aura_range = float(source_sr.get("enhancement_dreaming_crown_aura_range", 6.0) or 6.0)
                    except Exception:
                        aura_range = 6.0
                    if (
                        _weapon_is_melee(weapon_profile)
                        and _legion_of_excess_aura_attacker_valid(attacker_unit)
                        and _unit_within_aura_range(source, attacker_unit, float(max(0.0, aura_range)))
                    ):
                        if aura_key:
                            applied_aura_names.add(aura_key)
                        out = out.merge(
                            AuraAttackModifiers(
                                hit=1,
                                hit_reasons=("+1 to hit from Dreaming Crown (Aura)",),
                            )
                        )

        for ab in _iter_possible_abilities(source):
            if not _is_aura_ability(ab):
                continue

            ab_name = str(getattr(ab, "name", "") or "")
            if _requires_own_shooting_phase(ab) and not _attacker_in_own_shooting_phase(attacker_unit):
                continue
            if _norm_name(ab_name) == nurgles_gift_aura_key:
                if nurgles_gift_aura_key in applied_aura_names:
                    continue
                ng_mods = _nurgles_gift(attacker_unit, target_unit, source, game_map=game_map)
                if int(getattr(ng_mods, "target_toughness_delta", 0) or 0):
                    out = out.merge(ng_mods)
                    applied_aura_names.add(nurgles_gift_aura_key)
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
                if not _unit_within_aura_range(source, attacker_unit, 6.0, ability=ab):
                    continue
                out = out.merge(
                    AuraAttackModifiers(
                        reroll_hit_ones=True,
                        reroll_hit_reasons=("Aura: re-roll Hit rolls of 1",),
                    )
                )
                continue

            # Generic strict parser for "+1 to hit" auras (very limited subset).
            spec = _cached_parse_aura_spec("_parse_simple_plus_one_aura", ab, _parse_simple_plus_one_aura)
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
                if not _unit_within_aura_range(source, attacker_unit, float(spec["range"]), ability=ab):
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
            rr = _cached_parse_aura_spec("_parse_reroll_ones_aura", ab, _parse_reroll_ones_aura)
            if rr:
                if rr["faction_keyword"] and not attacker_unit.has_any_keyword(rr["faction_keyword"]):
                    continue
                if rr.get("attack_type") == "melee" and not _weapon_is_melee(weapon_profile):
                    continue
                if rr.get("attack_type") == "ranged" and _weapon_is_melee(weapon_profile):
                    continue
                if rr.get("excluded_keywords") and _excluded_by_unit_keywords(attacker_unit, rr.get("excluded_keywords", ())):
                    continue
                if not _unit_within_aura_range(source, attacker_unit, float(rr["range"]), ability=ab):
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
            full_hit = _cached_parse_aura_spec("_parse_full_hit_reroll_aura", ab, _parse_full_hit_reroll_aura)
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
                if not _unit_within_aura_range(source, attacker_unit, float(full_hit["range"]), ability=ab):
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
    _count_regex_hotspot("get_enemy_aura_psychic_hazardous")
    """
    Return (is_hazardous, reasons) for enemy auras that make Psychic weapons hazardous.
    Dedupe by Aura name (same aura never double-applies).
    """
    if attacker_unit is None or weapon_profile is None:
        return False, ()
    try:
        is_psychic_attack = bool(weapon_profile.is_psychic())
    except Exception:
        return False, ()
    if not is_psychic_attack:
        try:
            models = list(getattr(attacker_unit, "models", []) or [])
        except Exception:
            models = []
        probe_model = None
        for model in models:
            try:
                if bool(getattr(model, "is_alive", True)):
                    probe_model = model
                    break
            except Exception:
                continue
        matcher = getattr(weapon_profile, "_thousand_sons_infernal_fusillade_weapon_matches", None)
        if callable(matcher):
            try:
                is_psychic_attack = bool(matcher(probe_model))
            except Exception:
                is_psychic_attack = False
    if not is_psychic_attack:
        return False, ()
    if game_map is None:
        game_map = _get_map_from_attacker_unit(attacker_unit)
    if game_map is None:
        return False, ()

    reasons: list[str] = []
    applied_aura_names: set[str] = set()
    for source in list(game_map.get_enemy_units(attacker_unit)):
        for ab in _iter_possible_abilities(source):
            spec = _cached_parse_aura_spec("_parse_enemy_psychic_hazardous_aura", ab, _parse_enemy_psychic_hazardous_aura)
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
            if not _unit_within_aura_range(source, attacker_unit, float(spec["range"]), ability=ab):
                continue
            reasons.append(f"Aura: {ab_name} (Psychic weapons hazardous)")
    return bool(reasons), tuple(reasons)


def get_enemy_aura_psychic_wound_penalties(attacker_unit, weapon_profile, *, game_map=None) -> list[tuple[int, str]]:
    _count_regex_hotspot("get_enemy_aura_psychic_wound_penalties")
    """
    Return wound roll penalties from enemy auras that affect Psychic attacks.
    Dedupe by Aura name (same aura never double-applies).
    """
    if attacker_unit is None or weapon_profile is None:
        return []
    try:
        is_psychic_attack = bool(weapon_profile.is_psychic())
    except Exception:
        return []
    if not is_psychic_attack:
        try:
            models = list(getattr(attacker_unit, "models", []) or [])
        except Exception:
            models = []
        probe_model = None
        for model in models:
            try:
                if bool(getattr(model, "is_alive", True)):
                    probe_model = model
                    break
            except Exception:
                continue
        matcher = getattr(weapon_profile, "_thousand_sons_infernal_fusillade_weapon_matches", None)
        if callable(matcher):
            try:
                is_psychic_attack = bool(matcher(probe_model))
            except Exception:
                is_psychic_attack = False
    if not is_psychic_attack:
        return []
    if game_map is None:
        game_map = _get_map_from_attacker_unit(attacker_unit)
    if game_map is None:
        return []

    penalties: list[tuple[int, str]] = []
    applied_aura_names: set[str] = set()
    for source in list(game_map.get_enemy_units(attacker_unit)):
        for ab in _iter_possible_abilities(source):
            spec = _cached_parse_aura_spec("_parse_enemy_psychic_wound_penalty_aura", ab, _parse_enemy_psychic_wound_penalty_aura)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if not _unit_within_aura_range(source, attacker_unit, float(spec["range"]), ability=ab):
                continue
            amt = int(spec.get("amount", 0) or 0)
            if amt:
                penalties.append((amt, f"Aura: {ab_name}"))
    return penalties


def get_aura_objective_control_bonus(unit, *, game_map=None) -> int:
    _count_regex_hotspot("get_aura_objective_control_bonus")
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
            spec = _cached_parse_aura_spec("_parse_add_oc_aura", ab, _parse_add_oc_aura)
            if not spec:
                spec = _cached_parse_aura_spec("_parse_leadership_oc_aura", ab, _parse_leadership_oc_aura)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            # Same Aura name never double-applies.
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if spec.get("faction_keyword"):
                matches = _unit_matches_keyword_phrase(unit, spec["faction_keyword"])
                if not matches:
                    has_any_keyword = getattr(unit, "has_any_keyword", None)
                    if callable(has_any_keyword):
                        matches = bool(has_any_keyword(spec["faction_keyword"]))
                if not matches:
                    continue
            excluded_keywords = tuple(spec.get("excluded_keywords", ()) or ())
            if excluded_keywords and _excluded_by_unit_keywords(unit, excluded_keywords):
                continue
            if excluded_keywords and _excluded_by_battleshocked_state(unit, excluded_keywords):
                continue
            if not _unit_within_aura_range(source, unit, float(spec["range"]), ability=ab):
                continue
            total += int(spec["amount"])
    return int(total)

def get_aura_leadership_bonus(unit, *, game_map=None) -> int:
    _count_regex_hotspot("get_aura_leadership_bonus")
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
            spec = _cached_parse_aura_spec("_parse_leadership_oc_aura", ab, _parse_leadership_oc_aura)
            if not spec:
                spec = _cached_parse_aura_spec("_parse_leadership_only_aura", ab, _parse_leadership_only_aura)
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
            if not _unit_within_aura_range(source, unit, float(spec["range"]), ability=ab):
                continue
            amt = int(spec["amount"])
            if amt:
                total -= abs(amt)
    return int(total)


def get_aura_advance_charge_roll_modifiers(unit, *, game_map=None) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    _count_regex_hotspot("get_aura_advance_charge_roll_modifiers")
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
            spec = _cached_parse_aura_spec("_parse_advance_charge_roll_aura", ab, _parse_advance_charge_roll_aura)
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
            if not _unit_within_aura_range(source, unit, float(spec["range"]), ability=ab):
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


def has_aura_charge_reroll(unit, *, game_map=None) -> bool:
    _count_regex_hotspot("has_aura_charge_reroll")
    """
    Return whether any friendly aura currently grants re-roll Charge rolls for this unit.
    """
    if unit is None:
        return False
    if game_map is None:
        game_map = _get_map_from_attacker_unit(unit)
    if game_map is None:
        return False

    applied_aura_names: set[str] = set()
    for source in list(game_map.get_friendly_units(unit)):
        for ab in _iter_possible_abilities(source):
            spec = _cached_parse_aura_spec("_parse_charge_reroll_aura", ab, _parse_charge_reroll_aura)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if spec.get("faction_keyword"):
                matches = _unit_matches_keyword_phrase(unit, spec["faction_keyword"])
                if not matches:
                    has_any_keyword = getattr(unit, "has_any_keyword", None)
                    if callable(has_any_keyword):
                        matches = bool(has_any_keyword(spec["faction_keyword"]))
                if not matches:
                    continue
            if spec.get("excluded_keywords") and _excluded_by_unit_keywords(unit, spec.get("excluded_keywords", ())):
                continue
            if not _unit_within_aura_range(source, unit, float(spec["range"]), ability=ab):
                continue
            return True
    return False


def get_aura_move_characteristic_bonus(unit, *, game_map=None) -> tuple[int, tuple[str, ...]]:
    _count_regex_hotspot("get_aura_move_characteristic_bonus")
    """
    Return (move_bonus, reasons) from friendly movement characteristic auras affecting this unit.
    """
    if unit is None:
        return 0, ()
    if game_map is None:
        game_map = _get_map_from_attacker_unit(unit)
    if game_map is None:
        return 0, ()

    total = 0
    reasons: list[str] = []
    applied_aura_names: set[str] = set()
    for source in list(game_map.get_friendly_units(unit)):
        for ab in _iter_possible_abilities(source):
            spec = _cached_parse_aura_spec("_parse_move_characteristic_aura", ab, _parse_move_characteristic_aura)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if spec.get("faction_keyword"):
                matches = _unit_matches_keyword_phrase(unit, spec["faction_keyword"])
                if not matches:
                    has_any_keyword = getattr(unit, "has_any_keyword", None)
                    if callable(has_any_keyword):
                        matches = bool(has_any_keyword(spec["faction_keyword"]))
                if not matches:
                    continue
            if spec.get("excluded_keywords") and _excluded_by_unit_keywords(unit, spec.get("excluded_keywords", ())):
                continue
            if not _unit_within_aura_range(source, unit, float(spec["range"]), ability=ab):
                continue
            amt = int(spec.get("amount", 0) or 0)
            if amt:
                total += int(amt)
                reasons.append(f"Aura: +{amt} Move from {ab_name}")
    return int(total), tuple(reasons)


def get_aura_fnp_entries(unit, *, game_map=None) -> list[tuple[int, Optional[str]]]:
    _count_regex_hotspot("get_aura_fnp_entries")
    """
    Return [(fnp_value, condition)] from friendly auras affecting this unit.
    """
    if unit is None:
        return []
    if game_map is None:
        game_map = _get_map_from_attacker_unit(unit)
    if game_map is None:
        return []

    result: list[tuple[int, Optional[str]]] = []
    seen_entries: set[tuple[int, str]] = set()
    applied_aura_names: set[str] = set()
    for source in list(game_map.get_friendly_units(unit)):
        for ab in _iter_possible_abilities(source):
            spec = _cached_parse_aura_spec("_parse_fnp_aura", ab, _parse_fnp_aura)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if spec.get("faction_keyword"):
                matches = _unit_matches_keyword_phrase(unit, spec["faction_keyword"])
                if not matches:
                    has_any_keyword = getattr(unit, "has_any_keyword", None)
                    if callable(has_any_keyword):
                        matches = bool(has_any_keyword(spec["faction_keyword"]))
                if not matches:
                    continue
            if spec.get("excluded_keywords") and _excluded_by_unit_keywords(unit, spec.get("excluded_keywords", ())):
                continue
            if not _unit_within_aura_range(source, unit, float(spec["range"]), ability=ab):
                continue
            try:
                value = int(spec.get("value", 0) or 0)
            except Exception:
                value = 0
            if value <= 0:
                continue
            cond = str(spec.get("condition", "") or "").strip()
            key = (int(value), cond.lower())
            if key in seen_entries:
                continue
            seen_entries.add(key)
            result.append((int(value), cond or None))
    return result


def get_aura_battleshock_test_modifiers(unit, *, game_map=None) -> list[tuple[int, str]]:
    _count_regex_hotspot("get_aura_battleshock_test_modifiers")
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
            spec = _cached_parse_aura_spec("_parse_battleshock_leadership_test_aura", ab, _parse_battleshock_leadership_test_aura)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if not _unit_within_aura_range(source, unit, float(spec["range"]), ability=ab):
                continue
            amt = int(spec["amount"])
            if amt:
                modifiers.append((amt, f"Aura: {ab_name}"))
    return modifiers


def _collect_enemy_aura_move_oc_penalty_state(unit, *, game_map=None) -> tuple[int, int, int]:
    if unit is None:
        return 0, 0, 0
    if game_map is None:
        game_map = _get_map_from_attacker_unit(unit)
    if game_map is None:
        return 0, 0, 0
    move_penalty = 0
    oc_penalty = 0
    oc_minimum_floor = 0
    applied_aura_names: set[str] = set()
    for source in list(game_map.get_enemy_units(unit)):
        for ab in _iter_possible_abilities(source):
            spec = _cached_parse_aura_spec("_parse_enemy_move_oc_penalty_aura", ab, _parse_enemy_move_oc_penalty_aura)
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
            if not _unit_within_aura_range(source, unit, float(spec["range"]), ability=ab):
                continue
            move_penalty += int(spec["move"])
            oc_penalty += int(spec["oc"])
            try:
                oc_minimum_floor = max(oc_minimum_floor, int(spec.get("oc_minimum", 0) or 0))
            except Exception:
                pass
    return int(move_penalty), int(oc_penalty), int(max(0, oc_minimum_floor))


def get_enemy_aura_move_oc_penalties(unit, *, game_map=None) -> tuple[int, int]:
    _count_regex_hotspot("get_enemy_aura_move_oc_penalties")
    """
    Return (move_penalty, oc_penalty) from enemy auras affecting this unit.
    Dedupe by Aura name (same aura never double-applies).
    """
    move_penalty, oc_penalty, _oc_floor = _collect_enemy_aura_move_oc_penalty_state(unit, game_map=game_map)
    return int(move_penalty), int(oc_penalty)


def get_enemy_aura_objective_control_minimum_floor(unit, *, game_map=None) -> int:
    _count_regex_hotspot("get_enemy_aura_objective_control_minimum_floor")
    """
    Return the highest minimum Objective Control floor imposed by enemy auras.
    """
    _move_penalty, _oc_penalty, oc_floor = _collect_enemy_aura_move_oc_penalty_state(unit, game_map=game_map)
    return int(max(0, oc_floor))


def get_enemy_aura_leadership_characteristic_penalty(unit, *, game_map=None) -> int:
    _count_regex_hotspot("get_enemy_aura_leadership_characteristic_penalty")
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
            spec = _cached_parse_aura_spec("_parse_enemy_leadership_characteristic_penalty_aura", ab, _parse_enemy_leadership_characteristic_penalty_aura)
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
            if not _unit_within_aura_range(source, unit, float(spec["range"]), ability=ab):
                continue
            amt = int(spec.get("amount", 0) or 0)
            if amt:
                total += abs(int(amt))
    return int(total)


def get_aura_battleshock_test_reroll_sources(unit, *, game_map=None) -> list[str]:
    _count_regex_hotspot("get_aura_battleshock_test_reroll_sources")
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
    # Rubricae Phalanx: Arcane Thralls (Aura) from enhancement bearers.
    try:
        rubricae_match = _unit_matches_keyword_phrase(unit, "RUBRICAE")
        if not rubricae_match:
            rubricae_match = bool(getattr(unit, "has_any_keyword", lambda *_a, **_k: False)("RUBRICAE"))
    except Exception:
        rubricae_match = False
    if rubricae_match:
        explicit_key = _norm_name("Arcane Thralls (Aura)")
        seen_roots: set[str] = set()
        for source in list(game_map.get_friendly_units(unit)):
            try:
                root = source.get_attached_unit_root() if hasattr(source, "get_attached_unit_root") else source
            except Exception:
                root = source
            root_key = str(get_entity_id(root) or "")
            if root_key and root_key in seen_roots:
                continue
            if root_key:
                seen_roots.add(root_key)
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = []
            if not members:
                members = [root]
            for member in members:
                if member is None:
                    continue
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict) or not sr.get("enhancement_arcane_thralls"):
                    continue
                bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
                bearer_model = None
                for model in list(getattr(member, "models", []) or []):
                    try:
                        if not getattr(model, "is_alive", True):
                            continue
                    except Exception:
                        continue
                    model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
                    if bearer_id and model_id != bearer_id:
                        continue
                    bearer_model = model
                    break
                if bearer_model is None:
                    continue
                if not model_within_range_of_unit(
                    bearer_model,
                    unit,
                    9.0,
                    use_attached_aggregate=True,
                ):
                    continue
                if explicit_key not in applied_aura_names:
                    applied_aura_names.add(explicit_key)
                    sources.append("Arcane Thralls (Aura)")
                break

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
                if not _unit_within_aura_range(source, unit, 6.0, ability=ab):
                    continue
                sources.append(str(ab_name or "Shadow of Khorne (Aura)"))
                continue

            spec = _cached_parse_aura_spec("_parse_battleshock_leadership_test_reroll_aura", ab, _parse_battleshock_leadership_test_reroll_aura)
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
            if not _unit_within_aura_range(source, unit, float(spec["range"]), ability=ab):
                continue
            if not (spec.get("reroll_battleshock") or spec.get("reroll_leadership")):
                continue
            sources.append(str(ab_name or "Aura"))

    return list(sources)


def _parse_melee_attacks_aura(ability) -> Optional[dict]:
    _count_regex_hotspot("_parse_melee_attacks_aura")
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
    _count_regex_hotspot("_parse_melee_weapon_sustained_hits_aura")
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
    _count_regex_hotspot("get_aura_melee_attacks_bonus")
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
            spec = _cached_parse_aura_spec("_parse_melee_attacks_aura", ab, _parse_melee_attacks_aura)
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
            if not _unit_within_aura_range(source, attacker_unit, float(spec["range"]), ability=ab):
                continue
            amt = int(spec["amount"])
            total += amt
            reasons.append(f"Aura: +{amt}A (melee) from {ab_name}")

    return int(total), tuple(reasons)


def get_aura_weapon_keyword_bonuses(attacker_unit, weapon_profile, *, game_map=None) -> list[dict]:
    _count_regex_hotspot("get_aura_weapon_keyword_bonuses")
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
        source_sr = getattr(source, "special_rules", None)
        if isinstance(source_sr, dict) and bool(source_sr.get("enhancement_slaughterthirst_aura")):
            aura_key = _norm_name("Slaughterthirst (Aura)")
            if not aura_key or aura_key not in applied_aura_names:
                try:
                    aura_range = float(source_sr.get("enhancement_slaughterthirst_aura_range", 6.0) or 6.0)
                except Exception:
                    aura_range = 6.0
                if (
                    _blood_legion_aura_attacker_valid(attacker_unit)
                    and _unit_within_aura_range(source, attacker_unit, float(max(0.0, aura_range)))
                ):
                    if aura_key:
                        applied_aura_names.add(aura_key)
                    rules.append(
                        {
                            "attack_type": "melee",
                            "keyword": "LANCE",
                            "source": str(source_sr.get("enhancement_slaughterthirst_aura_source", "") or "Slaughterthirst (Aura)").strip()
                            or "Slaughterthirst (Aura)",
                        }
                    )
        for ab in _iter_possible_abilities(source):
            spec = _cached_parse_aura_spec("_parse_melee_weapon_sustained_hits_aura", ab, _parse_melee_weapon_sustained_hits_aura)
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
            if not _unit_within_aura_range(source, attacker_unit, float(spec["range"]), ability=ab):
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
    _count_regex_hotspot("_parse_stealth_aura")
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
    _count_regex_hotspot("_parse_benefit_of_cover_aura")
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
        m = re.search(
            r'While a friendly (?P<faction_kw>.+?) (?:unit|model) is within (?P<rng>\d+)" of this (?:model|unit|the bearer), '
            r"each time a ranged attack targets that unit, models in that unit have the Benefit of Cover against that attack",
            desc,
            flags=re.IGNORECASE,
        )
    if not m:
        m = re.search(
            r'While a friendly (?P<faction_kw>.+?) (?:unit|model) is within (?P<rng>\d+)" of this (?:model|unit|the bearer), '
            r"each time a ranged attack targets that model, (?:it|that model) has the Benefit of Cover(?: against that attack)?",
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
    _count_regex_hotspot("get_aura_stealth")
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

    # Cabal of Chaos: SHROUD OF CHAOS (Aura) from an affected source unit.
    explicit_key = _norm_name("Shroud of Chaos (Aura)")
    if bool(getattr(target_unit, "has_any_keyword", lambda *_a, **_k: False)("HERETIC ASTARTES")):
        seen_roots: set[str] = set()
        for source in list(game_map.get_friendly_units(target_unit)):
            try:
                root = source.get_attached_unit_root() if hasattr(source, "get_attached_unit_root") else source
            except Exception:
                root = source
            root_key = str(get_entity_id(root) or "")
            if root_key and root_key in seen_roots:
                continue
            if root_key:
                seen_roots.add(root_key)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("shroud_of_chaos_aura_active"):
                continue
            if not _unit_within_aura_range(root, target_unit, 6.0):
                continue
            if explicit_key not in applied_aura_names:
                applied_aura_names.add(explicit_key)
                reasons.append("Aura: Stealth from Shroud of Chaos (Aura)")
            return True, tuple(reasons)

    for source in list(game_map.get_friendly_units(target_unit)):
        for ab in _iter_possible_abilities(source):
            spec = _cached_parse_aura_spec("_parse_stealth_aura", ab, _parse_stealth_aura)
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
            if not _unit_within_aura_range(source, target_unit, float(spec["range"]), ability=ab):
                continue
            reasons.append(f"Aura: Stealth from {ab_name}")
            return True, tuple(reasons)

    return False, ()

def get_aura_benefit_of_cover(target_unit, *, game_map=None) -> tuple[bool, tuple[str, ...]]:
    _count_regex_hotspot("get_aura_benefit_of_cover")
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
            spec = _cached_parse_aura_spec("_parse_benefit_of_cover_aura", ab, _parse_benefit_of_cover_aura)
            if not spec:
                continue
            ab_name = str(getattr(ab, "name", "") or "")
            aura_key = _norm_name(ab_name)
            if aura_key:
                if aura_key in applied_aura_names:
                    continue
                applied_aura_names.add(aura_key)
            if spec["faction_keyword"]:
                if not _unit_matches_keyword_or_name_phrase(target_unit, spec["faction_keyword"]):
                    continue
            if not _unit_within_aura_range(source, target_unit, float(spec["range"]), ability=ab):
                continue
            reasons.append(f"Aura: Benefit of Cover from {ab_name}")
            return True, tuple(reasons)

    return False, ()


def get_aura_strength_bonus(attacker_unit, weapon_profile, *, game_map=None) -> tuple[int, tuple[str, ...]]:
    _count_regex_hotspot("get_aura_strength_bonus")
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
            spec = _cached_parse_aura_spec("_parse_strength_aura", ab, _parse_strength_aura)
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
            if not _unit_within_aura_range(source, attacker_unit, float(spec["range"]), ability=ab):
                continue
            amt = int(spec["amount"])
            total += amt
            reasons.append(f"Aura: +{amt}S from {ab_name}")

    return int(total), tuple(reasons)


def get_aura_toughness_bonus(unit, *, game_map=None) -> tuple[int, tuple[str, ...]]:
    _count_regex_hotspot("get_aura_toughness_bonus")
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
            spec = _cached_parse_aura_spec("_parse_toughness_aura", ab, _parse_toughness_aura)
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
            if not _unit_within_aura_range(source, unit, float(spec["range"]), ability=ab):
                continue
            amt = int(spec["amount"])
            total += amt
            reasons.append(f"Aura: +{amt}T from {ab_name}")

    return int(total), tuple(reasons)


def get_aura_melee_ap_bonus(attacker_unit, weapon_profile, *, game_map=None) -> tuple[int, tuple[str, ...]]:
    _count_regex_hotspot("get_aura_melee_ap_bonus")
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
            spec = _cached_parse_aura_spec("_parse_melee_ap_aura", ab, _parse_melee_ap_aura)
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
            if not _unit_within_aura_range(source, attacker_unit, float(spec["range"]), ability=ab):
                continue
            amt = int(spec["amount"])
            total += amt
            suffix = " after charge" if spec.get("requires_charge") else ""
            reasons.append(f"Aura: +{amt} AP (melee) from {ab_name}{suffix}")

    return int(total), tuple(reasons)

def get_aura_ap_bonus(attacker_model, weapon_profile, target_unit, *, game_map=None) -> tuple[int, tuple[str, ...]]:
    _count_regex_hotspot("get_aura_ap_bonus")
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
        source_sr = getattr(source, "special_rules", None)
        if isinstance(source_sr, dict) and bool(source_sr.get("enhancement_font_of_spores_aura")):
            aura_key = _norm_name("Font of Spores (Aura)")
            if not aura_key or aura_key not in applied_aura_names:
                try:
                    aura_range = float(source_sr.get("enhancement_font_of_spores_aura_range", 6.0) or 6.0)
                except Exception:
                    aura_range = 6.0
                try:
                    aura_bonus = int(source_sr.get("enhancement_font_of_spores_aura_ap_bonus", 1) or 1)
                except Exception:
                    aura_bonus = 1
                if (
                    int(aura_bonus or 0) > 0
                    and _plague_legion_nurgle_aura_attacker_valid(attacker_unit)
                    and _unit_within_aura_range(source, attacker_unit, float(max(0.0, aura_range)))
                ):
                    if aura_key:
                        applied_aura_names.add(aura_key)
                    total += int(aura_bonus)
                    reasons.append(
                        f"Aura: +{int(aura_bonus)} AP from "
                        f"{str(source_sr.get('enhancement_font_of_spores_aura_source', '') or 'Font of Spores (Aura)').strip() or 'Font of Spores (Aura)'}"
                    )
        for ab in _iter_possible_abilities(source):
            spec = _cached_parse_aura_spec("_parse_closest_enemy_ap_aura", ab, _parse_closest_enemy_ap_aura)
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
            if not _unit_within_aura_range(source, attacker_unit, float(spec["range"]), ability=ab):
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
