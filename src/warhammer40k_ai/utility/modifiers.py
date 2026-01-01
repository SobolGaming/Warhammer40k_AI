from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from fractions import Fraction
from typing import Iterable, Optional


class ModifierOp(Enum):
    """
    Core Rules ordering (10e):
      - replacements first (SET)
      - then division
      - then multiplication
      - then addition
      - then subtraction
      - round up after applying all modifiers
    """

    SET = auto()
    DIV = auto()
    MUL = auto()
    ADD = auto()
    SUB = auto()


@dataclass(frozen=True)
class Modifier:
    op: ModifierOp
    value: int
    source: str = ""


def _ceil_fraction(x: Fraction) -> int:
    # math.ceil for Fractions without float conversion.
    n = int(x.numerator)
    d = int(x.denominator)
    if d == 0:
        raise ZeroDivisionError("fraction denominator is 0")
    # Ceiling division that works for negatives too.
    return -((-n) // d)


def is_unmodifiable_raw_characteristic(raw: Optional[str]) -> bool:
    """
    Core Rules: characteristics of '20+"', '-', '*', 'N/A' can never be modified.
    We treat the raw value (as found in Wahapedia fields) as authoritative when present.
    """
    if raw is None:
        return False
    t = str(raw).strip().replace("’", "'")
    if not t:
        return False
    tl = t.lower()
    if tl in ("-", "–", "*", "n/a"):
        return True
    # Exact "20+\"" forms commonly show up as 20+" (sometimes without the quote)
    if tl in ('20+"', "20+", '20"+'):
        return True
    return False


def apply_numeric_modifiers(
    base_value: int,
    modifiers: Iterable[Modifier],
    *,
    base_raw: Optional[str] = None,
) -> tuple[int, dict]:
    """
    Apply core-ordering numeric modifiers and return (final_int_value, debug_info).
    Rounds fractions UP after applying all modifiers.
    """
    if is_unmodifiable_raw_characteristic(base_raw):
        return int(base_value), {"unmodifiable_raw": True, "applied": ()}

    mods = [m for m in (modifiers or []) if m is not None]

    # Replacement stage (last SET wins).
    working = Fraction(int(base_value), 1)
    had_set_to_zero = False
    set_mods = [m for m in mods if m.op == ModifierOp.SET]
    if set_mods:
        working = Fraction(int(set_mods[-1].value), 1)
        had_set_to_zero = int(set_mods[-1].value) == 0

    # Ordered stages
    for op in (ModifierOp.DIV, ModifierOp.MUL, ModifierOp.ADD, ModifierOp.SUB):
        for m in mods:
            if m.op != op:
                continue
            v = int(m.value)
            if op == ModifierOp.DIV:
                if v == 0:
                    raise ZeroDivisionError(f"DIV modifier has value 0 (source={m.source})")
                working = working / Fraction(v, 1)
            elif op == ModifierOp.MUL:
                working = working * Fraction(v, 1)
            elif op == ModifierOp.ADD:
                working = working + Fraction(v, 1)
            elif op == ModifierOp.SUB:
                working = working - Fraction(v, 1)

    out = _ceil_fraction(working)
    return int(out), {"unmodifiable_raw": False, "had_set_to_zero": had_set_to_zero, "applied": tuple(mods)}


def apply_characteristic_caps(
    characteristic: str,
    value: int,
    *,
    allow_damage_zero: bool = False,
    is_ranged_weapon_range: bool = False,
    base_raw: Optional[str] = None,
) -> int:
    """
    Apply post-modifier caps/floors from Core Rules.
    """
    if is_unmodifiable_raw_characteristic(base_raw):
        return int(value)

    c = (characteristic or "").strip().lower()
    v = int(value)

    # Strength, Toughness, Attacks, Damage min 1 (Damage may be 0 if explicitly set to 0)
    if c in ("strength", "toughness", "attacks"):
        return max(1, v)
    if c == "damage":
        if allow_damage_zero and v == 0:
            return 0
        return max(1, v)

    # Leadership cannot be modified to 4+ (or better) or 9+ (or worse)
    if c in ("leadership", "ld"):
        return min(max(v, 5), 8)

    # AP cannot be modified to worse than 0 (AP is <= 0 in 10e)
    if c in ("ap", "armour_penetration", "armor_penetration"):
        return min(v, 0)

    # OC cannot be modified to worse than 0 (i.e. cannot be negative)
    if c in ("objective_control", "oc"):
        return max(v, 0)

    # Move cannot be less than 1"
    if c in ("movement", "move", "m"):
        return max(1, v)

    # Range for ranged weapons cannot be less than 1"
    if c in ("range",) and is_ranged_weapon_range:
        return max(1, v)

    return v


