def test_support_matrix_classifies_leading_shoot_and_charge_after_advance_or_fall_back_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    status, notes = gsm._classify_ability(
        "Ride and Ruin",
        "While this model is leading a unit, that unit is eligible to shoot and declare a charge in a turn in which it Advanced or Fell Back.",
        faction_id="SM",
    )

    assert status == "Supported"
    assert "shoot-and-charge" in str(notes or "").lower()
