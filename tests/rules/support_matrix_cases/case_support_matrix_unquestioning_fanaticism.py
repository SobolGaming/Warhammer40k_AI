import os


def test_unquestioning_fanaticism_detachment_ability_is_supported():
    import scripts.generate_ability_support_matrix as gsm

    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    gsm.DETACHMENT_ABILITY_IDS = {
        str(row.get("id", "") or "").strip()
        for row in detachment_abilities
        if str(row.get("id", "") or "").strip()
    }
    gsm._seed_ability_support_maps(abilities, detachment_abilities)

    row = next(
        item
        for item in detachment_abilities
        if str(item.get("name", "") or "").strip() == "Unquestioning Fanaticism"
        and str(item.get("detachment", "") or "").strip() == "Xenocreed Congregation"
    )

    status, notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id=row.get("faction_id", ""),
    )

    assert status == "Supported"
    assert "feel no pain" in notes.lower()
