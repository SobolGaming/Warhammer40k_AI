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
    return gsm


def test_gc_manticore_furious_barrage_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Furious Barrage",
        (
            "In your Shooting phase, after this model has shot, select one enemy unit (excluding MONSTERS and "
            "VEHICLES) that was hit by one or more of those attacks made with this model's storm eagle rockets. "
            "Until the start of your next Shooting phase, that enemy unit is staggered. While a unit is staggered, "
            "subtract 1 from the Objective Control characteristic of models in that unit (to a minimum of 1)."
        ),
        ability_id="",
        faction_id="GC",
        datasheet_id="000003986",
    )
    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "storm eagle rockets" in lowered
    assert "objective control" in lowered
