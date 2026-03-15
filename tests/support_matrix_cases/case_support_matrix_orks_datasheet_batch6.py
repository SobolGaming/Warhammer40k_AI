import pytest

from scripts.generate_ability_support_matrix import _classify_ability


@pytest.mark.parametrize(
    ("name", "description", "note_fragment"),
    [
            (
                "Buzzer Squigs",
                "In your Shooting phase, after this model has shot, select one enemy unit (excluding MONSTERS and VEHICLES) hit by one or more of those attacks made with squig-launchas and roll one D6: on a 4+, until the end of your opponent's next turn, that enemy unit is hindered. While a unit is hindered, subtract 2\" from its Move characteristic and subtract 2 from Advance and Charge rolls made for it.",
                "squig launchas",
            ),
        (
            "Squig Mine",
            "Once per battle, at the start of any phase, select one enemy unit within 3\" of this model and roll one D6: on a 4+, that enemy unit suffers D6 mortal wounds.",
            "once per battle",
        ),
        (
            "Drive-by Dakka",
            "Each time a model in this unit makes a ranged attack that targets a unit within 9\", improve the Armour Penetration characteristic of that attack by 1.",
            "within 9",
        ),
        (
            "Waaagh! Effigy (Aura)",
            "While a friendly ORKS unit is within 12\" of this model, each time you take a Battle-shock test for that unit, add 1 to that test.",
            "friendly ORKS",
        ),
        (
            "Super Runts",
            "While this model is leading a unit: Models in that unit have the Scouts 9\" ability. Each time a model in that unit makes an attack, add 1 to the Hit roll and add 1 to the Wound roll. Each time an attack targets that unit, subtract 1 from the Wound roll.",
            "scouts 9",
        ),
        (
            "Unstable Oracle",
            "While this model is leading a unit, add 2 to the Attacks characteristic of this model's Eyez of Mork weapon for every 5 models in that unit (rounding down), but while that unit contains 10 or more models, that weapon has the [HAZARDOUS] ability.",
            "eyez of mork",
        ),
    ],
)
def test_orks_datasheet_batch6_support_matrix_cases(name: str, description: str, note_fragment: str):
    status, notes = _classify_ability(name, description, faction_id="ORK")
    assert status == "Supported"
    assert note_fragment.lower() in str(notes).lower()
