import pytest


@pytest.mark.parametrize(
    "description, keyword",
    [
        ("The bearer has the SMOKE keyword.", "SMOKE"),
        ("The bearer has the PSYKER keyword.", "PSYKER"),
    ],
)
def test_support_matrix_classifies_bearer_keyword_grants_as_supported(description: str, keyword: str):
    import scripts.generate_ability_support_matrix as gsm

    status, notes = gsm._classify_ability("Bearer Keyword", description, faction_id="NEC")

    assert status == "Supported"
    assert f"bearer gains the {keyword.lower()} keyword" in str(notes or "").lower()
