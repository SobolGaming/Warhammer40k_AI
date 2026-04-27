from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_handlers.movement import validate_move_unit_payload
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, move: str = "12"):
        slug = str(name or "unit").lower().replace(" ", "-")
        self.id = f"mock-{slug}"
        self.name = name
        self.faction_data = {"name": "Orks"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ORKS"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(move),
                "T": "6",
                "Sv": "4",
                "W": "8",
                "Ld": "7",
                "OC": "2",
                "base_size": "75x42mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _unit(name: str, *, keywords=None, faction_keywords=None, move: str = "12") -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords, move=move))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _place(game: Game, unit: Unit, x: float, y: float, facing: float = 0.0) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, float(facing))
    if unit not in game.map.units:
        game.map.units.append(unit)


def _ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Dakkagun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Profile",
        wargear_data={
            "range": "24",
            "A": "3",
            "BS_WS": "5+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
    game.auto_resolve_dice_rolls = True
    ork_army = Army.with_detachment("Orks", "Speedwaaagh!")
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    ork_player = Player("Ork Player", control=PlayerControl.REMOTE, army=ork_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, ork_player, ork_army, enemy_army


def _turbo_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == "orks_speedwaaagh_turbo_boostas":
            return request
    return None


def _option_with_choice(request, choice: bool):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if bool(payload.get("choice", False)) is bool(choice):
            return option
    return None


def _move_request(unit: Unit, player_id: str):
    unit_id = str(get_entity_id(unit) or "")
    return DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move unit",
        player_id=player_id,
        options=[DecisionOption.create("Move", payload={"unit_id": unit_id, "movement_type": "advance"})],
        context={"unit_id": unit_id, "movement_type": "advance"},
    )


def test_turbo_boostas_queues_optional_advance_choice_and_applies_turn_effects():
    game, ork_player, army, enemy_army = _build_game()
    warbikers = _unit("Warbikers", keywords=["MOUNTED", "SPEED FREEKS"], faction_keywords=["ORKS"], move="12")
    aircraft = _unit("Dakkajet", keywords=["VEHICLE", "AIRCRAFT", "SPEED FREEKS"], faction_keywords=["ORKS"], move="20")
    enemy = _unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], move="6")
    army.add_unit(warbikers)
    army.add_unit(aircraft)
    enemy_army.add_unit(enemy)
    _place(game, warbikers, 0.0, 0.0)
    _place(game, aircraft, 0.0, 12.0)
    _place(game, enemy, 8.0, 0.0)
    game.rebuild_entity_registry()

    mgr = army.orks_detachments
    assert mgr.speedwaaagh_turbo_boostas_eligible(warbikers) is True
    assert mgr.speedwaaagh_turbo_boostas_eligible(aircraft) is False

    request = mgr.queue_speedwaaagh_turbo_boostas_choice(warbikers, game=game, player=ork_player)
    assert request is _turbo_request(game)
    assert _option_with_choice(request, True) is not None
    assert _option_with_choice(request, False) is not None

    selected = _option_with_choice(request, True)
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=ork_player.id,
        option_id=selected.option_id,
        payload={},
    )
    applied = dispatch_decision(game, request, result)
    assert applied.ok is True

    effect = warbikers._get_advance_no_roll_effect()
    assert effect["source"] == "Turbo Boostas"
    assert effect["move_characteristic"] == 24
    assert warbikers.round_state.advance_roll == 0
    assert warbikers.can_shoot_after_advance(_ranged_profile()) is True

    warbikers.round_state.advanced_this_round = True
    warbikers.special_rules["pain_charge_after_advance"] = True
    assert warbikers.can_charge_after_advance() is True
    assert warbikers.can_declare_charge(game) is False


def test_turbo_boostas_move_validation_enforces_twenty_four_inches_and_no_pivot():
    game, ork_player, army, _enemy_army = _build_game()
    trukk = _unit("Trukk", keywords=["VEHICLE", "TRANSPORT", "TRUKK"], faction_keywords=["ORKS"], move="12")
    army.add_unit(trukk)
    _place(game, trukk, 0.0, 0.0, facing=0.0)
    game.rebuild_entity_registry()
    assert army.orks_detachments.apply_speedwaaagh_turbo_boostas_choice(
        trukk,
        use_turbo=True,
        game=game,
        player=ork_player,
    )

    model_id = str(get_entity_id(trukk.models[0]) or "")
    request = _move_request(trukk, ork_player.id)
    option_payload = {"unit_id": str(get_entity_id(trukk) or ""), "movement_type": "advance"}
    legal = [{"model_id": model_id, "position": [24.0, 0.0, 0.0], "facing": 0.0}]
    too_far = [{"model_id": model_id, "position": [24.1, 0.0, 0.0], "facing": 0.0}]
    pivot = [{"model_id": model_id, "position": [12.0, 0.0, 0.0], "facing": 45.0}]

    assert validate_move_unit_payload(
        game,
        request,
        option_payload=option_payload,
        result_payload={"movement_type": "advance", "model_positions": legal},
    ) == ()
    too_far_errors = validate_move_unit_payload(
        game,
        request,
        option_payload=option_payload,
        result_payload={"movement_type": "advance", "model_positions": too_far},
    )
    assert any("cannot exceed 24" in str(error) for error in too_far_errors)
    pivot_errors = validate_move_unit_payload(
        game,
        request,
        option_payload=option_payload,
        result_payload={"movement_type": "advance", "model_positions": pivot},
    )
    assert any("cannot pivot" in str(error) for error in pivot_errors)
