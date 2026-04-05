def test_support_matrix_classifies_soulless_horror_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Soulless Horror"
    description = (
        "Once per battle, at the start of any Command phase, this model can use this ability. If it does, "
        "each enemy unit within 9\" of this model must take a Battle-shock test, subtracting 1 from that test "
        "(or subtracting 2 if that unit is a PSYKER)."
    )

    status, note = _classify_ability(ability_name, description, faction_id="AOI")

    assert status == "Supported"
    assert "battle-shock" in note.lower()
