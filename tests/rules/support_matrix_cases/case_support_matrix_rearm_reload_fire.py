def test_support_matrix_classifies_rearm_reload_fire_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While this unit is being affected by an Order, provided it Remained Stationary this turn, "
        "all Heavy weapons equipped by models in this unit have the [SUSTAINED HITS 1] ability."
    )

    status, notes = gsm._classify_ability(
        "Rearm, Reload, Fire",
        description,
        faction_id="AM",
        datasheet_id="000000000",
    )

    assert status == "Supported"
    lowered = notes.lower()
    assert "order" in lowered
    assert "heavy" in lowered
    assert "sustained hits 1" in lowered
