from __future__ import annotations

import json
from pathlib import Path

import pytest

from warhammer40k_ai.roster.army_attachments import AttachmentBinding
from warhammer40k_ai.roster.army_build import (
    ArmyBlueprint,
    DetachmentSelection,
    EnhancementAssignment,
    RosterEntry,
    UpgradeAssignment,
)
from warhammer40k_ai.roster.build_capability import compile_build_capability_profile
from warhammer40k_ai.roster.build_capability_schema import (
    BUILD_CAPABILITY_EXTENSION_11E_FACTION_FOCUS_MAY2026,
    BUILD_CAPABILITY_SCHEMA_V2,
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


def _upgrade_complex_blueprint() -> ArmyBlueprint:
    blueprint = _melee_heavy_blueprint()
    blueprint.upgrade_assignments = [
        UpgradeAssignment(
            upgrade_id="preview_multi_unit_upgrade",
            source_detachment_id="det_liberator",
            target_kind="unit",
            target_ids=("unit_assault_alpha", "unit_assault_beta"),
            max_targets=3,
            counts_toward_enhancement_limit=False,
            points_cost_mode="per_target",
            declaration_step="declare_battle_formations",
        ),
        UpgradeAssignment(
            upgrade_id="preview_weapon_profile_upgrade",
            source_detachment_id="det_liberator",
            target_kind="weapon_profile",
            target_ids=("unit_bladeguard",),
            max_targets=1,
            points_cost_mode="once",
            selected_weapon_profile_id="bladeguard_master_crafted_power_weapon",
            declaration_step="declare_battle_formations",
        ),
    ]
    return blueprint


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


def _snapshot_sensitive_blueprint() -> ArmyBlueprint:
    return ArmyBlueprint(
        faction="Chaos Space Marines",
        detachments=[
            DetachmentSelection(
                selection_id="det_veterans",
                detachment_type="Veterans of the Long War",
            )
        ],
        unit_entries=[
            RosterEntry(
                entry_id="unit_defiler",
                name="Defiler",
                detachment_selection_id="det_veterans",
            )
        ],
    )


def _write_snapshot_data_dir(
    root: Path,
    *,
    ranged_weapon: dict[str, object],
) -> Path:
    root.mkdir()
    datasheet_id = "test-defiler"
    files: dict[str, object] = {
        "Abilities.json": [],
        "Stratagems.json": [],
        "Enhancements.json": [],
        "Source.json": [],
        "Factions.json": [],
        "Detachment_abilities.json": [],
        "Datasheets_leader.json": [],
        "Datasheets_enhancements.json": [],
        "Datasheets.json": [
            {
                "id": datasheet_id,
                "name": "Defiler",
                "faction_id": "CSM",
                "role": "Vehicle",
                "source_id": "",
            }
        ],
        "Datasheets_keywords.json": [
            {
                "datasheet_id": datasheet_id,
                "keyword": "Vehicle",
                "is_faction_keyword": "false",
            },
            {
                "datasheet_id": datasheet_id,
                "keyword": "Chaos Space Marines",
                "is_faction_keyword": "true",
            },
        ],
        "Datasheets_wargear.json": [
            {
                "datasheet_id": datasheet_id,
                "name": "Defiler claws",
                "range": "Melee",
                "type": "Melee",
                "A": "5",
                "WS": "3+",
                "BS": "",
                "S": "12",
                "AP": "-2",
                "D": "3",
                "description": "",
            },
            {"datasheet_id": datasheet_id, **ranged_weapon},
        ],
    }
    for filename, payload in files.items():
        (root / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    return root


def _preview_combat_scope() -> dict[str, object]:
    return {
        "rules_bundle_id": "rules_bundle:2026-04-15-preview-combat",
        "version_adapter_boundary": {
            "combat_profile_family": "11e_preview",
        },
    }


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
    bumped_once = compile_build_capability_profile(
        blueprint,
        rules_bundle_id="rules_bundle:2026-04-14",
        schema=BUILD_CAPABILITY_SCHEMA_V2,
        waha_helper=waha_helper,
    )
    bumped_twice = compile_build_capability_profile(
        blueprint,
        rules_bundle_id="rules_bundle:2026-04-14",
        schema=BUILD_CAPABILITY_SCHEMA_V2,
        waha_helper=waha_helper,
    )

    assert different_rules.build_capability_profile_id != baseline.build_capability_profile_id
    assert bumped_once.capability_schema_id == "capability_schema:build_capability_v2"
    assert bumped_once.build_capability_profile_id != baseline.build_capability_profile_id
    assert bumped_once.build_capability_profile_id == bumped_twice.build_capability_profile_id
    assert bumped_once.army_blueprint_hash == baseline.army_blueprint_hash


def test_build_capability_v2_surfaces_preview_combat_semantics(
    waha_helper: WahaHelper,
) -> None:
    blueprint = _melee_heavy_blueprint()

    current = compile_build_capability_profile(
        blueprint,
        rules_bundle_id="rules_bundle:2026-04-14",
        schema=BUILD_CAPABILITY_SCHEMA_V2,
        waha_helper=waha_helper,
    )
    preview = compile_build_capability_profile(
        blueprint,
        rules_bundle_id=_preview_combat_scope(),
        schema=BUILD_CAPABILITY_SCHEMA_V2,
        waha_helper=waha_helper,
    )

    preview_feature_names = {
        "charge_option_flexibility",
        "ingress_charge_conversion",
        "fight_order_resilience",
        "overrun_chain_potential",
        "consolidate_objective_swing",
        "engagement_footprint_pressure",
        "transport_pop_punish_index",
    }

    assert preview.capability_schema_id == "capability_schema:build_capability_v2"
    assert preview.rules_bundle_id == "rules_bundle:2026-04-15-preview-combat"
    assert preview_feature_names.issubset(preview.capability_scores)
    assert preview.capability_scores["charge_option_flexibility"] > current.capability_scores["charge_option_flexibility"]
    assert preview.capability_scores["ingress_charge_conversion"] > current.capability_scores["ingress_charge_conversion"]
    assert preview.capability_scores["fight_order_resilience"] > current.capability_scores["fight_order_resilience"]
    assert current.capability_scores["overrun_chain_potential"] == 0.0
    assert preview.capability_scores["overrun_chain_potential"] > 0.0
    assert preview.capability_scores["consolidate_objective_swing"] > current.capability_scores["consolidate_objective_swing"]
    assert (
        preview.capability_scores["engagement_footprint_pressure"]
        > current.capability_scores["engagement_footprint_pressure"]
    )
    assert preview.capability_scores["transport_pop_punish_index"] > current.capability_scores["transport_pop_punish_index"]


def test_build_capability_v2_extension_group_adds_explicit_faction_focus_features(
    waha_helper: WahaHelper,
) -> None:
    blueprint = _upgrade_complex_blueprint()

    baseline = compile_build_capability_profile(
        blueprint,
        rules_bundle_id=_preview_combat_scope(),
        schema=BUILD_CAPABILITY_SCHEMA_V2,
        waha_helper=waha_helper,
    )
    extended = compile_build_capability_profile(
        blueprint,
        rules_bundle_id=_preview_combat_scope(),
        schema=BUILD_CAPABILITY_SCHEMA_V2,
        extension_groups=(BUILD_CAPABILITY_EXTENSION_11E_FACTION_FOCUS_MAY2026,),
        waha_helper=waha_helper,
    )
    extended_by_id = compile_build_capability_profile(
        blueprint.to_dict(),
        rules_bundle_id=_preview_combat_scope(),
        schema=BUILD_CAPABILITY_SCHEMA_V2,
        extension_groups=("capability_extension:11e_faction_focus_may2026",),
        waha_helper=waha_helper,
    )

    extension_feature_names = set(BUILD_CAPABILITY_EXTENSION_11E_FACTION_FOCUS_MAY2026.feature_names)
    assert baseline.capability_schema_id == extended.capability_schema_id == "capability_schema:build_capability_v2"
    assert baseline.build_capability_profile_id != extended.build_capability_profile_id
    assert baseline.extension_group_ids == ()
    assert "extension_group_ids" not in baseline.to_dict()
    assert extension_feature_names.isdisjoint(baseline.capability_scores)
    assert extended.build_capability_profile_id == extended_by_id.build_capability_profile_id
    assert extended.extension_group_ids == ("capability_extension:11e_faction_focus_may2026",)
    assert extension_feature_names.issubset(extended.capability_scores)
    assert extended.capability_scores["cleave_horde_clearance"] > 0.0
    assert extended.capability_scores["detection_marker_coverage"] > 0.0
    assert extended.capability_scores["reactive_move_density"] > 0.0
    assert extended.capability_scores["upgrade_cardinality_complexity"] > 0.0
    payload = extended.to_dict()
    assert payload["extension_group_ids"] == ["capability_extension:11e_faction_focus_may2026"]
    assert payload["capability_extension_groups"][0]["activation"] == "explicit"
    assert payload["capability_extension_groups"][0]["source_provenance"][0]["preview_only"] is True


def test_build_capability_extension_group_requires_v2_schema(
    waha_helper: WahaHelper,
) -> None:
    with pytest.raises(ValueError, match="must target capability_schema:build_capability_v2"):
        compile_build_capability_profile(
            _upgrade_complex_blueprint(),
            rules_bundle_id=_preview_combat_scope(),
            extension_groups=(BUILD_CAPABILITY_EXTENSION_11E_FACTION_FOCUS_MAY2026,),
            waha_helper=waha_helper,
        )


def test_build_capability_profile_requires_explicit_snapshot_scope_without_helper() -> None:
    with pytest.raises(ValueError, match="snapshot-scoped waha_helper"):
        compile_build_capability_profile(
            _mixed_detachment_blueprint(),
            rules_bundle_id="rules_bundle:2026-04-14",
        )


def test_build_capability_profile_uses_rules_bundle_snapshot_path_when_provided(
    tmp_path: Path,
) -> None:
    blueprint = _snapshot_sensitive_blueprint()
    firepower_snapshot = _write_snapshot_data_dir(
        tmp_path / "firepower_snapshot",
        ranged_weapon={
            "name": "Defiler cannon",
            "range": "72",
            "type": "Heavy",
            "A": "D6+3",
            "WS": "",
            "BS": "3+",
            "S": "12",
            "AP": "-3",
            "D": "D6+1",
            "description": "",
        },
    )
    melee_snapshot = _write_snapshot_data_dir(
        tmp_path / "melee_snapshot",
        ranged_weapon={
            "name": "Degraded combi-bolter",
            "range": "24",
            "type": "Rapid Fire 1",
            "A": "1",
            "WS": "",
            "BS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
    )

    firepower_profile = compile_build_capability_profile(
        blueprint,
        rules_bundle_id={
            "rules_bundle_id": "rules_bundle:firepower_snapshot",
            "wahapedia_data_dir": str(firepower_snapshot),
        },
    )
    melee_profile = compile_build_capability_profile(
        blueprint,
        rules_bundle_id={
            "rules_bundle_id": "rules_bundle:melee_snapshot",
            "wahapedia_data_dir": str(melee_snapshot),
        },
    )

    assert firepower_profile.aggregate_counts == melee_profile.aggregate_counts
    assert firepower_profile.build_capability_profile_id != melee_profile.build_capability_profile_id
    assert firepower_profile.pressure_profile["ranged_pressure"] > melee_profile.pressure_profile["ranged_pressure"]
    assert firepower_profile.pressure_profile["anti_tank_pressure"] > melee_profile.pressure_profile[
        "anti_tank_pressure"
    ]
    assert firepower_profile.capability_scores["charge_delivery_reliance"] < melee_profile.capability_scores[
        "charge_delivery_reliance"
    ]


def test_build_capability_profile_rejects_conflicting_helper_and_snapshot_scope(
    waha_helper: WahaHelper,
    tmp_path: Path,
) -> None:
    snapshot = _write_snapshot_data_dir(
        tmp_path / "snapshot",
        ranged_weapon={
            "name": "Defiler cannon",
            "range": "72",
            "type": "Heavy",
            "A": "D6+3",
            "WS": "",
            "BS": "3+",
            "S": "12",
            "AP": "-3",
            "D": "D6+1",
            "description": "",
        },
    )

    with pytest.raises(ValueError, match="does not match the rules bundle snapshot path"):
        compile_build_capability_profile(
            _snapshot_sensitive_blueprint(),
            rules_bundle_id={
                "rules_bundle_id": "rules_bundle:snapshot",
                "wahapedia_data_dir": str(snapshot),
            },
            waha_helper=waha_helper,
        )


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
