from __future__ import annotations

import pytest

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.descriptor_compiler import compile_descriptor_bundle
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.army_build import (
    ArmyBlueprint,
    DetachmentSelection,
    RosterEntry,
    UpgradeAssignment,
    ValidatedMuster,
)
from warhammer40k_ai.roster.army_muster import ArmyMusterRequest
from warhammer40k_ai.roster.army_runtime import apply_validated_muster_to_army
from warhammer40k_ai.roster.army_validation import validate_army_muster_request
from warhammer40k_ai.roster.player import Player


pytestmark = pytest.mark.preview


def _preview_units() -> list[RosterEntry]:
    return [
        RosterEntry(
            entry_id="unit_alpha",
            name="Intercessor Squad",
            count=5,
            detachment_selection_id="detachment_alpha",
        ),
        RosterEntry(
            entry_id="unit_beta",
            name="Sternguard Veteran Squad",
            count=5,
            detachment_selection_id="detachment_alpha",
        ),
        RosterEntry(
            entry_id="unit_gamma",
            name="Bladeguard Veteran Squad",
            count=3,
            detachment_selection_id="detachment_alpha",
        ),
    ]


def _preview_blueprint(*, upgrade: UpgradeAssignment) -> ArmyBlueprint:
    return ArmyBlueprint(
        faction="Space Marines",
        points_limit=2000,
        battle_size="Strike Force",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_alpha",
                detachment_type="Gladius Task Force",
            )
        ],
        unit_entries=_preview_units(),
        upgrade_assignments=[upgrade],
    )


def _descriptor_id_for_blueprint(blueprint: ArmyBlueprint) -> str:
    army = Army.with_detachment("Space Marines", "Gladius Task Force", points_limit=2000)
    army.faction_id = "SM"
    apply_validated_muster_to_army(
        army,
        ValidatedMuster(
            blueprint=blueprint,
            faction_id="SM",
            detachment_points_spent=0,
        ),
    )
    player = Player("P1", army=army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    return compile_descriptor_bundle(game).descriptor_ids()["army_build_descriptor_id"]


def test_upgrade_assignment_round_trip_preserves_preview_semantics() -> None:
    assignment = UpgradeAssignment(
        assignment_id="upgrade_1",
        upgrade_id="preview_upgrade:does_not_count",
        source_detachment_id="detachment_alpha",
        target_kind="unit",
        target_ids=("unit_alpha",),
        max_targets=1,
        counts_toward_enhancement_limit=False,
        points_cost_mode="once",
        declaration_step="declare_battle_formations",
        metadata={"preview_only": True},
    )

    loaded = UpgradeAssignment.from_dict(assignment.to_dict())

    assert loaded.assignment_id == "upgrade_1"
    assert loaded.upgrade_id == "preview_upgrade:does_not_count"
    assert loaded.target_kind == "unit"
    assert loaded.target_ids == ("unit_alpha",)
    assert loaded.counts_toward_enhancement_limit is False
    assert loaded.declaration_step == "declare_battle_formations"
    assert loaded.metadata == {"preview_only": True}


def test_upgrade_that_does_not_count_toward_enhancement_total_validates_cleanly() -> None:
    request = ArmyMusterRequest(
        faction="Space Marines",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_alpha",
                detachment_type="Gladius Task Force",
            )
        ],
        units=_preview_units(),
        upgrade_assignments=[
            UpgradeAssignment(
                upgrade_id="preview_upgrade:free_selection",
                source_detachment_id="detachment_alpha",
                target_kind="unit",
                target_ids=("unit_alpha",),
                counts_toward_enhancement_limit=False,
                points_cost_mode="once",
                declaration_step="list_building",
            )
        ],
    )

    validated = validate_army_muster_request(request)

    assert validated.blueprint.upgrade_assignments[0].counts_toward_enhancement_limit is False
    assert validated.blueprint.upgrade_assignments[0].target_ids == ("unit_alpha",)


