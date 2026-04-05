from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch24_gladiator_reaper_rotating_death_support_matrix_case():
    status, notes = _classify_ability(
        "Rotating Death",
        "This model's twin heavy onslaught gatling cannon has the [SUSTAINED HITS 2] ability when targeting INFANTRY units.",
        faction_id="SM",
        datasheet_id="000001667",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "twin heavy onslaught gatling cannon" in notes_l
    assert "infantry" in notes_l
    assert "sustained hits 2" in notes_l


def test_space_marines_batch24_gladiator_reaper_reaping_tally_support_matrix_case():
    status, notes = _classify_ability(
        "Reaping Tally",
        "This model's twin heavy onslaught gatling cannon has the [SUSTAINED HITS 2] ability while targeting INFANTRY units.",
        faction_id="SM",
        datasheet_id="000002789",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "twin heavy onslaught gatling cannon" in notes_l
    assert "infantry" in notes_l
    assert "sustained hits 2" in notes_l
