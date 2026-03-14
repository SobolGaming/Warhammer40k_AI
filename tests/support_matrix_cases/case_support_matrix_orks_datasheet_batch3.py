import pytest

from scripts.generate_ability_support_matrix import _classify_ability


@pytest.mark.parametrize(
    ("name", "description", "note_fragment"),
    [
        (
            "Red Skull Kommandos",
            "While this model is leading a unit, models in that unit have the Benefit of Cover.",
            "benefit of cover",
        ),
        (
            "Kunnin' Infiltrator",
            "Once per battle, in your Movement phase, instead of making a Normal move with this model's unit, you can remove it from the battlefield and set it up again anywhere on the battlefield that is more than 9\" horizontally away from all enemy models.",
            "normal move",
        ),
        (
            "Burna Bomb",
            "Each time this model ends a Normal move, you can select one enemy unit it moved over during that move. Until the end of the turn, models in that unit cannot have the Benefit of Cover. In addition, roll one D6 for each model in that unit: for each 6, that unit suffers 1 mortal wound.",
            "loses benefit of cover",
        ),
        (
            "Pyromaniaks",
            "Each time a model in this unit makes a ranged attack with a burna that targets an enemy unit within 6\", re-roll a Wound roll of 1. If the target of that attack is also within range of an objective marker, you can re-roll the Wound roll instead.",
            "burna ranged attacks",
        ),
        (
            "Piston-driven Brutality",
            "Each time this model ends a Charge move, select one enemy unit within Engagement Range of this model and roll one D6: on a 2-5, that enemy unit suffers D3 mortal wounds; on a 6, that enemy unit suffers D3+3 mortal wounds.",
            "2-5=d3",
        ),
        (
            "Gun-crazy Show-offs",
            "Each time a model in this unit targets the closest eligible target with its snazzgun, until the end of the phase, that weapon has an Attacks characteristic of 4.",
            "attacks 4",
        ),
    ],
)
def test_orks_datasheet_batch3_support_matrix_cases(name: str, description: str, note_fragment: str):
    status, notes = _classify_ability(name, description, faction_id="ORK")
    assert status == "Supported"
    assert note_fragment.lower() in str(notes).lower()
