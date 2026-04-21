import pytest

from warhammer40k_ai.roster.army import ArmyValidationError
from warhammer40k_ai.roster.army_attachments import AttachmentBinding
from warhammer40k_ai.roster.army_build import (
    ArmyBlueprint,
    DetachmentSelection,
    EnhancementAssignment,
    RosterEntry,
)
from warhammer40k_ai.roster.army_muster import ArmyMusterRequest, ArmyMusterer, UnitSelection
from warhammer40k_ai.roster.army_validation import (
    build_army_blueprint_from_request,
    validate_army_muster_request,
)
from warhammer40k_ai.waha_helper import WahaHelper


@pytest.fixture(scope="module")
def waha_helper() -> WahaHelper:
    return WahaHelper()


def _materialized_space_marines_request() -> ArmyMusterRequest:
    return ArmyMusterRequest(
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
                enhancement_names=["Artificer Armour"],
                is_warlord=True,
            ),
            RosterEntry(
                entry_id="unit_bladeguard",
                name="Bladeguard Veteran Squad",
                count=3,
                detachment_selection_id="detachment_beta",
            ),
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


def _aeldari_support_blueprint() -> ArmyBlueprint:
    return ArmyBlueprint(
        faction="Aeldari",
        points_limit=2000,
        battle_size="Strike Force",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_alpha",
                detachment_type="Warhost",
            )
        ],
        unit_entries=[
            RosterEntry(
                entry_id="unit_support",
                name="D-cannon Platform",
                count=1,
                detachment_selection_id="detachment_alpha",
            ),
            RosterEntry(
                entry_id="unit_guardians",
                name="Guardian Defenders",
                count=10,
                detachment_selection_id="detachment_alpha",
            ),
        ],
        attachment_bindings=[
            AttachmentBinding(
                binding_id="binding_support",
                bodyguard_entry_id="unit_guardians",
                support_entry_id="unit_support",
            )
        ],
    )


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


def test_build_army_blueprint_from_request_returns_blueprint_only() -> None:
    request = ArmyMusterRequest(
        faction="Space Marines",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_alpha",
                detachment_type="Gladius Task Force",
            )
        ],
    )

    blueprint = build_army_blueprint_from_request(request)

    assert blueprint.faction == "Space Marines"
    assert blueprint.primary_detachment_type == "Gladius Task Force"


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

    assert validated.blueprint.primary_detachment_type == "Gladius Task Force"
    assert len(validated.blueprint.unit_entries) == 1
    assert validated.blueprint.unit_entries[0].name == "Captain"
    assert validated.blueprint.unit_entries[0].is_warlord is True
    assert [item.enhancement_name for item in validated.blueprint.enhancement_assignments] == [
        "Honours of Battle"
    ]
    assert "legacy_single_detachment_adapter_used" not in validated.to_dict()


def test_muster_army_accepts_deserialized_request_dict_and_attaches_validated_muster(
    waha_helper: WahaHelper,
) -> None:
    request = ArmyMusterRequest(
        faction="Space Marines",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_alpha",
                detachment_type="Gladius Task Force",
            )
        ],
    )

    army = ArmyMusterer(waha_helper).muster_army(request.to_dict())

    assert army.detachment_type == "Gladius Task Force"
    assert army.get_detachment_types() == ["Gladius Task Force"]
    assert army.army_blueprint.primary_detachment_type == "Gladius Task Force"
    assert "legacy_single_detachment_adapter_used" not in army.validated_muster.to_dict()
    assert army.build_detachments[0].selection_id == "detachment_alpha"


def test_muster_army_materializes_runtime_units_and_stable_blueprint_hash(
    waha_helper: WahaHelper,
) -> None:
    request = _materialized_space_marines_request()

    army = ArmyMusterer(waha_helper).muster_army(request)
    units_by_entry_id = {
        str(getattr(unit, "get_build_entry_id", lambda: "")() or ""): unit
        for unit in list(army.units or [])
    }
    captain = units_by_entry_id["unit_captain"]
    bladeguard = units_by_entry_id["unit_bladeguard"]

    assert len(army.units) == 2
    assert army.get_detachment_types() == ["Gladius Task Force", "1st Company Task Force"]
    assert army.detachment_points_summary == {"budget": 5, "spent": 5, "remaining": 0}
    assert army.army_blueprint_hash == request.to_blueprint().army_blueprint_hash
    assert army.warlord is captain
    assert captain.enhancement is not None
    assert captain.enhancement.name == "Artificer Armour"
    assert bladeguard.name == "Bladeguard Veteran Squad"

    result = army.apply_authored_attachment_bindings()

    assert result == {"leader_bindings_applied": 1, "support_bindings_applied": 0}
    assert captain.attached_to is bladeguard
    assert bladeguard.attached_leaders == [captain]


