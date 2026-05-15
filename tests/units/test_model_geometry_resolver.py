import json
import logging
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from warhammer40k_ai.utility.aura_utils import distance_between_bases_3d, horizontal_distance_between_bases_2d
from warhammer40k_ai.utility.calcs import convert_mm_to_inches
from warhammer40k_ai.utility.model_base import Base, BaseType, clone_base
from warhammer40k_ai.utility.model_geometry import resolve_model_geometry


_REPO_ROOT = Path(__file__).resolve().parents[2]
_OUT_OF_SCOPE_SOURCE_TOKENS = (
    "warhammer legends",
    "legends:",
    "forge world",
    "boarding actions",
    "kill team",
    "crusade",
    "adeptus titanicus",
)


def _load_wahapedia_json(filename: str) -> list[dict]:
    return json.loads((_REPO_ROOT / "wahapedia_data" / filename).read_text(encoding="utf-8"))


def _parse_flying_base_size(base_size: str) -> tuple[BaseType, tuple[float, float]]:
    match = re.match(
        r"^\s*(?P<major>\d+(?:\.\d+)?)\s*(?:x\s*(?P<minor>\d+(?:\.\d+)?))?\s*mm\s+flying\s+base\b",
        base_size,
        flags=re.IGNORECASE,
    )
    if not match:
        raise AssertionError(f"Unexpected flying base size: {base_size!r}")
    major_mm = float(match.group("major"))
    minor_mm = match.group("minor")
    if minor_mm is None:
        radius = convert_mm_to_inches(major_mm / 2.0)
        return BaseType.CIRCULAR, (radius, radius)
    return BaseType.ELLIPTICAL, (
        convert_mm_to_inches(major_mm / 2.0),
        convert_mm_to_inches(float(minor_mm) / 2.0),
    )


def test_resolve_khorne_lord_of_skulls_hull_override():
    resolved = resolve_model_geometry(
        datasheet_id="000002642",
        datasheet_name="Khorne Lord of Skulls",
        model_name="Khorne Lord of Skulls",
        unit_keywords=["Vehicle", "Monster", "Chaos"],
        parsed_base_type=BaseType.HULL,
        parsed_radius=(1.0, 1.0),
    )
    assert resolved.base_type == BaseType.HULL
    assert resolved.radius[0] == pytest.approx(convert_mm_to_inches(190.5) / 2.0, abs=1e-4)
    assert resolved.radius[1] == pytest.approx(convert_mm_to_inches(127.0) / 2.0, abs=1e-4)
    assert resolved.model_height == pytest.approx(convert_mm_to_inches(178.0), abs=1e-4)
    assert resolved.geometry_source == "geometry_override:khorne_lord_of_skulls"
    assert resolved.height_source == "override"


def test_resolve_drop_pod_uses_manual_hull_override():
    resolved = resolve_model_geometry(
        datasheet_id="000000087",
        datasheet_name="Drop Pod",
        model_name="Drop Pod",
        unit_keywords=["Vehicle", "Transport"],
        parsed_base_type=BaseType.HULL,
        parsed_radius=(1.0, 1.0),
    )
    assert resolved.base_type == BaseType.HULL
    assert resolved.radius[0] == pytest.approx(convert_mm_to_inches(80.0) / 2.0, abs=1e-4)
    assert resolved.radius[1] == pytest.approx(convert_mm_to_inches(40.0) / 2.0, abs=1e-4)
    assert resolved.geometry_source == "geometry_override:drop_pod"


