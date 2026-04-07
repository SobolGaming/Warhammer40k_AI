import pytest

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, Wargear


class MockDatasheet:
    def __init__(self, name: str, keywords=None, movement=6, model_count=1, base_size="32mm", save="4", wounds="5"):
        self.name = name
        self.faction_data = {"name": "Chaos Daemons"}
        self.keywords = keywords or []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [{
            "M": str(movement), "T": "4", "Sv": str(save), "W": str(wounds),
            "Ld": "7", "OC": "1",
            "base_size": base_size, "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


class ShadowStub:
    def __init__(self, within: bool):
        self.within = within

    def is_unit_within_shadow(self, unit, game=None) -> bool:
        return self.within


def _make_daemonic_army(within_shadow: bool):
    army = Army.with_detachment("Chaos Daemons", "Daemonic Incursion")
    army.faction_id = "CD"
    army.shadow_of_chaos = ShadowStub(within_shadow)
    player = Player("P1", PlayerControl.LOCAL, army)
    return army, player


def _make_unit(within_shadow: bool) -> Unit:
    army, _player = _make_daemonic_army(within_shadow)
    unit = Unit(MockDatasheet("Test Daemon", model_count=1))
    unit.deployed = True
    army.add_unit(unit)
    return unit


def _attack_result(profile_name="Test Weapon"):
    return AttackResult(
        weapon_name=profile_name,
        attacker_name="Attacker",
        target_unit_name="Target",
        attacks_rolled=0,
        attacks_dice_expression="1",
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


def test_argath_melee_bonuses_respect_shadow(monkeypatch):
    unit = _make_unit(within_shadow=False)
    enh = Enhancement(
        id="000008438002",
        name="A'rgath, the King of Blades",
        faction_id="CD",
        detachment="Daemonic Incursion",
    )
    enh.apply_to_unit(unit)

    weapon = Wargear({
        "name": "Test Sword",
        "type": "Melee",
        "range": "Melee",
        "A": "1",
        "BS_WS": "3",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    })
    profile = weapon.profiles["default"]
    attacker = unit.models[0]
    target = SimpleNamespace(toughness=5, models=[SimpleNamespace(is_alive=True)])

    result = profile._resolve_attack_count(
        target,
        attacker,
        _attack_result(),
        publish_roll_event=False,
    )
    assert result.num_attacks == 2

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _expr: 4)
    res = profile._wound_target_with_tracking(target, attacker, attack_instance={})
    assert res["wound"] is True

    unit_shadow = _make_unit(within_shadow=True)
    enh.apply_to_unit(unit_shadow)
    attacker_shadow = unit_shadow.models[0]
    result_shadow = profile._resolve_attack_count(
        target,
        attacker_shadow,
        _attack_result(),
        publish_roll_event=False,
    )
    assert result_shadow.num_attacks == 3

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _expr: 3)
    res_shadow = profile._wound_target_with_tracking(target, attacker_shadow, attack_instance={})
    assert res_shadow["wound"] is True


def test_everstave_ranged_bonuses_respect_shadow(monkeypatch):
    unit = _make_unit(within_shadow=False)
    enh = Enhancement(
        id="000008438005",
        name="The Everstave",
        faction_id="CD",
        detachment="Daemonic Incursion",
    )
    enh.apply_to_unit(unit)

    weapon = Wargear({
        "name": "Test Bolt",
        "type": "Ranged",
        "range": "24",
        "A": "1",
        "BS_WS": "3",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    })
    profile = weapon.profiles["default"]
    attacker = unit.models[0]

    assert profile._effective_range_max(attacker) == 27

    target = SimpleNamespace(toughness=5, models=[SimpleNamespace(is_alive=True)])
    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _expr: 4)
    res = profile._wound_target_with_tracking(target, attacker, attack_instance={})
    assert res["wound"] is True

    unit_shadow = _make_unit(within_shadow=True)
    enh.apply_to_unit(unit_shadow)
    attacker_shadow = unit_shadow.models[0]
    assert profile._effective_range_max(attacker_shadow) == 30

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _expr: 3)
    res_shadow = profile._wound_target_with_tracking(target, attacker_shadow, attack_instance={})
    assert res_shadow["wound"] is True


def test_endless_gift_applies_fnp_entry():
    unit = _make_unit(within_shadow=False)
    enh = Enhancement(
        id="000008438004",
        name="The Endless Gift",
        faction_id="CD",
        detachment="Daemonic Incursion",
        description="Nurgle Legiones Daemonica model only. The bearer has the Feel No Pain 5+ ability.",
    )
    enh.apply_to_unit(unit)

    entries = unit.special_rules.get("enhancement_bearer_fnp_entries", [])
    assert any(int(entry.get("value", 0)) == 5 for entry in entries if isinstance(entry, dict))


def test_soulstealer_heals_on_melee_kill_with_shadow_bonus(monkeypatch):
    from warhammer40k_ai.utility import dice as dice_mod

    monkeypatch.setattr(dice_mod, "get_roll", lambda _expr: 3)

    bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army = Army.with_detachment("Chaos Daemons", "Daemonic Incursion")
    army.faction_id = "CD"
    army.shadow_of_chaos = ShadowStub(True)
    p1 = Player("P1", PlayerControl.LOCAL, army)

    p2 = Player("P2", PlayerControl.REMOTE, Army.with_detachment("Army B", "Detachment B"))
    game.add_player(p1)
    game.add_player(p2)

    attacker = Unit(MockDatasheet("Attacker", model_count=1))
    attacker.deployed = True
    target = Unit(MockDatasheet("Target", model_count=1))
    target.deployed = True

    p1.army.add_unit(attacker)
    p2.army.add_unit(target)

    enh = Enhancement(
        id="000008438003",
        name="Soulstealer",
        faction_id="CD",
        detachment="Daemonic Incursion",
    )
    enh.apply_to_unit(attacker)

    attacker_model = attacker.models[0]
    attacker_model._wounds = attacker_model._base_wounds - 1

    melee_weapon = Wargear({
        "name": "Test Claws",
        "type": "Melee",
        "range": "Melee",
        "A": "1",
        "BS_WS": "3",
        "S": "6",
        "AP": "0",
        "D": "1",
        "description": "",
    })
    profile = melee_weapon.profiles["default"]

    game._on_model_destroyed_rules(
        attacker_model=attacker_model,
        attacker_unit=attacker,
        target_model=target.models[0],
        target_unit=target,
        weapon_profile=profile,
    )

    assert attacker_model.wounds == attacker_model._base_wounds
