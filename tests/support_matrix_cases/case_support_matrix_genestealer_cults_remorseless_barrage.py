def test_support_matrix_classifies_remorseless_barrage_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "In your Shooting phase, after this model has shot, if one or more of those attacks made with an Indirect Fire "
        "weapon scored a hit against an enemy unit, that unit must take a Battle-shock test (if an INFANTRY unit is hit "
        "by one or more attacks made by a multiple rocket launcher, they must subtract 1 from their Battle-shock test "
        "when doing so)."
    )
    status, notes = gsm._classify_ability("Remorseless Barrage", description, faction_id="GC")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "indirect fire" in notes_l
    assert "multiple rocket launcher" in notes_l
    assert "-1" in notes_l
