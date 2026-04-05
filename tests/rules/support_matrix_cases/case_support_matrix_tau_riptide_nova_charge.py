def test_support_matrix_classifies_tau_nova_charge_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Once per battle, when this unit is selected to shoot in your Shooting phase, select one ranged weapon "
        "equipped by this model. Until the end of the phase, that weapon has the [DEVASTATING WOUNDS] ability."
    )
    status, notes = gsm._classify_ability("Nova Charge", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "once per battle" in lowered
    assert "selected to shoot" in lowered
    assert "devastating wounds" in lowered
