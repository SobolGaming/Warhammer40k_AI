import pytest


CASES = [
    (
        "Primarch of the First Legion",
        "At the start of your Command phase, select two Primarch of the First Legion abilities. Until the start of your next Command phase, this model has those abilities.",
        ("exactly two", "command phase"),
    ),
    (
        "Mist-wreathed Shadow Realms",
        "In your Command phase, if this unit is not within Engagement Range of one or more enemy units, you can remove it from the battlefield and place it into Strategic Reserves.",
        ("strategic reserves", "command phase"),
    ),
    (
        "Martial Exemplar (Aura)",
        "While a friendly ADEPTUS ASTARTES unit is within 6\" of this model, each time a model in that unit makes a melee attack, re-roll a Hit roll of 1 and re-roll a Wound roll of 1.",
        ("melee", "wound"),
    ),
    (
        "No Hiding From the Watchers (Aura)",
        "While a friendly ADEPTUS ASTARTES unit is within 6\" of this model, models in that unit have the Feel No Pain 4+ ability against mortal wounds.",
        ("feel no pain 4+", "mortal"),
    ),
]


@pytest.mark.parametrize(("name", "description", "fragments"), CASES)
def test_support_matrix_space_marines_primarch_of_the_first_legion(
    name: str,
    description: str,
    fragments: tuple[str, str],
) -> None:
    from scripts.generate_ability_support_matrix import _classify_ability

    status, notes = _classify_ability(name, description, faction_id="SM", datasheet_id="000002682")

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    for fragment in fragments:
        assert fragment in notes_l
