def test_support_matrix_classifies_tyranids_warp_field_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        'While a friendly Tyranids unit is within 6" of this unit, '
        "models in that unit have a 6+ invulnerable save."
    )
    status, notes = gsm._classify_ability("Warp Field (Aura, Psychic)", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "aura" in notes_l
    assert "friendly tyranids" in notes_l
    assert "6+" in notes_l
    assert "invulnerable save" in notes_l
