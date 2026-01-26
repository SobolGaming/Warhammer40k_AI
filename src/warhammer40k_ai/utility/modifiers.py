from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from fractions import Fraction
from typing import Iterable, Optional

from .count import Count, CountType


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
    t = str(raw).strip().replace("\u2019", "'")
    if not t:
        return False
    tl = t.lower()
    if tl in ("-", "\u2013", "*", "n/a"):
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


def compute_save_roll_modifier(
    target_model,
    *,
    attack_instance: Optional[dict] = None,
    ap: int = 0,
    save_type: str = "armor",
    weapon_profile: Optional[object] = None,
) -> tuple[int, list[str]]:
    """
    Return (dice_modifier, effects) for a saving throw.

    The modifier is capped at +1 (core rules). Negative modifiers are allowed.
    """
    dice_modifier = 0
    effects: list[str] = []
    atk = attack_instance if isinstance(attack_instance, dict) else {}
    save_type = str(save_type or "armor").strip().lower()

    def _coerce_int(value) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _resolve_damage_characteristic() -> Optional[int]:
        dmg_val = None
        if isinstance(atk, dict):
            dmg_val = atk.get("damage_characteristic")
        if dmg_val is None and weapon_profile is not None:
            dmg_val = getattr(weapon_profile, "damage", None)
        if isinstance(dmg_val, Count) and dmg_val.ctype == CountType.FLAT:
            return _coerce_int(dmg_val.value)
        if isinstance(dmg_val, int):
            return dmg_val
        if isinstance(dmg_val, str):
            s = dmg_val.strip()
            if s.isdigit():
                return int(s)
        return None

    def _resolve_unmodified_damage_characteristic() -> Optional[int]:
        dmg_val = None
        if weapon_profile is not None:
            dmg_val = getattr(weapon_profile, "damage", None)
        if dmg_val is None and isinstance(atk, dict):
            dmg_val = atk.get("damage_characteristic")
        if isinstance(dmg_val, Count) and dmg_val.ctype == CountType.FLAT:
            return _coerce_int(dmg_val.value)
        if isinstance(dmg_val, int):
            return dmg_val
        if isinstance(dmg_val, str):
            s = dmg_val.strip()
            if s.isdigit():
                return int(s)
        return None

    # Benefit of Cover: +1 to armor saves against ranged attacks (not invulnerable).
    if save_type == "armor" and atk.get("benefit_of_cover", False):
        ignores_cover = bool(atk.get("ignores_cover", False))
        if ignores_cover:
            effects.append("Ignores Cover")
        else:
            ap_val = _coerce_int(ap) or 0
            save_val = _coerce_int(getattr(target_model, "save", 7)) or 7
            if not (ap_val == 0 and save_val <= 3):
                dice_modifier += 1
                src = atk.get("benefit_of_cover_source")
                if src:
                    effects.append(f"Benefit of Cover ({src})")
                else:
                    effects.append("Benefit of Cover")

    # Armor save bonuses based on the incoming damage characteristic.
    if save_type == "armor":
        t_unit = getattr(target_model, "parent_unit", None)
        sr = getattr(t_unit, "special_rules", None) if t_unit is not None else None
        dmg_char = _resolve_damage_characteristic()
        if isinstance(sr, dict) and dmg_char is not None:
            spec = sr.get("armor_save_bonus_vs_damage_characteristic")
            if isinstance(spec, dict):
                bonus = spec.get(dmg_char)
                if bonus is None:
                    bonus = spec.get(str(dmg_char))
                bonus_val = _coerce_int(bonus) or 0
                if bonus_val:
                    dice_modifier += bonus_val
                    effects.append(f"+{bonus_val} armor save vs Damage {int(dmg_char)}")

        # Thousand Sons: Rubricae Phalanx detachment ("All is Dust").
        unmod_dmg_char = _resolve_unmodified_damage_characteristic()
        if unmod_dmg_char == 1:
            try:
                army = t_unit.get_parent_army() if t_unit is not None else None
            except Exception:
                army = None
            mgr = getattr(army, "thousand_sons_detachments", None) if army is not None else None
            if mgr is not None and callable(getattr(mgr, "rubricae_phalanx_armor_save_bonus", None)):
                try:
                    bonus_val = int(mgr.rubricae_phalanx_armor_save_bonus(target_model, damage_characteristic=unmod_dmg_char) or 0)
                except Exception:
                    bonus_val = 0
                if bonus_val:
                    dice_modifier += bonus_val
                    effects.append("All is Dust (+1 armor save vs Damage 1)")

    # Apply externally supplied save roll modifiers.
    extra_save_mods = atk.get("save_roll_modifiers")
    if extra_save_mods:
        for mod in extra_save_mods:
            val = None
            reason = None
            if isinstance(mod, dict):
                val = mod.get("value", mod.get("modifier"))
                reason = mod.get("reason", mod.get("source"))
            elif isinstance(mod, (tuple, list)):
                if mod:
                    val = mod[0]
                    if len(mod) > 1:
                        reason = mod[1]
            else:
                val = mod
            val_int = _coerce_int(val)
            if val_int is None:
                continue
            dice_modifier += val_int
            if reason:
                if isinstance(reason, (list, tuple)):
                    reason = ", ".join(str(r) for r in reason if str(r or "").strip())
                effects.append(f"{val_int:+d} save ({reason})")
            else:
                effects.append(f"{val_int:+d} save modifier")

    if dice_modifier > 1:
        dice_modifier = 1

    return int(dice_modifier), effects
