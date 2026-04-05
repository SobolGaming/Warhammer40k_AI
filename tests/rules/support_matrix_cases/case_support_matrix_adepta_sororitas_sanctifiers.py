def test_support_matrix_classifies_as_sanctifiers_ministorum_sermon_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Ministorum Sermon"
    description = (
        "While this unit contains a MINISTORUM PRIEST, melee weapons equipped by models in this unit "
        "have the [SUSTAINED HITS 1] ability."
    )

    status, note = _classify_ability(ability_name, description, faction_id="AS")

    assert status == "Supported"
    assert "sustained hits" in note.lower()
