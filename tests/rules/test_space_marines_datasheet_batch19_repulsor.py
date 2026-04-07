from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_DECLARE_CHARGE,
    DECISION_DISEMBARK,
    DECISION_REQUEST_DICE_ROLL,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.auto_resolve_dice_rolls = False
    charging_army = Army.with_detachment("Chargers", detachment_type="Other")
    charging_army.faction_id = "EN"
    space_marines_army = Army.with_detachment("Space Marines", detachment_type="Other")
    space_marines_army.faction_id = "SM"
    charging_player = Player("Chargers", control=PlayerControl.LOCAL, army=charging_army)
    space_marines_player = Player("Space Marines", control=PlayerControl.LOCAL, army=space_marines_army)
    game.add_player(charging_player)
    game.add_player(space_marines_player)
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.turn = 1
    return game, charging_army, space_marines_army, charging_player, space_marines_player


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _find_request(game: Game, decision_type: str, *, ability: str | None = None, reason: str | None = None):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if ability is not None and str(ctx.get("ability", "") or "") != str(ability):
            continue
        if reason is not None and str(ctx.get("charge_retarget_reason", "") or "") != str(reason):
            continue
        return request
    return None


def _find_option(request, *, target_unit_id: str | None = None, transport_id: str | None = None, action: str | None = None):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if target_unit_id is not None and str(payload.get("target_unit_id", "") or "") != str(target_unit_id):
            continue
        if transport_id is not None and str(payload.get("transport_id", "") or "") != str(transport_id):
            continue
        if action is not None and str(payload.get("action", "") or "") != str(action):
            continue
        return option
    return None


def test_repulsor_emergency_combat_embarkation_embarks_target_and_retargets_charge() -> None:
    game, charging_army, sm_army, charging_player, sm_player = _build_game()
    charger = _actual_unit("Outrider Squad", datasheet_id="000002712")
    repulsor = _actual_unit("Repulsor", datasheet_id="000002721")
    target = _actual_unit("Intercessor Squad", datasheet_id="000001157")
    replacement = _actual_unit("Scout Squad", datasheet_id="000001160")
    charging_army.add_unit(charger)
    sm_army.add_unit(repulsor)
    sm_army.add_unit(target)
    sm_army.add_unit(replacement)
    _deploy(charger, 0.0, 0.0)
    _deploy(repulsor, 11.0, 0.0)
    _deploy(target, 8.8, 0.0)
    _deploy(replacement, 8.5, 7.0)
    game.map.units = [charger, repulsor, target, replacement]
    game.rebuild_entity_registry()
    game.map.is_path_blocked = lambda *_args, **_kwargs: False

    declared = game.declare_charge(charger, [target])

    assert declared is not None
    assert bool(declared.get("charge_pending", False)) is True
    assert charger.round_state.attempted_charge_this_round is False
    assert _find_request(game, DECISION_REQUEST_DICE_ROLL) is None

    embark_request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="emergency_combat_embarkation")
    assert embark_request is not None
    embark_option = _find_option(
        embark_request,
        target_unit_id=str(get_entity_id(target) or ""),
        transport_id=str(get_entity_id(repulsor) or ""),
    )
    assert embark_option is not None

    embark_result = resolve_decision_command(game, embark_request, embark_option.option_id, player_id=sm_player.id)
    assert bool(getattr(embark_result, "ok", False)) is True
    assert target.embarked_in is repulsor
    assert target in list(getattr(repulsor, "transport_passengers", []) or [])
    assert charger.round_state.attempted_charge_this_round is False

    retarget_request = _find_request(game, DECISION_DECLARE_CHARGE, reason="emergency_combat_embarkation")
    assert retarget_request is not None
    replacement_id = str(get_entity_id(replacement) or "")
    replacement_option = _find_option(retarget_request, target_unit_id=replacement_id)
    assert replacement_option is not None
    assert _find_option(retarget_request, target_unit_id=str(get_entity_id(target) or "")) is None

    retarget_result = resolve_decision_command(
        game,
        retarget_request,
        replacement_option.option_id,
        result_payload={"target_unit_ids": [replacement_id]},
        player_id=charging_player.id,
    )
    assert bool(getattr(retarget_result, "ok", False)) is True
    assert charger.round_state.attempted_charge_this_round is True
    assert charger.round_state.charge_target_ids == {replacement_id}

    roll_request = _find_request(game, DECISION_REQUEST_DICE_ROLL)
    assert roll_request is not None
    roll_ctx = dict(getattr(roll_request, "context", {}) or {})
    roll_spec = dict(roll_ctx.get("roll_spec", {}) or {})
    assert list(roll_spec.get("target_unit_ids", []) or []) == [replacement_id]


