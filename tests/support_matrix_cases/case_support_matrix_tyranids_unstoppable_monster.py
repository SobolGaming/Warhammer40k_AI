def test_support_matrix_classifies_tyranids_unstoppable_monster_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = "At the start of each player's Command phase, this model regains up to D3 lost wounds."
    status, notes = gsm._classify_ability("Unstoppable Monster", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "start of command phase" in notes_l
    assert "d3" in notes_l
    assert "regains up to" in notes_l
