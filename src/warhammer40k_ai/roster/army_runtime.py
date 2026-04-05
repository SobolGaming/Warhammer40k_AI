"""Runtime helpers for attaching build-side army state to Army."""

from __future__ import annotations

from .army import Army
from .army_build import ValidatedMuster


def apply_validated_muster_to_army(army: Army, validated_muster: ValidatedMuster) -> Army:
    """Attach build-side muster metadata to an already-created runtime army."""

    blueprint = validated_muster.blueprint
    army.army_blueprint = blueprint
    army.validated_muster = validated_muster
    army.build_detachments = list(blueprint.detachments or [])
    army.build_unit_entries = list(blueprint.unit_entries or [])
    army.build_enhancement_assignments = list(blueprint.enhancement_assignments or [])
    army.build_attachment_bindings = list(blueprint.attachment_bindings or [])
    army.detachment_points_budget = blueprint.detachment_points_budget
    army.detachment_points_spent = validated_muster.detachment_points_spent
    army.force_disposition = blueprint.force_disposition
    army.allowed_force_dispositions = list(blueprint.allowed_force_dispositions or [])
    army.build_metadata = {
        "legacy_single_detachment_adapter_used": bool(
            validated_muster.legacy_single_detachment_adapter_used
        ),
        "warnings": list(validated_muster.warnings or []),
    }
    return army
