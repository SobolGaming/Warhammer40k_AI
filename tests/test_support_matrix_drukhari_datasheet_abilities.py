import os

import pytest


GROUP1_HARLEQUIN_CORSAIR_CASES = [
    ("Cegorach's Favour", "Troupe Master"),
    ("Channeller Stones", "Corsair Voidscarred"),
    ("Choreographer of War", "Troupe Master"),
    ("Cruel Amusement", "Death Jester"),
    ("Dance of Death", "Troupe"),
    ("Death is Not Enough", "Death Jester"),
    ("Fury of the Void (Psychic)", "Kharseth"),
    ("Hallucinogen Grenades", "Starfangs"),
    ("Piratical Raiders", "Corsair Voidscarred"),
    ("Prince of Corsairs", "Prince Yriel"),
    ("Raid and Run", "Corsair Skyreavers"),
    ("Treacherous Illusion (Psychic)", "Shadowseer"),
]

GROUP2_DRUKHARI_UTILITY_CASES = [
    ("Airborne Evasion", "Scourges with Heavy Weapons"),
    ("Murderous Crossfire", "Scourges with Shardcarbines"),
    ("Phantasm Grenade Launcher", "Kabalite Warriors"),
    ("Kabalite Icon", "Kabalite Warriors"),
    ("Stimm-needler", "Hand of the Archon"),
    ("Mind Like a Steel Trap (Aura)", "Lady Malys"),
]

GROUP3_DRUKHARI_BATCH_CASES = [
    ("Pain Adept", "Haemonculus"),
    ("Pain Engine (Aura)", "Cronos"),
    ("Torture Device", "Talos"),
    ("Fear Incarnate (Aura)", "Haemonculus"),
    ("Tormentors", "Incubi"),
    ("Torturer's Craft", "Wracks"),
    ("Incubi Shrine Token", "Incubi"),
]

GROUP4_DRUKHARI_GROUP1_CASES = [
    ("Devoted to Pain", "Talos"),
    ("Eradicate the Foe", "Ravager"),
    ("Onslaught", "Drazhar"),
    ("Shadowfield", "Archon"),
    ("Silent Executioner", "Drazhar"),
    ("Soul Trap", "Archon"),
    ("Thrilling Spectacle", "Lelith Hesperax"),
]

GROUP5_DRUKHARI_GROUP2_CASES = [
    ("Archon's Will", "Hand of the Archon"),
    ("Precognisant", "Lady Malys"),
    ("Vanguard of the Dark City", "Raider"),
    ("Masters of the Shadowed Sky", "Raider"),
    ("Speed of the Kill", "Raider"),
    ("Visions of Butchery", "Raider"),
    ("Void Mine", "Voidraven Bomber"),
]


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


def _find_drukhari_datasheet_ability_row(gsm, *, ability_name: str, unit_name: str) -> dict:
    rows = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets_abilities.json"))
    datasheets = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets.json"))
    datasheet_by_id = {str(row.get("id", "") or ""): row for row in datasheets}
    ability_norm = _norm_name(ability_name)
    unit_norm = _norm_name(unit_name)

    for row in rows:
        dsid = str(row.get("datasheet_id", "") or "")
        ds = datasheet_by_id.get(dsid)
        if not ds:
            continue
        if str(ds.get("faction_id", "") or "").strip().upper() != "DRU":
            continue
        if _norm_name(row.get("name", "")) != ability_norm:
            continue
        if _norm_name(ds.get("name", "")) != unit_norm:
            continue
        return row
    raise AssertionError(f"Could not find DRU datasheet ability row for {ability_name} on {unit_name}")


@pytest.mark.parametrize(("ability_name", "unit_name"), GROUP1_HARLEQUIN_CORSAIR_CASES)
def test_support_matrix_group1_drukhari_harlequin_corsair_abilities_supported(ability_name: str, unit_name: str):
    import scripts.generate_ability_support_matrix as gsm

    _seed_maps(gsm)
    row = _find_drukhari_datasheet_ability_row(gsm, ability_name=ability_name, unit_name=unit_name)
    status, _notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id="DRU",
        datasheet_id=row.get("datasheet_id", ""),
    )

    assert status == "Supported"


@pytest.mark.parametrize(("ability_name", "unit_name"), GROUP2_DRUKHARI_UTILITY_CASES)
def test_support_matrix_group2_drukhari_utility_abilities_supported(ability_name: str, unit_name: str):
    import scripts.generate_ability_support_matrix as gsm

    _seed_maps(gsm)
    row = _find_drukhari_datasheet_ability_row(gsm, ability_name=ability_name, unit_name=unit_name)
    status, _notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id="DRU",
        datasheet_id=row.get("datasheet_id", ""),
    )

    assert status == "Supported"


@pytest.mark.parametrize(("ability_name", "unit_name"), GROUP3_DRUKHARI_BATCH_CASES)
def test_support_matrix_group3_drukhari_batch_abilities_supported(ability_name: str, unit_name: str):
    import scripts.generate_ability_support_matrix as gsm

    _seed_maps(gsm)
    row = _find_drukhari_datasheet_ability_row(gsm, ability_name=ability_name, unit_name=unit_name)
    status, _notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id="DRU",
        datasheet_id=row.get("datasheet_id", ""),
    )

    assert status == "Supported"


@pytest.mark.parametrize(("ability_name", "unit_name"), GROUP4_DRUKHARI_GROUP1_CASES)
def test_support_matrix_group4_drukhari_group1_abilities_supported(ability_name: str, unit_name: str):
    import scripts.generate_ability_support_matrix as gsm

    _seed_maps(gsm)
    row = _find_drukhari_datasheet_ability_row(gsm, ability_name=ability_name, unit_name=unit_name)
    status, _notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id="DRU",
        datasheet_id=row.get("datasheet_id", ""),
    )

    assert status == "Supported"


@pytest.mark.parametrize(("ability_name", "unit_name"), GROUP5_DRUKHARI_GROUP2_CASES)
def test_support_matrix_group5_drukhari_group2_abilities_supported(ability_name: str, unit_name: str):
    import scripts.generate_ability_support_matrix as gsm

    _seed_maps(gsm)
    row = _find_drukhari_datasheet_ability_row(gsm, ability_name=ability_name, unit_name=unit_name)
    status, _notes = gsm._classify_ability(
        row.get("name", ""),
        row.get("description", ""),
        ability_id=row.get("id", ""),
        faction_id="DRU",
        datasheet_id=row.get("datasheet_id", ""),
    )

    assert status == "Supported"
