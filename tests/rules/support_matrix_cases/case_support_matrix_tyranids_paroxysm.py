def test_support_matrix_classifies_tyranids_paroxysm_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "At the start of the Fight phase, you can select one enemy unit within 12\" of and visible to this model and roll one D6: "
        "on a 1, this PSYKER suffers D3 mortal wounds; on a 2+, until the end of the phase, subtract 1 from the Attacks "
        "characteristic of weapons equipped by models in that unit."
    )
    status, notes = gsm._classify_ability("Paroxysm (Psychic)", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "start of fight phase" in notes_l
    assert ("-1" in notes_l) or ("subtract 1" in notes_l)
    assert "attacks" in notes_l
