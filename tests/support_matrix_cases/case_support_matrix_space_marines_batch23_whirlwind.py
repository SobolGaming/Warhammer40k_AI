from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch23_whirlwind_pinning_bombardment_support_matrix_case():
    description = (
        "In your Shooting phase, after this model has shot, if one or more of those attacks made with its Whirlwind "
        "vengeance launcher scored a hit against an enemy INFANTRY unit, that unit must take a Battle-shock test."
    )

    status, notes = _classify_ability(
        "Pinning Bombardment",
        description,
        faction_id="SM",
        datasheet_id="000002727",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "infantry" in notes_l
    assert "whirlwind vengeance launcher" in notes_l
    assert "battle-shock test" in notes_l
