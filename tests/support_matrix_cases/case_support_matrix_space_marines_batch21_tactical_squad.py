def test_support_matrix_space_marines_batch21_tactical_squad() -> None:
    from scripts.generate_ability_support_matrix import _classify_ability

    description = (
        "At the start of the Declare Battle Formations step, before any units have been set up, this unit can be split "
        "into two units, each containing five models."
    )

    status, notes = _classify_ability(
        "Combat Squads",
        description,
        faction_id="SM",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "declare battle formations" in notes_l
    assert "5-model" in notes_l or "five-model" in notes_l
    assert "split" in notes_l
