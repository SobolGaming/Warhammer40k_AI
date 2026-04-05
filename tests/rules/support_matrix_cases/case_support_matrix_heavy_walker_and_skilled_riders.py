def test_support_matrix_classifies_heavy_walker_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time this model makes a Normal, Advance or Fall Back move, it can move over models "
        "(excluding TITANIC models) and terrain features that are 4\" or less in height as if they were not there."
    )
    status, notes = gsm._classify_ability(
        "Heavy Walker",
        description,
        faction_id="SM",
        datasheet_id="000000434",
    )

    assert status == "Supported"
    assert "excluding titanic" in str(notes or "").lower()


def test_support_matrix_classifies_skilled_riders_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Each time a model in this model's unit makes a Normal, Advance, Fall Back or Charge move, "
        "it can move horizontally through terrain features."
    )
    status, notes = gsm._classify_ability(
        "Skilled Riders",
        description,
        faction_id="SM",
        datasheet_id="000004167",
    )

    assert status == "Supported"
    assert "normal/advance/fall back/charge" in str(notes or "").lower()
