def test_support_matrix_classifies_tyranids_blistering_assault_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time an enemy unit is selected to shoot, after that unit has shot, if any models from this unit "
        "lost one or more wounds as a result of those attacks, this unit can make a Blistering Assault move. "
        "If it does, roll one D6, adding 2 to the result: each model in this unit can be moved a distance in inches "
        "up to the result, but this unit must finish that move as close as possible to the closest enemy unit. "
        "When doing so, those models can be moved within Engagement Range of that enemy unit. "
        "Each unit can only make one Blistering Assault move per phase."
    )
    status, notes = gsm._classify_ability("Blistering Assault", description, faction_id="TYR")

    assert status == "Supported"
    notes_l = notes.lower()
    assert "d6+2" in notes_l or "d6" in notes_l
    assert "closest enemy unit" in notes_l
