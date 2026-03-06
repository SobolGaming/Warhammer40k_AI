def test_support_matrix_classifies_acrobatic_escape_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Acrobatic Escape"
    description = (
        "At the end of the Fight phase, if this model is within Engagement Range of one or more enemy units, "
        "it can make a Fall Back move of up to D6\". In addition, at the end of your opponent's turn, if this "
        "model is not within 3\" of one or more enemy units, you can remove it from the battlefield and then, "
        "in the Reinforcements step of your next Movement phase, set it up anywhere on the battlefield that is "
        "more than 9\" horizontally away from all enemy models."
    )

    status, note = _classify_ability(ability_name, description, faction_id="AOI")

    assert status == "Supported"
    assert "reinforcements" in note.lower()


def test_support_matrix_classifies_lord_of_deceit_aura_cost_wording_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Lord of Deceit (Aura)"
    description = (
        "Each time your opponent targets a unit from their army with a Stratagem, if that unit is within 12\" "
        "of this model, increase the cost of that use of that Stratagem by 1CP."
    )

    status, note = _classify_ability(ability_name, description, faction_id="AOI")

    assert status == "Supported"
    assert "+1cp" in note.lower()
