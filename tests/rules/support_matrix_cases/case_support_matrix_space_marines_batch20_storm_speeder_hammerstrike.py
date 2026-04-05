def test_support_matrix_space_marines_batch20_storm_speeder_hammerstrike() -> None:
    from scripts.generate_ability_support_matrix import _classify_ability

    description = (
        "Each time this model has shot, select one enemy unit that was hit by one or more attacks made by this model this "
        "phase. Until the end of the phase, that enemy unit cannot have the Benefit of Cover."
    )

    status, notes = _classify_ability(
        "Hammerstrike",
        description,
        faction_id="SM",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "benefit of cover" in notes_l
    assert "phase end" in notes_l or "phase" in notes_l
