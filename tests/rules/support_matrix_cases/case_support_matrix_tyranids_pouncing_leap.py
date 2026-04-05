def test_support_matrix_classifies_tyranids_pouncing_leap_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "You can target this unit with the Heroic Intervention Stratagem for 0CP, and can do so even if "
        "you have already used that Stratagem on a different unit this phase."
    )
    status, notes = gsm._classify_ability("Pouncing Leap", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "heroic intervention" in notes_l
    assert "0cp" in notes_l