@pytest.mark.parametrize(
    "datasheet_id,datasheet_name,model_name,expected_key,length_mm,width_mm,height_mm",
    [
        ("000002640", "Chaos Rhino", "Chaos Rhino", "rhino_chassis", 115.0, 75.0, 50.0),
        ("000004093", "Chaos Rhino", "Chaos Rhino", "rhino_chassis", 115.0, 75.0, 50.0),
        ("000002634", "Chaos Land Raider", "Chaos Land Raider", "land_raider_hull", 170.0, 100.0, 70.0),
        ("000004082", "Chaos Land Raider", "Chaos Land Raider", "land_raider_hull", 170.0, 100.0, 70.0),
        ("000000884", "Venerable Land Raider", "Venerable Land Raider", "land_raider_hull", 170.0, 100.0, 70.0),
        ("000000393", "Land Raider Redeemer", "Land Raider Redeemer", "land_raider_hull", 170.0, 100.0, 70.0),
        ("000000912", "Exorcist", "Exorcist", "exorcist_hull", 140.0, 92.0, 130.0),
        ("000002484", "Castigator", "Castigator", "castigator_hull", 140.0, 100.0, 84.0),
        ("000003819", "Sisters of Battle Immolator", "Immolator", "immolator_hull", 140.0, 92.0, 115.0),
        ("000002714", "Predator Annihilator", "Predator Annihilator", "predator_hull", 120.0, 80.0, 80.0),
        ("000002637", "Chaos Predator Annihilator", "Chaos Predator Annihilator", "predator_hull", 120.0, 80.0, 80.0),
        ("000002636", "Chaos Predator Destructor", "Chaos Predator Destructor", "predator_hull", 120.0, 80.0, 80.0),
        ("000001027", "Chaos Vindicator", "Chaos Vindicator", "vindicator_hull", 140.0, 90.0, 60.0),
        ("000001651", "Skorpius Disintegrator", "Skorpius Disintegrator", "skorpius_hull", 120.0, 80.0, 70.0),
        ("000001376", "Plagueburst Crawler", "Plagueburst Crawler", "plagueburst_crawler_hull", 152.0, 102.0, 64.0),
        ("000000694", "Hellhound", "Hellhound", "hydra_chimera_hull", 117.0, 92.0, 110.0),
        ("000003980", "Leman Russ Demolisher", "Leman Russ Demolisher", "leman_russ_hull", 120.0, 105.0, 75.0),
        ("000003989", "Shadowsword", "Shadowsword", "baneblade_hull", 240.0, 180.0, 110.0),
        ("000000129", "Razorback", "Razorback", "rhino_chassis", 115.0, 75.0, 50.0),
    ],
)
def test_resolve_chaos_transport_hull_overrides(
    datasheet_id,
    datasheet_name,
    model_name,
    expected_key,
    length_mm,
    width_mm,
    height_mm,
):
    resolved = resolve_model_geometry(
        datasheet_id=datasheet_id,
        datasheet_name=datasheet_name,
        model_name=model_name,
        unit_keywords=["Vehicle", "Transport", "Chaos"],
        parsed_base_type=BaseType.HULL,
        parsed_radius=(1.0, 1.0),
    )
    assert resolved.base_type == BaseType.HULL
    assert resolved.radius[0] == pytest.approx(convert_mm_to_inches(length_mm) / 2.0, abs=1e-4)
    assert resolved.radius[1] == pytest.approx(convert_mm_to_inches(width_mm) / 2.0, abs=1e-4)
    assert resolved.model_height == pytest.approx(convert_mm_to_inches(height_mm), abs=1e-4)
    assert resolved.geometry_source == f"geometry_override:{expected_key}"
    assert resolved.height_source == "override"


@pytest.mark.parametrize(
    "datasheet_id,datasheet_name,expected_key,length_mm,width_mm,height_mm",
    [
        ("000000521", "Goliath Rockgrinder", "goliath_rockgrinder_hull", 135.0, 70.0, 65.0),
        ("000000516", "Goliath Truck", "goliath_truck_hull", 135.0, 70.0, 65.0),
        ("000000702", "Baneblade", "baneblade_hull", 240.0, 180.0, 110.0),
        ("000003963", "Baneblade", "baneblade_hull", 240.0, 180.0, 110.0),
        ("000000704", "Banesword", "baneblade_hull", 240.0, 180.0, 110.0),
        ("000000708", "Stormlord", "baneblade_hull", 240.0, 180.0, 110.0),
        ("000000709", "Stormsword", "baneblade_hull", 240.0, 180.0, 110.0),
        ("000003965", "Banesword", "baneblade_hull", 240.0, 180.0, 110.0),
        ("000003990", "Stormlord", "baneblade_hull", 240.0, 180.0, 110.0),
        ("000003991", "Stormsword", "baneblade_hull", 240.0, 180.0, 110.0),
        ("000002745", "Leman Russ Vanquisher", "leman_russ_hull", 120.0, 105.0, 75.0),
        ("000003985", "Leman Russ Vanquisher", "leman_russ_hull", 120.0, 105.0, 75.0),
        ("000000680", "Leman Russ Commander", "leman_russ_hull", 120.0, 105.0, 75.0),
        ("000000700", "Leman Russ Battle Tank", "leman_russ_hull", 120.0, 105.0, 75.0),
        ("000003942", "Leman Russ Commander", "leman_russ_hull", 120.0, 105.0, 75.0),
        ("000003979", "Leman Russ Battle Tank", "leman_russ_hull", 120.0, 105.0, 75.0),
        ("000002617", "Rogal Dorn Battle Tank", "rogal_dorn_hull", 148.0, 127.0, 84.0),
        ("000003892", "Rogal Dorn Commander", "rogal_dorn_hull", 148.0, 127.0, 84.0),
        ("000003944", "Rogal Dorn Commander", "rogal_dorn_hull", 148.0, 127.0, 84.0),
        ("000003987", "Rogal Dorn Battle Tank", "rogal_dorn_hull", 148.0, 127.0, 84.0),
        ("000000696", "Hydra", "hydra_chimera_hull", 117.0, 92.0, 110.0),
        ("000003975", "Hydra", "hydra_chimera_hull", 117.0, 92.0, 110.0),
        ("000000697", "Wyvern", "hydra_chimera_hull", 117.0, 92.0, 110.0),
        ("000003992", "Wyvern", "hydra_chimera_hull", 117.0, 92.0, 110.0),
        ("000002604", "Hekaton Land Fortress", "hekaton_land_fortress_hull", 170.0, 105.0, 110.0),
        ("000002602", "Sagitaur", "sagitaur_hull", 105.0, 68.0, 70.0),
    ],
)
def test_resolve_manual_vehicle_hull_overrides_from_recent_headless_warnings(
    datasheet_id,
    datasheet_name,
    expected_key,
    length_mm,
    width_mm,
    height_mm,
):
    resolved = resolve_model_geometry(
        datasheet_id=datasheet_id,
        datasheet_name=datasheet_name,
        model_name=datasheet_name,
        unit_keywords=["Vehicle"],
        parsed_base_type=BaseType.HULL,
        parsed_radius=(convert_mm_to_inches(80.0) / 2.0, convert_mm_to_inches(40.0) / 2.0),
    )
    assert resolved.base_type == BaseType.HULL
    assert resolved.radius[0] == pytest.approx(convert_mm_to_inches(length_mm) / 2.0, abs=1e-4)
    assert resolved.radius[1] == pytest.approx(convert_mm_to_inches(width_mm) / 2.0, abs=1e-4)
    assert resolved.model_height == pytest.approx(convert_mm_to_inches(height_mm), abs=1e-4)
    assert resolved.geometry_source == f"geometry_override:{expected_key}"
    assert resolved.height_source == "override"


