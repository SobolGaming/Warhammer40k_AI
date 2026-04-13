def test_support_matrix_classifies_remaining_admech_datasheet_abilities_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    cases = [
        (
            "Achillan Eye",
            "Each time this model makes an attack with a radium jezzail that targets an INFANTRY unit, you can re-roll the Wound roll. "
            "Each time this model makes an attack with a Skatros transuranic arquebus that targets a MONSTER or VEHICLE unit, "
            "you can re-roll the Wound roll.",
        ),
        (
            "Blistering Salvoes",
            "Each time this model makes an attack with a belleros energy cannon that targets an INFANTRY unit, add 1 to the Hit roll. "
            "Each time this model makes an attack with a ferrumite cannon that targets a MONSTER or VEHICLE unit, add 1 to the Hit roll.",
        ),
        (
            "Broad-spectrum Targeting Augurs",
            "Each time a model in this unit makes an attack with an eradication caster that targets a unit "
            "(excluding MONSTER and VEHICLE units), that attack has the [SUSTAINED HITS 1] ability.",
        ),
        (
            "Bomb Rack",
            "Each time this model ends a Normal move, you can select one enemy unit it moved across during that move and roll six D6: "
            "for each 4+, that unit suffers 1 mortal wound.",
        ),
        (
            "Breaching Command",
            "Each time a model in this unit makes an attack, re-roll a Hit roll of 1. While this unit is within 6\" of one or more "
            "friendly Adeptus Mechanicus Battleline units, you can re-roll the Hit roll instead.",
        ),
        (
            "Rod of the War Forge",
            "In your Command phase, select one of the abilities in the Icon of War section. Until the start of your next "
            "Command phase, this model has that ability.",
        ),
        (
            "Fanatical Devotion",
            "You can select one friendly Skitarii or THULIA GHULD unit within 6\" of this model; until the start of your next "
            "Command phase, that unit is eligible to shoot and declare a charge in a turn in which it Advanced.",
        ),
        (
            "Monocular Targeting Helms",
            "Each time a model in this unit makes an attack with a neutron fusil against a MONSTER or VEHICLE unit, "
            "that attack has the [IGNORES COVER] ability.",
        ),
        (
            "Adaptive Tactics",
            "You can select one friendly Skitarii or THULIA GHULD unit within 6\" of this model; until the start of your next "
            "Command phase, that unit is eligible to shoot and declare a charge in a turn in which it Fell Back.",
        ),
        (
            "The Fires of Mars",
            "You can select one friendly Skitarii or THULIA GHULD unit within 6\" of this model; until the start of your next "
            "Command phase, the Conqueror Imperative and Protector Imperative are both active for that unit.",
        ),
        (
            "Cybernetic Augmentation",
            "This model can move through terrain features, but cannot end a move within a wall, a floor, etc. This model can be "
            "set up or end a move on any floor level of RUINS, but if that level is not the ground floor, it can only do so if its "
            "base does not overhang the floor at that level.",
        ),
        (
            "Secutor of Olympus",
            "At the start of your Shooting phase, select one enemy VEHICLE unit within 12\" of this model and roll one D6: "
            "on a 2+, that enemy unit suffers D3+1 mortal wounds.",
        ),
        (
            "Dynamic Efficiency",
            "This unit is eligible to declare a charge in a turn in which it Advanced or Fell Back, and you can re-roll "
            "Desperate Escape tests taken for models in this unit.",
        ),
        (
            "Elevated Strider",
            "This unit is eligible to shoot in a turn in which it Fell Back or Advanced, and you can re-roll "
            "Desperate Escape tests taken for models in this unit.",
        ),
        (
            "Line-breakers",
            "Each time this unit ends a Charge move, select one enemy unit within Engagement Range of it and roll one D6 for each model "
            "in this unit that is within Engagement Range of that enemy unit, adding 2 to the result if this unit started its Charge move "
            "within 6\" of one or more friendly ADEPTUS MECHANICUS BATTLELINE units. For each 4+, that enemy unit suffers 1 mortal wound.",
        ),
        (
            "Optimised Gait",
            "Add 1 to Advance and Charge rolls made for this unit. While this unit is within 6\" of one or more friendly "
            "Adeptus Mechanicus Battleline units, add 2 to Advance and Charge rolls made for this unit instead.",
        ),
        (
            "Ride the Thermals",
            "In your Shooting phase, after this unit has shot, if it is not within Engagement Range of one or more enemy units, "
            "it can do one of the following: - Make a Normal move of up to 6\". - Make a Normal move of up to 12\", provided every model "
            "in this unit ends that move wholly within 6\" of one or more friendly Adeptus Mechanicus Battleline units. In either case, "
            "if it does, until the end of the turn, this unit is not eligible to declare a charge.",
        ),
        (
            "Searing Conflagration",
            "Each time a model in this unit makes an attack with a phosphor torch that targets an enemy unit within range of an objective "
            "marker, re-roll a Wound roll of 1. If this unit is also within 6\" of one or more friendly ADEPTUS MECHANICUS BATTLELINE units, "
            "each time such an attack targets such a unit, you can re-roll the Wound roll instead.",
        ),
    ]

    for ability_name, description in cases:
        status, notes = gsm._classify_ability(ability_name, description, faction_id="ADM")
        assert status == "Supported", f"{ability_name}: expected Supported, got {status} ({notes})"
