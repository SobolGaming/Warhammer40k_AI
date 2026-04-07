import pytest

from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.army_attachments import AttachmentBinding
from warhammer40k_ai.roster.army_build import DetachmentSelection, RosterEntry
from warhammer40k_ai.roster.army_muster import ArmyMusterRequest, ArmyMusterer
from warhammer40k_ai.roster.army_runtime import DetachmentInstance, apply_validated_muster_to_army
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.waha_helper import WahaHelper


@pytest.fixture(scope="module")
def waha_helper() -> WahaHelper:
    return WahaHelper()


def _build_multi_detachment_request() -> ArmyMusterRequest:
    return ArmyMusterRequest(
        faction="Space Marines",
        points_limit=2000,
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
                detachment_selection_id="detachment_alpha",
            ),
            RosterEntry(
                entry_id="unit_bladeguard",
                name="Bladeguard Veterans",
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
        allowed_force_dispositions=["Assault", "Bulwark"],
    )


class _DummyUnit:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, upgrade_tags=None):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.upgrade_tags = list(upgrade_tags or [])
        self.special_rules = {}
        self.enhancement = None
        self._parent_army = None

    @property
    def is_character(self) -> bool:
        return any(str(value).strip().upper() == "CHARACTER" for value in list(self.keywords or []))

    @property
    def is_epic_hero(self) -> bool:
        return any(str(value).strip().upper() == "EPIC HERO" for value in list(self.keywords or []))

    def get_effective_keywords(self):
        return list(self.keywords or [])

    def get_effective_faction_keywords(self):
        return list(self.faction_keywords or [])

    def set_parent_army(self, army):
        self._parent_army = army

    def get_parent_army(self):
        return self._parent_army


def _build_runtime_multi_detachment_army(waha_helper: WahaHelper) -> Army:
    muster = ArmyMusterer(waha_helper)
    validated = muster.validate_request(_build_multi_detachment_request())
    army = Army(
        faction=validated.blueprint.faction,
        points_limit=validated.blueprint.points_limit,
    )
    army.faction_id = validated.faction_id
    return apply_validated_muster_to_army(army, validated)


def test_muster_army_builds_runtime_detachment_instances_and_summary(waha_helper: WahaHelper) -> None:
    army = _build_runtime_multi_detachment_army(waha_helper)

    assert [item.detachment_type for item in army.detachments] == [
        "Gladius Task Force",
        "1st Company Task Force",
    ]
    assert army.get_primary_detachment_type() == "Gladius Task Force"
    assert army.detachment_points_summary == {"budget": 5, "spent": 5, "remaining": 0}
    assert army.attachment_bindings[0].binding_id == "binding_1"
    assert army.force_disposition == "Assault"


def test_detachment_rule_lookup_uses_runtime_detachment_instances(waha_helper: WahaHelper) -> None:
    army = _build_runtime_multi_detachment_army(waha_helper)

    manager = army.get_detachment_manager_for_detachment_instance(army.detachments[1])
    assert manager is army.space_marines_detachments
    assert manager.detachment_matches("1st Company Task Force") is True
    assert [item.selection_id for item in manager.get_matching_detachment_instances("1st Company Task Force")] == [
        "detachment_beta"
    ]

    stratagem = Stratagem(
        id="test_stratagem",
        name="Secondary Detachment Stratagem",
        type="Battle Tactic",
        description="Test",
        cp_cost=1,
        turn="",
        phase="Command phase",
        detachment="1st Company Task Force",
        faction_id="SM",
    )
    assert stratagem.applies_to_army(army) is True


def test_runtime_detachment_dicts_are_normalized_back_to_instances() -> None:
    army = Army.with_detachment("Space Marines", "Gladius Task Force")
    army.faction_id = "SM"
    army.detachments = [
        {
            "instance_id": "detachment_instance_1",
            "selection_id": "detachment_alpha",
            "faction_id": "SM",
            "detachment_type": "Gladius Task Force",
            "detachment_points_cost": 2,
            "metadata": {"source": "snapshot"},
        }
    ]

    detachment = army.get_primary_detachment_instance()

    assert isinstance(detachment, DetachmentInstance)
    assert detachment.selection_id == "detachment_alpha"
    assert detachment.metadata["source"] == "snapshot"


def test_primary_detachment_property_is_read_only_view_over_runtime_detachment_instances() -> None:
    army = Army.with_detachment("Space Marines", "Gladius Task Force")
    army.faction_id = "SM"

    assert army.get_detachment_types() == ["Gladius Task Force"]
    assert army.get_primary_detachment_instance().faction_id == "SM"

    army.build_detachments[0].detachment_type = "1st Company Task Force"
    army.detachments[0].detachment_type = "1st Company Task Force"

    assert army.detachment_type == "1st Company Task Force"
    assert army.get_detachment_types() == ["1st Company Task Force"]
    assert army.get_primary_detachment_instance().detachment_type == "1st Company Task Force"
    with pytest.raises(AttributeError):
        army.detachment_type = "Gladius Task Force"


def test_constructor_starts_detachment_free_until_runtime_state_is_attached() -> None:
    army = Army("Space Marines")

    assert army.detachment_type == ""
    assert army.get_detachment_types() == []
    assert army.get_primary_detachment_instance() is None


def test_with_detachment_seeds_primary_detachment_for_single_detachment_flows() -> None:
    army = Army.with_detachment("Space Marines", "Gladius Task Force")

    assert army.detachment_type == "Gladius Task Force"
    assert army.get_detachment_types() == ["Gladius Task Force"]
    assert army.get_primary_detachment_instance() is not None


def test_upgrade_tag_enhancement_can_target_eligible_non_character_unit() -> None:
    army = Army.with_detachment("Space Marines", "Gladius Task Force")
    army.faction_id = "SM"
    unit = _DummyUnit(
        "Sternguard Veterans",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        upgrade_tags=["auxiliary_wargear"],
    )
    army.add_unit(unit)
    enhancement = Enhancement(
        id="upgrade_tag_1",
        name="Auxiliary Wargear",
        faction_id="SM",
        detachment="Gladius Task Force",
        points=15,
        eligible_upgrade_tags=("auxiliary_wargear",),
    )

    army.add_enhancement(
        enhancement,
        unit,
        assignment_metadata={"upgrade_tag": "auxiliary_wargear"},
    )

    assert unit.enhancement is enhancement
    assert unit.special_rules["enhancement_upgrade_tag"] == "auxiliary_wargear"


def test_upgrade_tag_enhancement_rejects_non_matching_non_character_unit() -> None:
    army = Army.with_detachment("Space Marines", "Gladius Task Force")
    army.faction_id = "SM"
    unit = _DummyUnit(
        "Sternguard Veterans",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        upgrade_tags=["auxiliary_wargear"],
    )
    army.add_unit(unit)
    enhancement = Enhancement(
        id="upgrade_tag_2",
        name="Auxiliary Wargear",
        faction_id="SM",
        detachment="Gladius Task Force",
        points=15,
        eligible_upgrade_tags=("heavy_upgrade",),
    )

    with pytest.raises(ArmyValidationError, match="non-Epic Hero Characters"):
        army.add_enhancement(
            enhancement,
            unit,
            assignment_metadata={"upgrade_tag": "heavy_upgrade"},
        )
