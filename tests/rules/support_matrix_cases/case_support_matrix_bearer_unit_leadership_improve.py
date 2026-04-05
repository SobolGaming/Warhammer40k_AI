import pytest


@pytest.mark.parametrize(
    "description",
    [
        "Improve the Leadership characteristic of models in the bearer's unit by 1.",
        "While this model is leading a unit, improve the Leadership characteristic of models in that unit by 1.",
    ],
)
def test_bearer_unit_leadership_improve_clause_supported(description: str):
    import scripts.generate_ability_support_matrix as gsm

    status, notes = gsm._classify_ability(
        "Mark of Dread",
        description,
        faction_id="CD",
    )

    assert status == "Supported"
    assert "leadership characteristic improves by 1" in str(notes or "").lower()
