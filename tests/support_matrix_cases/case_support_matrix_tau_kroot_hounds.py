def test_support_matrix_classifies_tau_hunting_hounds_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        'While this unit is within 12" of one or more friendly Kroot Character models, '
        "the Objective Control characteristic of models in this unit is 1."
    )
    status, notes = gsm._classify_ability("Hunting Hounds", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "objective control" in lowered
    assert "kroot character" in lowered
    assert "set to 1" in lowered
