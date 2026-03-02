from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .ruleset import RulesetBundle


SURFACE_LEGALITY = "LEGALITY_SURFACE"
SURFACE_GEOMETRY = "GEOMETRY_MOVEMENT_VISIBILITY_SURFACE"
SURFACE_SCORING = "SCORING_SURFACE"
SURFACE_RESOURCE_ECONOMY = "RESOURCE_ECONOMY_TOOL_SURFACE"
SURFACE_COMBAT = "COMBAT_SURFACE"
SURFACE_DEPLOYMENT_RESERVE = "DEPLOYMENT_RESERVE_SURFACE"
SURFACE_ENTITY_TAXONOMY = "ENTITY_TAXONOMY_SURFACE"


_BUNDLE_FIELDS = (
    "core_rules_id",
    "rules_commentary_id",
    "mission_pack_id",
    "terrain_pack_id",
    "dataslate_id",
    "points_id",
    "faction_pack_id",
    "detachment_pack_id",
)

_FIELD_TO_SURFACES = {
    "core_rules_id": (
        SURFACE_LEGALITY,
        SURFACE_GEOMETRY,
        SURFACE_SCORING,
        SURFACE_RESOURCE_ECONOMY,
        SURFACE_COMBAT,
        SURFACE_DEPLOYMENT_RESERVE,
        SURFACE_ENTITY_TAXONOMY,
    ),
    "rules_commentary_id": (
        SURFACE_LEGALITY,
        SURFACE_GEOMETRY,
        SURFACE_SCORING,
        SURFACE_RESOURCE_ECONOMY,
        SURFACE_COMBAT,
        SURFACE_DEPLOYMENT_RESERVE,
    ),
    "mission_pack_id": (
        SURFACE_SCORING,
        SURFACE_DEPLOYMENT_RESERVE,
    ),
    "terrain_pack_id": (
        SURFACE_GEOMETRY,
        SURFACE_DEPLOYMENT_RESERVE,
    ),
    "dataslate_id": (
        SURFACE_COMBAT,
        SURFACE_ENTITY_TAXONOMY,
    ),
    "points_id": (
        SURFACE_RESOURCE_ECONOMY,
    ),
    "faction_pack_id": (
        SURFACE_RESOURCE_ECONOMY,
        SURFACE_COMBAT,
        SURFACE_ENTITY_TAXONOMY,
    ),
    "detachment_pack_id": (
        SURFACE_RESOURCE_ECONOMY,
        SURFACE_COMBAT,
    ),
}

_FIELD_TO_DESCRIPTOR_FAMILIES = {
    "core_rules_id": (
        "MissionDescriptor",
        "ObjectiveDescriptor",
        "TerrainDescriptor",
        "DeploymentDescriptor",
        "ToolDescriptor",
    ),
    "rules_commentary_id": (
        "MissionDescriptor",
        "ObjectiveDescriptor",
        "TerrainDescriptor",
        "DeploymentDescriptor",
        "ToolDescriptor",
    ),
    "mission_pack_id": (
        "MissionDescriptor",
        "ObjectiveDescriptor",
        "DeploymentDescriptor",
    ),
    "terrain_pack_id": (
        "TerrainDescriptor",
    ),
    "dataslate_id": (),
    "points_id": (),
    "faction_pack_id": (
        "ToolDescriptor",
    ),
    "detachment_pack_id": (
        "ToolDescriptor",
    ),
}


def _extract_edition_number(core_rules_id: str) -> int | None:
    text = str(core_rules_id or "").strip().lower()
    if not text:
        return None
    match = re.search(r"([0-9]{1,2})\s*e", text)
    if match is None:
        return None
    return int(match.group(1))


def _changed_bundle_fields(source: RulesetBundle, target: RulesetBundle) -> list[str]:
    changed: list[str] = []
    for field in _BUNDLE_FIELDS:
        source_value = str(getattr(source, field, "") or "")
        target_value = str(getattr(target, field, "") or "")
        if source_value != target_value:
            changed.append(field)
    return changed


def _changed_surfaces(changed_fields: list[str]) -> list[str]:
    surfaces: set[str] = set()
    for field in list(changed_fields or []):
        surfaces.update(_FIELD_TO_SURFACES.get(field, ()))
    return sorted(surfaces)


