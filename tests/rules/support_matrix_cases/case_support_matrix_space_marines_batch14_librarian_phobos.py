from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch14_librarian_phobos_shrouding_support_matrix_case():
    status, notes = _classify_ability(
        "Shrouding (Psychic)",
        "While this model is leading a unit, models in that unit have the Stealth ability and that unit cannot be targeted by ranged attacks unless the attacking model is within 12\".",
        faction_id="SM",
    )
    assert status == "Supported"
    lowered = str(notes).lower()
    assert "stealth" in lowered
    assert "within 12" in lowered
