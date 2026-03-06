def test_support_matrix_classifies_opponent_cp_gain_reaction_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time your opponent gains a CP as the result of an ability, roll one D6: "
        "on a 2+, you also gain 1CP."
    )

    status, notes = gsm._classify_ability(
        "Spy Network",
        description,
        faction_id="IA",
        datasheet_id="000000000",
    )

    assert status == "Supported"
    assert "opponent gains cp from an ability" in str(notes or "").lower()
