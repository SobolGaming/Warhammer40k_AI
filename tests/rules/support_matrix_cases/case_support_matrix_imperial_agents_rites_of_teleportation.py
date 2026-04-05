import os


def test_support_matrix_classifies_rites_of_teleportation_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    datasheets = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets.json"))
    datasheet_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets_abilities.json"))

    gsm.DETACHMENT_ABILITY_IDS = {
        str(row.get("id", "") or "").strip()
        for row in detachment_abilities
        if str(row.get("id", "") or "").strip()
    }
    gsm._seed_ability_support_maps(abilities, detachment_abilities)

    terminator_datasheet_id = str(
        next(
            row
            for row in datasheets
            if str(row.get("faction_id", "") or "").strip().upper() == "AOI"
            and str(row.get("name", "") or "").strip() == "Grey Knights Terminator Squad"
        ).get("id", "")
        or ""
    ).strip()
    assert terminator_datasheet_id

    row = next(
        item
        for item in datasheet_abilities
        if str(item.get("datasheet_id", "") or "").strip() == terminator_datasheet_id
        and str(item.get("name", "") or "").strip() == "Rites of Teleportation"
    )

    status, notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("ability_id", ""),
        faction_id="AOI",
    )

    assert status == "Supported"
    assert "inquisitor" in notes.lower()
    assert "deep strike" in notes.lower()
