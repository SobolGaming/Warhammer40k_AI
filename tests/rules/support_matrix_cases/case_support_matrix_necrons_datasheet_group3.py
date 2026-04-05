import pytest


@pytest.mark.parametrize(
    "name,description",
    [
        (
            "Crimson Harvest",
            (
                "Each time this model ends a Charge move, select one enemy unit within Engagement Range of this model and "
                "roll one D6: on a 2-5, that unit suffers D3 mortal wounds; on a 6, that unit suffers D3+3 mortal wounds."
            ),
        ),
        (
            "Lord of the Storm",
            (
                "Once per battle, at the end of your Command phase, this model can use this ability. If it does, roll one "
                "D6 for each enemy unit within 12\" of this model: on a 2-5, that enemy unit suffers D3 mortal wounds; "
                "on a 6, that enemy unit suffers D3+3 mortal wounds."
            ),
        ),
        (
            "Their Number is Legion",
            "Each time this unit's Reanimation Protocols activate, you can re-roll the dice to see how many wounds are reanimated.",
        ),
        (
            "Nanoscarab Reanimation Beam (Aura)",
            (
                "While a friendly NECRONS unit is within 3\" of this model, each time that unit's Reanimation Protocols "
                "activate, that unit reanimates an additional D3 wounds."
            ),
        ),
        (
            "Nanoscarab Projector",
            (
                "Once per battle round, when a friendly NECRONS unit within 3\" of the bearer activates its Reanimation "
                "Protocols, the bearer can use this ability. If it does, that unit reanimates 1 additional wound."
            ),
        ),
        (
            "Repair Barge",
            (
                "Once per turn, just after an enemy unit finishes making its attacks, if one or more friendly NECRON "
                "WARRIORS units within 3\" of this model lost one or more wounds as a result of those attacks, this model "
                "can use this ability. If it does, select one of those NECRON WARRIORS units; that unit's Reanimation "
                "Protocols activate. The same NECRON WARRIORS unit cannot be selected for this ability more than once per turn."
            ),
        ),
        (
            "Self-destruction",
            (
                "At the start of the Fight phase, if this unit is within Engagement Range of one or more enemy units, you can "
                "select one model in this unit to destroy. If you do, select one enemy unit within Engagement Range of that "
                "model and roll one D6, adding 1 to the result if that unit is a VEHICLE. On a 2-5, that unit suffers D3 mortal "
                "wounds; on a 6+, that unit suffers 3 mortal wounds."
            ),
        ),
        (
            "Chittering swarm",
            (
                "While an enemy unit is within Engagement Range of this unit, subtract 1 from the Objective Control "
                "characteristic of models in that enemy unit (to a minimum of 1). While this unit is within 6\" of one or "
                "more friendly CRYPTEK models, the Objective Control characteristic of models in this unit is 1."
            ),
        ),
        (
            "Canoptek Swarm",
            (
                "In your Command phase, select one friendly Canoptek Scarab Swarm unit within 6\" of this unit. One destroyed "
                "model is returned to that CANOPTEK SCARAB SWARM unit for each SPYDER model in this unit."
            ),
        ),
        (
            "Living Lightning",
            (
                "In your Shooting phase, select one enemy unit within 18\" of and visible to this model (excluding units with the "
                "Lone Operative ability that are not part of an Attached unit and are not within 12\" of this model) and roll four "
                "D6: for each 4+, that enemy unit suffers 1 mortal wound."
            ),
        ),
        (
            "Matter Absorption",
            (
                "At the start of your Shooting phase, select one enemy VEHICLE unit within 12\" of this model and roll one D6: "
                "on a 2+, that enemy unit suffers D3 mortal wounds and this model regains up to that many lost wounds."
            ),
        ),
        (
            "Malevolent Arcing",
            (
                "In your Shooting phase, each time you select a target for this model's twin tesla destructor, roll one D6 for "
                "the target unit and one D6 for every other enemy unit within 3\" of the target unit. On a 5+, the unit being "
                "rolled for is struck by arcing energies; after resolving all of this model's attacks against the target unit, "
                "each unit struck by arcing energies suffers D3 mortal wounds."
            ),
        ),
        (
            "Overwhelming Obliteration",
            (
                "In your Movement phase, if this model Remains Stationary, until the end of the turn, its doomsday cannon has "
                "the [DEVASTATING WOUNDS] ability."
            ),
        ),
        (
            "Tectonic Reverberations",
            (
                "In your Movement phase, you can select one enemy unit within 18\" of and visible to this model. Until the "
                "start of your next Movement phase that enemy unit is pinned. While a unit is pinned, subtract 2 from that "
                "unit's Move characteristic and subtract 2 from Charge rolls made for it."
            ),
        ),
        (
            "Obelisk Node Control",
            (
                "While this model is within range of an objective marker you control, enemy units that are set up on the "
                "battlefield from Reserves cannot be set up within 12\" of this model."
            ),
        ),
        (
            "Infectious Murder-madness (Aura)",
            (
                "While a friendly NECRONS unit (excluding Monster and Titanic units) is within 6\" of this model, each time "
                "a model in that unit makes an attack, if that model has the Destroyer Cult keyword or that enemy unit is "
                "the closest eligible target, that attack has the [SUSTAINED HITS 1] ability."
            ),
        ),
        (
            "Plasmacyte",
            (
                "Once per battle for each Plasmacyte this unit has, when this unit is selected to fight, you can use this "
                "ability. If you do, until the end of the phase, melee weapons equipped by models in this unit have the "
                "[DEVASTATING WOUNDS] ability."
            ),
        ),
    ],
)
def test_support_matrix_necrons_group3_datasheet_abilities_supported(name, description):
    import scripts.generate_ability_support_matrix as gsm

    status, _notes = gsm._classify_ability(name, description, faction_id="NEC")
    assert status == "Supported"
