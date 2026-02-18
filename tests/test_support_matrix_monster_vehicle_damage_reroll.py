def test_support_matrix_classifies_model_allocated_monster_vehicle_damage_reroll_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time a ranged attack made by this model is allocated to a MONSTER or VEHICLE model, "
        "you can re-roll the Damage roll."
    )
    status, notes = gsm._classify_ability(
        "Annihilator",
        description,
        faction_id="IK",
        datasheet_id="000000000",
    )

    assert status == "Supported"
    assert "Damage roll" in notes
