def test_support_matrix_classifies_warrant_of_trade_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "If your army includes one or more units with this ability, after both players have deployed their armies, "
        "select upto D3 IMpERIUM BATTlElINE units from your army and redeploy them. When doing so, you can set those "
        "units up in Strategic Reserves, regardless of how many units are already in Strategic Reserves."
    )

    status, notes = gsm._classify_ability("Warrant of Trade", description, faction_id="AOI")
    assert status == "Supported"
    assert "imperium battleline" in str(notes).lower()
    assert "strategic reserves" in str(notes).lower()