def test_repulsor_emergency_combat_embarkation_cancels_charge_when_no_targets_remain() -> None:
    game, charging_army, sm_army, _charging_player, sm_player = _build_game()
    charger = _actual_unit("Outrider Squad", datasheet_id="000002712")
    repulsor = _actual_unit("Repulsor", datasheet_id="000002721")
    target = _actual_unit("Intercessor Squad", datasheet_id="000001157")
    charging_army.add_unit(charger)
    sm_army.add_unit(repulsor)
    sm_army.add_unit(target)
    _deploy(charger, 0.0, 0.0)
    _deploy(repulsor, 11.0, 0.0)
    _deploy(target, 8.8, 0.0)
    game.map.units = [charger, repulsor, target]
    game.rebuild_entity_registry()
    game.map.is_path_blocked = lambda _unit, target_unit, *_args, **_kwargs: target_unit is repulsor

    declared = game.declare_charge(charger, [target])

    assert declared is not None
    assert bool(declared.get("charge_pending", False)) is True

    embark_request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="emergency_combat_embarkation")
    assert embark_request is not None
    embark_option = _find_option(
        embark_request,
        target_unit_id=str(get_entity_id(target) or ""),
        transport_id=str(get_entity_id(repulsor) or ""),
    )
    assert embark_option is not None

    embark_result = resolve_decision_command(game, embark_request, embark_option.option_id, player_id=sm_player.id)
    assert bool(getattr(embark_result, "ok", False)) is True
    assert target.embarked_in is repulsor
    assert charger.round_state.attempted_charge_this_round is False
    assert not list(getattr(charger.round_state, "charge_target_ids", set()) or [])
    assert _find_request(game, DECISION_DECLARE_CHARGE, reason="emergency_combat_embarkation") is None
    assert _find_request(game, DECISION_REQUEST_DICE_ROLL) is None


def test_repulsor_emergency_combat_embarkation_skip_continues_original_charge() -> None:
    game, charging_army, sm_army, charging_player, sm_player = _build_game()
    charger = _actual_unit("Outrider Squad", datasheet_id="000002712")
    repulsor = _actual_unit("Repulsor", datasheet_id="000002721")
    target = _actual_unit("Intercessor Squad", datasheet_id="000001157")
    charging_army.add_unit(charger)
    sm_army.add_unit(repulsor)
    sm_army.add_unit(target)
    _deploy(charger, 0.0, 0.0)
    _deploy(repulsor, 11.0, 0.0)
    _deploy(target, 8.8, 0.0)
    game.map.units = [charger, repulsor, target]
    game.rebuild_entity_registry()
    game.map.is_path_blocked = lambda *_args, **_kwargs: False

    declared = game.declare_charge(charger, [target])

    assert declared is not None
    embark_request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="emergency_combat_embarkation")
    assert embark_request is not None
    skip_option = _find_option(embark_request, action="skip")
    assert skip_option is not None

    skip_result = resolve_decision_command(game, embark_request, skip_option.option_id, player_id=sm_player.id)
    assert bool(getattr(skip_result, "ok", False)) is True
    assert target.embarked_in is None
    assert charger.round_state.attempted_charge_this_round is True
    assert charger.round_state.charge_target_ids == {str(get_entity_id(target) or "")}

    roll_request = _find_request(game, DECISION_REQUEST_DICE_ROLL)
    assert roll_request is not None
    roll_ctx = dict(getattr(roll_request, "context", {}) or {})
    roll_spec = dict(roll_ctx.get("roll_spec", {}) or {})
    assert list(roll_spec.get("target_unit_ids", []) or []) == [str(get_entity_id(target) or "")]


