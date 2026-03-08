def test_support_matrix_classifies_tyranids_onslaught_aura_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While a friendly TYRANIDS unit is within 6\" of this model, ranged weapons equipped by models in that unit "
        "have the [ASSAULT] and [LETHAL HITS] abilities."
    )
    status, notes = gsm._classify_ability("Onslaught (Aura, Psychic)", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "aura" in notes_l
    assert "assault" in notes_l
    assert "lethal hits" in notes_l
