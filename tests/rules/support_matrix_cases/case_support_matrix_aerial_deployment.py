def test_support_matrix_classifies_aerial_deployment_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    ability_name = "Aerial Deployment"
    description = (
        "If this model starts the game in Hover mode and in Strategic Reserves, it can be set up in the Reinforcements "
        "step of your first, second or third Movement phase, regardless of any mission rules."
    )

    status, notes = gsm._classify_ability(ability_name, description, faction_id="ADM")
    assert status == "Supported"
    assert "battle rounds 1-3" in str(notes)
