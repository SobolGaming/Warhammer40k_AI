def test_support_matrix_classifies_tyranids_neuroloids_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "In your Command phase, you can select up to two friendly TYRANIDS units within 18\" of this model's unit. "
        "Until the start of your next Command phase, the selected units are always considered to be within Synapse Range of your army. "
        "Designer's Note: Place a Neuroloid token next to each selected unit to remind you."
    )
    status, notes = gsm._classify_ability("Neuroloids", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "command phase" in notes_l
    assert "up to 2" in notes_l
    assert "synapse range" in notes_l
