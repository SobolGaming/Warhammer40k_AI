def test_support_matrix_classifies_tau_tidewall_defence_platform_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "If equipped with a Tidewall defence platform, this FORTIFICATION has a Wounds characteristic of 15."
    )
    status, notes = gsm._classify_ability("Tidewall Defence Platform", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "fortification" in lowered
    assert "wounds characteristic of 15" in lowered
