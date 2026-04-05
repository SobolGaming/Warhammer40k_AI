def test_support_matrix_classifies_tau_coordinated_leadership_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = "At the end of your Command phase, roll one D6: on a 4+, you gain 1CP."
    status, notes = gsm._classify_ability("Coordinated Leadership", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "end of command phase" in lowered
    assert "4+" in lowered
    assert "gain 1 cp" in lowered


def test_support_matrix_classifies_tau_hover_drone_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = "The bearer can FLY and has a Move characteristic of 10\"."
    status, notes = gsm._classify_ability("Hover Drone", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "fly keyword" in lowered
    assert "move characteristic of 10" in lowered

