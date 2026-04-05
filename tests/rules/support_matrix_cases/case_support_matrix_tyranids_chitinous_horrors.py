def test_support_matrix_classifies_tyranids_chitinous_horrors_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While an enemy unit is within Engagement Range of this unit, "
        "halve the Objective Control characteristic of models in that enemy unit."
    )
    status, notes = gsm._classify_ability("Chitinous Horrors (Aura)", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "engagement range" in notes_l
    assert "objective control" in notes_l
    assert "halved" in notes_l
