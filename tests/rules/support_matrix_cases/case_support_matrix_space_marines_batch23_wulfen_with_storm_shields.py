from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch23_wulfen_with_storm_shields_hammer_blow_support_matrix_case():
    description = (
        "In the Fight phase, after this unit has fought, select one enemy MONSTER or VEHICLE unit hit by one or more "
        "of those attacks. Until the end of the next turn, that enemy unit is suppressed. While a unit is suppressed, "
        "each time a model in that unit makes an attack, subtract 1 from the Hit roll."
    )

    status, notes = _classify_ability(
        "Hammer Blow",
        description,
        faction_id="SM",
        datasheet_id="000004132",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "monster or vehicle" in notes_l
    assert "suppressed" in notes_l
    assert "next turn" in notes_l
