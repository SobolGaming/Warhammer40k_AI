from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch23_execrator_condemnatory_annihilation_support_matrix_case():
    description = (
        "Each time this model's unit has fought, if one or more enemy units were destroyed as a result of those "
        "attacks, each enemy unit within 6\" of this model must take a Battle-shock test."
    )

    status, notes = _classify_ability(
        "Condemnatory Annihilation",
        description,
        faction_id="SM",
        datasheet_id="000004135",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "battle-shock" in notes_l
    assert "within 6" in notes_l
    assert "model's unit" in notes_l
