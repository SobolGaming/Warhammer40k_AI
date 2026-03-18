from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch25_incursor_squad_multi_spectrum_array_support_matrix_case():
    status, notes = _classify_ability(
        "Multi-spectrum Array",
        "In your Shooting phase, after this unit has shot, select one enemy unit that was hit by one or more attacks made by this unit this phase. Until the end of the phase, each time a friendly ADEPTUS ASTARTES unit makes an attack that targets that enemy unit, add 1 to the Hit roll.",
        faction_id="SM",
        datasheet_id="000001159",
    )

    assert status == "Supported"
    assert "ADEPTUS ASTARTES" in notes
    assert "+1 to hit" in notes
