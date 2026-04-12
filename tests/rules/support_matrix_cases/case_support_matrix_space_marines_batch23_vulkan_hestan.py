from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch23_vulkan_hestan_forgefather_support_matrix_case():
    description = (
        'In your Shooting phase, select one enemy unit within 24" of and visible to this model. Until the end of '
        "the phase, each time a friendly ADEPTUS ASTARTES model makes a ranged attack with a Torrent or Melta "
        "weapon that targets that enemy unit, you can re-roll the Wound roll."
    )

    status, notes = _classify_ability(
        "Forgefather",
        description,
        faction_id="SM",
        datasheet_id="000002726",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "visible enemy unit" in notes_l
    assert "torrent or melta" in notes_l


def test_space_marines_batch23_vulkan_hestan_seeker_of_lost_relics_support_matrix_case():
    description = (
        "The first time this model is set up on the battlefield, select one objective marker on the battlefield. "
        "While this model is within range of that objective marker, this model has an Objective Control "
        "characteristic of 10, a Leadership characteristic of 5+ and the Feel No Pain 4+ ability."
    )

    status, notes = _classify_ability(
        "Seeker of the Unfound",
        description,
        faction_id="SM",
        datasheet_id="000002726",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "objective marker" in notes_l
    assert "objective control 10" in notes_l
    assert "leadership 5+" in notes_l
    assert "feel no pain 4+" in notes_l
