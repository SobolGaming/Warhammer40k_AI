def test_support_matrix_classifies_tau_enforcer_commander_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While this model is leading a unit, each time a ranged attack targets that unit, "
        "worsen the Armour Penetration characteristic of that attack by 1."
    )
    status, notes = gsm._classify_ability("Enforcer Commander", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "ap worsened by 1" in lowered
    assert "ranged attacks" in lowered
