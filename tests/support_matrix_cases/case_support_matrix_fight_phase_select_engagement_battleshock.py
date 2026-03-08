def test_support_matrix_classifies_fight_phase_select_engagement_battleshock_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "At the start of the Fight phase, select one enemy unit within Engagement Range of this model. "
        "That enemy unit must take a Battle-shock test."
    )
    status, notes = gsm._classify_ability("Terror Aura", description, faction_id="TYR")

    assert status == "Supported"
    notes_l = notes.lower()
    assert "engagement range" in notes_l
    assert "battle-shock" in notes_l or "battle shock" in notes_l
