def test_support_matrix_classifies_direct_early_arrival_clause_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    ability_name = "Quantum Invader"
    description = (
        "This model can be set up in the Reinforcements step of your first, second or third Movement phase, "
        "regardless of any mission rules."
    )

    status, notes = gsm._classify_ability(ability_name, description, faction_id="NCR")
    assert status == "Supported"
    assert "battle rounds 1-3" in str(notes)