def test_repulsor_stabilised_disembarkation_parses_extended_reactive_disembark() -> None:
    repulsor = _actual_unit("Repulsor", datasheet_id="000002791")

    specs = repulsor.unit_stabilised_disembarkation_specs()

    assert specs == [
        {
            "source": "Stabilised Disembarkation",
            "disembark_max_distance": 6,
        }
    ]


def test_repulsor_stabilised_disembarkation_queues_after_targeted_shooting_and_allows_six_inch_disembark() -> None:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 1

    attacking_army = Army.with_detachment("Attackers", detachment_type="Other")
    attacking_army.faction_id = "EN"
    space_marines_army = Army.with_detachment("Space Marines", detachment_type="Other")
    space_marines_army.faction_id = "SM"
    attacking_player = Player("Attackers", control=PlayerControl.LOCAL, army=attacking_army)
    space_marines_player = Player("Space Marines", control=PlayerControl.LOCAL, army=space_marines_army)
    game.add_player(attacking_player)
    game.add_player(space_marines_player)
    game.current_player_index = 0

    attacker = _actual_unit("Outrider Squad", datasheet_id="000002712")
    repulsor = _actual_unit("Repulsor", datasheet_id="000002791")
    passenger = _actual_unit("Captain", datasheet_id="000000073")
    attacking_army.add_unit(attacker)
    space_marines_army.add_unit(repulsor)
    space_marines_army.add_unit(passenger)
    _deploy(attacker, 0.0, 0.0)
    _deploy(repulsor, 20.0, 20.0)
    game.map.units = [attacker, repulsor]
    game.rebuild_entity_registry()

    assert repulsor.add_passenger(passenger, game_map=game.map)
    passenger.round_state.embarked_this_round = False

    game.event_system.publish(
        "shooting_targets_selected",
        attacking_unit=attacker,
        target_units=[repulsor],
        weapon_declarations=[],
    )
    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=attacker,
        hits_by_target={},
    )

    disembark_request = _find_request(game, DECISION_DISEMBARK)
    assert disembark_request is not None
    disembark_ctx = dict(getattr(disembark_request, "context", {}) or {})
    assert float(disembark_ctx.get("disembark_max_distance", 0) or 0) == 6.0
    assert str(disembark_ctx.get("reactive_disembark_source", "") or "") == "Stabilised Disembarkation"
    assert str(disembark_ctx.get("reactive_disembark_enemy_unit_id", "") or "") == str(get_entity_id(attacker) or "")

    passenger_id = str(get_entity_id(passenger) or "")
    disembark_option = None
    for option in list(getattr(disembark_request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("unit_id", "") or "") == passenger_id and payload.get("transport_id") is not None:
            disembark_option = option
            break
    assert disembark_option is not None

    passenger_model = passenger.models[0]
    disembark_result = resolve_decision_command(
        game,
        disembark_request,
        disembark_option.option_id,
        player_id=space_marines_player.id,
        result_payload={
            "model_positions": [
                {
                    "model_id": str(get_entity_id(passenger_model) or ""),
                    "position": [26.0, 20.0, 0.0],
                    "facing": 0.0,
                }
            ]
        },
    )

    assert bool(getattr(disembark_result, "ok", False)) is True
    assert passenger.embarked_in is None
    assert passenger.round_state.disembarked_this_round is True
    location = passenger_model.get_location()
    assert location[0] == 26.0
