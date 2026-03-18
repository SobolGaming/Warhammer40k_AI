import pytest

from scripts.generate_ability_support_matrix import _classify_ability


@pytest.mark.parametrize(
    ("name", "description", "note_fragment"),
    [
        (
            "Teleport Homer",
            "At the start of the battle, you can set up one Teleport Homer token for this unit anywhere on the battlefield that is not in your opponent's deployment zone. If you do, once per battle, you can target this unit with the Rapid Ingress Stratagem for 0CP, but when resolving that Stratagem, you must set this unit up within 3\" horizontally of that token and not within 9\" horizontally of any enemy models. That token is then removed.",
            "rapid ingress",
        ),
        (
            "Terminatus Assault",
            "At the start of the Fight phase, each enemy unit within Engagement Range of this unit must take a Battle-shock test.",
            "engagement range",
        ),
    ],
)
def test_space_marines_batch21_terminator_assault_squad_support_matrix_cases(
    name: str,
    description: str,
    note_fragment: str,
):
    status, notes = _classify_ability(name, description, faction_id="SM")
    assert status == "Supported"
    assert note_fragment.lower() in str(notes).lower()
