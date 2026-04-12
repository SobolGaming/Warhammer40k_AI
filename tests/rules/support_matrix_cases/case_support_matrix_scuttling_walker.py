import os


def test_support_matrix_classifies_shared_scuttling_walker_factions_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    gsm.DETACHMENT_ABILITY_IDS = {
        str(row.get("id", "") or "").strip()
        for row in detachment_abilities
        if str(row.get("id", "") or "").strip()
    }
    gsm._seed_ability_support_maps(abilities, detachment_abilities)

    datasheets = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets.json"))
    datasheet_faction_by_id = {
        str(row.get("id", "") or "").strip(): str(row.get("faction_id", "") or "").strip()
        for row in datasheets
    }
    datasheet_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets_abilities.json"))
    expected_factions = {"DG", "EC", "TS", "WE"}

    for faction_id in expected_factions:
        row = next(
            item
            for item in datasheet_abilities
            if str(item.get("name", "") or "").strip() == "Scuttling Walker"
            and datasheet_faction_by_id.get(str(item.get("datasheet_id", "") or "").strip()) == faction_id
        )
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("ability_id", ""),
            faction_id=faction_id,
            datasheet_id=str(row.get("datasheet_id", "") or "").strip(),
        )
        assert status == "Supported"
        assert "desperate escape" in str(notes or "").lower()