@pytest.mark.parametrize(
    "datasheet_id,datasheet_name,model_name,expected_key,length_mm,width_mm,height_mm",
    [
        ("000000038", "Mek Gunz", "Mek Gunz", "mek_gunz_hull", 100.0, 52.0, 60.0),
        ("000000039", "Battlewagon", "Battlewagon", "battlewagon_hull", 165.0, 76.0, 127.0),
        ("000000097", "Hammerfall Bunker", "Hammerfall Bunker", "hammerfall_bunker_hull", 110.0, 110.0, 97.0),
        ("000000437", "Tidewall Gunrig", "Tidewall Gunrig", "tidewall_hull", 150.0, 105.0, 60.0),
        ("000000533", "Catacomb Command Barge", "Catacomb Command Barge", "necron_barge_hull", 127.0, 76.0, 76.0),
        ("000000540", "Triarch Stalker", "Triarch Stalker", "triarch_stalker_hull", 165.0, 120.0, 110.0),
        ("000000553", "Annihilation Barge", "Annihilation Barge", "necron_barge_hull", 127.0, 76.0, 76.0),
        ("000000693", "Taurox", "Taurox", "taurox_hull", 105.0, 70.0, 75.0),
        ("000001470", "Feculent Gnarlmaw", "Feculent Gnarlmaw", "feculent_gnarlmaw_hull", 121.0, 95.0, 114.0),
        ("000001587", "Noctilith Crown", "Noctilith Crown", "noctilith_crown_hull", 220.0, 100.0, 190.0),
        ("000001588", "Skull Altar", "Skull Altar", "skull_altar_hull", 135.0, 127.0, 165.0),
        (
            "000002361",
            "Convergence Of Dominion",
            "Convergence Of Dominion Starstele",
            "convergence_of_dominion_hull",
            70.0,
            38.0,
            108.0,
        ),
        ("000002462", "Miasmic Malignifier", "Miasmic Malignifier", "miasmic_malignifier_hull", 229.0, 51.0, 203.0),
        ("000002499", "Big'ed Bossbunka", "Big'ed Bossbunka", "big_ed_bossbunka_hull", 190.0, 150.0, 200.0),
        ("000002712", "Outrider Squad", "INVADER ATV", "invader_atv_hull", 95.0, 70.0, 60.0),
        ("000003952", "Taurox", "Taurox", "taurox_hull", 105.0, 70.0, 75.0),
    ],
)
def test_resolve_in_scope_use_model_hull_overrides(
    datasheet_id,
    datasheet_name,
    model_name,
    expected_key,
    length_mm,
    width_mm,
    height_mm,
):
    resolved = resolve_model_geometry(
        datasheet_id=datasheet_id,
        datasheet_name=datasheet_name,
        model_name=model_name,
        unit_keywords=["Vehicle", "Fortification"],
        parsed_base_type=BaseType.HULL,
        parsed_radius=(convert_mm_to_inches(80.0) / 2.0, convert_mm_to_inches(40.0) / 2.0),
    )
    assert resolved.base_type == BaseType.HULL
    assert resolved.radius[0] == pytest.approx(convert_mm_to_inches(length_mm) / 2.0, abs=1e-4)
    assert resolved.radius[1] == pytest.approx(convert_mm_to_inches(width_mm) / 2.0, abs=1e-4)
    assert resolved.model_height == pytest.approx(convert_mm_to_inches(height_mm), abs=1e-4)
    assert resolved.geometry_source == f"geometry_override:{expected_key}"
    assert resolved.height_source == "override"


