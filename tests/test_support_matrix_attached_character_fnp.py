import pytest


@pytest.mark.parametrize(
    "name,description,expected_note_fragment",
    [
        (
            "Silent Bodyguard",
            "While a CHARACTER model is leading this unit, that CHARACTER model has the Feel No Pain 4+ ability.",
            "CHARACTER gains Feel No Pain 4+",
        ),
        (
            "Robotic Bodyguard",
            "While a Cybernetica Datasmith model is leading this unit, that model has the Feel No Pain 4+ ability.",
            "cybernetica datasmith model leads the unit, that model gains Feel No Pain 4+",
        ),
    ],
)
def test_support_matrix_attached_character_fnp_variants_supported(
    name: str,
    description: str,
    expected_note_fragment: str,
):
    import scripts.generate_ability_support_matrix as gsm

    status, notes = gsm._classify_ability(name, description, faction_id="ADM")
    assert status == "Supported"
    assert expected_note_fragment in notes
