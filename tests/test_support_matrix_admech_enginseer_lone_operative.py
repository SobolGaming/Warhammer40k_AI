def test_support_matrix_classifies_admech_enginseer_lone_operative_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    ability_name = "Enginseer"
    description = (
        "While this model is within 3\" of one or more friendly Adeptus Mechanicus Vehicle units, "
        "unless it is leading a unit, this model has the Lone Operative ability."
    )

    status, notes = gsm._classify_ability(ability_name, description, faction_id="ADM")
    assert status == "Supported"
    assert "Disabled while leading a unit." in str(notes)
