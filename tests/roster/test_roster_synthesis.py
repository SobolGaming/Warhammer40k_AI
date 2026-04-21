from __future__ import annotations

import pytest

from warhammer40k_ai.roster.army import parse_army_list_text
from warhammer40k_ai.roster.army_muster import ArmyMusterer
from warhammer40k_ai.roster.roster_synthesis import (
    RosterSynthesisCatalog,
    RosterSynthesisSeed,
    muster_records_from_synthesis_report,
    score_capability_profile,
    synthesize_rosters,
)
from warhammer40k_ai.roster.muster_record import validate_muster_record
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper import WahaHelper

RULES_BUNDLE_ID = "rules_bundle:10th_local_wahapedia"


@pytest.fixture(scope="module")
def waha_helper() -> WahaHelper:
    return WahaHelper()


@pytest.fixture(scope="module")
def world_eaters_report(waha_helper: WahaHelper):
    return synthesize_rosters(
        RosterSynthesisSeed(
            max_points=2000,
            max_under_cap_allowance=25,
            faction="World Eaters",
            detachment="Khorne Daemonkin",
            style_tags=("melee", "offensive", "daemonkin"),
            include_units=("Lord on Juggernaut",),
        ),
        waha_helper=waha_helper,
        rules_bundle_id=RULES_BUNDLE_ID,
        top_k=3,
        random_seed=13,
    )


def test_seed_validation_requires_positive_point_cap() -> None:
    with pytest.raises(ValueError, match="max_points is required"):
        RosterSynthesisSeed.from_dict({})
    with pytest.raises(ValueError, match="max_points must be positive"):
        RosterSynthesisSeed(max_points=0)
    with pytest.raises(ValueError, match="max_under_cap_allowance cannot be negative"):
        RosterSynthesisSeed(max_points=500, max_under_cap_allowance=-1)


def test_seed_normalizes_style_text() -> None:
    seed = RosterSynthesisSeed(
        max_points=1000,
        style_tags=("ranged-heavy",),
        description_text="Fast vehicle heavy objective control list.",
    )
    assert seed.normalized_style_tags == (
        "ranged_heavy",
        "vehicle_heavy",
        "objective_control",
        "fast",
    )


def test_invalid_constraints_return_actionable_diagnostics(waha_helper: WahaHelper) -> None:
    with pytest.raises(ValueError, match="Unknown or unsupported faction"):
        synthesize_rosters(
            RosterSynthesisSeed(max_points=500, faction="Space Rats"),
            waha_helper=waha_helper,
            rules_bundle_id=RULES_BUNDLE_ID,
        )
    with pytest.raises(ValueError, match="Unknown detachment"):
        synthesize_rosters(
            RosterSynthesisSeed(
                max_points=500,
                faction="World Eaters",
                detachment="Not A Real Detachment",
            ),
            waha_helper=waha_helper,
            rules_bundle_id=RULES_BUNDLE_ID,
        )
    with pytest.raises(ValueError, match="Unknown include unit"):
        synthesize_rosters(
            RosterSynthesisSeed(
                max_points=500,
                faction="World Eaters",
                include_units=("Definitely Not A Datasheet",),
            ),
            waha_helper=waha_helper,
            rules_bundle_id=RULES_BUNDLE_ID,
        )
    with pytest.raises(ValueError, match="Unknown exclude unit"):
        synthesize_rosters(
            RosterSynthesisSeed(
                max_points=500,
                faction="World Eaters",
                exclude_units=("Definitely Not A Datasheet",),
            ),
            waha_helper=waha_helper,
            rules_bundle_id=RULES_BUNDLE_ID,
        )


def test_catalog_enumerates_faction_datasheets_points_and_detachments(
    waha_helper: WahaHelper,
) -> None:
    catalog = RosterSynthesisCatalog(waha_helper)
    unit_options = catalog.unit_options("WE")
    lord_options = [option for option in unit_options if option.name == "Lord on Juggernaut"]
    assert lord_options
    assert all(option.points > 0 for option in lord_options)
    assert all(option.model_count >= 1 for option in lord_options)
    detachments = catalog.detachment_options("WE")
    detachment_names = {option.name for option in detachments}
    assert "Khorne Daemonkin" in detachment_names
    assert not any("Boarding" in option.name for option in detachments)
    enhancement_options = catalog.enhancement_options("WE", detachment_name="Khorne Daemonkin")
    assert any(option.name == "Disciple of Khorne" for option in enhancement_options)


