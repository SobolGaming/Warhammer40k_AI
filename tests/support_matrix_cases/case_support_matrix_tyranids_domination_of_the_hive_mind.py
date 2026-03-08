def test_support_matrix_classifies_tyranids_domination_of_the_hive_mind_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While a friendly TYRANIDS unit is within 9\" of this model, "
        "that unit is within your army's Synapse Range."
    )
    status, notes = gsm._classify_ability("Domination of the Hive Mind (Aura)", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "synapse range" in notes_l
    assert "9" in notes_l
