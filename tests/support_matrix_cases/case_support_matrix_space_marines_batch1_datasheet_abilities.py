import pytest


CASES = [
    (
        "Narthecium",
        "While this model is leading a unit, in your Command phase, you can return 1 destroyed model (excluding Character models) to that unit.",
        ("return 1 destroyed model", "excludes character"),
    ),
    (
        "Master of Shadows",
        "In your Command phase, you can select one unit from your opponent's army. Until the start of your next Command phase, each time an ADEPTUS ASTARTES unit from your army declares a charge while it is within 12\" of that enemy unit, you can re-roll the Charge roll, but it must declare that enemy unit as a target of that charge (if possible).",
        ("re-roll charge", "must declare"),
    ),
    (
        "Blackwing Mantle",
        "You can target this model's unit with the Rapid Ingress and Heroic Intervention Stratagems for 0CP, even if you have already used that Stratagem on a different unit this phase.",
        ("rapid ingress", "heroic intervention"),
    ),
    (
        "Gene-seed Recovery",
        "When this model's Bodyguard unit is destroyed, roll one D6: on a 2+, you gain 1CP.",
        ("bodyguard unit is destroyed", "gain 1cp"),
    ),
    (
        "Vivispectrum",
        "If this model's unit destroys an enemy unit as the result of a melee attack, until the end of the battle, this model has an Objective Control characteristic of 9.",
        ("objective control becomes 9", "melee attack"),
    ),
    (
        "Feared Interrogator",
        "At the start of the Fight phase, each enemy CHARACTER unit within 6\" of this model must take a Battle-shock test, subtracting 1 from that test when they do. In addition, each time this model destroys an enemy CHARACTER model with a melee attack, you gain 1CP.",
        ("character units within 6", "gain 1 cp"),
    ),
    (
        "Overcharged Engines",
        "You can re-roll Advance rolls made for this model.",
        ("re-roll advance rolls", "this model"),
    ),
]


@pytest.mark.parametrize(("name", "description", "fragments"), CASES)
def test_support_matrix_space_marines_batch1_datasheet_abilities(name: str, description: str, fragments: tuple[str, str]):
    from scripts.generate_ability_support_matrix import _classify_ability

    status, notes = _classify_ability(name, description, faction_id="SM")

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    for fragment in fragments:
        assert fragment in notes_l
