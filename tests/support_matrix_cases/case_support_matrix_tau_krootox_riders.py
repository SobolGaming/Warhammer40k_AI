def test_support_matrix_classifies_tau_kroot_packmates_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    description = (
        "Once per turn, in your opponent's Shooting phase, when a friendly Kroot Infantry unit within 6\" of this unit "
        "is selected as the target of an attack, one unit from your army with this ability can use it. "
        "If it does, after that enemy unit has finished making its attacks, that unit with this ability can shoot as if it were "
        "your Shooting phase, but when resolving those attacks it can only target that enemy unit "
        "(and only if it is an eligible target)."
    )
    status, notes = gsm._classify_ability("Kroot Packmates", description, faction_id="TAU")

    assert status == "Supported"
    lowered = notes.lower()
    assert "reactive shooting" in lowered
    assert "kroot infantry" in lowered
