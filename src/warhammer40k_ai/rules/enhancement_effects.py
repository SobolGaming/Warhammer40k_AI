from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple



def _strip_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", " ", str(text))


def _normalize(text: str) -> str:
    t = (text or "").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _normalize_rules_tokens(text: str) -> str:
    """
    Normalize enhancement rules text into a token string suitable for strict
    full-consumption matching.

    This intentionally removes punctuation/formatting while preserving the
    meaningful rule clauses.
    """
    t = _normalize(_strip_html(text))
    if not t:
        return ""
    # Normalize possessives and common variants.
    t = t.replace("re-roll", "reroll").replace("re roll", "reroll")
    t = re.sub(r"'s\b", "s", t)
    # Collapse to alphanumeric tokens.
    t = re.sub(r"[^A-Za-z0-9]+", " ", t).strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def normalize_enhancement_token(text: str) -> str:
    return _normalize(_strip_html(text)).lower()


def _strip_eligibility_prefix(text: str) -> str:
    """
    Wahapedia enhancement descriptions often start with an eligibility clause:
      "<KEYWORDS> model only. <rules text...>"
    We keep the rules text portion for parsing.
    """
    t = _normalize(_strip_html(text))
    lower = t.lower()
    # Split on first "... model only." / "... models only."
    for marker in (" model only.", " models only."):
        idx = lower.find(marker)
        if idx != -1:
            return t[idx + len(marker) :].strip()
    return t


@dataclass(frozen=True)
class EnhancementEffectSpec:
    """
    Pure specification for a parsed enhancement effect.

    The goal is not to parse all enhancements, only the high-frequency/simple patterns.
    """

    kind: str
    value: int
    notes: str
    supported: bool = True


@dataclass(frozen=True)
class EnhancementEligibilitySpec:
    clause: str
    keyword_groups: Tuple[frozenset[str], ...] = ()
    name_options: Tuple[str, ...] = ()

    def is_empty(self) -> bool:
        return not self.keyword_groups and not self.name_options


_KEYWORD_POOL: Optional[Set[str]] = None


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _load_keyword_pool() -> Set[str]:
    global _KEYWORD_POOL
    if _KEYWORD_POOL is not None:
        return _KEYWORD_POOL
    path = os.path.join(_repo_root(), "wahapedia_data", "Datasheets_keywords.json")
    keywords: Set[str] = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for row in data:
            kw = normalize_enhancement_token(row.get("keyword", ""))
            if kw:
                keywords.add(kw)
    except Exception:
        keywords = set()
    _KEYWORD_POOL = keywords
    return _KEYWORD_POOL


def _contains_phrase(haystack: str, needle: str) -> bool:
    return f" {haystack} ".find(f" {needle} ") != -1


def _parse_eligibility_option(option: str, keyword_pool: Set[str]) -> Tuple[Set[str], str]:
    opt_norm = normalize_enhancement_token(option)
    if not opt_norm:
        return set(), ""
    candidates = [kw for kw in keyword_pool if _contains_phrase(opt_norm, kw)]
    if not candidates:
        return set(), opt_norm
    remaining = f" {opt_norm} "
    selected: Set[str] = set()
    for kw in sorted(candidates, key=len, reverse=True):
        phrase = f" {kw} "
        if phrase in remaining:
            selected.add(kw)
            remaining = remaining.replace(phrase, " ")
    remaining = re.sub(r"\s+", " ", remaining).strip()
    if remaining:
        remaining = re.sub(r"\band\b", " ", remaining).strip()
        remaining = re.sub(r"\s+", " ", remaining).strip()
    return selected, remaining


