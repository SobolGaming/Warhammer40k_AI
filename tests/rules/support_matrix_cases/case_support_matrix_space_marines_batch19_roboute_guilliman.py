import pytest


CASES = [
    (
        "Author of the Codex",
        "At the Start of your Command phase, select two Author of the Codex abilities (see left). Until the start of your next Command phase, this model has those abilities.",
        ("exactly two", "master of battle", "supreme strategist"),
    ),
    (
        "Primarch of the XIII (Aura)",
        'While a friendly ADEPTUS ASTARTES unit is within 6" of this model, add 1 to the Objective Control characteristic of models in that unit and you can re-roll Battle-shock and Leadership tests taken for that unit.',
        ("objective control", "battle-shock", "leadership"),
    ),
    (
        "Master of Battle",
        "At the start of your Command phase, after you have selected your Oath of Moment target, select a second enemy unit. Until the start of your next Command phase, if your Oath of Moment target is destroyed, that second enemy unit becomes your Oath of Moment target until you select a new one.",
        ("backup", "oath target", "destroyed"),
    ),
]


@pytest.mark.parametrize(("name", "description", "fragments"), CASES)
def test_support_matrix_space_marines_batch19_roboute_guilliman(
    name: str,
    description: str,
    fragments: tuple[str, ...],
) -> None:
    from scripts.generate_ability_support_matrix import _classify_ability

    status, notes = _classify_ability(name, description, faction_id="SM", datasheet_id="000000138")

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    for fragment in fragments:
        assert fragment in notes_l
