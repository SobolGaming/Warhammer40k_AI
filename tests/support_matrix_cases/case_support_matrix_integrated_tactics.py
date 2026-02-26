import os


def _classify_detachment_ability(*, name: str, detachment: str):
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
        if str(item.get("name", "") or "").strip() == name
        and str(item.get("detachment", "") or "").strip() == detachment
    )
    return gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id=row.get("faction_id", ""),
    )


def test_integrated_tactics_detachment_ability_is_supported():
    status, notes = _classify_detachment_ability(
        name="Integrated Tactics",
        detachment="Brood Brother Auxilia",
    )
    assert status == "Supported"
    assert "overlapping fire" in notes.lower()


def test_brood_brothers_detachment_restriction_is_supported():
    status, notes = _classify_detachment_ability(
        name="BROOD BROTHERS",
        detachment="Brood Brother Auxilia",
    )
    assert status == "Supported"
    assert "warlord" in notes.lower()
