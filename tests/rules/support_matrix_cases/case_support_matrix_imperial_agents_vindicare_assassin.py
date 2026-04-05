def test_support_matrix_classifies_vindicare_shieldbreaker_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Shieldbreaker"
    description = (
        "Once per battle, when selecting targets for this model's exitus rifle, it can fire a shieldbreaker round. "
        "If it does, until the end of the phase, each time this model makes an attack with that weapon, add 1 to "
        "the Wound roll and any successful Wound roll scores a Critical Wound."
    )

    status, note = _classify_ability(ability_name, description, faction_id="AOI")

    assert status == "Supported"
    assert "critical wound" in note.lower()
