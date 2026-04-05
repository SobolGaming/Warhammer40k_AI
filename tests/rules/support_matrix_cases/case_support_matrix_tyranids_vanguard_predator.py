def test_support_matrix_classifies_tyranids_vanguard_predator_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time a model in this unit makes an attack, re-roll a Hit roll of 1. "
        "If the target is within range of one or more objective markers, re-roll a Wound roll of 1 as well."
    )
    status, notes = gsm._classify_ability("Vanguard Predator", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "re-roll hit rolls of 1" in notes_l
    assert "objective marker" in notes_l
    assert "wound rolls of 1" in notes_l
