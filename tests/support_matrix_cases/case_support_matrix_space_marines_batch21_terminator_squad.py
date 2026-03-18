from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch21_terminator_squad_support_matrix_case():
    description = "Each time a model in this unit makes an attack that targets your Oath of Moment target, add 1 to the Hit roll."

    status, notes = _classify_ability(
        "Fury of the First",
        description,
        faction_id="SM",
        datasheet_id="000001183",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "oath of moment target" in notes_l
    assert "+1" in notes_l
    assert "hit roll" in notes_l
