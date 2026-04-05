import pytest


CASES = [
    (
        "Lead From the Front",
        'While this model is leading a unit, models in that unit have the Scouts 6" ability and ranged weapons equipped by models in that unit have the [ASSAULT] ability.',
        "000000081",
        ("scouts 6", "assault"),
    ),
    (
        "Lightning Assault",
        'Once per turn, when an enemy unit ends a Normal, Advance or Fall Back move within 9" of this model, if this model’s unit is not within Engagement Range of one or more enemy units, it can make a Normal move of up to 6".',
        "000000081",
        ("reactive", "9"),
    ),
    (
        "Angel’s Wrath",
        "While this model is leading a unit, each time that unit ends a Charge move, until the end of the turn, add 1 to the Strength characteristic of melee weapons equipped by models in that unit.",
        "000000083",
        ("charge move", "strength"),
    ),
    (
        "Prioritised Eradication",
        "Each time a model in this model’s unit makes a melee attack that destroys one or more enemy units, roll one D6: on a 4+, you gain 1CP.",
        "000002793",
        ("4+", "1cp"),
    ),
    (
        "Vehement Aggression",
        "While this model is leading a unit, each time that unit is selected to fight, take a Leadership test for that unit: if passed, until the end of the phase, each time a model in that unit makes an attack, you can re-roll the Hit roll; if failed, until the end of the phase, each time a model in that unit makes an attack, re-roll a Hit roll of 1.",
        "000002793",
        ("leadership", "re-roll"),
    ),
    (
        "Knight Champion of Macragge",
        'Once per turn, when an enemy unit ends a Normal, Advance or Fall Back move within 9" of this model’s unit, if this unit is not within Engagement Range of one or more enemy units, it can make a Normal move of up to 6".',
        "000004184",
        ("reactive", "6"),
    ),
    (
        "Honour of Ultramar",
        "If this model is destroyed by a melee attack, if it has not fought this phase, roll one D6: on a 2+, do not remove it from play. This model can fight after the attacking unit has finished making its attacks. If one or more enemy models are destroyed as a result of those attacks, this model regains D3 lost wounds and is not destroyed; otherwise, it is removed from play.",
        "000004187",
        ("d3", "remains alive"),
    ),
]


@pytest.mark.parametrize(("name", "description", "datasheet_id", "fragments"), CASES)
def test_support_matrix_space_marines_batch4_datasheet_abilities(
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
