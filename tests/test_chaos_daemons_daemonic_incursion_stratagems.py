import unittest
from types import SimpleNamespace

import pytest

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_handlers.abilities import (
    _apply_select_realm_of_chaos_units,
    _validate_select_realm_of_chaos_units,
)
from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        inv_sv: str = "7",
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": str(inv_sv),
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    inv_sv: str = "7",
) -> Unit:
    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        inv_sv=inv_sv,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.round_state.shot_this_round = False
    unit.round_state.fought_this_round = False
    return unit


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(x, y, 0.0, 0.0)


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    daemon_army = Army("Chaos Daemons", "Daemonic Incursion")
    daemon_army.faction_id = "CD"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    daemon_player = Player("P1", control=PlayerControl.LOCAL, army=daemon_army)
    enemy_player = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)

    game.add_player(daemon_player)
    game.add_player(enemy_player)

    daemon_player.command_points = 3
    enemy_player.command_points = 3
    return game, daemon_player, enemy_player, daemon_army, enemy_army


class TestDaemonicIncursionStratagems(unittest.TestCase):
    def test_corrupt_realspace_breaks_only_on_turn_boundary(self):
        game, daemon_player, enemy_player, daemon_army, enemy_army = _build_game()
        daemon_unit = _make_unit(
            "Daemon",
            faction_keywords=["LEGIONES DAEMONICA"],
        )
        daemon_unit.is_within_objective_range = lambda _loc: True
        enemy_unit = _make_unit("Enemy")
        daemon_army.add_unit(daemon_unit)
        enemy_army.add_unit(enemy_unit)

        objective_point = ObjectivePoint(0.0, 0.0)
        objective_point.controlling_player = daemon_player
        objective = Objective(
            "Marker",
            ObjectiveCategory.PRIMARY,
            0,
            "",
            lambda _g: False,
            location=objective_point,
        )
        game.map.add_objective(objective)

        game.phase = SimpleNamespace(name="COMMAND_PHASE")
        game.current_player_index = 0
        ok = daemon_player.stratagems.use(
            "CORRUPT REALSPACE",
            unit=daemon_unit,
            objective=objective,
            phase_name="Command phase",
        )
        self.assertTrue(ok)
        self.assertEqual(objective_point.sticky_source, "corrupt_realspace")

        _deploy_unit(daemon_unit, 20.0, 20.0)
        _deploy_unit(enemy_unit, 0.0, 0.0)

        objective_point.update_control(game)
        self.assertIs(objective_point.sticky_controller, daemon_player)
        self.assertIs(objective_point.controlling_player, daemon_player)

        game._evaluate_corrupt_realspace_turn_boundary(timing="start", player=enemy_player)
        self.assertIs(objective_point.sticky_controller, None)
        self.assertIs(objective_point.controlling_player, enemy_player)


