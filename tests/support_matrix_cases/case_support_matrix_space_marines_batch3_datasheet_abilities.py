import pytest


CASES = [
    (
        "Cold and Calculating",
        "Each time a model in this model’s unit makes an attack that targets a MONSTER or VEHICLE unit, that attack has the [LETHAL HITS] ability. Each time a model in this model’s unit makes an attack that targets any other unit, that attack has the [SUSTAINED HITS 1] ability.",
        "000004166",
        ("lethal hits", "sustained hits 1"),
    ),
    (
        "Cerebrex Logic Engine",
        'At the start of the Declare Battle Formations step, you can select one Adeptus Astartes Infantry unit from your army. Until the end of the battle, that unit gains the Scouts 6" ability. After both players have deployed their armies, you can select one ADEPTUS ASTARTES unit from your army and redeploy it. When doing so, you can set that unit up in Strategic Reserves if you wish, regardless of how many units are already in Strategic Reserves.',
        "000004166",
        ("scouts 6", "redeploy one adeptus astartes unit"),
    ),
    (
        "Master of Deceit",
        "After both players have deployed their armies, if your army includes one or more models with this ability, you can select up to three friendly Adeptus Astartes Infantry units and redeploy all of those units. When doing so, any of those units can be placed into Strategic Reserves, regardless of how many units are already in Strategic Reserves.",
        "000002701",
        ("up to three", "adeptus astartes infantry"),
    ),
]


@pytest.mark.parametrize(("name", "description", "datasheet_id", "fragments"), CASES)
def test_support_matrix_space_marines_batch3_datasheet_abilities(
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