@pytest.mark.integration
def test_synthesizes_valid_2000_point_world_eaters_khorne_daemonkin_candidate(
    waha_helper: WahaHelper,
    world_eaters_report,
) -> None:
    assert world_eaters_report.candidates
    for candidate in world_eaters_report.candidates:
        assert candidate.points <= 2000
        assert candidate.points >= 1975
        assert "Lord on Juggernaut" in {
            entry.name for entry in candidate.army_blueprint.unit_entries
        }
        army = ArmyMusterer(waha_helper).validate_runtime_legality(candidate.army_blueprint)
        assert army.get_total_points() == candidate.points


@pytest.mark.integration
def test_synthesizes_valid_space_marine_chapter_constrained_candidate(
    waha_helper: WahaHelper,
) -> None:
    report = synthesize_rosters(
        RosterSynthesisSeed(
            max_points=500,
            chapter="Ultramarines",
            detachment="Gladius Task Force",
            style_tags=("objective-control",),
        ),
        waha_helper=waha_helper,
        rules_bundle_id=RULES_BUNDLE_ID,
        top_k=1,
    )
    assert report.candidates
    candidate = report.candidates[0]
    assert candidate.army_blueprint.faction == "Ultramarines"
    ArmyMusterer(waha_helper).validate_runtime_legality(candidate.army_blueprint)


@pytest.mark.integration
def test_omitted_faction_searches_multiple_supported_factions_deterministically(
    waha_helper: WahaHelper,
) -> None:
    first = synthesize_rosters(
        RosterSynthesisSeed(max_points=500),
        waha_helper=waha_helper,
        rules_bundle_id=RULES_BUNDLE_ID,
        top_k=2,
        random_seed=4,
    )
    second = synthesize_rosters(
        RosterSynthesisSeed(max_points=500),
        waha_helper=waha_helper,
        rules_bundle_id=RULES_BUNDLE_ID,
        top_k=2,
        random_seed=4,
    )
    assert len(first.searched_factions) > 1
    assert first.candidates
    assert [candidate.army_blueprint.army_blueprint_hash for candidate in first.candidates] == [
        candidate.army_blueprint.army_blueprint_hash for candidate in second.candidates
    ]


@pytest.mark.integration
def test_synthesis_filters_candidates_with_illegal_mandatory_reserves(
    waha_helper: WahaHelper,
) -> None:
    report = synthesize_rosters(
        RosterSynthesisSeed(
            max_points=2000,
            max_under_cap_allowance=0,
        ),
        waha_helper=waha_helper,
        rules_bundle_id=RULES_BUNDLE_ID,
        top_k=1,
        random_seed=41101,
    )
    assert report.candidates
    assert any("mandatory reserves allocation invalid" in item for item in report.diagnostics)
    muster = ArmyMusterer(waha_helper)
    for candidate in report.candidates:
        army = muster.validate_runtime_legality(candidate.army_blueprint)
        decisions = {}
        for root in list(army._reserve_group_roots() or []):
            must_start = getattr(root, "must_start_in_reserves", None)
            status = "reserves" if callable(must_start) and bool(must_start()) else "deploy"
            decisions[str(get_entity_id(root) or "")] = status
        reserve_status = army.validate_reserves_decisions(decisions)
        assert bool(reserve_status["valid"]), reserve_status


@pytest.mark.integration
def test_exported_synthesized_roster_round_trips_through_army_list_parser(
    waha_helper: WahaHelper,
    world_eaters_report,
) -> None:
    candidate = world_eaters_report.candidates[0]
    assert "Bladed horn" in candidate.export_text
    assert "Exalted chainblade" in candidate.export_text
    assert "Plasma pistol" in candidate.export_text
    parsed_army = parse_army_list_text(
        candidate.export_text,
        waha_helper,
        list_name="synthesized_world_eaters",
    )
    parsed_army.validate()
    assert parsed_army.get_total_points() == candidate.points
    records = muster_records_from_synthesis_report(world_eaters_report)
    assert records
    record = records[0].to_dict()
    assert validate_muster_record(record) == []
    assert record["source_tag"] == "roster_synthesis"
    assert record["record_kind"] == "search_candidate"
    assert record["army_blueprint_hash"] == candidate.army_blueprint.army_blueprint_hash


