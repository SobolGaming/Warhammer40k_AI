from types import SimpleNamespace
import types

import pytest

from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit as UnitClass
from warhammer40k_ai.units.wargear import Wargear, WargearProfile
from warhammer40k_ai.utility.model_base import Base, BaseType


class DummyPlayer:
    def __init__(self, name="Player", has_control=False):
        self.name = name
        self._has_control = has_control

    def has_control(self):
        return bool(self._has_control)


class DummyArmy:
    def __init__(self, player):
        self.player = player


class DummyUnit:
    def __init__(self, name, *, models=None, toughness=4, keywords=None, parent_army=None):
        self.name = name
        self._id = name
        self.models = list(models or [])
        self.toughness = toughness
        self.special_rules = {}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.attached_leaders = []
        self.parent_army = parent_army
        self.round_state = SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False)

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self

    def get_models_for_wound_allocation(self):
        return [m for m in self.models if getattr(m, "is_alive", True)]

    def get_models_for_collision(self):
        models = list(self.models)
        for leader in self.attached_leaders:
            models.extend(getattr(leader, "models", []) or [])
        return models

    def has_keyword(self, keyword):
        kw = (keyword or "").strip().lower()
        return kw and any(kw == k.lower() for k in (self.keywords or []))

    def has_keyword_local(self, keyword):
        return self.has_keyword(keyword)

    def has_stealth(self):
        return False

    def has_feel_no_pain(self):
        return []

    def is_alive(self):
        alive = any(getattr(m, "is_alive", False) for m in (self.models or []))
        for leader in self.attached_leaders:
            alive = alive or any(getattr(m, "is_alive", False) for m in (getattr(leader, "models", []) or []))
        return alive


def _make_model(name, wounds, parent_unit):
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=wounds,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = parent_unit
    return model


def _attach_mortal_helpers(unit):
    unit._player_has_local_control = types.MethodType(UnitClass._player_has_local_control, unit)
    unit._apply_mortal_wounds_to_unit = types.MethodType(UnitClass._apply_mortal_wounds_to_unit, unit)
    unit._resolve_pending_attack_mortal_wounds = types.MethodType(
        UnitClass._resolve_pending_attack_mortal_wounds, unit
    )


def test_devastating_wounds_no_spillover(monkeypatch):
    weapon = Wargear(
        {
            "name": "Test Dev",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "2+",
            "S": "6",
            "AP": "0",
            "D": "2",
            "description": "Devastating Wounds",
        }
    )
    prof = weapon.profiles["default"]

    attacker_player = DummyPlayer("Attacker")
    attacker_army = DummyArmy(attacker_player)
    attacker_unit = DummyUnit("Attacker", parent_army=attacker_army)
    _attach_mortal_helpers(attacker_unit)
    attacker_model = _make_model("Attacker", 3, attacker_unit)
    attacker_model.return_closest_model_in_unit = lambda _unit: (None, 0.0)
    attacker_unit.models = [attacker_model]

    target_player = DummyPlayer("Target")
    target_army = DummyArmy(target_player)
    target_unit = DummyUnit("Target", parent_army=target_army)
    wounded = _make_model("Wounded", 2, target_unit)
    wounded.wounds = 1
    fresh = _make_model("Fresh", 1, target_unit)
    target_unit.models = [wounded, fresh]

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _s: 6)

    prof.attack(target_unit, attacker_model, game_map=None)

    assert not wounded.is_alive
    assert fresh.is_alive


