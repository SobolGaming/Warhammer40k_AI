def test_support_matrix_classifies_logan_grimnar_embarking_within_transports_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "EMBARKING WITHIN TRANSPORTS"
    description = (
        "This model can embark within friendly Adeptus Astartes Transport models that can transport "
        "Terminator models. When doing so, it takes up the space of 4 Infantry models."
    )

    status, note = _classify_ability(ability_name, description, faction_id="SM")

    assert status == "Supported"
    assert "transport slots" in note
    assert "4" in note
