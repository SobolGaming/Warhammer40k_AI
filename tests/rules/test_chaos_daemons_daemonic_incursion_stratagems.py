import logging
import unittest
from types import SimpleNamespace

import pytest

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_handlers.abilities import (
    _apply_select_realm_of_chaos_units,
    _validate_select_realm_of_chaos_units,
)
from warhammer40k_ai.engine.decision_handlers.movement import _validate_pick_objective
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_PICK_OBJECTIVE,
    DECISION_SELECT_REALM_OF_CHAOS_UNITS,
)
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
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

    daemon_army = Army.with_detachment("Chaos Daemons", "Daemonic Incursion")
    daemon_army.faction_id = "CD"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    daemon_player = Player("P1", control=PlayerControl.LOCAL, army=daemon_army)
    enemy_player = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)

    game.add_player(daemon_player)
    game.add_player(enemy_player)

    daemon_player.command_points = 3
    enemy_player.command_points = 3
    return game, daemon_player, enemy_player, daemon_army, enemy_army


def _find_request(game: Game, decision_type: str, *, ability: str) -> DecisionRequest | None:
    queue = getattr(game, "decision_queue", None)
    if queue is None or not hasattr(queue, "list"):
        return None
    for request in list(queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != str(ability):
            continue
        return request
    return None


def _find_option(request: DecisionRequest, **expected_payload) -> DecisionOption | None:
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if all(payload.get(key) == value for key, value in dict(expected_payload or {}).items()):
            return option
    return None


def _pending_by_name(manager, name: str):
    for reaction in list(getattr(manager, "_pending_reactions", []) or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == str(name or "").strip().upper():
            return reaction
    return None


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

    def test_corrupt_realspace_queues_decisions_and_applies_selected_objective(self):
        game, daemon_player, _enemy_player, daemon_army, _enemy_army = _build_game()
        daemon_unit = _make_unit(
            "Daemon",
            faction_keywords=["LEGIONES DAEMONICA"],
        )
        daemon_army.add_unit(daemon_unit)

        objective_a = Objective(
            "Marker A",
            ObjectiveCategory.PRIMARY,
            0,
            "",
            lambda _g: False,
            location=ObjectivePoint(0.0, 0.0),
        )
        objective_b = Objective(
            "Marker B",
            ObjectiveCategory.PRIMARY,
            1,
            "",
            lambda _g: False,
            location=ObjectivePoint(12.0, 0.0),
        )
        objective_a.location.controlling_player = daemon_player
        objective_b.location.controlling_player = daemon_player
        game.map.add_objective(objective_a)
        game.map.add_objective(objective_b)
        game.rebuild_entity_registry()

        daemon_player.stratagems._daemon_incursion_battlefield_unit_candidates = lambda: [daemon_unit]
        daemon_player.stratagems._corrupting_taint_objective_candidates = lambda _unit: [objective_a, objective_b]

        game.phase = SimpleNamespace(name="COMMAND_PHASE")
        game.current_player_index = 0
        daemon_player.stratagems._on_phase_start(player=daemon_player, phase=game.phase)

        pending = _pending_by_name(daemon_player.stratagems, "CORRUPT REALSPACE")
        self.assertIsNotNone(pending)

        request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="corrupt_realspace")
        self.assertIsNotNone(request)
        skip_option = _find_option(request, action="skip")
        unit_option = _find_option(request, target_unit_id=str(get_entity_id(daemon_unit) or ""))
        self.assertIsNotNone(skip_option)
        self.assertIsNotNone(unit_option)

        result = resolve_decision_command(game, request, unit_option.option_id, player_id=daemon_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        objective_request = _find_request(game, DECISION_PICK_OBJECTIVE, ability="corrupt_realspace")
        self.assertIsNotNone(objective_request)
        objective_option = _find_option(objective_request, objective_id=str(get_entity_id(objective_b) or ""))
        self.assertIsNotNone(objective_option)

        objective_result = resolve_decision_command(game, objective_request, objective_option.option_id, player_id=daemon_player.id)
        self.assertTrue(bool(getattr(objective_result, "ok", False)))
        self.assertEqual(int(daemon_player.command_points or 0), 2)
        self.assertEqual(objective_b.location.sticky_source, "corrupt_realspace")
        self.assertIs(objective_b.location.sticky_controller, daemon_player)
        self.assertIsNone(_pending_by_name(daemon_player.stratagems, "CORRUPT REALSPACE"))

    def test_corrupt_realspace_objective_validation_rejects_non_candidate(self):
        game, daemon_player, _enemy_player, daemon_army, _enemy_army = _build_game()
        daemon_unit = _make_unit(
            "Daemon",
            faction_keywords=["LEGIONES DAEMONICA"],
        )
        daemon_army.add_unit(daemon_unit)

        objective_a = Objective(
            "Marker A",
            ObjectiveCategory.PRIMARY,
            0,
            "",
            lambda _g: False,
            location=ObjectivePoint(0.0, 0.0),
        )
        objective_b = Objective(
            "Marker B",
            ObjectiveCategory.PRIMARY,
            1,
            "",
            lambda _g: False,
            location=ObjectivePoint(12.0, 0.0),
        )
        objective_a.location.controlling_player = daemon_player
        objective_b.location.controlling_player = daemon_player
        game.map.add_objective(objective_a)
        game.map.add_objective(objective_b)
        game.rebuild_entity_registry()

        request = DecisionRequest.create(
            DECISION_PICK_OBJECTIVE,
            "Corrupt Realspace objective selection",
            player_id=daemon_player.id,
            options=[
                DecisionOption.create(
                    "Marker A",
                    payload={
                        "objective_id": str(get_entity_id(objective_a) or ""),
                        "unit_id": str(get_entity_id(daemon_unit) or ""),
                        "source_unit_id": str(get_entity_id(daemon_unit) or ""),
                    },
                )
            ],
            context={
                "ability": "corrupt_realspace",
                "ability_name": "CORRUPT REALSPACE",
                "phase_name": "Command phase",
                "unit_id": str(get_entity_id(daemon_unit) or ""),
                "source_unit_id": str(get_entity_id(daemon_unit) or ""),
                "candidate_objective_ids": [str(get_entity_id(objective_a) or "")],
            },
        )
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=daemon_player.id,
            option_id=request.options[0].option_id,
            payload={"objective_id": str(get_entity_id(objective_b) or "")},
        )

        errors = _validate_pick_objective(game, request, result)
        self.assertEqual(errors, ("Corrupt Realspace selected objective marker is not in this request's candidate list.",))


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


def test_denizens_of_the_warp_phase_only_context_is_not_available():
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

    stratagem = daemon_player.stratagems.get_by_name("DENIZENS OF THE WARP")
    availability = daemon_player.stratagems._evaluate_availability(
        stratagem,
        {"phase_name": "Movement phase"},
        is_active_turn=True,
    )

    assert availability["available"] is False
    assert availability["reason"] == "Requires valid trigger or target"


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


def test_draught_of_terror_logs_at_info_not_error(caplog):
    game, daemon_player, _enemy_player, daemon_army, _enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Flesh Hounds",
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    daemon_army.add_unit(daemon_unit)

    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    game.current_player_index = 0

    with caplog.at_level(logging.INFO, logger="warhammer40k_ai.rules.stratagems"):
        ok = daemon_player.stratagems.use(
            "DRAUGHT OF TERROR",
            unit=daemon_unit,
            phase_name="Shooting phase",
        )

    assert ok is True
    draught_records = [
        record
        for record in list(caplog.records or [])
        if "DRAUGHT OF TERROR:" in str(record.getMessage() or "")
    ]
    assert draught_records
    assert all(record.levelno == logging.INFO for record in draught_records)


def test_warp_surge_phase_only_context_is_not_available():
    game, daemon_player, _enemy_player, daemon_army, _enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Daemon",
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    daemon_army.add_unit(daemon_unit)

    game.phase = SimpleNamespace(name="CHARGE_PHASE")
    game.current_player_index = 0

    daemon_player.stratagems._unit_within_shadow_of_chaos = lambda unit: unit is daemon_unit
    stratagem = daemon_player.stratagems.get_by_name("WARP SURGE")
    availability = daemon_player.stratagems._evaluate_availability(
        stratagem,
        {"phase_name": "Charge phase"},
        is_active_turn=True,
    )

    assert availability["available"] is False
    assert availability["reason"] == "Requires valid trigger or target"


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
