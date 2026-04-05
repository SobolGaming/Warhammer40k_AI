def test_support_matrix_classifies_overkill_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Overkill"
    description = (
        "Once per battle, in your Movement phase, this model can use this ability before it makes a Normal move. "
        "If it does, until the end of the turn, add 6\" to this model's Move characteristic and add 3 to the "
        "Attacks characteristic of this model's melee weapons."
    )

    status, note = _classify_ability(ability_name, description, faction_id="AOI")

    assert status == "Supported"
    assert "attacks" in note.lower()
