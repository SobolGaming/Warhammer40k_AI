from __future__ import annotations

import pytest

from warhammer40k_ai.roster.army_attachments import AttachmentBinding
from warhammer40k_ai.roster.army_build import (
    ArmyBlueprint,
    DetachmentSelection,
    EnhancementAssignment,
    RosterEntry,
)
from warhammer40k_ai.roster.build_capability import compile_build_capability_profile
from warhammer40k_ai.roster.build_capability_schema import (
    BuildCapabilitySchema,
    DEFAULT_BUILD_CAPABILITY_SCHEMA,
)
from warhammer40k_ai.waha_helper import WahaHelper


@pytest.fixture(scope="module")
def waha_helper() -> WahaHelper:
    return WahaHelper()


def _mixed_detachment_blueprint() -> ArmyBlueprint:
    return ArmyBlueprint(
        faction="Space Marines",
        detachments=[
            DetachmentSelection(
                selection_id="det_gladius",
                detachment_type="Gladius Task Force",
            ),
            DetachmentSelection(
                selection_id="det_first_company",
                detachment_type="1st Company Task Force",
            ),
        ],
        unit_entries=[
            RosterEntry(
                entry_id="unit_captain",
                name="Captain",
                detachment_selection_id="det_gladius",
                is_warlord=True,
            ),
            RosterEntry(
                entry_id="unit_bladeguard",
                name="Bladeguard Veteran Squad",
                count=3,
                detachment_selection_id="det_first_company",
            ),
            RosterEntry(
                entry_id="unit_intercessors",
                name="Intercessor Squad",
                count=5,
                detachment_selection_id="det_gladius",
            ),
        ],
        enhancement_assignments=[
            EnhancementAssignment(
                assignment_id="enhancement_1",
                enhancement_name="Honours of Battle",
                target_entry_id="unit_captain",
                detachment_selection_id="det_gladius",
            )
        ],
        attachment_bindings=[
            AttachmentBinding(
                binding_id="binding_1",
                bodyguard_entry_id="unit_bladeguard",
                leader_entry_id="unit_captain",
            )
        ],
    )


def _melee_heavy_blueprint() -> ArmyBlueprint:
    return ArmyBlueprint(
        faction="Space Marines",
        detachments=[
            DetachmentSelection(
                selection_id="det_liberator",
                detachment_type="Liberator Assault Group",
            )
        ],
        unit_entries=[
            RosterEntry(
                entry_id="unit_assault_alpha",
                name="Assault Intercessor Squad",
                count=5,
                detachment_selection_id="det_liberator",
            ),
            RosterEntry(
                entry_id="unit_assault_beta",
                name="Assault Intercessor Squad",
                count=5,
                detachment_selection_id="det_liberator",
            ),
            RosterEntry(
                entry_id="unit_bladeguard",
                name="Bladeguard Veteran Squad",
                count=3,
                detachment_selection_id="det_liberator",
            ),
        ],
    )


def _towering_heavy_blueprint() -> ArmyBlueprint:
    return ArmyBlueprint(
        faction="Imperial Knights",
        detachments=[
            DetachmentSelection(
                selection_id="det_noble_lance",
                detachment_type="Noble Lance",
            )
        ],
        unit_entries=[
            RosterEntry(
                entry_id="unit_castellan_alpha",
                name="Knight Castellan",
                detachment_selection_id="det_noble_lance",
            ),
            RosterEntry(
                entry_id="unit_castellan_beta",
                name="Knight Castellan",
                detachment_selection_id="det_noble_lance",
            ),
        ],
    )


def _action_heavy_blueprint() -> ArmyBlueprint:
    return ArmyBlueprint(
        faction="Space Marines",
        detachments=[
            DetachmentSelection(
                selection_id="det_vanguard",
                detachment_type="Vanguard Spearhead",
            )
        ],
        unit_entries=[
            RosterEntry(
                entry_id="unit_scouts",
                name="Scout Squad",
                count=5,
                detachment_selection_id="det_vanguard",
            ),
            RosterEntry(
                entry_id="unit_incursors",
                name="Incursor Squad",
                count=5,
                detachment_selection_id="det_vanguard",
            ),
            RosterEntry(
                entry_id="unit_intercessors",
                name="Intercessor Squad",
                count=5,
                detachment_selection_id="det_vanguard",
            ),
        ],
    )


def _bumped_schema() -> BuildCapabilitySchema:
    return BuildCapabilitySchema(
        capability_schema_id="capability_schema:build_capability_v2",
        aggregate_count_names=DEFAULT_BUILD_CAPABILITY_SCHEMA.aggregate_count_names,
        pressure_metric_names=DEFAULT_BUILD_CAPABILITY_SCHEMA.pressure_metric_names,
        feature_definitions=DEFAULT_BUILD_CAPABILITY_SCHEMA.feature_definitions,
    )


