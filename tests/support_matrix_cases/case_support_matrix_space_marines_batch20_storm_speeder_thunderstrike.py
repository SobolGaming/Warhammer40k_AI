def test_support_matrix_space_marines_batch20_storm_speeder_thunderstrike() -> None:
    from scripts.generate_ability_support_matrix import _classify_ability

    description = (
        "Each time this model has shot, select one enemy MONSTER or VEHICLE unit that was hit by one or more attacks made "
        "by this model this phase. Until the end of the phase, each time a friendly ADEPTUS ASTARTES unit makes a ranged "
        "attack that targets that enemy unit, add 1 to the Wound roll."
    )

    status, notes = _classify_ability(
        "Thunderstrike",
        description,
        faction_id="SM",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "monster/vehicle" in notes_l
    assert "+1 to wound" in notes_l
    assert "adeptus astartes" in notes_l