def test_upgrade_target_up_to_three_units_validates_cardinality() -> None:
    request = ArmyMusterRequest(
        faction="Space Marines",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_alpha",
                detachment_type="Gladius Task Force",
            )
        ],
        units=_preview_units(),
        upgrade_assignments=[
            UpgradeAssignment(
                upgrade_id="preview_upgrade:up_to_three_units",
                source_detachment_id="detachment_alpha",
                target_kind="unit",
                target_ids=("unit_alpha", "unit_beta", "unit_gamma"),
                max_targets=3,
                counts_toward_enhancement_limit=True,
                points_cost_mode="per_target",
                declaration_step="list_building",
            )
        ],
    )

    validated = validate_army_muster_request(request)

    assert validated.blueprint.upgrade_assignments[0].max_targets == 3
    assert validated.blueprint.upgrade_assignments[0].points_cost_mode == "per_target"


def test_upgrade_cardinality_rejects_too_many_targets() -> None:
    with pytest.raises(ValueError, match="max_targets is 3"):
        UpgradeAssignment(
            upgrade_id="preview_upgrade:too_many_units",
            source_detachment_id="detachment_alpha",
            target_kind="unit",
            target_ids=("unit_alpha", "unit_beta", "unit_gamma", "unit_delta"),
            max_targets=3,
            points_cost_mode="per_target",
        )


def test_weapon_profile_upgrade_persists_selected_profile_identity() -> None:
    assignment = UpgradeAssignment(
        upgrade_id="preview_upgrade:selected_weapon_profile",
        source_detachment_id="detachment_alpha",
        target_kind="weapon_profile",
        target_ids=("unit_alpha",),
        max_targets=1,
        points_cost_mode="once",
        selected_weapon_profile_id="unit_alpha:bolt_rifle:focused_burst",
        declaration_step="declare_battle_formations",
    )
    blueprint = _preview_blueprint(upgrade=assignment)
    loaded = ArmyBlueprint.from_dict(blueprint.to_dict())

    assert loaded.upgrade_assignments[0].target_kind == "weapon_profile"
    assert loaded.upgrade_assignments[0].selected_weapon_profile_id == "unit_alpha:bolt_rifle:focused_burst"
    assert loaded.to_dict()["upgrade_assignments"][0]["selected_weapon_profile_id"] == (
        "unit_alpha:bolt_rifle:focused_burst"
    )


def test_unknown_unit_target_is_rejected_for_unit_upgrade() -> None:
    request = ArmyMusterRequest(
        faction="Space Marines",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_alpha",
                detachment_type="Gladius Task Force",
            )
        ],
        units=_preview_units(),
        upgrade_assignments=[
            UpgradeAssignment(
                upgrade_id="preview_upgrade:bad_target",
                source_detachment_id="detachment_alpha",
                target_kind="unit",
                target_ids=("unit_missing",),
            )
        ],
    )

    with pytest.raises(ArmyValidationError, match="references unknown unit entry"):
        validate_army_muster_request(request)


def test_descriptor_id_changes_when_upgrade_assignment_semantics_change() -> None:
    baseline = _preview_blueprint(
        upgrade=UpgradeAssignment(
            upgrade_id="preview_upgrade:descriptor",
            source_detachment_id="detachment_alpha",
            target_kind="unit",
            target_ids=("unit_alpha",),
            counts_toward_enhancement_limit=True,
            points_cost_mode="once",
        )
    )
    changed = _preview_blueprint(
        upgrade=UpgradeAssignment(
            upgrade_id="preview_upgrade:descriptor",
            source_detachment_id="detachment_alpha",
            target_kind="unit",
            target_ids=("unit_alpha", "unit_beta"),
            max_targets=2,
            counts_toward_enhancement_limit=False,
            points_cost_mode="per_target",
        )
    )

    assert baseline.army_blueprint_hash != changed.army_blueprint_hash
    assert _descriptor_id_for_blueprint(baseline) != _descriptor_id_for_blueprint(changed)
