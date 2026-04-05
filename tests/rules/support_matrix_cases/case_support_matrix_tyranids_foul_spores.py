def test_support_matrix_classifies_tyranids_foul_spores_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While a friendly TYRANIDS unit is within 6\" of this unit, each time a ranged attack targets that unit, "
        "models in that unit have the Benefit of Cover against that attack. In addition, while a friendly TYRANIDS "
        "unit (excluding Monsters) is within 6\" of this unit, models in that unit have the Stealth ability."
    )
    status, notes = gsm._classify_ability("Foul Spores (Aura)", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "benefit of cover" in notes_l
    assert "stealth" in notes_l
    assert "non-monster" in notes_l
