def test_support_matrix_classifies_nuncio_aquila_objective_battleshock_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Once per battle, at the start of any Command phase, you can select one objective marker within 6\" of the bearer. "
        "All enemy units (excluding MONSTERS and VEHICLES ) within range of that objective marker must take a Battle-shock test. "
        "Each objective marker can only be targeted by this ability once per turn. Designer's Note: Place one Nuncio-aquila token "
        "next to the bearer, removing it once it uses this ability."
    )
    status, notes = gsm._classify_ability("Nuncio Aquila", description, faction_id="AOI")

    assert status == "Supported"
    notes_l = notes.lower()
    assert "objective marker" in notes_l
    assert "battle-shock" in notes_l or "battle shock" in notes_l
    assert "once per turn" in notes_l
