import pytest

from warhammer40k_ai.roster.army import ArmyValidationError
from warhammer40k_ai.roster.army_attachments import AttachmentBinding
from warhammer40k_ai.roster.army_build import DetachmentSelection, EnhancementAssignment, RosterEntry
from warhammer40k_ai.roster.army_muster import ArmyMusterRequest, ArmyMusterer, UnitSelection
from warhammer40k_ai.roster.army_validation import validate_army_muster_request
from warhammer40k_ai.waha_helper import WahaHelper


def test_army_muster_request_round_trip_preserves_multi_detachment_shape() -> None:
    request = ArmyMusterRequest(
        faction="Space Marines",
        points_limit=2000,
        battle_size="Strike Force",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_alpha",
                detachment_type="Gladius Task Force",
                detachment_points_cost=2,
            ),
            DetachmentSelection(
                selection_id="detachment_beta",
                detachment_type="1st Company Task Force",
                detachment_points_cost=3,
            ),
        ],
        detachment_points_budget=5,
        units=[
            RosterEntry(
                entry_id="unit_captain",
                name="Captain",
                count=1,
                detachment_selection_id="detachment_alpha",
                is_warlord=True,
            ),
            RosterEntry(
                entry_id="unit_bladeguard",
                name="Bladeguard Veterans",
                count=3,
                detachment_selection_id="detachment_beta",
            ),
        ],
        enhancement_assignments=[
            EnhancementAssignment(
                assignment_id="enhancement_1",
                enhancement_name="Honours of Battle",
                target_entry_id="unit_captain",
                detachment_selection_id="detachment_alpha",
            )
        ],
        attachment_bindings=[
            AttachmentBinding(
                binding_id="binding_1",
                bodyguard_entry_id="unit_bladeguard",
                leader_entry_id="unit_captain",
            )
        ],
        force_disposition="Assault",
        allowed_force_dispositions=["Assault", "Siege"],
    )

    loaded = ArmyMusterRequest.from_dict(request.to_dict())
    blueprint = loaded.to_blueprint()

    assert [item.detachment_type for item in loaded.detachments] == [
        "Gladius Task Force",
        "1st Company Task Force",
    ]
    assert blueprint.detachment_points_budget == 5
    assert blueprint.force_disposition == "Assault"
    assert blueprint.allowed_force_dispositions == ["Assault", "Siege"]
    assert [item.selection_id for item in blueprint.detachments] == [
        "detachment_alpha",
        "detachment_beta",
    ]


def test_validate_detachment_points_budget_rejects_overspend() -> None:
    request = ArmyMusterRequest(
        faction="Space Marines",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_alpha",
                detachment_type="Gladius Task Force",
                detachment_points_cost=2,
            ),
            DetachmentSelection(
                selection_id="detachment_beta",
                detachment_type="1st Company Task Force",
                detachment_points_cost=4,
            ),
        ],
        detachment_points_budget=5,
    )

    with pytest.raises(ArmyValidationError, match="Detachment-point budget exceeded"):
        validate_army_muster_request(request)


def test_enhancement_assignment_round_trip_representation() -> None:
    assignment = EnhancementAssignment(
        assignment_id="enhancement_1",
        enhancement_name="Honours of Battle",
        target_entry_id="unit_captain",
        detachment_selection_id="detachment_alpha",
        metadata={"source": "test"},
    )

    loaded = EnhancementAssignment.from_dict(assignment.to_dict())

    assert loaded.assignment_id == "enhancement_1"
    assert loaded.enhancement_name == "Honours of Battle"
    assert loaded.target_entry_id == "unit_captain"
    assert loaded.detachment_selection_id == "detachment_alpha"
    assert loaded.metadata == {"source": "test"}


def test_attachment_binding_round_trip_representation() -> None:
    binding = AttachmentBinding(
        binding_id="binding_1",
        bodyguard_entry_id="unit_bladeguard",
        leader_entry_id="unit_captain",
        support_entry_id="unit_ancient",
    )

    loaded = AttachmentBinding.from_dict(binding.to_dict())

    assert loaded.binding_id == "binding_1"
    assert loaded.bodyguard_entry_id == "unit_bladeguard"
    assert loaded.leader_entry_id == "unit_captain"
    assert loaded.support_entry_id == "unit_ancient"


def test_muster_request_requires_explicit_detachments() -> None:
    request = ArmyMusterRequest(
        faction="Space Marines",
        units=[
            UnitSelection(
                name="Captain",
                count=1,
                enhancements=["Honours of Battle"],
                is_warlord=True,
            )
        ],
    )

    with pytest.raises(ArmyValidationError, match="must define at least one detachment"):
        validate_army_muster_request(request)


def test_validate_request_preserves_explicit_single_detachment_and_unit_selection() -> None:
    request = ArmyMusterRequest(
        faction="Space Marines",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_alpha",
                detachment_type="Gladius Task Force",
            )
        ],
        units=[
            UnitSelection(
                name="Captain",
                count=1,
                enhancements=["Honours of Battle"],
                is_warlord=True,
            )
        ],
    )

    validated = validate_army_muster_request(request)

    assert validated.legacy_single_detachment_adapter_used is False
    assert validated.blueprint.primary_detachment_type == "Gladius Task Force"
    assert len(validated.blueprint.unit_entries) == 1
    assert validated.blueprint.unit_entries[0].name == "Captain"
    assert validated.blueprint.unit_entries[0].is_warlord is True
    assert [item.enhancement_name for item in validated.blueprint.enhancement_assignments] == [
        "Honours of Battle"
    ]


def test_muster_army_accepts_deserialized_request_dict_and_attaches_validated_muster() -> None:
    request = ArmyMusterRequest(
        faction="Space Marines",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_alpha",
                detachment_type="Gladius Task Force",
            )
        ],
    )

    army = ArmyMusterer(WahaHelper()).muster_army(request.to_dict())

    assert army.detachment_type == "Gladius Task Force"
    assert army.get_detachment_types() == ["Gladius Task Force"]
    assert army.army_blueprint.primary_detachment_type == "Gladius Task Force"
    assert army.validated_muster.legacy_single_detachment_adapter_used is False
    assert army.build_detachments[0].selection_id == "detachment_alpha"
