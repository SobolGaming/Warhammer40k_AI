from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch22_thunderwolf_cavalry_support_matrix_case():
    description = (
        "Each time a model in this unit makes a melee attack with its Wolf Guard weapon, "
        "if it made a Charge move this turn, add 1 to the Damage characteristic of that attack."
    )

    status, notes = _classify_ability(
        "Thunderous Charge",
        description,
        faction_id="SM",
        datasheet_id="000000322",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "wolf guard weapon" in notes_l
    assert "charging" in notes_l
    assert "+1 damage" in notes_l
