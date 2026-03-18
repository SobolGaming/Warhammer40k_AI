from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch21_the_sanguinor_support_matrix_case():
    description = (
        "While a friendly ADEPTUS ASTARTES unit is within 6\" of this model, "
        "you can re-roll Battle-shock and Leadership tests taken for that unit."
    )

    status, notes = _classify_ability(
        "Aura of Fervour (Aura)",
        description,
        faction_id="SM",
        datasheet_id="000000156",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "adeptus astartes" in notes_l
    assert "battle-shock" in notes_l
    assert "leadership tests" in notes_l
