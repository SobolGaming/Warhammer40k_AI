def test_support_matrix_classifies_tau_crack_shot_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time this model makes a ranged attack, on a Critical Wound, "
        "that attack has an Armour Penetration characteristic of -3."
    )
    status, notes = gsm._classify_ability("Crack Shot", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "critical wounds" in lowered
    assert "ap characteristic" in lowered
    assert "-3" in lowered