def _descriptor_families_to_recompile(changed_fields: list[str]) -> list[str]:
    families: set[str] = set()
    for field in list(changed_fields or []):
        families.update(_FIELD_TO_DESCRIPTOR_FAMILIES.get(field, ()))
    return sorted(families)


def _is_points_only(changed_fields: list[str]) -> bool:
    return set(changed_fields) == {"points_id"}


def _is_edition_transition(source: RulesetBundle, target: RulesetBundle) -> bool:
    source_edition = _extract_edition_number(str(source.core_rules_id or ""))
    target_edition = _extract_edition_number(str(target.core_rules_id or ""))
    if source_edition is None or target_edition is None:
        return False
    return int(source_edition) != int(target_edition)


@dataclass(frozen=True)
class TrainingScopeRecommendation:
    scope_id: str
    adapter_first: bool
    relabel_required: bool
    broad_retrain_required: bool
    descriptor_families_to_recompile: tuple[str, ...]
    fine_tune_targets: tuple[str, ...]
    freeze_targets: tuple[str, ...]
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope_id": str(self.scope_id or ""),
            "adapter_first": bool(self.adapter_first),
            "relabel_required": bool(self.relabel_required),
            "broad_retrain_required": bool(self.broad_retrain_required),
            "descriptor_families_to_recompile": list(self.descriptor_families_to_recompile),
            "fine_tune_targets": list(self.fine_tune_targets),
            "freeze_targets": list(self.freeze_targets),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class SemanticDiffResult:
    source_bundle: RulesetBundle
    target_bundle: RulesetBundle
    changed_bundle_fields: tuple[str, ...]
    changed_surfaces: tuple[str, ...]
    edition_transition: bool
    training_scope: TrainingScopeRecommendation

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_bundle": self.source_bundle.to_dict(),
            "source_rules_bundle_id": str(self.source_bundle.rules_bundle_id or ""),
            "target_bundle": self.target_bundle.to_dict(),
            "target_rules_bundle_id": str(self.target_bundle.rules_bundle_id or ""),
            "changed_bundle_fields": list(self.changed_bundle_fields),
            "changed_surfaces": list(self.changed_surfaces),
            "edition_transition": bool(self.edition_transition),
            "training_scope": self.training_scope.to_dict(),
        }


