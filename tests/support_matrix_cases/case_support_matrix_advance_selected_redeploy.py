import pytest


@pytest.mark.parametrize(
    "name,description",
    [
        (
            "Transdimensional Displacement",
            (
                "Each time this model is selected to Advance, you can remove it from the battlefield and set it up again "
                "anywhere on the battlefield that is more than 9\" horizontally away from all enemy units."
            ),
        ),
        (
            "Shokk Tunnel",
            (
                "Each time this model is selected to Advance, you can remove it from the battlefield and set it up again "
                "anywhere on the battlefield that is more than 9\" horizontally away from all enemy models instead of "
                "making an Advance move (this model is still considered to have Advanced this turn)."
            ),
        ),
    ],
)
def test_support_matrix_classifies_advance_selected_redeploy_as_supported(name, description):
    import scripts.generate_ability_support_matrix as gsm

    status, notes = gsm._classify_ability(name, description, faction_id="NEC")

    assert status == "Supported"
    assert "more than 9" in notes.lower()
    assert "counts as advanced" in notes.lower()
