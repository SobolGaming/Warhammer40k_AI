def test_support_matrix_classifies_weapon_specific_post_shoot_suppression_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "In your Shooting phase, after this model has shot, select one enemy unit (excluding MONSTERS and VEHICLES ) "
        "hit by one or more of those attacks made with an Armiger autocannon. Until the start of your next turn, "
        "that enemy unit is suppressed. While a unit is suppressed, each time a model in that unit makes an attack, "
        "subtract 1 from the Hit roll."
    )
    status, notes = gsm._classify_ability(
        "Suppressive Barrage",
        description,
        faction_id="IK",
        datasheet_id="000000000",
    )

    assert status == "Supported"
    assert "armiger autocannon" in notes.lower()
    assert "-1 to hit" in notes.lower()
