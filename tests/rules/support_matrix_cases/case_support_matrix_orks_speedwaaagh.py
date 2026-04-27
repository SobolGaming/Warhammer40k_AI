import os


def _seed_support_maps():
    import scripts.generate_ability_support_matrix as gsm

    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    gsm.DETACHMENT_ABILITY_IDS = {
        str(row.get("id", "") or "").strip()
        for row in detachment_abilities
        if str(row.get("id", "") or "").strip()
    }
    gsm._seed_ability_support_maps(abilities, detachment_abilities)
    return gsm, detachment_abilities


def test_speedwaaagh_turbo_boostas_detachment_ability_is_supported():
    gsm, detachment_abilities = _seed_support_maps()
    row = next(
        item
        for item in detachment_abilities
        if str(item.get("id", "") or "").strip() == "000010794"
    )

    status, notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id=row.get("faction_id", ""),
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "speedwaaagh" in notes_l
    assert "24" in notes_l
    assert "assault" in notes_l
    assert "no-pivot" in notes_l or "no pivot" in notes_l
    assert "no-charge" in notes_l or "blocking charges" in notes_l


def test_speedwaaagh_mobile_dakkastorm_stratagem_is_supported():
    gsm, _detachment_abilities = _seed_support_maps()
    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == "000010796003"
    )

    status, notes, canonical_name = gsm._stratagem_support(
        row.get("name", ""),
        row.get("description", ""),
        detachment_name="Speedwaaagh!",
        stratagem_id=row.get("id", ""),
    )

    assert status in {"Implemented", "Supported"}
    assert canonical_name == "MOBILE DAKKASTORM"
    notes_l = str(notes or "").lower()
    assert "non-indirect" in notes_l
    assert "speed freeks" in notes_l
    assert "+2 strength" in notes_l


def test_speedwaaagh_evasive_manoova_stratagem_is_supported():
    gsm, _detachment_abilities = _seed_support_maps()
    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == "000010796007"
    )

    status, notes, canonical_name = gsm._stratagem_support(
        row.get("name", ""),
        row.get("description", ""),
        detachment_name="Speedwaaagh!",
        stratagem_id=row.get("id", ""),
    )

    assert status in {"Implemented", "Supported"}
    assert canonical_name == "EVASIVE MANOOVA"
    notes_l = str(notes or "").lower()
    assert "strategic reserves" in notes_l
    assert "speed freeks" in notes_l
    assert "trukk" in notes_l


def test_speedwaaagh_dust_trails_stratagem_is_supported():
    gsm, _detachment_abilities = _seed_support_maps()
    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == "000010796006"
    )

    status, notes, canonical_name = gsm._stratagem_support(
        row.get("name", ""),
        row.get("description", ""),
        detachment_name="Speedwaaagh!",
        stratagem_id=row.get("id", ""),
    )

    assert status in {"Implemented", "Supported"}
    assert canonical_name == "DUST TRAILS"
    notes_l = str(notes or "").lower()
    assert "benefit of cover" in notes_l
    assert "opponent shooting" in notes_l
    assert "orks" in notes_l


def test_speedwaaagh_ded_killy_construction_stratagem_is_supported():
    gsm, _detachment_abilities = _seed_support_maps()
    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == "000010796005"
    )

    status, notes, canonical_name = gsm._stratagem_support(
        row.get("name", ""),
        row.get("description", ""),
        detachment_name="Speedwaaagh!",
        stratagem_id=row.get("id", ""),
    )

    assert status in {"Implemented", "Supported"}
    assert canonical_name == "DED KILLY CONSTRUCTION"
    notes_l = str(notes or "").lower()
    assert "lance" in notes_l
    assert "+1 melee damage" in notes_l
    assert "speed freeks" in notes_l


def test_speedwaaagh_on_da_move_stratagem_is_supported():
    gsm, _detachment_abilities = _seed_support_maps()
    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == "000010796002"
    )

    status, notes, canonical_name = gsm._stratagem_support(
        row.get("name", ""),
        row.get("description", ""),
        detachment_name="Speedwaaagh!",
        stratagem_id=row.get("id", ""),
    )

    assert status in {"Implemented", "Supported"}
    assert canonical_name == "ON DA MOVE"
    notes_l = str(notes or "").lower()
    assert "advancing" in notes_l or "advanced" in notes_l
    assert "falling back" in notes_l or "fell back" in notes_l
    assert "turbo" in notes_l


def test_speedwaaagh_speshul_ammo_stratagem_is_supported():
    gsm, _detachment_abilities = _seed_support_maps()
    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    row = next(
        item
        for item in stratagems
        if str(item.get("id", "") or "").strip() == "000010796004"
    )

    status, notes, canonical_name = gsm._stratagem_support(
        row.get("name", ""),
        row.get("description", ""),
        detachment_name="Speedwaaagh!",
        stratagem_id=row.get("id", ""),
    )

    assert status in {"Implemented", "Supported"}
    assert canonical_name == "SPESHUL AMMO"
    notes_l = str(notes or "").lower()
    assert "anti-monster" in notes_l
    assert "anti-vehicle" in notes_l
    assert "non-torrent" in notes_l
