import pytest

from scripts.generate_ability_support_matrix import _classify_ability


@pytest.mark.parametrize(
    ("name", "description", "note_fragment"),
    [
        (
            "Gift of the Iron Wolf",
            "In your Command phase, you can select one friendly Adeptus Astartes Vehicle model within 3\" of this model. That model regains up to D3 lost wounds and, until the start of your next Command phase, select one ranged weapon equipped by that model to have the [RAPID FIRE 1] ability. Each model can only be selected for this ability or the Blessing of the Omnissiah ability once per turn.",
            "rapid fire 1",
        ),
        (
            "Judgement of the Omnissiah",
            "Each time this model makes an attack that targets an enemy unit within Engagement Range of one or more friendly Adeptus Astartes Vehicle units, you can re-roll the Wound roll.",
            "engagement range of friendly adeptus astartes vehicle units",
        ),
    ],
)
def test_space_marines_iron_priest_support_matrix_cases(name: str, description: str, note_fragment: str):
    status, notes = _classify_ability(name, description, faction_id="SM")
    assert status == "Supported"
    assert note_fragment.lower() in str(notes).lower()
