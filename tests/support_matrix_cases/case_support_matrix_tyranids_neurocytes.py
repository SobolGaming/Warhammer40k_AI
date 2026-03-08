def test_support_matrix_classifies_tyranids_neurocytes_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While this unit is within Synapse Range of a friendly TYRANIDS unit "
        "(excluding NEUROGAUNT units), it has the Synapse keyword."
    )
    status, notes = gsm._classify_ability("Neurocytes", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "synapse range" in notes_l
    assert "non-neurogaunt" in notes_l
    assert "synapse" in notes_l
