def test_support_matrix_space_marines_batch20_sword_brethren_squad() -> None:
    from scripts.generate_ability_support_matrix import _classify_ability

    description = (
        "Each time an enemy unit within Engagement Range of this unit is selected to Fall Back, after it ends that Fall "
        "Back move, if this unit is not within Engagement Range of one or more enemy units, this unit can make a Normal move."
    )

    status, notes = _classify_ability(
        "Exploit Their Cowardice",
        description,
        faction_id="SM",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "fall back" in notes_l
    assert "normal move" in notes_l
    assert "no longer engaged" in notes_l or "engagement range" in notes_l