def _training_scope_for_diff(
    *,
    changed_fields: list[str],
    changed_surfaces: list[str],
    descriptor_families: list[str],
    edition_transition: bool,
) -> TrainingScopeRecommendation:
    freeze_defaults = (
        "Tier0Legality",
        "InvariantBoardEncoder",
    )
    if not changed_fields:
        return TrainingScopeRecommendation(
            scope_id="no_change",
            adapter_first=False,
            relabel_required=False,
            broad_retrain_required=False,
            descriptor_families_to_recompile=tuple(),
            fine_tune_targets=tuple(),
            freeze_targets=freeze_defaults,
            notes=("No bundle field changed.",),
        )
    if _is_points_only(changed_fields):
        return TrainingScopeRecommendation(
            scope_id="points_only_value_recalibration",
            adapter_first=False,
            relabel_required=False,
            broad_retrain_required=False,
            descriptor_families_to_recompile=tuple(),
            fine_tune_targets=("ValueCalibrationHead",),
            freeze_targets=freeze_defaults + ("Tier1PlannerHead", "Tier2BinderHead", "Tier3MovementHead"),
            notes=(
                "Points-only update: update muster/value calibration before any broad in-game retrain.",
            ),
        )
    if edition_transition or "core_rules_id" in changed_fields:
        return TrainingScopeRecommendation(
            scope_id="edition_migration_adapter_first",
            adapter_first=True,
            relabel_required=True,
            broad_retrain_required=False,
            descriptor_families_to_recompile=tuple(sorted(set(descriptor_families) | set(_FIELD_TO_DESCRIPTOR_FAMILIES["core_rules_id"]))),
            fine_tune_targets=(
                "RulesConditionedAdapters",
                "Tier1PlannerHead",
                "Tier2BinderHead",
                "Tier3TargetingTradeHeads",
            ),
            freeze_targets=freeze_defaults + ("Tier3MovementHead",),
            notes=(
                "Edition/core transition: compile descriptor bundle and train adapters before broader retraining.",
            ),
        )
    if "mission_pack_id" in changed_fields or SURFACE_SCORING in changed_surfaces:
        return TrainingScopeRecommendation(
            scope_id="scoring_surface_update",
            adapter_first=True,
            relabel_required=True,
            broad_retrain_required=False,
            descriptor_families_to_recompile=tuple(sorted(set(descriptor_families) | set(_FIELD_TO_DESCRIPTOR_FAMILIES["mission_pack_id"]))),
            fine_tune_targets=(
                "Tier1PlannerHead",
                "Tier2BinderHead",
            ),
            freeze_targets=freeze_defaults + ("Tier3MovementHead",),
            notes=(
                "Mission scoring changed: relabel historical records and fine-tune planning/binding heads.",
            ),
        )
    if "terrain_pack_id" in changed_fields or SURFACE_GEOMETRY in changed_surfaces:
        return TrainingScopeRecommendation(
            scope_id="geometry_surface_update",
            adapter_first=True,
            relabel_required=True,
            broad_retrain_required=False,
            descriptor_families_to_recompile=tuple(sorted(set(descriptor_families) | set(_FIELD_TO_DESCRIPTOR_FAMILIES["terrain_pack_id"]))),
            fine_tune_targets=(
                "Tier3MovementHead",
                "Tier3PositioningHead",
            ),
            freeze_targets=freeze_defaults + ("Tier1PlannerHead", "Tier2BinderHead"),
            notes=(
                "Terrain/geometry changed: regenerate movement semantics and fine-tune movement heads only.",
            ),
        )
    if "dataslate_id" in changed_fields or SURFACE_COMBAT in changed_surfaces:
        return TrainingScopeRecommendation(
            scope_id="combat_surface_update",
            adapter_first=True,
            relabel_required=False,
            broad_retrain_required=False,
            descriptor_families_to_recompile=tuple(descriptor_families),
            fine_tune_targets=(
                "Tier3TargetingTradeHeads",
            ),
            freeze_targets=freeze_defaults + ("Tier3MovementHead",),
            notes=(
                "Dataslate/combat profile changed: recompute threat features and fine-tune combat micro heads.",
            ),
        )
    if (
        "faction_pack_id" in changed_fields
        or "detachment_pack_id" in changed_fields
        or SURFACE_RESOURCE_ECONOMY in changed_surfaces
    ):
        return TrainingScopeRecommendation(
            scope_id="resource_tool_update",
            adapter_first=True,
            relabel_required=False,
            broad_retrain_required=False,
            descriptor_families_to_recompile=tuple(sorted(set(descriptor_families) | {"ToolDescriptor"})),
            fine_tune_targets=(
                "Tier2ResourcePostureHead",
                "Tier3ToolUsageHead",
            ),
            freeze_targets=freeze_defaults + ("Tier3MovementHead",),
            notes=(
                "Tool/resource surface changed: update tool descriptors and fine-tune resource/timing heads.",
            ),
        )
    return TrainingScopeRecommendation(
        scope_id="mixed_patch_adapter_first",
        adapter_first=True,
        relabel_required=True,
        broad_retrain_required=False,
        descriptor_families_to_recompile=tuple(descriptor_families),
        fine_tune_targets=(
            "Tier1PlannerHead",
            "Tier2BinderHead",
            "Tier3TaskSpecificHeads",
        ),
        freeze_targets=freeze_defaults,
        notes=("Mixed bundle changes detected; start with adapters and scoped head fine-tuning.",),
    )


def classify_semantic_diff(
    source_bundle: RulesetBundle,
    target_bundle: RulesetBundle,
) -> SemanticDiffResult:
    changed_fields = _changed_bundle_fields(source_bundle, target_bundle)
    changed_surfaces = _changed_surfaces(changed_fields)
    descriptor_families = _descriptor_families_to_recompile(changed_fields)
    edition_transition = _is_edition_transition(source_bundle, target_bundle)
    training_scope = _training_scope_for_diff(
        changed_fields=changed_fields,
        changed_surfaces=changed_surfaces,
        descriptor_families=descriptor_families,
        edition_transition=edition_transition,
    )
    return SemanticDiffResult(
        source_bundle=source_bundle,
        target_bundle=target_bundle,
        changed_bundle_fields=tuple(changed_fields),
        changed_surfaces=tuple(changed_surfaces),
        edition_transition=bool(edition_transition),
        training_scope=training_scope,
    )
