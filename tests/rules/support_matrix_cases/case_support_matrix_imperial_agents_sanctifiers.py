def test_support_matrix_classifies_sanctifiers_cherub_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Cherub"
    description = (
        "Once per battle, you can target this unit with the Command Re-roll Stratagem for 0CP, and can do so "
        "even if you have already targeted a different unit with that Stratagem this phase."
    )

    status, note = _classify_ability(ability_name, description, faction_id="AOI")

    assert status == "Supported"
    assert "command re-roll" in note.lower()
    assert "0cp" in note.lower()


def test_support_matrix_classifies_sanctifiers_ministorum_sermon_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Ministorum Sermon"
    description = (
        "While this unit contains a MINISTORUM PRIEST, each time a model in this unit makes a melee attack, "
        "add 1 to the Wound roll."
    )

    status, note = _classify_ability(ability_name, description, faction_id="AOI")

    assert status == "Supported"
    assert "attack roll" in note.lower()
