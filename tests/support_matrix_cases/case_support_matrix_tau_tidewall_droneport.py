def test_support_matrix_classifies_tau_droneport_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time this FORTIFICATION is selected to shoot, its drone defender's weapon will target and resolve "
        "attacks against every enemy unit that is an eligible target to this FORTIFICATION."
    )
    status, notes = gsm._classify_ability("Droneport", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "fortification" in lowered
    assert "drone defenders" in lowered
    assert "every eligible enemy target" in lowered