def test_outrider_squad_atv_override_does_not_apply_to_outrider_bikes():
    parsed_radius = (
        convert_mm_to_inches(90.0) / 2.0,
        convert_mm_to_inches(52.0) / 2.0,
    )
    resolved = resolve_model_geometry(
        datasheet_id="000002712",
        datasheet_name="Outrider Squad",
        model_name="OUTRIDER",
        unit_keywords=["Mounted", "Grenades", "Imperium", "Tacticus"],
        parsed_base_type=BaseType.ELLIPTICAL,
        parsed_radius=parsed_radius,
    )

    assert resolved.geometry_source == "parsed_base"
    assert resolved.base_type == BaseType.ELLIPTICAL
    assert resolved.radius[0] == pytest.approx(parsed_radius[0], abs=1e-4)
    assert resolved.radius[1] == pytest.approx(parsed_radius[1], abs=1e-4)
    assert not resolved.compound_parts


def test_resolve_aegis_compound_override():
    resolved = resolve_model_geometry(
        datasheet_id="000002619",
        datasheet_name="Aegis Defence Line",
        model_name="Aegis Defence Line",
        unit_keywords=["Fortification", "Vehicle"],
        parsed_base_type=BaseType.HULL,
        parsed_radius=(1.0, 1.0),
    )
    assert resolved.base_type == BaseType.HULL
    assert resolved.compound_parts
    assert len(resolved.compound_parts) >= 2
    assert resolved.model_height == pytest.approx(convert_mm_to_inches(50.0), abs=1e-4)
    assert resolved.geometry_source == "geometry_override:aegis_defence_line"


def test_resolve_uses_keyword_height_heuristic_when_no_override():
    base_radius = convert_mm_to_inches(32.0 / 2.0)
    resolved = resolve_model_geometry(
        datasheet_id="test_no_override",
        datasheet_name="Test Infantry Unit",
        model_name="Test Infantry Unit",
        unit_keywords=["Infantry", "Character"],
        parsed_base_type=BaseType.CIRCULAR,
        parsed_radius=(base_radius, base_radius),
    )
    expected_height = (base_radius * 2.0) * 1.4
    assert resolved.model_height == pytest.approx(expected_height, abs=1e-4)
    assert resolved.height_source == "keyword:infantry_or_character"


@pytest.mark.parametrize(
    "radius_mm, expected_z_offset_mm",
    [
        ((32.0 / 2.0, 32.0 / 2.0), 20.0),
        ((60.0 / 2.0, 60.0 / 2.0), 32.0),
        ((120.0 / 2.0, 92.0 / 2.0), 45.0),
        ((170.0 / 2.0, 109.0 / 2.0), 55.0),
    ],
)
def test_resolve_applies_flying_base_size_z_offset(radius_mm, expected_z_offset_mm):
    parsed_radius = (
        convert_mm_to_inches(float(radius_mm[0])),
        convert_mm_to_inches(float(radius_mm[1])),
    )
    resolved = resolve_model_geometry(
        datasheet_id="test_flying_base",
        datasheet_name="Test Flying Base",
        model_name="Test Flying Base",
        unit_keywords=["Vehicle"],
        parsed_base_type=BaseType.ELLIPTICAL,
        parsed_radius=parsed_radius,
        parsed_is_flying_base=True,
    )
    assert resolved.z_offset == pytest.approx(convert_mm_to_inches(expected_z_offset_mm), abs=1e-4)


