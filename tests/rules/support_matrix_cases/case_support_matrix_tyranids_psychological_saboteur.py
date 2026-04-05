def test_support_matrix_classifies_tyranids_psychological_saboteur_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While an enemy unit is within 12\" of this model, if that unit is Battle-shocked: "
        "- Each time a model in that unit makes an attack, subtract 1 from the Hit roll. "
        "- Each time a friendly TYRANIDS model makes an attack that targets that unit, add 1 to the Wound roll."
    )
    status, notes = gsm._classify_ability("Psychological Saboteur (Aura)", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "battle-shocked" in notes_l
    assert "hit" in notes_l
    assert "wound" in notes_l
