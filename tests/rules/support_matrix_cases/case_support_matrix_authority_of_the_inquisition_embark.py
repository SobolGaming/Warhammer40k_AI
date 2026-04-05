def test_support_matrix_classifies_leading_bodyguard_transport_embark_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Authority of the Inquisition"
    description = (
        "While this model is leading a unit, it can embark within any TRANSPORT "
        "that its Bodyguard unit can embark within."
    )

    status, note = _classify_ability(ability_name, description, faction_id="AOI")

    assert status == "Supported"
    assert "embark" in note.lower()


def test_support_matrix_classifies_joined_bodyguard_transport_embark_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Loyal Protector"
    description = (
        "While this unit is joined to a unit, it can embark within any Transport "
        "that unit can embark within."
    )

    status, note = _classify_ability(ability_name, description, faction_id="AM")

    assert status == "Supported"
    assert "bodyguard host" in note
