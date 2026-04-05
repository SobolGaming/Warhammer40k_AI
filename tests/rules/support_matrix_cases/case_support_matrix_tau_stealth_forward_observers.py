def test_support_matrix_classifies_tau_forward_observers_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time this unit is an Observer unit, until the end of the phase, each time a ranged attack is made by "
        "a model in a Guided unit that targets their Spotted unit, re-roll a Hit roll of 1 and re-roll a Wound roll of 1."
    )
    status, notes = gsm._classify_ability("Forward Observers", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "observer" in lowered
    assert "guided" in lowered
    assert "re-roll hit rolls of 1" in lowered
    assert "re-roll wound rolls of 1" in lowered
