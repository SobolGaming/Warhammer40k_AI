def test_support_matrix_classifies_aerial_seeding_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    ability_name = "Aerial Seeding"
    description = (
        "This model must start the battle in Reserves, but neither it nor any units embarked within it are counted "
        "towards any limits placed on the maximum number of Reserves units you can start the battle with. This model "
        "can be set up in the Reinforcements step of your first, second or third Movement phase, regardless of any "
        "mission rules. Any units embarked within this model must immediately disembark after it has been set up on "
        "the battlefield, and they must be set up more than 9\" away from all enemy models. After this model has been "
        "set up on the battlefield, no units can embark within it."
    )

    status, notes = gsm._classify_ability(ability_name, description, faction_id="TYR")
    assert status == "Supported"
    assert "reserves unit-count cap" in str(notes).lower()
