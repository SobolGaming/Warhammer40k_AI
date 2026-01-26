from warhammer40k_ai.utility.modifier_choice import (
    CHOICE_KEEP_ALL,
    CHOICE_IGNORE_NEGATIVE,
    CHOICE_IGNORE_POSITIVE,
    CHOICE_IGNORE_ALL,
    options_for_signed_values,
    filter_signed_modifiers,
    options_for_numeric_modifiers,
    filter_numeric_modifiers,
)
from warhammer40k_ai.utility.modifiers import Modifier, ModifierOp


def test_options_for_signed_values():
    assert options_for_signed_values([]) == []
    assert options_for_signed_values([1, 2]) == [CHOICE_KEEP_ALL, CHOICE_IGNORE_POSITIVE]
    assert options_for_signed_values([-1, -2]) == [CHOICE_KEEP_ALL, CHOICE_IGNORE_NEGATIVE]
    assert options_for_signed_values([1, -1]) == [
        CHOICE_KEEP_ALL,
        CHOICE_IGNORE_NEGATIVE,
        CHOICE_IGNORE_POSITIVE,
        CHOICE_IGNORE_ALL,
    ]


def test_filter_signed_modifiers():
    mods = [(1, "pos"), (-1, "neg"), (2, "pos2")]
    kept, ignored = filter_signed_modifiers(mods, CHOICE_IGNORE_NEGATIVE)
    assert kept == [(1, "pos"), (2, "pos2")]
    assert ignored == [(-1, "neg")]
    kept, ignored = filter_signed_modifiers(mods, CHOICE_IGNORE_POSITIVE)
    assert kept == [(-1, "neg")]
    assert ignored == [(1, "pos"), (2, "pos2")]
    kept, ignored = filter_signed_modifiers(mods, CHOICE_IGNORE_ALL)
    assert kept == []
    assert ignored == mods


def test_numeric_modifier_options_and_filtering():
    mods = [
        Modifier(ModifierOp.ADD, 2, source="pos"),
        Modifier(ModifierOp.ADD, -1, source="neg"),
        Modifier(ModifierOp.MUL, 2, source="mul_pos"),
        Modifier(ModifierOp.DIV, 2, source="div_neg"),
    ]
    options = options_for_numeric_modifiers(mods, base_val=6)
    assert options == [
        CHOICE_KEEP_ALL,
        CHOICE_IGNORE_NEGATIVE,
        CHOICE_IGNORE_POSITIVE,
        CHOICE_IGNORE_ALL,
    ]
    kept, ignored = filter_numeric_modifiers(mods, CHOICE_IGNORE_NEGATIVE, base_val=6)
    assert [m.source for m in kept] == ["pos", "mul_pos"]
    assert [m.source for m in ignored] == ["neg", "div_neg"]
    kept, ignored = filter_numeric_modifiers(mods, CHOICE_IGNORE_POSITIVE, base_val=6)
    assert [m.source for m in kept] == ["neg", "div_neg"]
    assert [m.source for m in ignored] == ["pos", "mul_pos"]
