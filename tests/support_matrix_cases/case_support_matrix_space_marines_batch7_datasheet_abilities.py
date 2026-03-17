import pytest


CASES = [
    (
        "Martial Honour",
        "The first time a model in this model's unit makes a melee attack that destroys one or more enemy units, until the end of the battle, while this model's unit is not Battle-shocked, add 5 to this model's Objective Control characteristic.",
        "000004136",
        ("objective control", "battle-shocked"),
    ),
    (
        "Righteous Zeal",
        "In your opponent's Shooting phase, each time an enemy unit has shot, if any models in this unit were destroyed as a result of those attacks, this unit can make a Righteous Zeal move. To do so, roll one D6 and add 2 to the result: models in this unit move a number of inches up to this result, but this unit must end that move as close as possible to the closest enemy unit (excluding AIRCRAFT). When doing so, those models can be moved within Engagement Range of that enemy unit. This unit cannot make a Righteous Zeal move while it is Battle-shocked or within Engagement Range of one or more enemy units, and can only make one Righteous Zeal move per phase.",
        "000002799",
        ("d6+2", "once per phase"),
    ),
    (
        "Icon of Obstinacy",
        "Each time an attack targets this model's unit, if the Strength characteristic of that attack is greater than or equal to the Toughness characteristic of that unit, subtract 1 from the Wound roll.",
        "000002105",
        ("-1 to wound", "s >= t"),
    ),
]


@pytest.mark.parametrize(("name", "description", "datasheet_id", "fragments"), CASES)
def test_support_matrix_space_marines_batch7_datasheet_abilities(
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
