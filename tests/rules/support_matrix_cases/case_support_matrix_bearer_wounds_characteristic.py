def test_support_matrix_classifies_bearer_wounds_characteristic_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = "The bearer has a Wounds characteristic of 6."
    status, notes = gsm._classify_ability("Relic Shield", description, faction_id="SM")

    assert status == "Supported"
    lowered = notes.lower()
    assert "bearer" in lowered
    assert "wounds characteristic of 6" in lowered
