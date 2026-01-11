from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple



def _normalize(text: str) -> str:
    t = (text or "").replace("’", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _strip_eligibility_prefix(text: str) -> str:
    """
    Wahapedia enhancement descriptions often start with an eligibility clause:
      "<KEYWORDS> model only. <rules text...>"
    We keep the rules text portion for parsing.
    """
    t = _normalize(text)
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


def parse_enhancement_effects(description: str) -> List[EnhancementEffectSpec]:
    """
    Parse a *small* set of common enhancement patterns.

    Returns a list of effect specs. If empty, no supported effect was recognized.
    """
    rules = _strip_eligibility_prefix(description)
    r = _normalize(rules)
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

    return out


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

        if eff.kind == "save_set" and eff.supported:
            from ..utility.modifiers import Modifier, ModifierOp
            unit.add_characteristic_modifier("save", Modifier(ModifierOp.SET, int(eff.value), source="enhancement:save_set"))
            continue

        if eff.kind == "reduce_damage_taken" and eff.supported:
            unit.special_rules["enhancement_reduce_damage_taken"] = int(unit.special_rules.get("enhancement_reduce_damage_taken", 0)) + eff.value
            continue


def classify_enhancement_support(description: str) -> Tuple[str, str]:
    """
    Classify enhancement support from the engine's enhancement effect parser.

    Note: enhancements are always loadable/assignable; we only distinguish whether their RULES effects are executed.
    """
    effects = parse_enhancement_effects(description)
    supported = [e for e in effects if e.supported]
    if supported:
        notes = "; ".join(e.notes for e in supported)
        return "Supported", notes
    if effects:
        # Recognized, but conditional/partial parsing.
        notes = "; ".join(e.notes for e in effects)
        return "Partial", notes
    return "Partial", "Loadable/assignable + points counted + UI display; rules effects not executed yet."
