def test_support_matrix_classifies_shooty_power_trip_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    status, notes = gsm._classify_ability(
        "Shooty Power Trip",
        (
            "Each time this unit is selected to shoot, you can roll one D6: "
            "On a 1-2, this unit suffers D3 mortal wounds. "
            "On a 3-4, until the end of the phase, add 1 to the Strength characteristic of ranged weapons equipped by models in this unit. "
            "On a 5-6, until the end of the phase, add 1 to the Attacks characteristic of ranged weapons equipped by models in this unit."
        ),
        faction_id="ORK",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "mortal" in notes_l
    assert "strength" in notes_l
    assert "attacks" in notes_l


def test_support_matrix_classifies_pulsa_rokkit_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    status, notes = gsm._classify_ability(
        "Pulsa Rokkit",
        (
            "Once per battle, when the bearer's unit is selected to shoot in your Shooting phase, "
            "the bearer can use its pulsa rokkit. If it does, until the end of the phase, improve the Strength "
            "and Armour Penetration characteristics of ranged weapons equipped by models in the bearer's unit by 1."
        ),
        faction_id="ORK",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "once per battle" in notes_l
    assert "strength" in notes_l
    assert "ap" in notes_l