def test_mortal_wounds_in_addition_spillover_even_if_saved(monkeypatch):
    weapon = Wargear(
        {
            "name": "Extra Mortals",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "2+",
            "S": "6",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    prof = weapon.profiles["default"]

    attacker_player = DummyPlayer("Attacker")
    attacker_army = DummyArmy(attacker_player)
    attacker_unit = DummyUnit("Attacker", parent_army=attacker_army)
    _attach_mortal_helpers(attacker_unit)
    attacker_model = _make_model("Attacker", 3, attacker_unit)
    attacker_model.return_closest_model_in_unit = lambda _unit: (None, 0.0)
    attacker_unit.models = [attacker_model]

    target_player = DummyPlayer("Target")
    target_army = DummyArmy(target_player)
    target_unit = DummyUnit("Target", parent_army=target_army)
    t1 = _make_model("T1", 1, target_unit)
    t2 = _make_model("T2", 1, target_unit)
    target_unit.models = [t1, t2]

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _s: 6)

    original_wound = prof._wound_target_with_tracking

    def _wound_with_extra(target, attacker, attack_instance):
        result = original_wound(target, attacker, attack_instance)
        if result.get("wound"):
            attack_instance["mortal_wound_in_addition"] = True
            attack_instance["mortal_wound_amount"] = 2
        return result

    def _save_stub(_target_model, _attack_instance, _ap):
        return {
            "saved": True,
            "roll": 6,
            "needed": 3,
            "save_type": "armor",
            "base_save": 3,
            "ap_modifier": 0,
            "final_save": 3,
            "special_effects": [],
        }

    monkeypatch.setattr(prof, "_wound_target_with_tracking", _wound_with_extra)
    monkeypatch.setattr(prof, "_save_with_tracking", _save_stub)

    prof.attack(target_unit, attacker_model, game_map=None)

    assert not t1.is_alive
    assert not t2.is_alive


def test_deferred_mortal_wounds_across_weapons(monkeypatch):
    dev_weapon = Wargear(
        {
            "name": "Dev Gun",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "2+",
            "S": "6",
            "AP": "0",
            "D": "1",
            "description": "Devastating Wounds",
        }
    )
    normal_weapon = Wargear(
        {
            "name": "Normal Gun",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "2+",
            "S": "6",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    dev_prof = dev_weapon.profiles["default"]
    normal_prof = normal_weapon.profiles["default"]

    attacker_player = DummyPlayer("Attacker")
    attacker_army = DummyArmy(attacker_player)
    attacker_unit = DummyUnit("Attacker", parent_army=attacker_army)
    _attach_mortal_helpers(attacker_unit)
    attacker_model = _make_model("Attacker", 3, attacker_unit)
    attacker_model.return_closest_model_in_unit = lambda _unit: (None, 0.0)
    attacker_unit.models = [attacker_model]

    target_player = DummyPlayer("Target")
    target_army = DummyArmy(target_player)
    target_unit = DummyUnit("Target", parent_army=target_army)
    target_model = _make_model("Target", 3, target_unit)
    target_unit.models = [target_model]

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _s: 6)

    damage_order = []

    def _damage_stub(_target_model, _attacker, attack_instance, game_map=None):
        damage_order.append("mortal" if attack_instance.get("mortal_wound", False) else "normal")
        return {
            "damage_rolled": 1,
            "damage_applied": 1,
            "target_model": getattr(_target_model, "name", "Target"),
            "excess_damage": 0,
            "model_killed": False,
            "fnp_saves": 0,
            "fnp_rolls": [],
            "damage_dice_rolls": [],
            "damage_expression": "1",
            "special_effects": [],
        }

    def _save_fail(_target_model, _attack_instance, _ap):
        return {
            "saved": False,
            "roll": 1,
            "needed": 3,
            "save_type": "armor",
            "base_save": 3,
            "ap_modifier": 0,
            "final_save": 3,
            "special_effects": [],
        }

    dev_prof._damage_target_with_tracking = _damage_stub
    normal_prof._damage_target_with_tracking = _damage_stub
    normal_prof._save_with_tracking = _save_fail

    attack_context = {"pending_mortal_wounds": {}, "defer_mortal_wounds": True}
    dev_prof.attack(target_unit, attacker_model, game_map=None, attack_context=attack_context)
    normal_prof.attack(target_unit, attacker_model, game_map=None, attack_context=attack_context)
    WargearProfile.resolve_pending_mortal_wounds_for_target(
        attack_context["pending_mortal_wounds"], target_unit, game_map=None
    )

    assert damage_order == ["normal", "mortal"]


def test_precision_allocates_mortal_wounds_to_character(monkeypatch):
    weapon = Wargear(
        {
            "name": "Precision Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "2+",
            "S": "6",
            "AP": "0",
            "D": "2",
            "description": "Devastating Wounds, Precision",
        }
    )
    prof = weapon.profiles["default"]

    attacker_player = DummyPlayer("Attacker")
    attacker_army = DummyArmy(attacker_player)
    attacker_unit = DummyUnit("Attacker", parent_army=attacker_army)
    _attach_mortal_helpers(attacker_unit)
    attacker_model = _make_model("Attacker", 3, attacker_unit)
    attacker_model.return_closest_model_in_unit = lambda _unit: (None, 0.0)
    attacker_unit.models = [attacker_model]

    target_player = DummyPlayer("Target")
    target_army = DummyArmy(target_player)
    bodyguard_unit = DummyUnit("Bodyguard", parent_army=target_army)
    leader_unit = DummyUnit("Leader", parent_army=target_army, keywords=["Character"])
    bodyguard = _make_model("Bodyguard", 3, bodyguard_unit)
    leader = _make_model("Leader", 3, leader_unit)
    bodyguard_unit.models = [bodyguard]
    leader_unit.models = [leader]
    bodyguard_unit.attached_leaders = [leader_unit]

    class DummyMap:
        def __init__(self, chosen):
            self.precision_allocation_provider = lambda _attacker, _root, _chars, _wp: chosen

        def can_model_see_model(self, _attacker, _model):
            return True

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _s: 6)

    game_map = DummyMap(leader)
    prof.attack(bodyguard_unit, attacker_model, game_map=game_map)

    assert leader.wounds == 1
    assert bodyguard.wounds == 3
