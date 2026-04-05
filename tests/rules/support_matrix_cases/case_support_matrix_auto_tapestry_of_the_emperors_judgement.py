def test_support_matrix_classifies_auto_tapestry_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While this unit is leading a unit and contains an Aestred Thurga model, weapons equipped by models in "
        "that unit have the [DEVASTATING WOUNDS] ability."
    )

    status, notes = gsm._classify_ability(
        "Auto-Tapestry of the Emperor's Judgement",
        description,
        faction_id="AS",
        datasheet_id="000000000",
    )

    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "aestred thurga" in lowered
    assert "devastating wounds" in lowered