def test_resolve_flying_base_z_offset_uses_parsed_support_base_when_override_changes_footprint(tmp_path):
    overrides = {
        "schema_version": "5.3",
        "units": {
            "test_vehicle": {
                "type": "hull",
                "length_mm": 190.5,
                "width_mm": 139.7,
                "height_mm": 88.9,
            }
        },
    }
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps(overrides), encoding="utf-8")

    parsed_radius = (convert_mm_to_inches(60.0 / 2.0), convert_mm_to_inches(60.0 / 2.0))
    resolved = resolve_model_geometry(
        datasheet_id="test_vehicle",
        datasheet_name="Test Vehicle",
        model_name="Test Vehicle",
        unit_keywords=["Vehicle"],
        parsed_base_type=BaseType.CIRCULAR,
        parsed_radius=parsed_radius,
        parsed_is_flying_base=True,
        catalog_path=str(path),
    )
    assert resolved.z_offset == pytest.approx(convert_mm_to_inches(32.0), abs=1e-4)


def test_resolve_flying_hull_override_expands_to_support_base_and_hull_proxy(tmp_path):
    overrides = {
        "schema_version": "5.3",
        "units": {
            "test_aircraft": {
                "type": "flying_hull",
                "support_base": {
                    "shape": "ellipse",
                    "major_mm": 120.0,
                    "minor_mm": 92.0,
                },
                "length_mm": 200.0,
                "width_mm": 80.0,
                "height_mm": 70.0,
            }
        },
        "aliases": {"test_aircraft_datasheet": "test_aircraft"},
    }
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps(overrides), encoding="utf-8")

    parsed_radius = (convert_mm_to_inches(60.0 / 2.0), convert_mm_to_inches(60.0 / 2.0))
    resolved = resolve_model_geometry(
        datasheet_id="test_aircraft_datasheet",
        datasheet_name="Test Aircraft",
        model_name="Test Aircraft",
        unit_keywords=["Vehicle", "Aircraft"],
        parsed_base_type=BaseType.CIRCULAR,
        parsed_radius=parsed_radius,
        parsed_is_flying_base=True,
        catalog_path=str(path),
    )

    assert resolved.geometry_source == "geometry_override:test_aircraft"
    assert resolved.base_type == BaseType.HULL
    assert resolved.radius[0] == pytest.approx(convert_mm_to_inches(200.0) / 2.0, abs=1e-4)
    assert resolved.radius[1] == pytest.approx(convert_mm_to_inches(92.0) / 2.0, abs=1e-4)
    assert resolved.model_height == pytest.approx(convert_mm_to_inches(70.0), abs=1e-4)
    assert resolved.height_source == "override"
    assert resolved.z_offset == pytest.approx(convert_mm_to_inches(32.0), abs=1e-4)

    support = resolved.compound_parts[0]
    hull = resolved.compound_parts[1]
    assert support["part_id"] == "support_base"
    assert support["shape"] == "ellipse"
    assert support["radius"][0] == pytest.approx(convert_mm_to_inches(120.0) / 2.0, abs=1e-4)
    assert support["radius"][1] == pytest.approx(convert_mm_to_inches(92.0) / 2.0, abs=1e-4)
    assert hull["part_id"] == "hull_proxy"
    assert hull["shape"] == "hull"
    assert hull["radius"][0] == pytest.approx(convert_mm_to_inches(200.0) / 2.0, abs=1e-4)
    assert hull["radius"][1] == pytest.approx(convert_mm_to_inches(80.0) / 2.0, abs=1e-4)


def test_resolve_auto_compound_for_flying_vehicle_without_override():
    parsed_radius = (convert_mm_to_inches(60.0 / 2.0), convert_mm_to_inches(60.0 / 2.0))
    resolved = resolve_model_geometry(
        datasheet_id="test_auto_flying_vehicle",
        datasheet_name="Test Auto Flying Vehicle",
        model_name="Test Auto Flying Vehicle",
        unit_keywords=["Vehicle"],
        parsed_base_type=BaseType.CIRCULAR,
        parsed_radius=parsed_radius,
        parsed_is_flying_base=True,
    )
    assert resolved.geometry_source == "auto_flying_vehicle_compound"
    assert resolved.base_type == BaseType.HULL
    assert len(resolved.compound_parts) == 2
    support = resolved.compound_parts[0]
    hull = resolved.compound_parts[1]
    assert support["part_id"] == "support_base"
    assert support["shape"] == "circle"
    assert hull["part_id"] == "hull_proxy"
    assert hull["shape"] == "hull"
    assert hull["radius"][0] > support["radius"][0]
    assert hull["radius"][1] > support["radius"][1]


def test_resolve_flying_non_vehicle_keeps_parsed_geometry():
    parsed_radius = (convert_mm_to_inches(60.0 / 2.0), convert_mm_to_inches(60.0 / 2.0))
    resolved = resolve_model_geometry(
        datasheet_id="test_flying_non_vehicle",
        datasheet_name="Test Flying Non Vehicle",
        model_name="Test Flying Non Vehicle",
        unit_keywords=["Infantry"],
        parsed_base_type=BaseType.CIRCULAR,
        parsed_radius=parsed_radius,
        parsed_is_flying_base=True,
    )
    assert resolved.geometry_source == "parsed_base"
    assert resolved.base_type == BaseType.CIRCULAR
    assert not resolved.compound_parts