@pytest.mark.integration
def test_synthesis_assigns_legal_enhancements_when_points_allow(
    waha_helper: WahaHelper,
) -> None:
    report = synthesize_rosters(
        RosterSynthesisSeed(
            max_points=500,
            faction="World Eaters",
            detachment="Khorne Daemonkin",
            include_units=("Lord on Juggernaut",),
        ),
        waha_helper=waha_helper,
        rules_bundle_id=RULES_BUNDLE_ID,
        top_k=1,
        random_seed=1,
    )
    assert report.candidates
    candidate = report.candidates[0]
    assert candidate.army_blueprint.enhancement_assignments
    assert "Enhancements:" in candidate.export_text
    assert candidate.points < candidate.army_blueprint.points_limit
    assert candidate.export_text.splitlines()[0].endswith(f"({candidate.points:,} Points)")
    assert not candidate.export_text.splitlines()[0].endswith(
        f"({candidate.army_blueprint.points_limit:,} Points)"
    )
    army = ArmyMusterer(waha_helper).validate_runtime_legality(candidate.army_blueprint)
    assert any(getattr(unit, "enhancement", None) is not None for unit in army.units)


@pytest.mark.integration
def test_include_and_exclude_constraints_are_hard(waha_helper: WahaHelper) -> None:
    report = synthesize_rosters(
        RosterSynthesisSeed(
            max_points=500,
            faction="World Eaters",
            detachment="Khorne Daemonkin",
            include_units=("Lord on Juggernaut",),
            exclude_units=("Khorne Berzerkers",),
        ),
        waha_helper=waha_helper,
        rules_bundle_id=RULES_BUNDLE_ID,
        top_k=1,
    )
    assert report.candidates
    names = {entry.name for entry in report.candidates[0].army_blueprint.unit_entries}
    assert "Lord on Juggernaut" in names
    assert "Khorne Berzerkers" not in names


@pytest.mark.integration
def test_style_scoring_prefers_matching_pressure_and_vehicle_tags(
    waha_helper: WahaHelper,
) -> None:
    melee_report = synthesize_rosters(
        RosterSynthesisSeed(
            max_points=1000,
            faction="World Eaters",
            detachment="Khorne Daemonkin",
            style_tags=("melee", "offensive"),
        ),
        waha_helper=waha_helper,
        rules_bundle_id=RULES_BUNDLE_ID,
        top_k=1,
        random_seed=2,
    )
    neutral_report = synthesize_rosters(
        RosterSynthesisSeed(
            max_points=1000,
            faction="World Eaters",
            detachment="Khorne Daemonkin",
        ),
        waha_helper=waha_helper,
        rules_bundle_id=RULES_BUNDLE_ID,
        top_k=1,
        random_seed=2,
    )
    vehicle_report = synthesize_rosters(
        RosterSynthesisSeed(
            max_points=1000,
            faction="World Eaters",
            detachment="Khorne Daemonkin",
            style_tags=("vehicle-heavy",),
        ),
        waha_helper=waha_helper,
        rules_bundle_id=RULES_BUNDLE_ID,
        top_k=1,
        random_seed=2,
    )
    melee_score, _breakdown = score_capability_profile(
        melee_report.candidates[0].capability_profile,
        ("melee", "offensive"),
    )
    vehicle_as_melee_score, _breakdown = score_capability_profile(
        vehicle_report.candidates[0].capability_profile,
        ("melee", "offensive"),
    )
    assert melee_score > vehicle_as_melee_score
    assert (
        vehicle_report.candidates[0]
        .capability_profile.aggregate_counts["vehicle_or_monster_unit_count"]
        >= neutral_report.candidates[0]
        .capability_profile.aggregate_counts["vehicle_or_monster_unit_count"]
    )
