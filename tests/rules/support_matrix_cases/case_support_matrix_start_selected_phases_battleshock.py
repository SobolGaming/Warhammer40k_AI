def test_support_matrix_classifies_start_selected_phases_enemy_range_battleshock_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Once per turn, at the start of your Command, Movement, Shooting, Charge or Fight phase, "
        "you can select one enemy unit within 18\" of this model. That unit must take a Battle-shock test, "
        "subtracting 1 from the test when it does so."
    )
    status, notes = gsm._classify_ability("Harbinger of Despair", description, faction_id="NEC")

    assert status == "Supported"
    notes_l = notes.lower()
    assert "once per turn" in notes_l
    assert "battle-shock" in notes_l or "battle shock" in notes_l
    assert "-1" in notes