def test_build_capability_profile_is_deterministic_for_same_blueprint_and_rules_bundle(
    waha_helper: WahaHelper,
) -> None:
    blueprint = _mixed_detachment_blueprint()

    first = compile_build_capability_profile(
        blueprint,
        rules_bundle_id="rules_bundle:2026-04-14",
        waha_helper=waha_helper,
    )
    second = compile_build_capability_profile(
        blueprint.to_dict(),
        rules_bundle_id="rules_bundle:2026-04-14",
        waha_helper=waha_helper,
    )

    assert first.to_dict() == second.to_dict()
    assert first.build_capability_profile_id == second.build_capability_profile_id
    assert first.build_capability_profile_id.startswith("build_capability_profile:")
    assert first.capability_schema_id == DEFAULT_BUILD_CAPABILITY_SCHEMA.capability_schema_id
    assert [record.entry_id for record in first.unit_breakdown] == [
        "unit_bladeguard",
        "unit_captain",
        "unit_intercessors",
    ]


def test_build_capability_profile_changes_deterministically_for_rules_bundle_and_schema_version(
    waha_helper: WahaHelper,
) -> None:
    blueprint = _mixed_detachment_blueprint()

    baseline = compile_build_capability_profile(
        blueprint,
        rules_bundle_id="rules_bundle:2026-04-14",
        waha_helper=waha_helper,
    )
    different_rules = compile_build_capability_profile(
        blueprint,
        rules_bundle_id="rules_bundle:2026-04-15",
        waha_helper=waha_helper,
    )
    bumped_schema = _bumped_schema()
    bumped_once = compile_build_capability_profile(
        blueprint,
        rules_bundle_id="rules_bundle:2026-04-14",
        schema=bumped_schema,
        waha_helper=waha_helper,
    )
    bumped_twice = compile_build_capability_profile(
        blueprint,
        rules_bundle_id="rules_bundle:2026-04-14",
        schema=bumped_schema,
        waha_helper=waha_helper,
    )

    assert different_rules.build_capability_profile_id != baseline.build_capability_profile_id
    assert bumped_once.capability_schema_id == "capability_schema:build_capability_v2"
    assert bumped_once.build_capability_profile_id != baseline.build_capability_profile_id
    assert bumped_once.build_capability_profile_id == bumped_twice.build_capability_profile_id
    assert bumped_once.army_blueprint_hash == baseline.army_blueprint_hash


def test_build_capability_regression_fixtures_capture_expected_roster_semantics(
    waha_helper: WahaHelper,
) -> None:
    mixed = compile_build_capability_profile(
        _mixed_detachment_blueprint(),
        rules_bundle_id="rules_bundle:2026-04-14",
        waha_helper=waha_helper,
    )
    melee = compile_build_capability_profile(
        _melee_heavy_blueprint(),
        rules_bundle_id="rules_bundle:2026-04-14",
        waha_helper=waha_helper,
    )
    towering = compile_build_capability_profile(
        _towering_heavy_blueprint(),
        rules_bundle_id="rules_bundle:2026-04-14",
        waha_helper=waha_helper,
    )
    action = compile_build_capability_profile(
        _action_heavy_blueprint(),
        rules_bundle_id="rules_bundle:2026-04-14",
        waha_helper=waha_helper,
    )

    assert len(
        {
            mixed.build_capability_profile_id,
            melee.build_capability_profile_id,
            towering.build_capability_profile_id,
            action.build_capability_profile_id,
        }
    ) == 4

    assert mixed.aggregate_counts["detachment_count"] == 2
    assert mixed.aggregate_counts["leader_binding_count"] == 1
    assert mixed.aggregate_counts["enhancement_count"] == 1
    assert mixed.capability_scores["detachment_diversity_index"] == 0.5
    assert mixed.capability_scores["attachment_dependency_risk"] > 0.4

    assert melee.pressure_profile["melee_share"] > 0.7
    assert melee.capability_scores["terrain_occlusion_reliance"] > 0.9
    assert melee.capability_scores["elevated_fire_affinity"] < 0.1

    assert action.aggregate_counts["infiltrator_unit_count"] == 1
    assert action.aggregate_counts["scout_unit_count"] == 2
    assert action.capability_scores["deployment_reveal_pressure"] > mixed.capability_scores[
        "deployment_reveal_pressure"
    ]
    assert action.capability_scores["mission_action_flex_capacity"] > mixed.capability_scores[
        "mission_action_flex_capacity"
    ]

    assert towering.aggregate_counts["towering_unit_count"] == 2
    assert towering.aggregate_counts["titanic_unit_count"] == 2
    assert towering.capability_scores["towering_exposure_index"] == 1.0
    assert towering.capability_scores["elevated_fire_affinity"] > 0.8
    assert towering.capability_scores["objective_spread_tolerance"] < 0.2

    assert towering.capability_scores["elevated_fire_affinity"] > melee.capability_scores[
        "elevated_fire_affinity"
    ]
    assert melee.capability_scores["charge_delivery_reliance"] > towering.capability_scores[
        "charge_delivery_reliance"
    ]
    assert action.capability_scores["mission_action_flex_capacity"] > towering.capability_scores[
        "mission_action_flex_capacity"
    ]
