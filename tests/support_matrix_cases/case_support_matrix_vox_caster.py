def test_support_matrix_classifies_vox_caster_refund_with_officer_bonus_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time you target the bearer's unit with a Stratagem, roll one D6, adding 1 to the result "
        "if there are one or more friendly Officer models within 6\": on a 5+, you gain 1CP."
    )

    status, notes = gsm._classify_ability(
        "Vox-caster",
        description,
        faction_id="AM",
        datasheet_id="000000000",
    )

    assert status == "Supported"
    assert "officer" in notes.lower()
    assert "within 6" in notes.lower()
