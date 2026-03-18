from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch23_vindicator_siege_shield_support_matrix_case():
    description = (
        "When making ranged attacks with its demolisher cannon, this model can target enemy units within Engagement "
        "Range of it (provided no other friendly units are also within Engagement Range of that enemy unit). In "
        "addition, when making ranged attacks, this model does not suffer the penalty to its Hit rolls for being "
        "within Engagement Range of one or more enemy units."
    )

    status, notes = _classify_ability(
        "Siege Shield",
        description,
        faction_id="SM",
        datasheet_id="000001188",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "demolisher cannon" in notes_l
    assert "big guns never tire" in notes_l or "engagement" in notes_l
