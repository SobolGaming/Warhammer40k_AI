def test_support_matrix_classifies_tyranids_spore_mine_cysts_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time this model ends a Normal move, you can select one of the following: "
        "- Select one enemy unit it moved over during that move and roll six D6: for each 3+, that unit suffers 1 mortal wound. "
        "- Add one new Spore Mines unit containing D3 models to your army and set it up anywhere on the battlefield that is wholly "
        "within 6\" of this model and more than 9\" horizontally away from all enemy units. "
        "You cannot select this option for more than one model per turn."
    )
    status, notes = gsm._classify_ability("Spore Mine Cysts", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "mortal" in notes_l
    assert "spore mines" in notes_l
    assert "one model per turn" in notes_l
