import pytest


@pytest.mark.parametrize(
    "name,description,note_fragment",
    [
        (
            "Ram Jets",
            (
                'Each time this unit is selected to make a Normal or Advance move, until the end of the phase, '
                'add D3" to the Move characteristic of this model.'
            ),
            "normal/advance move",
        ),
        (
            "Thundercharge",
            (
                "If this model is equipped with a thundershock spear and a bellatus reaper chainsword, add 2 to "
                "the Attacks characteristic of melee weapons equipped by this model."
            ),
            "thundershock spear",
        ),
    ],
)
def test_imperial_knights_destrier_support_matrix_cases(name: str, description: str, note_fragment: str):
    import scripts.generate_ability_support_matrix as gsm

    status, notes = gsm._classify_ability(name, description, faction_id="IK")

    assert status == "Supported"
    assert note_fragment in notes.lower()
