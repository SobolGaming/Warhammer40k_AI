def test_support_matrix_classifies_tyranids_bio_stimulus_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "In your Shooting phase, after this model has shot, select one enemy unit hit by one or more of those attacks. "
        "Until the end of the turn, each time a friendly TYRANIDS unit makes a melee attack that targets that enemy unit, "
        "improve the Armour Penetration characteristic of that attack by 1. "
        "The same enemy unit can only be affected by this ability once per turn."
    )
    status, notes = gsm._classify_ability("Bio-stimulus", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "tyranids" in notes_l
    assert "melee" in notes_l
    assert "ap +1" in notes_l
    assert "turn end" in notes_l
