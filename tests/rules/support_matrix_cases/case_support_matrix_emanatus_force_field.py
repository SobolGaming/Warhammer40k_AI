def test_support_matrix_classifies_emanatus_force_field_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    ability_name = "Emanatus Force Field (Aura)"
    description = (
        "While a friendly ADEPTUS MECHANICUS BATTLELINE model is wholly within 6\" of this model, "
        "that BATTLELINE model has a 4+ invulnerable save against ranged attacks."
    )

    status, notes = gsm._classify_ability(ability_name, description, faction_id="ADM")
    assert status == "Supported"
    assert "invulnerable save against ranged attacks" in str(notes).lower()
