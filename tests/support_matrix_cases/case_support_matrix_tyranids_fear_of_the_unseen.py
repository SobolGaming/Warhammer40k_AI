def test_support_matrix_classifies_tyranids_fear_of_the_unseen_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While an enemy unit is within 6\" of this model, worsen the Leadership characteristic of models in that unit by 1. "
        "In addition, in the Battle-shock step of your opponent's Command phase, if such an enemy unit is below its Starting Strength, "
        "it must take a Battle-shock test."
    )
    status, notes = gsm._classify_ability("Fear of the Unseen (Aura)", description, faction_id="TYR")

    assert status == "Supported"
    assert "opponent command phase" in notes.lower()
    assert "leadership" in notes.lower()