def test_all_in_scope_flying_base_datasheets_have_explicit_geometry_overrides():
    datasheets = {row["id"]: row for row in _load_wahapedia_json("Datasheets.json")}
    sources = {row["id"]: row["name"].lower() for row in _load_wahapedia_json("Source.json")}
    keywords_by_datasheet: dict[str, list[str]] = {}
    for row in _load_wahapedia_json("Datasheets_keywords.json"):
        keywords_by_datasheet.setdefault(row["datasheet_id"], []).append(row["keyword"])

    rows = []
    for model_row in _load_wahapedia_json("Datasheets_models.json"):
        base_size = str(model_row.get("base_size", ""))
        if " flying base" not in base_size.lower():
            continue
        datasheet = datasheets[model_row["datasheet_id"]]
        source_name = sources.get(datasheet.get("source_id", ""), "")
        if any(token in source_name for token in _OUT_OF_SCOPE_SOURCE_TOKENS):
            continue
        rows.append((datasheet, model_row))
    rows.sort(key=lambda item: (item[0]["id"], item[1]["line"], item[1]["name"]))

    assert len(rows) == 72
    missing = []
    for datasheet, model_row in rows:
        parsed_base_type, parsed_radius = _parse_flying_base_size(str(model_row["base_size"]))
        resolved = resolve_model_geometry(
            datasheet_id=datasheet["id"],
            datasheet_name=datasheet["name"],
            model_name=model_row["name"],
            unit_keywords=keywords_by_datasheet.get(datasheet["id"], []),
            parsed_base_type=parsed_base_type,
            parsed_radius=parsed_radius,
            parsed_is_flying_base=True,
        )
        if not resolved.geometry_source.startswith("geometry_override:"):
            missing.append((datasheet["id"], datasheet["name"], model_row["name"], resolved.geometry_source))
            continue

        parts = {part["part_id"]: part for part in resolved.compound_parts}
        assert {"support_base", "hull_proxy"}.issubset(parts), (datasheet["id"], datasheet["name"])
        support = parts["support_base"]
        assert support["radius"][0] == pytest.approx(parsed_radius[0], abs=1e-4)
        assert support["radius"][1] == pytest.approx(parsed_radius[1], abs=1e-4)
        assert support["shape"] in {"circle", "ellipse"}
        if parsed_base_type == BaseType.CIRCULAR:
            assert support["shape"] == "circle"
        else:
            assert support["shape"] == "ellipse"
        assert parts["hull_proxy"]["shape"] == "hull"
        assert resolved.base_type == BaseType.HULL
        assert resolved.height_source == "override"
        assert resolved.model_height > 0.0
        assert resolved.z_offset > 0.0

    assert missing == []


def test_resolve_wave_serpent_compound_override_uses_base_or_hull_footprint():
    parsed_radius = (convert_mm_to_inches(60.0 / 2.0), convert_mm_to_inches(60.0 / 2.0))
    resolved = resolve_model_geometry(
        datasheet_id="000000599",
        datasheet_name="Wave Serpent",
        model_name="Wave Serpent",
        unit_keywords=["Vehicle", "Transport", "Aeldari"],
        parsed_base_type=BaseType.CIRCULAR,
        parsed_radius=parsed_radius,
        parsed_is_flying_base=True,
    )
    assert resolved.geometry_source == "geometry_override:wave_serpent"
    assert resolved.base_type == BaseType.HULL
    assert len(resolved.compound_parts) == 2
    assert resolved.z_offset == pytest.approx(convert_mm_to_inches(32.0), abs=1e-4)

    wave_base = Base(resolved.base_type, resolved.radius)
    wave_base.set_compound_parts(resolved.compound_parts)
    plain_base = Base(BaseType.CIRCULAR, convert_mm_to_inches(60.0 / 2.0))
    probe = Base(BaseType.CIRCULAR, 0.1)
    probe.set_position(convert_mm_to_inches(80.0), 0.0, 0.0)

    wave_distance = horizontal_distance_between_bases_2d(wave_base, probe)
    plain_distance = horizontal_distance_between_bases_2d(plain_base, probe)
    assert wave_distance < plain_distance
    assert wave_distance == pytest.approx(0.0, abs=1e-6)


