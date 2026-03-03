import json
from types import SimpleNamespace

import pytest

from warhammer40k_ai.utility.aura_utils import horizontal_distance_between_bases_2d
from warhammer40k_ai.utility.calcs import convert_mm_to_inches
from warhammer40k_ai.utility.model_base import Base, BaseType, clone_base
from warhammer40k_ai.utility.model_geometry import resolve_model_geometry


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
