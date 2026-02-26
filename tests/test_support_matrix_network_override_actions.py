def test_support_matrix_classifies_network_override_actions_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While this unit contains one or more Tech-Priest models, this unit is: "
        "Eligible to perform an Action in a turn in which it Advanced. "
        "Eligible to shoot in a turn in which it started an Action."
    )

    status, notes = gsm._classify_ability("Network Override", description, faction_id="ADM")
    assert status == "Supported"
    lowered = notes.lower()
    assert "unit contains tech priest" in lowered
    assert "perform actions after advancing" in lowered
    assert "shoot in turns it started an action" in lowered
