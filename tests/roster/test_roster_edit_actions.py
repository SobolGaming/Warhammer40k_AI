from __future__ import annotations

from warhammer40k_ai.roster.army_attachments import AttachmentBinding
from warhammer40k_ai.roster.army_build import (
    ArmyBlueprint,
    DetachmentSelection,
    EnhancementAssignment,
    RosterEntry,
)
from warhammer40k_ai.roster.roster_edit_actions import (
    AddUnitEntryAction,
    AssignEnhancementAction,
    BindAttachmentAction,
    ChangeWargearChoiceAction,
    MutateForceDispositionAction,
    RebalanceDetachmentPointSpendAction,
    RemoveUnitEntryAction,
    SelectWarlordAction,
    apply_roster_edit_action,
)


def _seed_blueprint() -> ArmyBlueprint:
    return ArmyBlueprint(
        faction="Space Marines",
        points_limit=2000,
        battle_size="Strike Force",
        detachments=[
            DetachmentSelection(
                selection_id="det_gladius",
                detachment_type="Gladius Task Force",
                detachment_points_cost=2,
            )
        ],
        detachment_points_budget=5,
        unit_entries=[
            RosterEntry(
                entry_id="entry_captain",
                name="Captain",
                count=1,
                detachment_selection_id="det_gladius",
            ),
            RosterEntry(
                entry_id="entry_intercessors",
                name="Intercessor Squad",
                count=5,
                detachment_selection_id="det_gladius",
            ),
        ],
        allowed_force_dispositions=["Assault", "Siege"],
    )


def test_edit_actions_update_blueprint_and_keep_related_state_in_sync() -> None:
    blueprint = _seed_blueprint()

    blueprint = apply_roster_edit_action(
        blueprint,
        AssignEnhancementAction(
            EnhancementAssignment(
                assignment_id="enh_1",
                enhancement_name="Artificer Armour",
                target_entry_id="entry_captain",
                detachment_selection_id="det_gladius",
            )
        ),
    )
    blueprint = apply_roster_edit_action(
        blueprint,
        SelectWarlordAction(entry_id="entry_captain"),
    )
    blueprint = apply_roster_edit_action(
        blueprint,
        ChangeWargearChoiceAction(
            entry_id="entry_intercessors",
            wargear=("Astartes grenade launcher",),
        ),
    )
    blueprint = apply_roster_edit_action(
        blueprint,
        BindAttachmentAction(
            AttachmentBinding(
                binding_id="binding_1",
                bodyguard_entry_id="entry_intercessors",
                leader_entry_id="entry_captain",
            )
        ),
    )

    captain = next(entry for entry in blueprint.unit_entries if entry.entry_id == "entry_captain")
    intercessors = next(entry for entry in blueprint.unit_entries if entry.entry_id == "entry_intercessors")
    assert captain.is_warlord is True
    assert captain.enhancement_names == ["Artificer Armour"]
    assert intercessors.wargear == ["Astartes grenade launcher"]
    assert blueprint.attachment_bindings[0].leader_entry_id == "entry_captain"


def test_remove_unit_entry_cleans_related_enhancements_and_bindings() -> None:
    blueprint = _seed_blueprint()
    blueprint = apply_roster_edit_action(
        blueprint,
        AssignEnhancementAction(
            EnhancementAssignment(
                assignment_id="enh_1",
                enhancement_name="Artificer Armour",
                target_entry_id="entry_captain",
                detachment_selection_id="det_gladius",
            )
        ),
    )
    blueprint = apply_roster_edit_action(
        blueprint,
        BindAttachmentAction(
            AttachmentBinding(
                binding_id="binding_1",
                bodyguard_entry_id="entry_intercessors",
                leader_entry_id="entry_captain",
            )
        ),
    )

    updated = apply_roster_edit_action(
        blueprint,
        RemoveUnitEntryAction(entry_id="entry_captain"),
    )

    assert [entry.entry_id for entry in updated.unit_entries] == ["entry_intercessors"]
    assert updated.enhancement_assignments == []
    assert updated.attachment_bindings == []


def test_detachment_rebalance_and_force_disposition_actions_have_stable_ids() -> None:
    rebalance = RebalanceDetachmentPointSpendAction(
        selection_costs={"det_gladius": 3},
        detachment_points_budget=6,
    )
    mutate = MutateForceDispositionAction(
        force_disposition="Siege",
        allowed_force_dispositions=("Assault", "Siege"),
    )

    first_id = rebalance.action_id
    second_id = RebalanceDetachmentPointSpendAction(
        selection_costs={"det_gladius": 3},
        detachment_points_budget=6,
    ).action_id

    blueprint = apply_roster_edit_action(_seed_blueprint(), rebalance)
    blueprint = apply_roster_edit_action(blueprint, mutate)
    blueprint = apply_roster_edit_action(
        blueprint,
        AddUnitEntryAction(
            RosterEntry(
                entry_id="entry_bladeguard",
                name="Bladeguard Veteran Squad",
                count=3,
                detachment_selection_id="det_gladius",
            )
        ),
    )

    assert first_id == second_id
    assert blueprint.detachment_points_budget == 6
    assert blueprint.detachments[0].detachment_points_cost == 3
    assert blueprint.force_disposition == "Siege"
    assert blueprint.allowed_force_dispositions == ["Assault", "Siege"]
    assert [entry.entry_id for entry in blueprint.unit_entries][-1] == "entry_bladeguard"
