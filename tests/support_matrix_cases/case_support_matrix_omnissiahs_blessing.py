def test_support_matrix_classifies_omnissiahs_blessing_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    ability_name = "Omnissiah's Blessing"
    description = (
        "In your Command phase, select one friendly ADEPTUS MECHANICUS model within 3\" of this model. "
        "That model regains up to D3 lost wounds and, if it is a VEHICLE model, until the start of your next Command phase, "
        "that model has the Feel No Pain 5+ ability. Each model can only be selected for this ability once per Command phase."
    )

    status, notes = gsm._classify_ability(ability_name, description, faction_id="ADM")
    assert status == "Supported"
    assert "Feel No Pain 5+" in str(notes)