def parse_enhancement_eligibility(description: str) -> Optional[EnhancementEligibilitySpec]:
    """
    Parse simple eligibility clauses of the form:
      "<KEYWORDS/UNITS> model only."
    Returns None if no eligibility clause is detected.
    """
    text = _normalize(_strip_html(description))
    if not text:
        return None
    m = re.match(r"^(.+?)\s+models?\s+only\.", text, flags=re.IGNORECASE)
    if not m:
        return None
    clause = m.group(1).strip()
    if not clause:
        return None
    clause_norm = _normalize(clause)
    clause_norm = clause_norm.replace(",", " or ")
    options = [o.strip() for o in re.split(r"\s+or\s+", clause_norm, flags=re.IGNORECASE) if o.strip()]
    if not options:
        return None
    keyword_pool = _load_keyword_pool()
    keyword_groups: List[frozenset[str]] = []
    name_options: List[str] = []
    for opt in options:
        selected, remaining = _parse_eligibility_option(opt, keyword_pool)
        if selected and not remaining:
            keyword_groups.append(frozenset(selected))
            continue
        name_opt = normalize_enhancement_token(opt)
        if name_opt:
            name_options.append(name_opt)
    spec = EnhancementEligibilitySpec(
        clause=clause.strip(),
        keyword_groups=tuple(keyword_groups),
        name_options=tuple(name_options),
    )
    if spec.is_empty():
        return None
    return spec


