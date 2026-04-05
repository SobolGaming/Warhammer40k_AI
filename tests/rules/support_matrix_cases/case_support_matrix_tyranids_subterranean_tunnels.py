def test_support_matrix_classifies_tyranids_subterranean_tunnels_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "In your Movement phase, when this model is set up on the battlefield using the Deep Strike ability, it can "
        "use a subterranean tunnel. If it does, this model can be set up anywhere on the battlefield that is more "
        "than 6\" horizontally away from all enemy units, but until the end of the turn, it is not eligible to "
        "declare a charge."
    )
    status, notes = gsm._classify_ability("Subterranean Tunnels", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "deep strike" in notes_l
    assert "cannot declare a charge" in notes_l
    assert "6" in notes_l
