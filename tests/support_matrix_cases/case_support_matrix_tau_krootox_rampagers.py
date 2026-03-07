def test_support_matrix_classifies_tau_kroot_linebreakers_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time this unit ends a Charge move, select one enemy unit within Engagement Range of it, "
        "then roll one D6 for each model in this unit that is within Engagement Range of that enemy unit: "
        "for each 4+, that enemy unit suffers D3 mortal wounds. "
        "If one or more enemy models are destroyed as a result of these mortal wounds, "
        "that enemy unit must take a Battle-shock test."
    )
    status, notes = gsm._classify_ability("Kroot Linebreakers", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "charge end" in lowered
    assert "d3 mortal wounds" in lowered
    assert "battle-shock" in lowered
