def test_support_matrix_classifies_imperial_navy_breachers_abilities_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    cases = [
        (
            "Breaching Team",
            (
                "Each time a model in this unit makes an attack, re-roll a Wound roll of 1. "
                "If the target is within range of an objective marker, you can re-roll the Wound roll instead."
            ),
        ),
        (
            "CAT Unit",
            (
                "Once per battle, when this unit is selected to shoot, until the end of the phase, "
                "ranged weapons equipped by models in this unit gain the [IGNORES COVER] ability."
            ),
        ),
        (
            "Gheistskull",
            (
                "Once per battle, when you select this unit as the target of the Grenade Stratagem, "
                "you can target one enemy unit visible to and within 18\" of this unit that is not within "
                "Engagement Range of any units from your army, instead of one within 8\"."
            ),
        ),
    ]

    for ability_name, description in cases:
        status, note = _classify_ability(ability_name, description, faction_id="AOI")
        assert status == "Supported", f"{ability_name} should be Supported but was {status}: {note}"
