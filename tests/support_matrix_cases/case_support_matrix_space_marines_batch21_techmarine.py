from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch21_techmarine_support_matrix_case():
    status, notes = _classify_ability(
        "Blessing of the Omnissiah",
        (
            "In your Command phase, you can select one friendly Adeptus Astartes Vehicle model within 3\" of this model. "
            "That model regains up to D3 lost wounds and, until the start of your next Command phase, each time that "
            "VEHICLE model makes an attack, add 1 to the Hit roll. Each model can only be selected for this ability once per turn."
        ),
        faction_id="SM",
    )
    assert status == "Supported"
    assert "gain +1 to hit" in str(notes).lower()
