def test_support_matrix_classifies_electro_shock_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Electro-shock"
    description = (
        "In your Shooting phase, after this unit has shot, select one enemy unit (excluding MONSTERS and VEHICLES) "
        "hit by one or more of those attacks. Until the end of your opponent's next turn, that enemy unit is shocked. "
        "While a unit is shocked, subtract 2\" from its Move characteristic and subtract 2 from Advance and Charge rolls made for it."
    )

    status, note = _classify_ability(ability_name, description, faction_id="ADM")

    assert status == "Supported"
    assert "shocked" in note.lower()
