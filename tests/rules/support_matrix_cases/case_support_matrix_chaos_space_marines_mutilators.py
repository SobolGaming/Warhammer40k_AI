def test_support_matrix_classifies_csm_mutilators_crushing_charge_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "You can re-roll charge rolls made for this unit, and each time this unit makes a Charge move, select one "
        "enemy unit and roll one D6 for each model in this unit that is within Engagement Range of that unit: "
        "for each 4+, that enemy unit suffers D3 mortal wounds."
    )

    status, notes = gsm._classify_ability(
        "Crushing Charge",
        description,
        faction_id="CSM",
        datasheet_id="000004206",
    )

    assert status == "Supported"
    lowered = notes.lower()
    assert "re-roll charge rolls" in lowered or "reroll charge rolls" in lowered
    assert "charge end" in lowered
    assert "d3 mortal wounds" in lowered
