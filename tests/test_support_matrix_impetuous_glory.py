def test_support_matrix_classifies_impetuous_glory_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time this model makes a Charge move, until the end of the turn, add 1 to the Attacks "
        "characteristic of this model's reaper chain-cleaver - strike profile, and add 2 to the Attacks "
        "characteristic of this model's reaper chain-cleaver - sweep profile."
    )
    status, notes = gsm._classify_ability(
        "Impetuous Glory",
        description,
        faction_id="IK",
        datasheet_id="000000000",
    )

    assert status == "Supported"
    assert "strike profile" in notes.lower()
    assert "sweep profile" in notes.lower()