def test_resolve_heldrake_uses_complete_footprint_bounding_rectangle():
    parsed_radius = _parse_flying_base_size("120 x 92mm flying base")[1]
    resolved = resolve_model_geometry(
        datasheet_id="000000961",
        datasheet_name="Heldrake",
        model_name="Heldrake",
        unit_keywords=["Vehicle", "Aircraft", "Chaos"],
        parsed_base_type=BaseType.ELLIPTICAL,
        parsed_radius=parsed_radius,
        parsed_is_flying_base=True,
    )

    assert resolved.geometry_source == "geometry_override:heldrake_hull"
    assert resolved.base_type == BaseType.HULL
    assert len(resolved.compound_parts) == 2
    parts = {part["part_id"]: part for part in resolved.compound_parts}
    support = parts["support_base"]
    hull = parts["hull_proxy"]
    assert support["shape"] == "ellipse"
    assert support["radius"][0] == pytest.approx(convert_mm_to_inches(120.0) / 2.0, abs=1e-4)
    assert support["radius"][1] == pytest.approx(convert_mm_to_inches(92.0) / 2.0, abs=1e-4)
    assert hull["shape"] == "hull"
    assert hull["radius"][0] == pytest.approx(5.0, abs=1e-4)
    assert hull["radius"][1] == pytest.approx(3.75, abs=1e-4)
    assert resolved.radius[0] == pytest.approx(5.0, abs=1e-4)
    assert resolved.radius[1] == pytest.approx(3.75, abs=1e-4)


def test_clone_base_preserves_compound_geometry():
    compound = Base(BaseType.HULL, (0.5, 0.5))
    compound.set_compound_parts(
        [
            {"part_id": "left", "shape": "circle", "radius": (0.5, 0.5), "offset": (-2.0, 0.0), "facing": 0.0},
            {"part_id": "right", "shape": "circle", "radius": (0.5, 0.5), "offset": (2.0, 0.0), "facing": 0.0},
        ]
    )
    other = Base(BaseType.CIRCULAR, 0.5)
    other.set_position(3.3, 0.0, 0.0)

    before = float(horizontal_distance_between_bases_2d(compound, other))
    assert before == pytest.approx(0.3, abs=1e-4)

    cloned = clone_base(compound)
    assert cloned.has_compound_parts()
    after = float(horizontal_distance_between_bases_2d(cloned, other))
    assert after == pytest.approx(before, abs=1e-4)


def test_non_circular_base_distance_reuses_exact_shape_distance_cache(monkeypatch):
    from warhammer40k_ai.utility import aura_utils

    aura_utils._BASE_SHAPE_DISTANCE_2D_CACHE.clear()
    first = Base(BaseType.ELLIPTICAL, (2.0, 1.0))
    second = Base(BaseType.HULL, (1.5, 0.75))
    first.set_position(0.0, 0.0, 0.0)
    second.set_position(4.0, 0.0, 0.0)

    original = Base.get_base_shape
    call_count = {"shape": 0}

    def _counted_get_base_shape(self):
        call_count["shape"] += 1
        return original(self)

    monkeypatch.setattr(Base, "get_base_shape", _counted_get_base_shape)

    before = float(distance_between_bases_3d(first, second))
    first_count = int(call_count["shape"])
    assert first_count > 0

    assert float(distance_between_bases_3d(first, second)) == pytest.approx(before, abs=1e-9)
    assert int(call_count["shape"]) == first_count

    second.set_position(5.0, 0.0, 0.0)
    assert float(distance_between_bases_3d(first, second)) > before
    assert int(call_count["shape"]) > first_count


def test_resolve_requires_manual_geometry_for_hull_when_guide_marks_required(tmp_path):
    overrides = {
        "schema_version": "5.3",
        "units": {},
        "base_size_guide": {
            "units": {
                "test_manual_hull": {
                    "classification": "hull",
                    "requires_manual_geometry": True,
                }
            }
        },
    }
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps(overrides), encoding="utf-8")

    with pytest.raises(ValueError, match="Missing model geometry override"):
        resolve_model_geometry(
            datasheet_id="test_manual_hull",
            datasheet_name="Manual Hull",
            model_name="Manual Hull",
            unit_keywords=["Vehicle"],
            parsed_base_type=BaseType.HULL,
            parsed_radius=(1.0, 1.0),
            catalog_path=str(path),
        )


