def test_support_matrix_space_marines_batch20_sternguard_veteran_squad() -> None:
    from scripts.generate_ability_support_matrix import _classify_ability

    description = (
        "Each time a model in this unit makes an attack that targets your Oath of Moment target, "
        "you can re-roll the Wound roll."
    )

    status, notes = _classify_ability(
        "Sternguard Focus",
        description,
        faction_id="SM",
        datasheet_id="000002255",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "oath of moment target" in notes_l
    assert "re-roll the wound roll" in notes_l


def test_support_matrix_space_marines_batch20_black_templars_sternguard_veteran_squad() -> None:
    from scripts.generate_ability_support_matrix import _classify_ability

    description = (
        "Each time a model in this unit makes an attack that targets the closest eligible target, "
        "re-roll a Wound roll of 1."
    )

    status, notes = _classify_ability(
        "Virtuous Onslaught",
        description,
        faction_id="SM",
        datasheet_id="000004137",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "closest eligible target" in notes_l
    assert "re-roll wound rolls of 1" in notes_l
