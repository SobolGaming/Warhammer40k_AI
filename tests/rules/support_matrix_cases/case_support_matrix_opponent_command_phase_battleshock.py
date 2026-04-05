def test_support_matrix_classifies_opponent_command_phase_battleshock_flat_penalty_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "In the Battle-shock step of your opponent's Command phase, if an enemy unit that is below its Starting Strength "
        "is within 6\" of this model, that enemy unit must take a Battle-shock test, subtracting 1 from the test when it does so."
    )
    status, notes = gsm._classify_ability("Dread Toll (Aura)", description, faction_id="DG")

    assert status == "Supported"
    assert "opponent command phase" in notes.lower()
    assert "-1" in notes


def test_support_matrix_classifies_opponent_command_phase_battleshock_psyker_penalty_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While an enemy unit is within 6\" of this model, in the Battle-shock step of your opponent's Command phase, "
        "if such an enemy unit is below its Starting Strength, it must take a Battle-shock test, subtracting 1 from that test "
        "if it is a PSYKER unit."
    )
    status, notes = gsm._classify_ability("Terrifying Chimes (Aura)", description, faction_id="DRU")

    assert status == "Supported"
    assert "opponent command phase" in notes.lower()
    assert "psyker" in notes.lower()