@pytest.mark.parametrize(
    ("bodyguard_name", "bodyguard_count"),
    [
        ("Bloodcrushers", 3),
        ("Flesh Hounds", 5),
    ],
)
def test_validate_runtime_legality_accepts_disciple_of_khorne_attachment_override(
    waha_helper: WahaHelper,
    bodyguard_name: str,
    bodyguard_count: int,
) -> None:
    blueprint = ArmyBlueprint(
        faction="World Eaters",
        points_limit=2000,
        battle_size="Strike Force",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_khorne_daemonkin",
                detachment_type="Khorne Daemonkin",
            )
        ],
        unit_entries=[
            RosterEntry(
                entry_id="unit_lord_juggernaut",
                name="Lord on Juggernaut",
                count=1,
                detachment_selection_id="detachment_khorne_daemonkin",
            ),
            RosterEntry(
                entry_id="unit_bodyguard",
                name=bodyguard_name,
                count=bodyguard_count,
                detachment_selection_id="detachment_khorne_daemonkin",
            ),
            RosterEntry(
                entry_id="unit_master_of_executions",
                name="Master of Executions",
                count=1,
                detachment_selection_id="detachment_khorne_daemonkin",
                is_warlord=True,
            ),
        ],
        enhancement_assignments=[
            EnhancementAssignment(
                assignment_id="enhancement_disciple",
                enhancement_name="Disciple of Khorne",
                target_entry_id="unit_lord_juggernaut",
                detachment_selection_id="detachment_khorne_daemonkin",
            )
        ],
        attachment_bindings=[
            AttachmentBinding(
                binding_id="binding_disciple_override",
                bodyguard_entry_id="unit_bodyguard",
                leader_entry_id="unit_lord_juggernaut",
            )
        ],
    )

    army = ArmyMusterer(waha_helper).validate_runtime_legality(blueprint)
    units_by_entry_id = {
        str(getattr(unit, "get_build_entry_id", lambda: "")() or ""): unit
        for unit in list(army.units or [])
    }
    lord = units_by_entry_id["unit_lord_juggernaut"]
    bodyguard = units_by_entry_id["unit_bodyguard"]

    assert lord.has_disciple_of_khorne() is True
    assert lord.attached_to is bodyguard
    assert bodyguard.attached_leaders == [lord]
    assert lord.has_deep_strike() is True
    assert "blood legions" in {str(value).lower() for value in bodyguard.get_effective_faction_keywords()}
    assert "world eaters" not in {str(value).lower() for value in bodyguard.get_effective_faction_keywords()}


def test_bloodcrushers_resolve_curly_possessive_horn_alias(
    waha_helper: WahaHelper,
) -> None:
    blueprint = ArmyBlueprint(
        faction="World Eaters",
        points_limit=2000,
        battle_size="Strike Force",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_khorne_daemonkin",
                detachment_type="Khorne Daemonkin",
            )
        ],
        unit_entries=[
            RosterEntry(
                entry_id="unit_master_of_executions",
                name="Master of Executions",
                count=1,
                detachment_selection_id="detachment_khorne_daemonkin",
                is_warlord=True,
            ),
            RosterEntry(
                entry_id="unit_bloodcrushers",
                name="Bloodcrushers",
                count=3,
                detachment_selection_id="detachment_khorne_daemonkin",
                wargear=["3x Juggernaut\u2019s bladed horn"],
            ),
        ],
    )

    army = ArmyMusterer(waha_helper).validate_runtime_legality(blueprint)

    bloodcrushers = next(unit for unit in army.units if unit.name == "Bloodcrushers")
    assigned_names = [
        str(getattr(wargear, "name", "") or "")
        for model in list(bloodcrushers.models or [])
        for wargear in list(getattr(model, "wargear", []) or [])
    ]
    assert assigned_names.count("Bladed horn") == 3


def test_bloodcrushers_resolve_short_horn_alias_against_possessive_datasheet_name(
    waha_helper: WahaHelper,
) -> None:
    blueprint = ArmyBlueprint(
        faction="World Eaters",
        points_limit=2000,
        battle_size="Strike Force",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_khorne_daemonkin",
                detachment_type="Khorne Daemonkin",
            )
        ],
        unit_entries=[
            RosterEntry(
                entry_id="unit_master_of_executions",
                name="Master of Executions",
                count=1,
                detachment_selection_id="detachment_khorne_daemonkin",
                is_warlord=True,
            ),
            RosterEntry(
                entry_id="unit_bloodcrushers",
                name="Bloodcrushers",
                count=3,
                detachment_selection_id="detachment_khorne_daemonkin",
                wargear=["3x Bladed horn"],
            ),
        ],
    )

    army = ArmyMusterer(waha_helper).validate_runtime_legality(blueprint)

    bloodcrushers = next(unit for unit in army.units if unit.name == "Bloodcrushers")
    assigned_names = [
        str(getattr(wargear, "name", "") or "")
        for model in list(bloodcrushers.models or [])
        for wargear in list(getattr(model, "wargear", []) or [])
    ]
    assert assigned_names.count("Bladed horn") == 3


def test_muster_blueprint_materializes_authored_support_binding(
    waha_helper: WahaHelper,
) -> None:
    blueprint = _aeldari_support_blueprint()

    army = ArmyMusterer(waha_helper).muster_blueprint(blueprint)
    units_by_entry_id = {
        str(getattr(unit, "get_build_entry_id", lambda: "")() or ""): unit
        for unit in list(army.units or [])
    }
    support = units_by_entry_id["unit_support"]
    guardians = units_by_entry_id["unit_guardians"]

    result = army.apply_authored_attachment_bindings()

    assert len(army.units) == 2
    assert army.army_blueprint_hash == blueprint.army_blueprint_hash
    assert result == {"leader_bindings_applied": 0, "support_bindings_applied": 1}
    assert support.support_joined_to is guardians
    assert guardians.attached_support_units == [support]
