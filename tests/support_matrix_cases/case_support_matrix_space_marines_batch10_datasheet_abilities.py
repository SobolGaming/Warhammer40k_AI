import pytest

from scripts.generate_ability_support_matrix import _classify_ability


@pytest.mark.parametrize(
    ("name", "description", "note_fragment"),
    [
        (
            "Unyielding in the Face of the Foe",
            "While this unit is within range of an objective marker you control, each time an attack with a Damage characteristic of 1 is allocated to a model in this unit, add 1 to any armour saving throw made against that attack.",
            "objective marker you control",
        ),
        (
            "Braziers of Judgement",
            "While a Character model is leading this unit, each time an attack targets this unit, subtract 1 from the Hit roll.",
            "led by a character",
        ),
    ],
)
def test_space_marines_batch10_support_matrix_cases(name: str, description: str, note_fragment: str):
    status, notes = _classify_ability(name, description, faction_id="SM")
    assert status == "Supported"
    assert note_fragment.lower() in str(notes).lower()