def parse_enhancement_effects(description: str) -> List[EnhancementEffectSpec]:
    """
    Parse a *small* set of common enhancement patterns.

    Returns a list of effect specs. If empty, no supported effect was recognized.
    """
    rules = _strip_eligibility_prefix(description)
    r = _normalize(rules)
    low = r.lower()
    out: List[EnhancementEffectSpec] = []

    # Add X" to Move characteristic.
    m = re.search(r"add\s+(\d+)\s*\"\s+to\s+the\s+bearer'?s\s+move\s+characteristic\.", r, flags=re.IGNORECASE)
    if m:
        out.append(
            EnhancementEffectSpec(
                kind="move_add",
                value=int(m.group(1)),
                notes=f'Add {m.group(1)}" to bearer Move.',
            )
        )

    # Add X to Wounds characteristic.
    m = re.search(r"add\s+(\d+)\s+to\s+the\s+bearer'?s\s+wounds\s+characteristic\.", r, flags=re.IGNORECASE)
    if m:
        out.append(
            EnhancementEffectSpec(
                kind="wounds_add",
                value=int(m.group(1)),
                notes=f"Add {m.group(1)} to bearer Wounds.",
            )
        )

    # Improve the Attacks, Strength and Damage characteristics of melee weapons equipped by the bearer by X.
    m = re.search(
        r"improve\s+the\s+attacks,\s*strength\s+and\s+damage\s+characteristics\s+of\s+melee\s+weapons\s+equipped\s+by\s+the\s+bearer\s+by\s+(\d+)\.",
        r,
        flags=re.IGNORECASE,
    )
    if m:
        out.append(
            EnhancementEffectSpec(
                kind="melee_asd_add",
                value=int(m.group(1)),
                notes=f"Improve melee weapons' A/S/D by {m.group(1)}.",
            )
        )

    # Add X to the Attacks, Strength and Damage characteristics of the bearer's melee weapons.
    m = re.search(
        r"add\s+(\d+)\s+to\s+the\s+attacks,\s*strength\s+and\s+damage\s+characteristics\s+of\s+the\s+bearer'?s\s+melee\s+weapons\.",
        r,
        flags=re.IGNORECASE,
    )
    if m:
        out.append(
            EnhancementEffectSpec(
                kind="melee_asd_add",
                value=int(m.group(1)),
                notes=f"Improve melee weapons' A/S/D by {m.group(1)}.",
            )
        )

    # Add/Improve X to the Attacks and Damage characteristics of the bearer's melee weapons.
    if "excluding extra attacks" not in low:
        m = re.search(
            r"add\s+(\d+)\s+to\s+the\s+attacks\s+and\s+damage\s+characteristics\s+of\s+"
            r"(?:the\s+bearer'?s\s+melee\s+weapons|melee\s+weapons\s+equipped\s+by\s+the\s+bearer)\b",
            r,
            flags=re.IGNORECASE,
        )
        if not m:
            m = re.search(
                r"improve\s+the\s+attacks\s+and\s+damage\s+characteristics\s+of\s+"
                r"(?:the\s+bearer'?s\s+melee\s+weapons|melee\s+weapons\s+equipped\s+by\s+the\s+bearer)\s+by\s+(\d+)\b",
                r,
                flags=re.IGNORECASE,
            )
        if m:
            out.append(
                EnhancementEffectSpec(
                    kind="melee_ad_add",
                    value=int(m.group(1)),
                    notes=f"Improve melee weapons' A/D by {m.group(1)}.",
                )
            )

    # The bearer has a Save characteristic of X+.
    m = re.search(
        r"(?:the\s+)?bearer\s+has\s+a\s+save\s+characteristic\s+of\s+(\d+)\+\.",
        r,
        flags=re.IGNORECASE,
    )
    if m:
        out.append(
            EnhancementEffectSpec(
                kind="save_set",
                value=int(m.group(1)),
                notes=f"Set bearer Save to {m.group(1)}+.",
            )
        )

    # Each time an attack is allocated to the bearer, subtract X from the Damage characteristic of that attack.
    # IMPORTANT: only supported when it is unconditional (no trailing 'If ...' clause).
    m = re.search(
        r"each\s+time\s+an\s+attack\s+is\s+allocated\s+to\s+the\s+bearer,\s+subtract\s+(\d+)\s+from\s+the\s+damage\s+characteristic\s+of\s+that\s+attack\.",
        r,
        flags=re.IGNORECASE,
    )
    if m:
        # If the description contains "If that attack was made..." it's a conditional variant -> not fully supported.
        if re.search(r"\bif\s+that\s+attack\b", r, flags=re.IGNORECASE):
            out.append(
                EnhancementEffectSpec(
                    kind="reduce_damage_taken",
                    value=int(m.group(1)),
                    notes="Conditional damage reduction (partially supported: unconditional portion only).",
                    supported=False,
                )
            )
        else:
            out.append(
                EnhancementEffectSpec(
                    kind="reduce_damage_taken",
                    value=int(m.group(1)),
                    notes=f"Reduce damage allocated to bearer by {m.group(1)} (min 1).",
                )
            )

    charge_conditional = False
    # Re-roll Charge rolls if target is within objective range.
    if re.search(
        r"bearer'?s\s+unit\s+declares\s+a\s+charge.*?objective\s+marker.*?re-?roll\s+the\s+charge\s+roll",
        r,
        flags=re.IGNORECASE,
    ):
        out.append(
            EnhancementEffectSpec(
                kind="reroll_charge_objective_target",
                value=1,
                notes="Re-roll Charge rolls if the charge target is within objective range.",
            )
        )
        charge_conditional = True

    # Re-roll Charge rolls on turns the unit is set up on the battlefield.
    if re.search(
        r"re-?roll\s+charge\s+rolls?\s+made\s+for\s+(?:the\s+bearer'?s\s+unit|that\s+unit).*?\bset\s+up\s+on\s+the\s+battlefield\b",
        r,
        flags=re.IGNORECASE,
    ):
        out.append(
            EnhancementEffectSpec(
                kind="reroll_charge_setup_turn",
                value=1,
                notes="Re-roll Charge rolls for the bearer's unit on setup turns.",
            )
        )
        charge_conditional = True

    # Re-roll Advance and Charge rolls.
    m = re.search(
        r"re-?roll\s+advance\s+and\s+charge\s+rolls?\s+made\s+for\s+(?:this\s+model|the\s+bearer'?s\s+unit|that\s+unit)",
        r,
        flags=re.IGNORECASE,
    )
    if m:
        note = "Re-roll Advance and Charge rolls."
        if "bearer" in low:
            note = "Re-roll Advance and Charge rolls for the bearer's unit."
        out.append(
            EnhancementEffectSpec(
                kind="reroll_advance_charge",
                value=1,
                notes=note,
            )
        )

    # Re-roll Charge rolls.
    m = None
    if not charge_conditional:
        m = re.search(
        r"re-?roll\s+charge\s+rolls?\s+made\s+for\s+(?:this\s+model|the\s+bearer'?s\s+unit|that\s+unit)",
        r,
        flags=re.IGNORECASE,
        )
    if m:
        note = "Re-roll Charge rolls."
        if "bearer" in low:
            note = "Re-roll Charge rolls for the bearer's unit."
        out.append(
            EnhancementEffectSpec(
                kind="reroll_charge",
                value=1,
                notes=note,
            )
        )

    # Once per battle, start of Fight phase: bearer unit gains Fights First until end of phase.
    if re.search(
        r"once\s+per\s+battle,\s+at\s+the\s+start\s+of\s+the\s+fight\s+phase,.*?"
        r"bearer\s+can\s+use\s+this\s+enhancement.*?"
        r"until\s+the\s+end\s+of\s+the\s+phase,\s+(?:models\s+in\s+)?the\s+bearer'?s\s+unit\s+(?:has|have)\s+the\s+fights\s+first\s+ability",
        r,
        flags=re.IGNORECASE,
    ):
        out.append(
            EnhancementEffectSpec(
                kind="fight_first_once_per_battle_fight_phase",
                value=1,
                notes="Once per battle: start of Fight phase, bearer unit can gain Fights First until end of phase.",
            )
        )

    return out