def test_unit_model_build_uses_geometry_override_for_lord_of_skulls():
    from warhammer40k_ai.units.unit import Unit

    unit = Unit.__new__(Unit)
    unit.name = "Khorne Lord of Skulls"
    unit.keywords = ["Vehicle", "Monster"]
    unit.faction_keywords = []

    profile = {
        "name": "Khorne Lord of Skulls",
        "M": '10"',
        "T": "13",
        "Sv": "2+",
        "inv_sv": "-",
        "inv_sv_descr": "",
        "W": "24",
        "Ld": "7+",
        "OC": "8",
        "base_size": "Use model",
        "base_size_descr": "",
    }
    datasheet = SimpleNamespace(
        id="000002642",
        name="Khorne Lord of Skulls",
        datasheets_models=[profile],
        keywords=["Vehicle", "Monster"],
        faction_keywords=[],
    )

    model = unit._build_model_from_profile(datasheet, "Khorne Lord of Skulls", profile)

    assert model.model_base.base_type == BaseType.HULL
    assert model.model_base.radius[0] == pytest.approx(convert_mm_to_inches(190.5) / 2.0, abs=1e-4)
    assert model.model_base.radius[1] == pytest.approx(convert_mm_to_inches(127.0) / 2.0, abs=1e-4)
    assert model.model_base.model_height == pytest.approx(convert_mm_to_inches(178.0), abs=1e-4)


def test_create_models_preserves_lord_of_skulls_name_and_suppresses_fallback_warning(caplog):
    from warhammer40k_ai.units.unit import Unit

    unit = Unit.__new__(Unit)
    unit.name = "Khorne Lord of Skulls"
    unit.keywords = ["Vehicle", "Monster"]
    unit.faction_keywords = []
    unit.unit_composition = {"Khorne Lord of Skulls": (1, 1)}
    unit.unit_composition_options = []
    unit.unit_models_maximum = None

    profile = {
        "name": "Khorne Lord of Skulls",
        "M": '10"',
        "T": "13",
        "Sv": "2+",
        "inv_sv": "-",
        "inv_sv_descr": "",
        "W": "24",
        "Ld": "7+",
        "OC": "8",
        "base_size": "Use model",
        "base_size_descr": "",
    }
    datasheet = SimpleNamespace(
        id="000002642",
        name="Khorne Lord of Skulls",
        datasheets_models=[profile],
        keywords=["Vehicle", "Monster"],
        faction_keywords=[],
    )

    caplog.set_level(logging.WARNING, logger="warhammer40k_ai.units.unit_mixins.datasheet_wargear_mixin")
    models = unit._create_models(datasheet, quantity=1)

    assert [model.name for model in models] == ["Khorne Lord of Skulls"]
    assert models[0].model_base.base_type == BaseType.HULL
    assert models[0].model_base.radius[0] == pytest.approx(convert_mm_to_inches(190.5) / 2.0, abs=1e-4)
    assert "base size for 'Khorne Lord of Skulls' is unspecified" not in caplog.text
    assert "base size for 'Khorne Lord of Skull' is unspecified" not in caplog.text


def test_unit_model_build_rejects_unknown_base_without_override(caplog):
    from warhammer40k_ai.units.unit import Unit

    unit = Unit.__new__(Unit)
    unit.name = "Test Tank"
    unit.keywords = ["Vehicle"]
    unit.faction_keywords = []

    profile = {
        "name": "Test Tank",
        "M": '10"',
        "T": "10",
        "Sv": "3+",
        "inv_sv": "-",
        "inv_sv_descr": "",
        "W": "12",
        "Ld": "7+",
        "OC": "3",
        "base_size": "Use model",
        "base_size_descr": "",
    }
    datasheet = SimpleNamespace(
        id="test_tank_no_geometry_override",
        name="Test Tank",
        datasheets_models=[profile],
        keywords=["Vehicle"],
        faction_keywords=[],
    )

    caplog.set_level(logging.WARNING, logger="warhammer40k_ai.units.unit_mixins.datasheet_wargear_mixin")

    with pytest.raises(ValueError, match="complete geometry override"):
        unit._build_model_from_profile(datasheet, "Test Tank", profile)


def test_unit_model_build_applies_z_offset_for_flying_base():
    from warhammer40k_ai.units.unit import Unit

    unit = Unit.__new__(Unit)
    unit.name = "Test Skimmer"
    unit.keywords = ["Vehicle"]
    unit.faction_keywords = []

    profile = {
        "name": "Test Skimmer",
        "M": '14"',
        "T": "8",
        "Sv": "3+",
        "inv_sv": "-",
        "inv_sv_descr": "",
        "W": "10",
        "Ld": "6+",
        "OC": "3",
        "base_size": "60mm flying base",
        "base_size_descr": "",
    }
    datasheet = SimpleNamespace(
        id="test_skimmer_datasheet",
        name="Test Skimmer",
        datasheets_models=[profile],
        keywords=["Vehicle"],
        faction_keywords=[],
    )

    model = unit._build_model_from_profile(datasheet, "Test Skimmer", profile)
    assert model.model_base.z_offset == pytest.approx(convert_mm_to_inches(32.0), abs=1e-4)
