def test_support_matrix_classifies_focused_hunters_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    ability_name = "Focused Hunters"
    description = (
        "At the start of the battle, select one unit from your opponent's army. "
        "Until the end of the battle, each time a model in this unit makes an attack that targets that unit, "
        "you can re-roll the Hit roll."
    )

    status, _notes = gsm._classify_ability(ability_name, description, faction_id="ADM")
    assert status == "Supported"
