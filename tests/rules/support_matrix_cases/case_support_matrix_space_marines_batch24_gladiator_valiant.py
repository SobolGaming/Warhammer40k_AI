from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch24_gladiator_valiant_ferocious_assault_support_matrix_case():
    status, notes = _classify_ability(
        "Ferocious Assault",
        "Each time this model makes an attack with its twin las-talon that targets the closest eligible MONSTER or VEHICLE unit, add 1 to the Hit roll.",
        faction_id="SM",
        datasheet_id="000001825",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "twin las talon" in notes_l
    assert "closest eligible" in notes_l
    assert "monster/vehicle" in notes_l
    assert "+1" in notes_l


def test_space_marines_batch24_gladiator_valiant_priority_target_acquisition_support_matrix_case():
    status, notes = _classify_ability(
        "Priority Target Acquisition",
        "Each time this model makes an attack with its twin las-talon that targets the closest eligible MONSTER or VEHICLE unit, add 1 to the Hit roll.",
        faction_id="SM",
        datasheet_id="000002788",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "twin las talon" in notes_l
    assert "closest eligible" in notes_l
    assert "monster/vehicle" in notes_l
    assert "+1" in notes_l
