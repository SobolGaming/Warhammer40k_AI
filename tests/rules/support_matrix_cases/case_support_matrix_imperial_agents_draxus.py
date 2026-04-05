def test_support_matrix_classifies_psychic_veil_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    status, note = _classify_ability(
        "Psychic Veil (Psychic)",
        (
            "In your Command phase, this PSYKER can use this ability. If it does, roll one D6: on a 1, this "
            "PSYKER's unit suffers D3 mortal wounds; on a 2+, until the start of your next Command phase, this "
            "PSYKER's unit can only be selected as the target of a ranged attack if the attacking model is within 18\"."
        ),
        faction_id="AOI",
    )
    assert status == "Supported", f"Psychic Veil (Psychic) should be Supported but was {status}: {note}"
