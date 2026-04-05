def test_support_matrix_classifies_tau_advanced_scouting_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time this model makes a ranged attack that hits an enemy unit, until the end of the turn, "
        "each time another Kroot model from your army makes an attack that targets that enemy unit, "
        "you can re-roll the Hit roll."
    )
    status, notes = gsm._classify_ability("Advanced Scouting", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "kroot" in lowered
    assert "re-roll hit" in lowered
