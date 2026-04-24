import pytest

from warhammer40k_ai.utility.dice import DiceCollection


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("D6", (1, 6, 0)),
        ("2D6", (2, 6, 0)),
        ("D6+1", (1, 6, 1)),
        ("D6-1", (1, 6, -1)),
        ("2D6+3", (2, 6, 3)),
        ("2D6-3", (2, 6, -3)),
        ("2 + D6", (1, 6, 2)),
    ],
)
def test_dice_collection_from_string(expression, expected):
    dice = DiceCollection.from_string(expression)

    assert (dice.number, dice.die_faces, dice.modifier) == expected


def test_dice_collection_str_includes_negative_modifier():
    assert str(DiceCollection.from_string("D6-1")) == "1D6-1"


@pytest.mark.parametrize("expression", ["", "D", "2+", "D6+-1", "2 - D6"])
def test_dice_collection_from_string_rejects_invalid_expression(expression):
    with pytest.raises(ValueError):
        DiceCollection.from_string(expression)
