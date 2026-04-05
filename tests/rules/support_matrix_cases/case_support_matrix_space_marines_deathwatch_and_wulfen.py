def test_support_matrix_classifies_death_to_the_alien_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    description = (
        "Each time a model in this unit makes an attack, re-roll a Hit roll of 1. "
        "If the target of that attack does not have the IMPERIUM or CHAOS keywords, "
        "you can re-roll the Hit roll instead."
    )

    status, note = _classify_ability("Death to the Alien", description, faction_id="SM")

    note_lower = note.lower()
    assert status == "Supported"
    assert "re-roll hit rolls of 1" in note_lower
    assert "imperium/chaos" in note_lower


def test_support_matrix_classifies_death_totem_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    status, note = _classify_ability(
        "Death Totem",
        "Each time the bearer makes a melee attack, re-roll a Hit roll of 1.",
        faction_id="SM",
    )

    assert status == "Supported"
    assert "model attack roll modifiers supported" in note.lower()
