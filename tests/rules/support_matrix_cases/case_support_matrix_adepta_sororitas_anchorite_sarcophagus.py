def test_support_matrix_classifies_anchorite_sarcophagus_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Anchorite Sarcophagus"
    description = 'The bearer has a Move characteristic of 7" and a Save characteristic of 3+.'

    status, note = _classify_ability(ability_name, description, faction_id="AS")

    assert status == "Supported"
    lowered = note.lower()
    assert "move characteristic 7" in lowered
    assert "save characteristic 3" in lowered
