def test_support_matrix_classifies_navigator_third_eye_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Third Eye (Psychic)"
    description = (
        "At the start of your Shooting phase, select one enemy unit within 12\" of and visible to this model. "
        "That unit must take a Battle-shock test, subtracting 2 from the result if it is an INFANTRY unit. "
        "If the test is failed, that enemy unit suffers 3 mortal wounds."
    )

    status, note = _classify_ability(ability_name, description, faction_id="AOI")

    assert status == "Supported"
    assert "battle-shock" in note.lower()
    assert "infantry" in note.lower()
    assert "mortal" in note.lower()
