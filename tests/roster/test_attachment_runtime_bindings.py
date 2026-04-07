from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.decision_requests import (
    build_leader_attachment_requests,
    build_support_artillery_attachment_requests,
)
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.army_attachments import AttachmentBinding
from warhammer40k_ai.roster.army_build import RosterEntry
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit


class _DummyPlayer:
    def __init__(self, name: str = "P1") -> None:
        self.name = name
        self.game = None


class _DummyDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        *,
        abilities=None,
        attached_to=None,
        attached_to_names=None,
        keywords=None,
    ) -> None:
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "TestFaction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.datasheets_unit_composition = []
        self.datasheets_models_cost = []
        self.datasheets_wargear = []
        self.datasheets_options = []
        self.datasheets_abilities = []
        self.attached_to = list(attached_to or [])
        self.attached_to_names = list(attached_to_names or [])
        self.transport = ""
        self.damaged_w = ""
        self.damaged_description = ""
        self.abilities_override = list(abilities or [])


class _TestUnit(Unit):
    def _parse_unit_composition(self, _data):
        return {"TestModel": 1}

    def _create_models(self, datasheet, quantity=None):
        class _M:
            def __init__(self, model_name: str) -> None:
                self.is_alive = True
                self.wounds = 1
                self._base_wounds = 1
                self.name = model_name
                self.leadership = 7
                self.objective_control = 1
                self.movement = 6
                self.toughness = 4
                self._toughness = 4
                self.save = 3
                self.inv_save = None
                self._pending_placement = False
                self.model_base = None
                self.abilities = []

        n = 1 if quantity is None else int(quantity)
        return [_M("M") for _ in range(n)]

    def _parse_models_cost(self, _data):
        return {1: 100}

    def _parse_wargear(self, _datasheet):
        return []

    def _parse_wargear_options(self, _datasheet):
        return

    def _parse_abilities(self, datasheet):
        return list(getattr(datasheet, "abilities_override", []) or [])

    def add_wargear(self):
        return


def _make_army(units: list[Unit]) -> Army:
    army = Army.with_detachment(faction="Test", detachment_type="Test", points_limit=2000)
    army.player = _DummyPlayer()
    for unit in units:
        army.add_unit(unit)
    return army


def _leader_unit() -> _TestUnit:
    return _TestUnit(
        _DummyDatasheet(
            "Captain",
            "L1",
            attached_to=["BG1"],
            attached_to_names=["Bladeguard Veteran Squad"],
            keywords=["Character", "Captain"],
        )
    )


def _bodyguard_unit() -> _TestUnit:
    return _TestUnit(_DummyDatasheet("Bladeguard Veteran Squad", "BG1", keywords=["Infantry"]))


def _support_artillery_unit() -> _TestUnit:
    ability = Ability(
        "SUPPORT ARTILLERY",
        "",
        "At the start of the Declare Battle Formations step, this model can join one Guardian Defenders unit from your army "
        "(a unit cannot have more than one Support Weapon model joined to it).",
        "",
        "",
    )
    return _TestUnit(_DummyDatasheet("D-cannon Platform", "S1", abilities=[ability]))


def _guardian_bodyguard_unit() -> _TestUnit:
    return _TestUnit(_DummyDatasheet("Guardian Defenders", "G1", keywords=["Infantry"]))


def _loyal_protector_unit() -> _TestUnit:
    ability = Ability(
        "LOYAL PROTECTOR",
        "",
        "At the start of the Declare Battle Formations step, this unit must join one Command Squad unit from your army "
        "(a unit cannot have more than one Loyal Protector model joined to it).",
        "",
        "",
    )
    return _TestUnit(_DummyDatasheet("Loyal Protector", "LP1", abilities=[ability]))


def _command_squad_unit() -> _TestUnit:
    return _TestUnit(_DummyDatasheet("Cadian Command Squad", "CS1", keywords=["Infantry", "Command Squad"]))


def test_authored_leader_binding_applies_to_runtime_setup_and_skips_prompt() -> None:
    leader = _leader_unit()
    bodyguard = _bodyguard_unit()
    army = _make_army([leader, bodyguard])
    leader.set_build_entry_id("leader")
    bodyguard.set_build_entry_id("bodyguard")
    army.build_unit_entries = [
        RosterEntry(entry_id="leader", name="Captain"),
        RosterEntry(entry_id="bodyguard", name="Bladeguard Veteran Squad"),
    ]
    army.attachment_bindings = [
        AttachmentBinding(
            binding_id="binding_1",
            bodyguard_entry_id="bodyguard",
            leader_entry_id="leader",
        )
    ]

    result = army.apply_authored_attachment_bindings()

    assert result == {"leader_bindings_applied": 1, "support_bindings_applied": 0}
    assert leader.attached_to is bodyguard
    assert bodyguard.attached_leaders == [leader]
    assert leader.has_build_authored_leader_attachment() is True
    assert build_leader_attachment_requests(object(), army.units, queue_requests=False) == []


def test_authored_support_binding_applies_to_runtime_setup_and_skips_prompt() -> None:
    support = _support_artillery_unit()
    bodyguard = _guardian_bodyguard_unit()
    army = _make_army([support, bodyguard])
    support.set_build_entry_id("support")
    bodyguard.set_build_entry_id("bodyguard")
    army.build_unit_entries = [
        RosterEntry(entry_id="support", name="D-cannon Platform"),
        RosterEntry(entry_id="bodyguard", name="Guardian Defenders"),
    ]
    army.attachment_bindings = [
        AttachmentBinding(
            binding_id="binding_1",
            bodyguard_entry_id="bodyguard",
            support_entry_id="support",
        )
    ]

    result = army.apply_authored_attachment_bindings()

    assert result == {"leader_bindings_applied": 0, "support_bindings_applied": 1}
    assert support.support_joined_to is bodyguard
    assert bodyguard.attached_support_units == [support]
    assert support.has_build_authored_support_attachment() is True
    assert build_support_artillery_attachment_requests(object(), army.units, queue_requests=False) == []


def test_support_without_bodyguard_fails_clearly_during_runtime_validation() -> None:
    support = _loyal_protector_unit()
    bodyguard = _command_squad_unit()
    army = _make_army([support, bodyguard])

    with pytest.raises(
        ArmyValidationError,
        match="or be supplied by an authored attachment binding",
    ):
        army.validate_support_artillery()


def test_bodyguard_death_detaches_leader_but_preserves_surviving_character_unit() -> None:
    leader = _leader_unit()
    bodyguard = _bodyguard_unit()
    army = _make_army([leader, bodyguard])
    leader.attach_to_unit(bodyguard)
    game_map = SimpleNamespace(units=[bodyguard])

    bodyguard.begin_attack_resolution()
    for model in list(bodyguard.models or []):
        bodyguard.remove_model(model, game_map=game_map)
    bodyguard.end_attack_resolution(game_map=game_map)

    assert leader.attached_to is None
    assert leader in game_map.units
    assert bodyguard not in game_map.units
    assert len(leader.models) == 1
