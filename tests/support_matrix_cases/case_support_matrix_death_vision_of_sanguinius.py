def test_support_matrix_classifies_tycho_death_vision_of_sanguinius_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    status, notes = gsm._classify_ability(
        "Death Vision of Sanguinius",
        (
            "If this model is destroyed by a melee attack, after the attacking unit has finished making its attacks, "
            "you can roll one D6, adding 2 to the result if the attacking unit contains the enemy WARLORD: on a 2-3, "
            "that enemy unit suffers 3 mortal wounds; on a 4-5, that enemy unit suffers D3+3 mortal wounds; on a 6+, "
            "that enemy unit suffers D6+3 mortal wounds."
        ),
        faction_id="SM",
    )

    assert status == "Supported"
    assert "warlord" in notes.lower()
    assert "mortal wounds" in notes.lower()


def test_support_matrix_classifies_captain_death_vision_of_sanguinius_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    status, notes = gsm._classify_ability(
        "Death Vision of Sanguinius",
        (
            "If this model is destroyed by a melee attack, after the attacking unit has finished making its attacks, "
            "you can roll one D6, adding 2 to the result if the attacking unit contains the enemy WARLORD: on a 2-3, "
            "that enemy unit suffers D3 mortal wounds; on a 4-5, that enemy unit suffers 3 mortal wounds; on a 6+, "
            "that enemy unit suffers D3+3 mortal wounds."
        ),
        faction_id="SM",
    )

    assert status == "Supported"
    assert "2-3" in notes
    assert "6+" in notes
