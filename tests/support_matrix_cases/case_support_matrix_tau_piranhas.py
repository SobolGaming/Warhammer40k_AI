def test_support_matrix_classifies_tau_drone_harassment_tactics_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "At the end of your Movement phase, select one enemy unit within 12\" of this unit; "
        "that enemy unit must take a Battle-shock test."
    )
    status, notes = gsm._classify_ability("Drone Harassment Tactics", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "end of movement phase" in lowered
    assert "enemy unit within 12" in lowered
    assert "battle-shock" in lowered
