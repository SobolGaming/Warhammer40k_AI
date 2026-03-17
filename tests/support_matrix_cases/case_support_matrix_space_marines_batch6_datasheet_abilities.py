import pytest


CASES = [
    (
        "Catechism of Fire",
        "Each time this model's unit is selected to shoot, you can select one enemy unit within 12\" of and visible to this model. Until the end of the phase, ranged weapons equipped by models in this model's unit have the [DEVASTATING WOUNDS] ability when targeting that enemy unit.",
        "000000094",
        ("selected to shoot", "devastating wounds"),
    ),
    (
        "Exhortation of Rage",
        "Each time this model's unit is selected to fight, you can select one enemy unit within Engagement Range of this model's unit and roll one D6: on a 4-5, that enemy unit suffers D3 mortal wounds; on a 6, that enemy unit suffers 3 mortal wounds.",
        "000000112",
        ("selected to fight", "mortal wounds"),
    ),
    (
        "Transfixing Gaze (Aura, Psychic)",
        "While an enemy unit is within 6\" of this model, each time that unit is selected to Fall Back, it must take a Leadership test. If that test is failed, that unit must Remain Stationary this phase instead.",
        "000000155",
        ("leadership test", "remain stationary"),
    ),
    (
        "Master of Prescience (Psychic)",
        "While this model is leading a unit, each time an attack targets that unit, subtract 1 from the Hit roll. In addition, once per battle round, you can target that unit with one of the following Stratagems for 0CP: Counter-offensive; Fire Overwatch; Go to Ground; Heroic Intervention",
        "000001611",
        ("0cp", "go to ground"),
    ),
    (
        "Death Mask of Sanguinius",
        "At the start of the Fight phase, each enemy unit within 6\" of this model must take a Battle-shock test, subtracting 1 from that test when they do.",
        "000000151",
        ("battle-shock test", "-1"),
    ),
    (
        "Warden of the Imperium Nihilus",
        "While this model is leading a unit, add 1 to Advance and Charge rolls made for that unit and each time a model in that unit makes an attack, add 1 to the Hit roll.",
        "000000151",
        ("advance and charge", "+1 to hit"),
    ),
]


@pytest.mark.parametrize(("name", "description", "datasheet_id", "fragments"), CASES)
def test_support_matrix_space_marines_batch6_datasheet_abilities(
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
