from __future__ import annotations

from warhammer40k_ai.engine.ruleset import RulesetBundle
from warhammer40k_ai.engine.semantic_diff import (
    SURFACE_GEOMETRY,
    SURFACE_RESOURCE_ECONOMY,
    SURFACE_SCORING,
    classify_semantic_diff,
)


def _bundle(
    *,
    core_rules_id: str = "core_10e",
    rules_commentary_id: str = "commentary_a",
    mission_pack_id: str = "mission_a",
    terrain_pack_id: str = "terrain_a",
    dataslate_id: str = "dataslate_a",
    points_id: str = "points_a",
    faction_pack_id: str = "faction_a",
    detachment_pack_id: str = "detachment_a",
) -> RulesetBundle:
    return RulesetBundle.from_values(
        core_rules_id=core_rules_id,
        rules_commentary_id=rules_commentary_id,
        mission_pack_id=mission_pack_id,
        terrain_pack_id=terrain_pack_id,
        dataslate_id=dataslate_id,
        points_id=points_id,
        faction_pack_id=faction_pack_id,
        detachment_pack_id=detachment_pack_id,
    )


def test_points_only_diff_selects_value_recalibration_scope() -> None:
    source = _bundle(points_id="points_old")
    target = _bundle(points_id="points_new")

    diff = classify_semantic_diff(source, target)

    assert diff.changed_bundle_fields == ("points_id",)
    assert SURFACE_RESOURCE_ECONOMY in diff.changed_surfaces
    assert diff.training_scope.scope_id == "points_only_value_recalibration"
    assert diff.training_scope.relabel_required is False
    assert diff.training_scope.broad_retrain_required is False


def test_mission_pack_diff_selects_scoring_surface_scope() -> None:
    source = _bundle(mission_pack_id="mission_old")
    target = _bundle(mission_pack_id="mission_new")

    diff = classify_semantic_diff(source, target)

    assert "mission_pack_id" in diff.changed_bundle_fields
    assert SURFACE_SCORING in diff.changed_surfaces
    assert diff.training_scope.scope_id == "scoring_surface_update"
    assert diff.training_scope.relabel_required is True
    assert "MissionDescriptor" in diff.training_scope.descriptor_families_to_recompile


def test_terrain_diff_selects_geometry_scope() -> None:
    source = _bundle(terrain_pack_id="terrain_old")
    target = _bundle(terrain_pack_id="terrain_new")

    diff = classify_semantic_diff(source, target)

    assert "terrain_pack_id" in diff.changed_bundle_fields
    assert SURFACE_GEOMETRY in diff.changed_surfaces
    assert diff.training_scope.scope_id == "geometry_surface_update"
    assert "TerrainDescriptor" in diff.training_scope.descriptor_families_to_recompile


def test_edition_change_uses_adapter_first_scope() -> None:
    source = _bundle(core_rules_id="core_10e_2025")
    target = _bundle(core_rules_id="core_11e_2026")

    diff = classify_semantic_diff(source, target)

    assert diff.edition_transition is True
    assert diff.training_scope.scope_id == "edition_migration_adapter_first"
    assert diff.training_scope.adapter_first is True
    assert diff.training_scope.relabel_required is True
