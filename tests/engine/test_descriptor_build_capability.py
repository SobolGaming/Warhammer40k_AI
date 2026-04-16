from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.descriptor_build_capability import (
    compile_build_capability_descriptor_for_army,
)
from warhammer40k_ai.roster.army_build import ArmyBlueprint, DetachmentSelection, RosterEntry
from warhammer40k_ai.roster.build_capability_schema import BUILD_CAPABILITY_SCHEMA_V2
from warhammer40k_ai.waha_helper import WahaHelper


@pytest.fixture(scope="module")
def waha_helper() -> WahaHelper:
    return WahaHelper()


def _descriptor_blueprint() -> ArmyBlueprint:
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
                entry_id="unit_intercessors",
                name="Intercessor Squad",
                count=5,
                detachment_selection_id="det_vanguard",
            ),
        ],
    )


def _preview_combat_scope() -> dict[str, object]:
    return {
        "rules_bundle_id": "rules_bundle:2026-04-15-preview-combat",
        "version_adapter_boundary": {
            "combat_profile_family": "11e_preview",
        },
    }


def test_build_capability_descriptor_wrapper_is_deterministic(
    waha_helper: WahaHelper,
) -> None:
    army = SimpleNamespace(army_blueprint=_descriptor_blueprint())

    first = compile_build_capability_descriptor_for_army(
        army,
        rules_bundle_id="rules_bundle:2026-04-14",
        waha_helper=waha_helper,
    )
    second = compile_build_capability_descriptor_for_army(
        army,
        rules_bundle_id="rules_bundle:2026-04-14",
        waha_helper=waha_helper,
    )

    assert first is not None
    assert second is not None
    assert first.family == "BuildCapabilityDescriptor"
    assert first.descriptor_id == second.descriptor_id
    assert first.descriptor_id.startswith("build_capability_descriptor:")
    assert first.payload == second.payload
    assert first.payload["build_capability_profile_id"].startswith("build_capability_profile:")
    assert first.payload["capability_schema_id"] == "capability_schema:build_capability_v1"


def test_build_capability_descriptor_wrapper_accepts_rules_bundle_snapshot_scope_without_helper() -> None:
    army = SimpleNamespace(army_blueprint=_descriptor_blueprint())

    descriptor = compile_build_capability_descriptor_for_army(
        army,
        rules_bundle_id={
            "rules_bundle_id": "rules_bundle:live_snapshot",
            "wahapedia_data_dir": "wahapedia_data",
        },
    )

    assert descriptor is not None
    assert descriptor.payload["build_capability_profile_id"].startswith("build_capability_profile:")
    assert descriptor.payload["rules_bundle_id"] == "rules_bundle:live_snapshot"


def test_build_capability_descriptor_wrapper_can_target_preview_v2_schema(
    waha_helper: WahaHelper,
) -> None:
    army = SimpleNamespace(army_blueprint=_descriptor_blueprint())

    baseline = compile_build_capability_descriptor_for_army(
        army,
        rules_bundle_id=_preview_combat_scope(),
        waha_helper=waha_helper,
    )
    first = compile_build_capability_descriptor_for_army(
        army,
        rules_bundle_id=_preview_combat_scope(),
        schema=BUILD_CAPABILITY_SCHEMA_V2,
        waha_helper=waha_helper,
    )
    second = compile_build_capability_descriptor_for_army(
        army,
        rules_bundle_id=_preview_combat_scope(),
        schema=BUILD_CAPABILITY_SCHEMA_V2,
        waha_helper=waha_helper,
    )

    assert baseline is not None
    assert first is not None
    assert second is not None
    assert first.descriptor_id == second.descriptor_id
    assert first.descriptor_id != baseline.descriptor_id
    assert first.payload["capability_schema_id"] == "capability_schema:build_capability_v2"
    assert first.payload["rules_bundle_id"] == "rules_bundle:2026-04-15-preview-combat"
    assert "charge_option_flexibility" in first.payload["capability_scores"]
    assert first.payload["capability_scores"]["overrun_chain_potential"] > 0.0


def test_build_capability_descriptor_wrapper_returns_none_without_roster_context() -> None:
    assert (
        compile_build_capability_descriptor_for_army(
            SimpleNamespace(),
            rules_bundle_id="rules_bundle:2026-04-14",
        )
        is None
    )
