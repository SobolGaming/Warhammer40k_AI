import pytest

from scripts.generate_ability_support_matrix import _classify_ability


@pytest.mark.parametrize(
    ("name", "description", "note_fragment"),
    [
        (
            "Da Jump (Psychic)",
            "Once per turn, at the end of your Movement phase, one WEIRDBOY from your army can use this ability. If it does, roll one D6: on a 1, that WEIRDBOY's unit suffers D6 mortal wounds; on a 2+, remove this WEIRDBOY's unit from the battlefield and set it up again anywhere on the battlefield that is more than 9\" horizontally away from all enemy models.",
            "WEIRDBOY",
        ),
    ],
)
def test_orks_datasheet_batch7_support_matrix_cases(name: str, description: str, note_fragment: str):
    status, notes = _classify_ability(name, description, faction_id="ORK")
    assert status == "Supported"
    assert note_fragment.lower() in str(notes).lower()
