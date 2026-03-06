def test_support_matrix_classifies_imperial_law_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Imperial Law"
    description = (
        "At the start of the battle, select one unit from your opponent's army. "
        "Each time a model in this unit makes an attack that targets that unit, "
        "that attack has the [LETHAL HITS] and [PRECISION] abilities."
    )

    status, note = _classify_ability(ability_name, description, faction_id="AOI")

    assert status == "Supported"
    lower_note = note.lower()
    assert "lethal hits" in lower_note
    assert "precision" in lower_note
