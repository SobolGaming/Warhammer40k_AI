def test_support_matrix_classifies_tyranids_hypersensory_array_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Once per battle round, you can target this unit with the Rapid Ingress or Heroic Intervention Stratagem for 0CP, "
        "and can do so even if you have already targeted a different unit with that Stratagem this turn."
    )
    status, notes = gsm._classify_ability("Hypersensory Array", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "rapid ingress" in notes_l
    assert "heroic intervention" in notes_l
    assert "0cp" in notes_l
