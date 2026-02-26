def test_support_matrix_classifies_cawl_canticles_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    cases = [
        (
            "Canticles of the Omnissiah",
            "At the start of your Command phase, select one of the abilities in the Canticles of the Omnissiah section. Until the start of your next Command phase, this model has that ability.",
        ),
        (
            "Invocation of Machine Vengeance",
            "At the start of your Command phase, select one unit from your opponent's army. Until the start of your next Command phase, that enemy unit is your Machine Vengeance target. Each time a model in a friendly Adeptus Mechanicus unit makes an attack that targets your Machine Vengeance target, you can re-roll the Hit roll.",
        ),
        (
            "Mantra of Discipline",
            "This model has the BATTLELINE keyword and has the following ability: Binharic Courage (Aura): While a friendly ADEPTUS MECHANICUS unit is within 6\" of this model, add 1 to the Objective Control characteristic of models in that unit and each time you take a Battle-shock or Leadership test for that unit, add 1 to that test.",
        ),
        (
            "Shroudpsalm (Aura)",
            "While a friendly ADEPTUS MECHANICUS unit is within 6\" of this model, that unit has the Stealth ability.",
        ),
    ]

    for ability_name, description in cases:
        status, _notes = gsm._classify_ability(ability_name, description, faction_id="ADM")
        assert status == "Supported"
