def test_support_matrix_classifies_big_gob_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    status, notes = gsm._enhancement_support(
        "Big Gob",
        "000008885002",
        (
            "Infantry Warboss model only. At the start of the Fight phase, select one enemy unit within "
            "Engagement Range of the bearer. That enemy unit must take a Battle-shock test, subtracting 1 from that test."
        ),
    )

    assert status == "Supported"
    notes_l = notes.lower()
    assert "engagement range" in notes_l
    assert "battle-shock" in notes_l or "battle shock" in notes_l


def test_support_matrix_classifies_squig_flingin_as_implemented():
    import scripts.generate_ability_support_matrix as gsm

    status, notes, _ = gsm._stratagem_support(
        "SQUIG FLINGIN'",
        (
            "When: Your Movement phase, just after a SPEED FREEKS or TRUKK unit from your army ends a Normal, "
            "Advance or Fall Back move. Target: That Speed Freeks or Trukk unit. Effect: Select one enemy unit "
            "within 9\" of your unit. That enemy unit must take a Battle-shock test and, when doing so, subtract 1 from the result."
        ),
        detachment_name="Kult of Speed",
        stratagem_id="000008873003",
    )

    assert status == "Implemented"
    notes_l = notes.lower()
    assert "movement phase" in notes_l
    assert "battle-shock" in notes_l or "battle shock" in notes_l
