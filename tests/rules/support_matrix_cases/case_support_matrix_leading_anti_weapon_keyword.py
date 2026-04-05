def test_support_matrix_classifies_leading_anti_weapon_keyword_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    status, notes = gsm._classify_ability(
        "Psyoculum",
        "While this model is leading a unit, ranged weapons equipped by models in that unit have the [ANTI-PSYKER 4+] ability.",
        faction_id="IA",
    )

    assert status == "Supported"
    notes_text = str(notes or "").lower()
    assert "leading" in notes_text
    assert "anti-psyker 4+" in notes_text
