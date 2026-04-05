import os


def _norm_name(value: str) -> str:
    return str(value or "").replace("\u2019", "'").strip().lower()


def _seed_maps(gsm) -> None:
    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    gsm.DETACHMENT_ABILITY_IDS = {
        str(row.get("id", "") or "").strip()
        for row in detachment_abilities
        if str(row.get("id", "") or "").strip()
    }
    gsm._seed_ability_support_maps(abilities, detachment_abilities)


def _find_tyranids_datasheet_ability_row(gsm, *, ability_name: str, unit_name: str) -> dict:
    rows = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets_abilities.json"))
    datasheets = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets.json"))
    datasheet_by_id = {str(row.get("id", "") or ""): row for row in datasheets}
    ability_norm = _norm_name(ability_name)
    unit_norm = _norm_name(unit_name)

    for row in rows:
        datasheet_id = str(row.get("datasheet_id", "") or "")
        datasheet = datasheet_by_id.get(datasheet_id)
        if not datasheet:
            continue
        if str(datasheet.get("faction_id", "") or "").strip().upper() != "TYR":
            continue
        if _norm_name(row.get("name", "")) != ability_norm:
            continue
        if _norm_name(datasheet.get("name", "")) != unit_norm:
            continue
        return row
    raise AssertionError(f"Could not find TYR datasheet ability row for {ability_name} on {unit_name}")


def test_support_matrix_tyranids_seed_spore_mines_supported():
    import scripts.generate_ability_support_matrix as gsm

    _seed_maps(gsm)
    row = _find_tyranids_datasheet_ability_row(
        gsm,
        ability_name="Seed Spore Mines",
        unit_name="Biovores",
    )
    status, _notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id="TYR",
        datasheet_id=row.get("datasheet_id", ""),
    )
    assert status == "Supported"
