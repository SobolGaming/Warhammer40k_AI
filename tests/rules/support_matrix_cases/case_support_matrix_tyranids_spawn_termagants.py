def test_support_matrix_classifies_tyranids_spawn_termagants_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "In your Command phase, you can select one friendly Termagants unit within 6\" of this model and return "
        "up to D3+3 destroyed models to that unit. A TERMAGANTS unit cannot be selected for this ability more than once per phase."
    )
    status, notes = gsm._classify_ability("Spawn Termagants", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "termagants" in notes_l
    assert "d3+3" in notes_l
