def test_support_matrix_classifies_immolator_purge_and_cleanse_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Purge and Cleanse"
    description = (
        "Each time this model has shot, select one enemy unit hit by one or more of those attacks. "
        "Until the end of the phase, that enemy unit cannot have the Benefit of Cover."
    )

    status, note = _classify_ability(ability_name, description, faction_id="AOI")

    assert status == "Supported"
    assert "benefit of cover" in note.lower()
