def test_support_matrix_classifies_command_phase_end_self_heal_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = "At the end of your Command phase, this model regains 1 lost wound."
    status, notes = gsm._classify_ability("End-Phase Repair", description, faction_id="TF")

    assert status == "Supported"
    assert "end of command phase" in notes.lower()
    assert "regains 1" in notes.lower()


def test_support_matrix_classifies_bearer_gated_command_phase_model_return_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "In your Command phase, if the bearer is on the battlefield, you can return up to D3 destroyed models "
        "(excluding CHARACTER models) to this unit."
    )
    status, notes = gsm._classify_ability("Icon of Restoration", description, faction_id="TF")

    assert status == "Supported"
    assert "command phase" in notes.lower()
    assert "d3" in notes.lower()
    assert "requires the bearer" in notes.lower()


def test_support_matrix_classifies_below_starting_strength_named_model_return_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "At the start of your Command phase, if the bearer's unit is below its Starting Strength, "
        "you can return up to D3 destroyed Exaction Vigilants to this unit."
    )
    status, notes = gsm._classify_ability("Salvationist Medikit", description, faction_id="TF")

    assert status == "Supported"
    assert "start of command phase" in notes.lower()
    assert "d3" in notes.lower()
    assert "below starting strength" in notes.lower()
    assert "exaction vigilants" in notes.lower()
