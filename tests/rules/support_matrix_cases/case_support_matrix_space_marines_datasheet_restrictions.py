import os


def _seed_support_maps(gsm):
    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    gsm.DETACHMENT_ABILITY_IDS = {
        str(row.get("id", "") or "").strip()
        for row in detachment_abilities
        if str(row.get("id", "") or "").strip()
    }
    gsm._seed_ability_support_maps(abilities, detachment_abilities)


def test_support_matrix_classifies_chosen_of_the_emperor_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    _seed_support_maps(gsm)
    status, notes = gsm._classify_ability(
        "CHOSEN OF THE EMPEROR",
        "You cannot include more than one EMPEROR'S CHAMPION model in your army.",
        faction_id="SM",
    )

    assert status == "Supported"
    assert "one-model inclusion cap" in notes


def test_support_matrix_classifies_crimson_fists_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    _seed_support_maps(gsm)
    status, notes = gsm._classify_ability(
        "CRIMSON FISTS",
        (
            "This model is from the Crimson Fists Chapter, a successor of the Imperial Fists. "
            "For all rules purposes, it is treated as an Imperial Fists model, but it cannot be "
            "included in an army that includes any other Imperial Fists Epic Hero models."
        ),
        faction_id="SM",
    )

    assert status == "Supported"
    assert "imperial fists epic hero" in notes.lower()


def test_support_matrix_classifies_company_heroes_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    _seed_support_maps(gsm)
    status, notes = gsm._classify_ability(
        "COMPANY HEROES",
        (
            "You must attach one CAPTAIN or CHAPTER MASTER model to this unit. "
            "If this is not possible, this unit does not take part in the battle and counts as having been destroyed."
        ),
        faction_id="SM",
    )

    assert status == "Supported"
    assert "captain/chapter master" in notes.lower()


def test_support_matrix_classifies_heroes_of_ultramar_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    _seed_support_maps(gsm)
    status, notes = gsm._classify_ability(
        "HEROES OF ULTRAMAR",
        (
            "At the start of the Declare Battle Formations step, this unit can join one of the following units. "
            "Assault Intercessor Squad, Bladeguard Veteran Squad, Intercessor Squad, Sternguard Veteran Squad. "
            "This unit cannot join an Attached unit, and only Captain Titus can join a unit this unit has joined."
        ),
        faction_id="SM",
    )

    assert status == "Supported"
    assert "captain titus" in notes.lower()


def test_support_matrix_classifies_chapter_master_of_the_raven_guard_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    _seed_support_maps(gsm)
    status, notes = gsm._classify_ability(
        "CHAPTER MASTER OF THE RAVEN GUARD",
        (
            "At the start of the Declare Battle Formations step, if your army includes AETHON SHAAN and Kayvaan Shrike, "
            "until the end of the battle, your KAYVAAN SHRIKE unit loses its Lone Operative ability and it replaces "
            "its CHAPTER MASTER keyword with CAPTAIN."
        ),
        faction_id="SM",
    )

    assert status == "Supported"
    assert "kayvaan shrike" in notes.lower()
