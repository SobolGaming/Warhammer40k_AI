import pytest


@pytest.mark.parametrize(
    "name,description",
    [
        (
            "Chronometron",
            (
                "In your Shooting phase, after this model's unit has shot, if it is not within Engagement Range of any enemy "
                "units, that unit can make a Normal move of up to 5\" as if it were your Movement phase. If it does, until "
                "the end of the turn, that unit is not eligible to declare a charge."
            ),
        ),
        (
            "Evasion Engrams",
            (
                "In your Shooting phase, after this unit has shot, it can make a Normal move of up to 6\". If it does, until "
                "the end of the turn, this unit is not eligible to declare a charge."
            ),
        ),
        (
            "Targeting Relay",
            (
                "In your Shooting phase, each time this model is selected to shoot, after resolving its attacks, select one "
                "enemy unit that was hit by one or more of those attacks. Until the end of the phase, that unit cannot have "
                "the Benefit of Cover."
            ),
        ),
        (
            "Sentinel Construct",
            (
                "Each time you target this unit with the Fire Overwatch Stratagem, while resolving that Stratagem, "
                "hits are scored on unmodified Hit rolls of 5+."
            ),
        ),
        (
            "Hard-wired for Destruction",
            (
                "Each time a model in this unit makes a ranged attack that targets the closest eligible enemy unit, re-roll "
                "a Hit roll of 1. If the target of that attack is within range of an objective marker your opponent controls, "
                "you can re-roll the Hit roll instead."
            ),
        ),
        (
            "Implacable Eradication",
            (
                "Each time a model in this unit makes an attack, re-roll a Wound roll of 1. If the target of that attack is "
                "an enemy unit within range of an objective marker, you can re-roll the Wound roll instead."
            ),
        ),
        (
            "Whirling Onslaught",
            (
                "Each time a model in this unit makes a melee attack, re-roll a Hit roll of 1. If this unit made a Charge "
                "move this turn, you can re-roll the Hit roll instead."
            ),
        ),
        (
            "Driven by Hatred",
            (
                "Each time this model makes an attack that targets an enemy unit that is Below Half-strength, you can re-roll "
                "the Hit roll and you can re-roll the Wound roll."
            ),
        ),
    ],
)
def test_support_matrix_necrons_group1_datasheet_abilities_supported(name, description):
    import scripts.generate_ability_support_matrix as gsm

    status, _notes = gsm._classify_ability(name, description, faction_id="NEC")
    assert status == "Supported"
