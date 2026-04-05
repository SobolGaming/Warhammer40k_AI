def test_support_matrix_classifies_vengeance_for_the_omnissiah_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    ability_name = "Vengeance for the Omnissiah"
    description = (
        "If a friendly Adeptus Mechanicus Vehicle model is destroyed within 12\" of this model, "
        "until the end of the battle, this model's Omnissian axe has an Attacks characteristic of 6."
    )

    status, _notes = gsm._classify_ability(ability_name, description, faction_id="ADM")
    assert status == "Supported"
