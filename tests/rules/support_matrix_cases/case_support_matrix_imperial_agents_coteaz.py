def test_support_matrix_classifies_inquisitor_coteaz_abilities_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    cases = [
        (
            "Malefic Wardings (Psychic)",
            (
                "While this model is leading a unit, models in that unit have a 6+ invulnerable save, "
                "and a 4+ invulnerable save against Psychic Attacks and attacks made by DAEMON models."
            ),
        ),
        (
            "Glovodan Psyber-eagle",
            (
                "In your Command phase, you can select one enemy unit within 18\" of the bearer. "
                "Until the start of your next Command phase, that unit cannot have the Benefit of Cover."
            ),
        ),
    ]

    for ability_name, description in cases:
        status, note = _classify_ability(ability_name, description, faction_id="AOI")
        assert status == "Supported", f"{ability_name} should be Supported but was {status}: {note}"
