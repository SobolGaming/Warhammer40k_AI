def test_support_matrix_classifies_tyranids_guardian_organism_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = "While a Character model is leading this unit, that CHARACTER has the Feel No Pain 5+ ability."
    status, notes = gsm._classify_ability("Guardian Organism", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "character" in notes_l
    assert "feel no pain 5+" in notes_l