def _enhancement_rules_fully_consumed(description: str) -> bool:
    """
    Return True only when the enhancement rules text is fully matched by one of
    the supported full-consumption patterns.
    """
    rules = _strip_eligibility_prefix(description)
    tokens = _normalize_rules_tokens(rules)
    if not tokens:
        return False

    fullmatch_patterns = (
        # Add X" to Move.
        r"add \d+ to the bearers move characteristic",
        # Add X to Wounds.
        r"add \d+ to the bearers wounds characteristic",
        # Improve A/S/D of bearer melee weapons by X.
        r"improve the attacks strength and damage characteristics of melee weapons equipped by the bearer by \d+",
        # Add X to A/S/D of bearer melee weapons.
        r"add \d+ to the attacks strength and damage characteristics of the bearers melee weapons",
        # Add/Improve X to A/D of bearer melee weapons.
        r"add \d+ to the attacks and damage characteristics of (?:the bearers melee weapons|melee weapons equipped by the bearer)",
        r"improve the attacks and damage characteristics of (?:the bearers melee weapons|melee weapons equipped by the bearer) by \d+",
        # Set Save characteristic.
        r"(?:the )?bearer has a save characteristic of \d+",
        # Unconditional damage reduction.
        r"each time an attack is allocated to the bearer subtract \d+ from the damage characteristic of that attack",
        # Charge/Advance rerolls.
        r"(?:you can )?reroll advance and charge rolls made for (?:this model|the bearers unit|that unit)",
        r"(?:you can )?reroll charge rolls made for (?:this model|the bearers unit|that unit)",
        r"(?:you can )?reroll charge rolls made for (?:the bearers unit|that unit) in a turn in which it was set up on the battlefield",
        r"each time the bearers unit declares a charge if one or more targets of that charge are within range of an objective marker you can reroll the charge roll",
        # Once per battle: Fights First in Fight phase.
        r"once per battle at the start of the fight phase the bearer can use this enhancement if it does until the end of the phase models in the bearers unit have the fights first ability",
    )
    return any(re.fullmatch(pat, tokens) for pat in fullmatch_patterns)


