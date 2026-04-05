import pytest


CASES = [
    (
        "Annihilator Protocols",
        "Melee weapons equipped by models in this unit have the [SUSTAINED HITS 2] ability when targeting MONSTER, VEHICLE or FORTIFICATION units.",
        "000002703",
        ("sustained hits 2", "fortification"),
    ),
    (
        "Decimator Protocols",
        "Each time a model in this unit makes a ranged attack, re-roll a Hit roll of 1. If the target of that attack is an enemy unit within range of an objective marker, you can re-roll the Hit roll instead.",
        "000001193",
        ("objective", "re-roll"),
    ),
    (
        "Temple Relics",
        "At the start of your Command phase, if this unit contains one or more Cenobyte Servitor models, select one of the abilities listed below. Until the start of your next Command phase, this model has that ability.",
        "000002792",
        ("command phase", "banner of the emperor victorious"),
    ),
    (
        "Column from the Major Altar",
        "Add 1 to the Toughness characteristic of models in this unit.",
        "000002792",
        ("+1 toughness", "unit models"),
    ),
    (
        "Water from the Stoup of Elucidation",
        "Improve the Armour Penetration characteristic of melee weapons equipped by models in this unit by 1.",
        "000002792",
        ("melee weapons", "improve ap by 1"),
    ),
]


@pytest.mark.parametrize(("name", "description", "datasheet_id", "fragments"), CASES)
def test_support_matrix_space_marines_batch5_datasheet_abilities(
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
