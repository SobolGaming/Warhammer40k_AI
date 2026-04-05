def test_support_matrix_classifies_tyranids_encephalic_diffusion_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "While an enemy unit is within 6\" of this model, each time a model in that unit makes an attack, "
        "subtract 1 from the Hit roll, and, if that enemy unit is Below Half-strength, subtract 1 from the Wound roll as well."
    )
    status, notes = gsm._classify_ability("Encephalic Diffusion (Aura, Psychic)", description, faction_id="TYR")

    notes_l = notes.lower()
    assert status == "Supported"
    assert "within 6" in notes_l
    assert "hit" in notes_l
    assert "below half" in notes_l
    assert "wound" in notes_l