def apply_enhancement_effects(unit, effects: List[EnhancementEffectSpec]) -> None:
    """
    Apply parsed enhancement effects onto a unit/model in a simple, engine-native way.
    """
    if not effects:
        return

    if getattr(unit, "special_rules", None) is None:
        unit.special_rules = {}

    # Prevent double application.
    applied = getattr(unit, "_enhancement_effect_kinds_applied", None)
    if applied is None:
        applied = set()
        setattr(unit, "_enhancement_effect_kinds_applied", applied)

    for eff in effects:
        if eff.kind in applied:
            continue
        applied.add(eff.kind)

        if eff.kind == "move_add" and eff.supported:
            from ..utility.modifiers import Modifier, ModifierOp
            unit.add_characteristic_modifier("movement", Modifier(ModifierOp.ADD, int(eff.value), source="enhancement:move_add"))
            continue

        if eff.kind == "wounds_add" and eff.supported:
            for m in getattr(unit, "models", []) or []:
                try:
                    m._base_wounds = int(getattr(m, "_base_wounds", 0)) + eff.value
                    m._wounds = int(getattr(m, "_wounds", 0)) + eff.value
                except Exception:
                    continue
            try:
                unit.starting_total_wounds = sum(int(getattr(m, "_base_wounds", 0)) for m in (getattr(unit, "models", []) or []))
            except Exception:
                pass
            continue

        if eff.kind == "melee_asd_add" and eff.supported:
            unit.special_rules["enhancement_melee_attacks_bonus"] = int(unit.special_rules.get("enhancement_melee_attacks_bonus", 0)) + eff.value
            unit.special_rules["enhancement_melee_strength_bonus"] = int(unit.special_rules.get("enhancement_melee_strength_bonus", 0)) + eff.value
            unit.special_rules["enhancement_melee_damage_bonus"] = int(unit.special_rules.get("enhancement_melee_damage_bonus", 0)) + eff.value
            continue

        if eff.kind == "melee_ad_add" and eff.supported:
            unit.special_rules["enhancement_melee_attacks_bonus"] = int(unit.special_rules.get("enhancement_melee_attacks_bonus", 0)) + eff.value
            unit.special_rules["enhancement_melee_damage_bonus"] = int(unit.special_rules.get("enhancement_melee_damage_bonus", 0)) + eff.value
            continue

        if eff.kind == "save_set" and eff.supported:
            from ..utility.modifiers import Modifier, ModifierOp
            unit.add_characteristic_modifier("save", Modifier(ModifierOp.SET, int(eff.value), source="enhancement:save_set"))
            continue

        if eff.kind == "reduce_damage_taken" and eff.supported:
            unit.special_rules["enhancement_reduce_damage_taken"] = int(unit.special_rules.get("enhancement_reduce_damage_taken", 0)) + eff.value
            continue

        if eff.kind == "reroll_advance" and eff.supported:
            unit.special_rules["enhancement_reroll_advance"] = True
            continue

        if eff.kind == "reroll_charge" and eff.supported:
            unit.special_rules["enhancement_charge_reroll"] = True
            continue

        if eff.kind == "reroll_advance_charge" and eff.supported:
            unit.special_rules["enhancement_reroll_advance"] = True
            unit.special_rules["enhancement_charge_reroll"] = True
            continue

        if eff.kind == "reroll_charge_setup_turn" and eff.supported:
            unit.special_rules["enhancement_charge_reroll_on_setup_turn"] = True
            continue

        if eff.kind == "reroll_charge_objective_target" and eff.supported:
            unit.special_rules["enhancement_charge_reroll_if_target_on_objective"] = True
            continue

        if eff.kind == "fight_first_once_per_battle_fight_phase" and eff.supported:
            unit.special_rules["enhancement_fight_first_once_per_battle"] = True
            continue


def classify_enhancement_support(description: str) -> Tuple[str, str]:
    """
    Classify enhancement support from the engine's enhancement effect parser.

    Note: enhancements are always loadable/assignable; we only distinguish whether their RULES effects are executed.
    """
    effects = parse_enhancement_effects(description)
    supported = [e for e in effects if e.supported]
    fully_consumed = _enhancement_rules_fully_consumed(description)
    if supported and fully_consumed:
        notes = "; ".join(e.notes for e in supported)
        return "Supported", notes
    if supported:
        notes = "; ".join(e.notes for e in supported)
        return "Partial", f"{notes} Additional clauses not fully supported."
    if effects:
        # Recognized, but conditional/partial parsing.
        notes = "; ".join(e.notes for e in effects)
        return "Partial", notes
    return "Partial", "Loadable/assignable + points counted + UI display; rules effects not executed yet."
