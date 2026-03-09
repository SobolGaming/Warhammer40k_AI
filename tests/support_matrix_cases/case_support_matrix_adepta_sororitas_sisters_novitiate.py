def test_support_matrix_classifies_as_sisters_novitiate_impetuous_fervour_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Impetuous Fervour"
    description = (
        "Each time a model in this unit makes an attack, re-roll a Hit roll of 1. "
        "If the target of that attack is an enemy unit within range of an objective marker, "
        "you can re-roll the Hit roll instead."
    )

    status, note = _classify_ability(ability_name, description, faction_id="AS")

    assert status == "Supported"
    assert "re-roll hit rolls of 1" in note.lower()
    assert "objective marker" in note.lower()
