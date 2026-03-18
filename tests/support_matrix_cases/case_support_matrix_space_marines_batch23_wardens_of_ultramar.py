from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch23_wardens_of_ultramar_second_company_banner_support_matrix_case():
    description = (
        "While this unit contains Ancient Gadriel, add 1 to the Objective Control characteristic of models in this "
        "unit. While this unit contains Ancient Gadriel and Captain Titus, improve the Leadership characteristic of "
        "models in this unit by 1 as well."
    )

    status, notes = _classify_ability(
        "Second Company Banner",
        description,
        faction_id="SM",
        datasheet_id="000004188",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "ancient gadriel" in notes_l
    assert "objective control" in notes_l
    assert "captain titus" in notes_l


def test_space_marines_batch23_wardens_of_ultramar_strategium_command_support_matrix_case():
    description = (
        "After both players have deployed their armies, if this unit is on the battlefield (or any Transport it is "
        "embarked within is on the battlefield), select up to three ADEPTUS ASTARTES units from your army and "
        "redeploy them. When doing so, you can set those units up in Strategic Reserves, regardless of how many units "
        "are already in Strategic Reserves."
    )

    status, notes = _classify_ability(
        "Strategium Command",
        description,
        faction_id="SM",
        datasheet_id="000004188",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "source is on the battlefield" in notes_l
    assert "adeptus astartes" in notes_l
    assert "strategic reserves" in notes_l
