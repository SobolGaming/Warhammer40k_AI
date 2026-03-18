import pytest


CASES = [
    (
        "Grand Master of the Ravenwing",
        "While this model is leading a unit, that unit is eligible to shoot and declare a charge in a turn in which it Advanced. If that unit is already eligible to shoot and declare a charge in a turn in which it Advanced, add 1 to Advance and Charge rolls made for that unit instead.",
        ("leading", "shoot-and-charge after advance", "+1 to advance and charge rolls"),
    ),
    (
        "Cut Off Their Escape",
        "Each time an enemy unit (excluding MONSTERS and VEHICLES ) within Engagement Range of this model’s unit is selected to Fall Back, models in that enemy unit must take Desperate Escape tests as if their unit was Battle-shocked. When doing so, if that enemy unit is also Battle-shocked by other means, subtract 1 from each of those Desperate Escape tests.",
        ("non-monster/vehicle", "as if battle-shocked", "-1"),
    ),
]


@pytest.mark.parametrize(("name", "description", "fragments"), CASES)
def test_support_matrix_space_marines_batch19_sammael(
    name: str,
    description: str,
    fragments: tuple[str, ...],
) -> None:
    from scripts.generate_ability_support_matrix import _classify_ability

    status, notes = _classify_ability(name, description, faction_id="SM", datasheet_id="000002291")

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    for fragment in fragments:
        assert fragment in notes_l
