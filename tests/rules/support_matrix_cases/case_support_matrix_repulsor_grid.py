def test_support_matrix_classifies_repulsor_grid_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    ability_name = "Repulsor Grid"
    description = (
        "Each time a ranged attack is allocated to a KASTELAN ROBOT model in this unit, "
        "on an unmodified saving throw of 6, the attacking unit suffers 1 mortal wound after it has "
        "finished making its attacks."
    )

    status, _notes = gsm._classify_ability(ability_name, description, faction_id="ADM")
    assert status == "Supported"

