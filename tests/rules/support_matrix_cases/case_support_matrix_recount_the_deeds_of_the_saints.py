def test_support_matrix_classifies_recount_the_deeds_of_the_saints_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While this unit is leading a unit and contains an Agathae Dolan model, each time that unit destroys "
        "an enemy unit, you gain 1 Miracle dice. When that Agathae Dolan model is destroyed, you gain D3 Miracle dice."
    )

    status, notes = gsm._classify_ability(
        "Recount the Deeds of the Saints",
        description,
        faction_id="AS",
        datasheet_id="000000000",
    )

    assert status == "Supported"
    notes_lower = str(notes or "").lower()
    assert "agathae dolan" in notes_lower
    assert "d3" in notes_lower
