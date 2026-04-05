def test_support_matrix_classifies_hammerhand_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Hammerhand (Psychic)"
    description = (
        "Each time a model in this unit makes a Charge move, until the end of the turn, "
        "melee weapons equipped by models in this unit have the [LETHAL HITS] ability."
    )

    status, note = _classify_ability(ability_name, description, faction_id="AOI")

    assert status == "Supported"
    assert "lethal hits" in note.lower()