def test_daemonic_invulnerability_rerolls_invulnerable_ones(monkeypatch):
    game, daemon_player, enemy_player, daemon_army, enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Daemon",
        faction_keywords=["LEGIONES DAEMONICA"],
        inv_sv="4",
    )
    enemy_unit = _make_unit("Enemy")
    daemon_army.add_unit(daemon_unit)
    enemy_army.add_unit(enemy_unit)

    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    game.current_player_index = 1

    ok = daemon_player.stratagems.use(
        "DAEMONIC INVULNERABILITY",
        unit=daemon_unit,
        phase_name="Shooting phase",
    )
    assert ok is True

    rolls = iter([1, 4])

    def rigged(_expr):
        return next(rolls)

    import warhammer40k_ai.utility.dice as dice_mod
    import warhammer40k_ai.units.wargear as wargear_mod

    monkeypatch.setattr(dice_mod, "get_roll", rigged)
    monkeypatch.setattr(wargear_mod, "get_roll", rigged)

    weapon = Wargear(
        {
            "name": "Test Blaster",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "-3",
            "D": "1",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]
    save_result = profile._save_with_tracking(daemon_unit.models[0], {}, -3)

    assert save_result.get("save_type") == "invulnerable"
    assert save_result.get("reroll") == 4
    assert save_result.get("reroll_of_one") == 1
    assert any("Daemonic Invulnerability" in effect for effect in save_result.get("special_effects", []))


def test_denizens_of_the_warp_sets_min_distance_and_expires():
    game, daemon_player, _enemy_player, daemon_army, _enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Daemon",
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    daemon_unit.special_rules = {"bearer_unit_deep_strike": True}
    daemon_unit._ability_cache = {}
    daemon_unit.reserve_status = "reserves"
    daemon_unit.deployed = False
    daemon_army.add_unit(daemon_unit)

    game.turn = 2
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
    game.current_player_index = 0

    ok = daemon_player.stratagems.use(
        "DENIZENS OF THE WARP",
        unit=daemon_unit,
        phase_name="Movement phase",
    )
    assert ok is True
    assert daemon_unit.get_deep_strike_min_distance_override() == 6.0

    game.event_system.publish("phase_end", player=daemon_player, phase=game.phase)
    assert daemon_unit.get_deep_strike_min_distance_override() is None


def test_draught_of_terror_ap_bonus_and_battleshock_rerolls():
    game, daemon_player, _enemy_player, daemon_army, enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Daemon",
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy")
    daemon_army.add_unit(daemon_unit)
    enemy_army.add_unit(enemy_unit)

    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    game.current_player_index = 0

    ok = daemon_player.stratagems.use(
        "DRAUGHT OF TERROR",
        unit=daemon_unit,
        phase_name="Shooting phase",
    )
    assert ok is True

    weapon = Wargear(
        {
            "name": "Test Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]
    ap_val = profile.get_effective_ap(daemon_unit.models[0], enemy_unit)
    assert ap_val == -1

    effect = BattleShockEffect(current_turn=1)
    effect.apply_battle_shock(enemy_unit)
    enemy_unit.status_effects.append(effect)

    wound_result = profile._wound_target_with_tracking(
        enemy_unit,
        daemon_unit.models[0],
        {},
        roll_value=4,
        allow_rerolls=True,
        log_roll=False,
    )
    assert "Draught of Terror" in wound_result.get("reroll_full_reasons", [])


def test_realm_of_chaos_allows_two_units_within_shadow(monkeypatch):
    game, daemon_player, enemy_player, daemon_army, _enemy_army = _build_game()
    unit_a = _make_unit("Daemon A", faction_keywords=["LEGIONES DAEMONICA"])
    unit_b = _make_unit("Daemon B", faction_keywords=["LEGIONES DAEMONICA"])
    daemon_army.add_unit(unit_a)
    daemon_army.add_unit(unit_b)

    game.map.place_unit(unit_a)
    game.map.place_unit(unit_b)

    game.phase = SimpleNamespace(name="END_OF_TURN")
    game.current_player_index = 1

    monkeypatch.setattr(daemon_player.stratagems, "_unit_within_shadow_of_chaos", lambda _u: True)

    ok = daemon_player.stratagems.use(
        "THE REALM OF CHAOS",
        units=[unit_a, unit_b],
    )
    assert ok is True
    assert unit_a.reserve_status == "strategic_reserves"
    assert unit_b.reserve_status == "strategic_reserves"
    assert unit_a.has_deep_strike() is True
    assert unit_b.has_deep_strike() is True


def test_warp_surge_grants_advance_and_charge_and_expires(monkeypatch):
    game, daemon_player, _enemy_player, daemon_army, _enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Daemon",
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    daemon_army.add_unit(daemon_unit)

    game.phase = SimpleNamespace(name="CHARGE_PHASE")
    game.current_player_index = 0

    monkeypatch.setattr(daemon_player.stratagems, "_unit_within_shadow_of_chaos", lambda _u: True)

    ok = daemon_player.stratagems.use(
        "WARP SURGE",
        unit=daemon_unit,
        phase_name="Charge phase",
    )
    assert ok is True
    assert daemon_unit.can_charge_after_advance() is True

    game.event_system.publish("phase_end", player=daemon_player, phase=game.phase)
    assert daemon_unit.can_charge_after_advance() is False


def test_realm_of_chaos_decision_validation():
    game, daemon_player, _enemy_player, daemon_army, _enemy_army = _build_game()
    unit_a = _make_unit("Daemon A", faction_keywords=["LEGIONES DAEMONICA"])
    unit_b = _make_unit("Daemon B", faction_keywords=["LEGIONES DAEMONICA"])
    daemon_army.add_unit(unit_a)
    daemon_army.add_unit(unit_b)
    game.rebuild_entity_registry()

    uid_a = get_entity_id(unit_a)
    uid_b = get_entity_id(unit_b)

    option = DecisionOption.create("Select units")
    request = DecisionRequest.create(
        decision_type=DECISION_SELECT_REALM_OF_CHAOS_UNITS,
        prompt="Select units",
        player_id=daemon_player.id,
        options=[option],
        context={
            "allowed_unit_ids": [uid_a, uid_b],
            "outside_shadow_unit_ids": [],
            "max_units": 2,
        },
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=daemon_player.id,
        option_id=option.option_id,
        payload={"unit_ids": [uid_a, uid_b]},
    )

    errors = _validate_select_realm_of_chaos_units(game, request, result)
    assert errors == ()
    selected = _apply_select_realm_of_chaos_units(game, request, result)
    assert set(selected) == {unit_a, unit_b}

    request.context["outside_shadow_unit_ids"] = [uid_b]
    errors = _validate_select_realm_of_chaos_units(game, request, result)
    assert errors == ("Only one unit can be selected if it is outside the Shadow of Chaos.",)
