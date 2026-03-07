def test_support_matrix_classifies_tau_ds8_support_turret_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "In your Movement phase, if this unit Remains Stationary, until the start of your next "
        "Movement phase, its Fire Warrior Shas'ui model is equipped with the support turret missile system weapon."
    )
    status, notes = gsm._classify_ability("DS8 Support Turret", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "remains stationary" in lowered
    assert "shas'ui" in lowered
    assert "support turret" in lowered
