from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch22_uriel_ventris_master_of_the_fleet_support_matrix_case():
    description = (
        "During the Declare Battle Formations step, if your army includes this model, select one Phobos, "
        "Gravis or Tacticus Adeptus Astartes Infantry unit from your army. That unit gains the Deep Strike ability."
    )

    status, notes = _classify_ability(
        "Master of the Fleet",
        description,
        faction_id="SM",
        datasheet_id="000000121",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "declare battle formations" in notes_l
    assert "deep strike" in notes_l
    assert "phobos" in notes_l
    assert "gravis" in notes_l
    assert "tacticus" in notes_l
