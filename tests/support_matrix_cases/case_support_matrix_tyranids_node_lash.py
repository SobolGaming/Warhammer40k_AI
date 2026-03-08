def test_support_matrix_classifies_tyranids_node_lash_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While this model is leading a unit, each time a model in that unit makes an attack, add 1 to the Hit roll. "
        "If the target is Battle-shocked, add 1 to the Wound roll as well."
    )
    status, notes = gsm._classify_ability("Node Lash (Psychic)", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "+1 to hit" in notes_l
    assert "+1 to wound" in notes_l
    assert "battle-shocked" in notes_l
