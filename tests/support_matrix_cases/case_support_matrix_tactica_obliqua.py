def test_support_matrix_classifies_tactica_obliqua_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Tactica Obliqua"
    description = (
        "Once per turn, when an enemy unit ends a Normal, Advance or Fall Back move within 9\" of this unit, "
        "if this unit is not within Engagement Range of one or more enemy units, it can do one of the following: "
        "- Make a Normal move of up to D6\". "
        "- Make a Normal move of up to 6\", provided every model in this unit ends that move wholly within 6\" "
        "of one or more friendly Adeptus Mechanicus Battleline units."
    )

    status, note = _classify_ability(ability_name, description, faction_id="ADM")

    assert status == "Supported"
    assert "reactive Normal move" in note
