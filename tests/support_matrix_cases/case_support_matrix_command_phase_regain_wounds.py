def test_support_matrix_classifies_command_phase_up_to_d3_self_heal_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = "At the start of your Command phase, this model regains up to D3 lost wounds."
    status, notes = gsm._classify_ability("Regenerative Carapace", description, faction_id="TS")

    assert status == "Supported"
    assert "command phase" in notes.lower()
    assert "d3" in notes.lower()
