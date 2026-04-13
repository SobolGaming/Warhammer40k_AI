def test_support_matrix_classifies_csm_kravek_morne_architect_of_ruin_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "At the start of the battle, select one unit in your opponent's army to be this model's hated foe. "
        "Each time this model makes an attack that targets its hated foe, you can re-roll the Wound roll. "
        "Each time this model's hated foe is destroyed, you can select a new unit from your opponent's army to be its hated foe."
    )

    status, notes = gsm._classify_ability(
        "Architect of Ruin",
        description,
        faction_id="CSM",
        datasheet_id="000004205",
    )

    assert status == "Supported"
    lowered = notes.lower()
    assert "start of battle" in lowered
    assert "wound" in lowered
    assert "re-pick" in lowered or "repick" in lowered


def test_support_matrix_classifies_csm_kravek_morne_headlong_destruction_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time a model in this unit makes an attack that targets the closest eligible enemy unit, improve the Armour "
        "Penetration characteristic of that attack by 1."
    )

    status, notes = gsm._classify_ability(
        "Headlong Destruction",
        description,
        faction_id="CSM",
        datasheet_id="000004205",
    )

    assert status == "Supported"
    lowered = notes.lower()
    assert "closest eligible target" in lowered
    assert "ap by 1" in lowered
