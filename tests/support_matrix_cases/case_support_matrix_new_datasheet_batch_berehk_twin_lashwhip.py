import pytest


@pytest.mark.parametrize(
    "faction_id,name,description",
    [
        (
            "LOV",
            "Break the Foe",
            "Melee weapons equipped by models in this model's unit have the [SUSTAINED HITS 1] ability.",
        ),
        (
            "LOV",
            "Relentless Avalanche",
            "You can target this model's unit with the Heroic Intervention Stratagem for 0CP, and can do so even if you have already targeted a different unit with that Stratagem this phase.",
        ),
        (
            "TYR",
            "Alpha Warrior",
            "Weapons equipped by models in this model's unit have the [SUSTAINED HITS 1] ability.",
        ),
        (
            "TYR",
            "Aggressive Leader-beast",
            "In your opponent's Shooting phase, each time an enemy unit has shot, if any models from this unit were destroyed as a result of those attacks, this unit can make a Surge move. To do so, roll one D6: models in this unit move a number of inches up to this result, but this unit must end that move as close as possible to the closest enemy unit (excluding AIRCRAFT). When doing so, those models can be moved within Engagement Range of that enemy unit. This unit cannot make a Surge move while it is Battle-shocked or within Engagement Range of one or more enemy units, and can only make one Surge move per phase.",
        ),
        (
            "TAU",
            "Exemplars of Mont'ka",
            "Each time a model in this unit makes a ranged attack that targets the closest eligible target, that attack has the [SUSTAINED HITS 1] and [IGNORES COVER] abilities.",
        ),
        (
            "TAU",
            "Retro-thrusters",
            "At the end of the Fight phase, this unit can either make a Normal move of up to 6\" or a Fall Back move.",
        ),
        (
            "TAU",
            "MV15 Gun Drone",
            "The bearer is equipped with 1 twin pulse blaster.",
        ),
    ],
)
def test_support_matrix_new_datasheet_batch_berehk_twin_lashwhip_supported(faction_id, name, description):
    import scripts.generate_ability_support_matrix as gsm

    status, _notes = gsm._classify_ability(name, description, faction_id=faction_id)
    assert status == "Supported"
