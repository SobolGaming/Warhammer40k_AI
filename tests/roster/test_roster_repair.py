from __future__ import annotations

import pytest

from warhammer40k_ai.roster.army_build import ArmyBlueprint, DetachmentSelection, EnhancementAssignment, RosterEntry
from warhammer40k_ai.roster.roster_repair import validate_blueprint_runtime_legality
from warhammer40k_ai.waha_helper import WahaHelper


@pytest.fixture(scope="module")
def waha_helper() -> WahaHelper:
    return WahaHelper()


def _space_marines_blueprint() -> ArmyBlueprint:
    return ArmyBlueprint(
        faction="Space Marines",
        points_limit=2000,
        battle_size="Strike Force",
        detachments=[
            DetachmentSelection(
                selection_id="det_gladius",
                detachment_type="Gladius Task Force",
            )
        ],
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


def test_runtime_legality_validation_repairs_missing_warlord_with_real_muster_path(
    waha_helper: WahaHelper,
) -> None:
    blueprint = _space_marines_blueprint()

    result = validate_blueprint_runtime_legality(
        blueprint,
        waha_helper=waha_helper,
    )

    assert result.is_valid is True
    assert "selected repaired warlord entry_captain" in result.repairs
    captain = next(entry for entry in result.repaired_blueprint.unit_entries if entry.entry_id == "entry_captain")
    assert captain.is_warlord is True
    assert result.runtime_summary["warlord_entry_id"] == "entry_captain"


def test_runtime_legality_validation_rejects_duplicate_non_battleline_datasheets(
    waha_helper: WahaHelper,
) -> None:
    blueprint = ArmyBlueprint(
        faction="Space Marines",
        points_limit=2000,
        detachments=[
            DetachmentSelection(
                selection_id="det_gladius",
                detachment_type="Gladius Task Force",
            )
        ],
        unit_entries=[
            RosterEntry(entry_id="captain_1", name="Captain", count=1, detachment_selection_id="det_gladius", is_warlord=True),
            RosterEntry(entry_id="captain_2", name="Captain", count=1, detachment_selection_id="det_gladius"),
            RosterEntry(entry_id="captain_3", name="Captain", count=1, detachment_selection_id="det_gladius"),
            RosterEntry(entry_id="captain_4", name="Captain", count=1, detachment_selection_id="det_gladius"),
        ],
    )

    result = validate_blueprint_runtime_legality(
        blueprint,
        waha_helper=waha_helper,
    )

    assert result.is_valid is False
    assert "exceeds the limit of 3" in result.issues[0].message


def test_runtime_legality_validation_rejects_invalid_enhancement_assignment(
    waha_helper: WahaHelper,
) -> None:
    blueprint = _space_marines_blueprint()
    blueprint.unit_entries[0].is_warlord = True
    blueprint.enhancement_assignments = [
        EnhancementAssignment(
            assignment_id="enh_invalid",
            enhancement_name="Artificer Armour",
            target_entry_id="entry_intercessors",
            detachment_selection_id="det_gladius",
        )
    ]

    result = validate_blueprint_runtime_legality(
        blueprint,
        waha_helper=waha_helper,
    )

    assert result.is_valid is False
    assert "Enhancements can only be assigned" in result.issues[0].message


def test_runtime_legality_validation_checks_optional_wargear_choices(
    waha_helper: WahaHelper,
) -> None:
    valid_blueprint = _space_marines_blueprint()
    valid_blueprint.unit_entries[0].is_warlord = True
    valid_blueprint.unit_entries[1].wargear = ["Astartes grenade launcher"]

    valid_result = validate_blueprint_runtime_legality(
        valid_blueprint,
        waha_helper=waha_helper,
    )

    invalid_blueprint = _space_marines_blueprint()
    invalid_blueprint.unit_entries[0].is_warlord = True
    invalid_blueprint.unit_entries[1].wargear = ["Laser banana"]
    invalid_result = validate_blueprint_runtime_legality(
        invalid_blueprint,
        waha_helper=waha_helper,
    )

    assert valid_result.is_valid is True
    assert invalid_result.is_valid is False
    assert "Could not resolve wargear option" in invalid_result.issues[0].message
