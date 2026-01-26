from __future__ import annotations

from typing import Iterable, Tuple, List, Any

from .modifiers import ModifierOp


CHOICE_KEEP_ALL = "keep_all"
CHOICE_IGNORE_NEGATIVE = "ignore_negative"
CHOICE_IGNORE_POSITIVE = "ignore_positive"
CHOICE_IGNORE_ALL = "ignore_all"

CHOICE_LABELS = {
    CHOICE_KEEP_ALL: "Keep all modifiers",
    CHOICE_IGNORE_NEGATIVE: "Ignore negative modifiers",
    CHOICE_IGNORE_POSITIVE: "Ignore positive modifiers",
    CHOICE_IGNORE_ALL: "Ignore all modifiers",
}


def available_modifier_choices(has_positive: bool, has_negative: bool) -> List[str]:
    if not has_positive and not has_negative:
        return []
    if has_positive and has_negative:
        return [CHOICE_KEEP_ALL, CHOICE_IGNORE_NEGATIVE, CHOICE_IGNORE_POSITIVE, CHOICE_IGNORE_ALL]
    if has_positive:
        return [CHOICE_KEEP_ALL, CHOICE_IGNORE_POSITIVE]
    if has_negative:
        return [CHOICE_KEEP_ALL, CHOICE_IGNORE_NEGATIVE]
    return [CHOICE_KEEP_ALL]


def options_for_signed_values(values: Iterable[int]) -> List[str]:
    has_positive = False
    has_negative = False
    for val in list(values or []):
        try:
            v = int(val)
        except Exception:
            v = 0
        if v > 0:
            has_positive = True
        elif v < 0:
            has_negative = True
        if has_positive and has_negative:
            break
    return available_modifier_choices(has_positive, has_negative)


def options_for_signed_pairs(modifiers: Iterable[Tuple[int, Any]]) -> List[str]:
    return options_for_signed_values([int(val) for val, _ in list(modifiers or [])])


def filter_signed_modifiers(
    modifiers: Iterable[Tuple[int, Any]],
    choice: str,
) -> Tuple[List[Tuple[int, Any]], List[Tuple[int, Any]]]:
    kept: List[Tuple[int, Any]] = []
    ignored: List[Tuple[int, Any]] = []
    mods = list(modifiers or [])
    if not mods:
        return kept, ignored
    if choice == CHOICE_IGNORE_ALL:
        return kept, list(mods)
    for val, reason in mods:
        try:
            v = int(val)
        except Exception:
            v = 0
        if choice == CHOICE_IGNORE_NEGATIVE and v < 0:
            ignored.append((val, reason))
        elif choice == CHOICE_IGNORE_POSITIVE and v > 0:
            ignored.append((val, reason))
        else:
            kept.append((val, reason))
    return kept, ignored


def _numeric_modifier_polarity(value: float, op: ModifierOp, *, base_val: float | None = None) -> int | None:
    if op == ModifierOp.ADD:
        return 1 if value > 0 else -1 if value < 0 else 0
    if op == ModifierOp.SUB:
        return -1 if value > 0 else 1 if value < 0 else 0
    if op == ModifierOp.MUL:
        return 1 if value > 1 else -1 if value < 1 else 0
    if op == ModifierOp.DIV:
        return -1 if value > 1 else 1 if value < 1 else 0
    if op == ModifierOp.SET:
        if base_val is None:
            return None
        return 1 if value > base_val else -1 if value < base_val else 0
    return 0


def options_for_numeric_modifiers(modifiers: Iterable[Any], *, base_val: float | None = None) -> List[str]:
    has_positive = False
    has_negative = False
    for mod in list(modifiers or []):
        try:
            val = float(getattr(mod, "value", 0) or 0)
        except Exception:
            val = 0.0
        try:
            op = getattr(mod, "op", None)
        except Exception:
            op = None
        polarity = _numeric_modifier_polarity(val, op, base_val=base_val)
        if polarity is None:
            has_positive = True
            has_negative = True
            break
        if polarity > 0:
            has_positive = True
        elif polarity < 0:
            has_negative = True
        if has_positive and has_negative:
            break
    return available_modifier_choices(has_positive, has_negative)


def filter_numeric_modifiers(
    modifiers: Iterable[Any],
    choice: str,
    *,
    base_val: float | None = None,
) -> Tuple[List[Any], List[Any]]:
    kept: List[Any] = []
    ignored: List[Any] = []
    mods = list(modifiers or [])
    if not mods:
        return kept, ignored
    if choice == CHOICE_IGNORE_ALL:
        return kept, list(mods)
    for mod in mods:
        try:
            val = float(getattr(mod, "value", 0) or 0)
        except Exception:
            val = 0.0
        try:
            op = getattr(mod, "op", None)
        except Exception:
            op = None
        polarity = _numeric_modifier_polarity(val, op, base_val=base_val)
        if polarity is None:
            kept.append(mod)
            continue
        if choice == CHOICE_IGNORE_NEGATIVE and polarity < 0:
            ignored.append(mod)
        elif choice == CHOICE_IGNORE_POSITIVE and polarity > 0:
            ignored.append(mod)
        else:
            kept.append(mod)
    return kept, ignored
