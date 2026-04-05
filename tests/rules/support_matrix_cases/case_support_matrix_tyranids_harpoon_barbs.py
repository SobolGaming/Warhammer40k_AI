def test_support_matrix_classifies_tyranids_harpoon_barbs_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Once per turn, when an enemy unit within Engagement Range of this model is selected to Fall Back, "
        "roll one D6: on a 2+, that unit suffers D6 mortal wounds."
    )
    status, notes = gsm._classify_ability("Harpoon Barbs", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "fall back" in notes_l
    assert "2+" in notes_l
    assert "d6 mortal wounds" in notes_l
