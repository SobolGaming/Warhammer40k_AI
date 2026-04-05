import pytest

from scripts.generate_ability_support_matrix import _classify_ability


@pytest.mark.parametrize(
    ("name", "description", "note_fragment"),
    [
        (
            "Shokk-boosta",
            "You can re-roll Advance rolls made for this model's unit. In addition, each time this model's unit makes a Normal, "
            "Advance or Fall Back move, models in that unit can move through models and terrain features. When doing so, they can "
            "move within Engagement Range of such models but cannot end that move within Engagement Range of them, and any "
            "Desperate Escape test is automatically passed.",
            "auto-passes Desperate Escape tests",
        ),
        (
            "Kustom Force Field",
            "While the bearer is leading a unit, models in that unit have a 4+ invulnerable save against ranged attacks.",
            "against ranged attacks",
        ),
        (
            "Grot Assistant",
            "Once per battle, after rolling to determine how many attacks the bearer’s shokk attack gun makes, you can re-roll that dice."
            "<br><br><b>Designer’s Note:</b> <i>Place a Grot Assistant token next to the bearer, removing it once this ability has been used.</i>",
            "shokk attack gun",
        ),
        (
            "Boom Bomb",
            "Each time this model ends a Normal move, you can select one enemy unit it moved over during that move and roll one D6: "
            "on a 4+, that unit suffers D6 mortal wounds.",
            "roll D6, on 4+ inflict D6 mortal wounds",
        ),
        (
            "Dust Trails (Aura)",
            "While an enemy unit (excluding MONSTERS and VEHICLES) is within 6\" of this model, each time a model in that unit "
            "makes an attack, subtract 1 from the Hit roll.",
            "within 6\" suffer -1 to Hit rolls",
        ),
    ],
)
def test_orks_datasheet_batch2_support_matrix_cases(name: str, description: str, note_fragment: str):
    status, notes = _classify_ability(name, description)
    assert status == "Supported"
    assert note_fragment.lower() in str(notes).lower()
