import pytest


CASES = [
    (
        "Forlorn Hero",
        "While this model is leading a unit, unless that unit starts the battle embarked within a Transport, models in that unit have the Scouts 6\" ability.",
        "000003832",
        ("scouts 6", "transport"),
    ),
    (
        "Driven by Fury",
        "In your opponent's Shooting phase, each time an enemy unit has shot, if this model was hit by one or more of those attacks, it can make a Driven by Fury move. To do so, roll one D6 and add 2 to the roll: this model moves a number of inches up to the result, but must finish as close as possible to the closest enemy unit (excluding AIRCRAFT). When doing so, this model can be moved within Engagement Range of that enemy unit. A model cannot make a Driven by Fury move while it is Battle-shocked or within Engagement Range of one or more enemy units, and can only make one Driven by Fury move per phase.",
        "000000166",
        ("d6+2", "once per phase"),
    ),
    (
        "An Honourable Death in Combat",
        "Each time a model in this unit makes an attack, that attack has the [SUSTAINED HITS 1] ability if this unit is below its Starting Strength, or the [SUSTAINED HITS 2] ability if this unit is Below Half-strength.",
        "000001997",
        ("sustained hits 1", "below half-strength"),
    ),
    (
        "Visions of Heresy",
        "Once per turn, you can target this unit with the Fire Overwatch or the Heroic Intervention Stratagem for 0CP. While resolving that Stratagem, each time a model in this unit makes a ranged attack you can re-roll the Hit roll, or you can re-roll the Charge roll made for this unit (whichever applies).",
        "000002285",
        ("fire overwatch or heroic intervention", "charge roll"),
    ),
]


@pytest.mark.parametrize(("name", "description", "datasheet_id", "fragments"), CASES)
def test_support_matrix_space_marines_batch8_datasheet_abilities(
    name: str,
    description: str,
    datasheet_id: str,
    fragments: tuple[str, str],
):
    from scripts.generate_ability_support_matrix import _classify_ability

    status, notes = _classify_ability(name, description, faction_id="SM", datasheet_id=datasheet_id)

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    for fragment in fragments:
        assert fragment in notes_l
