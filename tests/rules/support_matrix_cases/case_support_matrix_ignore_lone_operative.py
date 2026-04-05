def test_support_matrix_classifies_ignore_lone_operative_targeting_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time this model makes a ranged attack, when selecting targets for that attack, "
        "you can ignore the Lone Operative ability."
    )
    status, notes = gsm._classify_ability(
        "Ghosthunter Scope",
        description,
        faction_id="ASM",
        datasheet_id="000000000",
    )

    assert status == "Supported"
    assert "ignore lone operative" in str(notes or "").lower()
