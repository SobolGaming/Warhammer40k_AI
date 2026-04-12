from scripts.generate_ability_support_matrix import _classify_ability


def test_revel_in_desecration_is_supported() -> None:
    status, notes = _classify_ability(
        "Revel in Desecration",
        "Each time this model makes an attack that targets an enemy unit that is not below Half-strength, add 1 to the Hit roll.",
        faction_id="EC",
        datasheet_id="000004208",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "not below half-strength" in notes_l
    assert "+1 to hit" in notes_l
