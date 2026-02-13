from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _ConvergenceDatasheet:
    def __init__(self):
        self.id = "000002361"
        self.name = "Convergence Of Dominion"
        self.faction_data = {"name": "Necrons"}
        self.keywords = ["Fortification"]
        self.faction_keywords = ["NECRONS"]
        self.datasheets_unit_composition = [{"description": "1-3 Convergence of Dominion Starsteles"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 180}]
        self.datasheets_models = [
            {
                "M": "0",
                "T": "8",
                "Sv": "3",
                "W": "5",
                "Ld": "6",
                "OC": "3",
                "base_size": "80mm",
                "inv_sv": "4",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {
                "ability_data": {
                    "name": "DEPLOYMENT",
                    "faction_id": "NEC",
                    "description": (
                        "When this unit is first set up on the battlefield, its models do not have to be set up in Unit Coherency. "
                        "Instead, each model must be set up wholly within 12\" of one other model from its unit. "
                        "From that point on, each model in this unit is treated as a separate unit."
                    ),
                    "legend": "",
                },
                "type": "Special",
                "parameter": "",
            }
        ]
        self.loadout = "This model is equipped with: transdimensional abductor."


def _build_game_with_convergence(quantity: int = 3) -> tuple[Game, Player, Army, Unit]:
    necron_army = Army("Necrons", "Hypercrypt Legion")
    enemy_army = Army("Space Marines", "Gladius Task Force")

    necron_player = Player("Necrons", PlayerControl.LOCAL, army=necron_army)
    enemy_player = Player("Enemy", PlayerControl.LOCAL, army=enemy_army)
    necron_army.set_player(necron_player)
    enemy_army.set_player(enemy_player)

    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[necron_player, enemy_player])
    unit = Unit(_ConvergenceDatasheet(), quantity=quantity)
    necron_army.add_unit(unit)
    game.rebuild_entity_registry()
    game.is_valid_single_model_deployment = (
        lambda _model, _x, _y, _z, _player_id: {"valid": True, "reason": "ok"}
    )
    return game, necron_player, necron_army, unit


def _build_deployment_request(game: Game, player: Player, unit: Unit) -> DecisionRequest:
    unit_id = get_entity_id(unit)
    options = [
        DecisionOption.create(
            "Confirm",
            payload={"unit_id": unit_id, "movement_type": "deploy", "action": "confirm"},
        )
    ]
    context = {
        "unit_id": unit_id,
        "movement_type": "deploy",
        "placement_kind": "deployment",
        "allowed_model_ids": [get_entity_id(model) for model in list(unit.models or [])],
        "allow_skip": False,
    }
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Deploy Convergence Of Dominion",
        player_id=player.id,
        options=options,
        context=context,
    )
    game.request_decision(request)
    return request


def _deployment_payload(unit: Unit, positions: list[tuple[float, float, float]]) -> dict:
    payload_positions = []
    for model, position in zip(list(unit.models or []), positions):
        payload_positions.append(
            {
                "model_id": get_entity_id(model),
                "position": [float(position[0]), float(position[1]), float(position[2])],
                "facing": 0.0,
            }
        )
    return {"model_positions": payload_positions}


def test_convergence_deployment_requires_12_inch_model_chain():
    game, player, army, unit = _build_game_with_convergence(quantity=3)
    request = _build_deployment_request(game, player, unit)
    option_id = request.options[0].option_id

    result = resolve_decision_command(
        game,
        request,
        option_id,
        result_payload=_deployment_payload(
            unit,
            [
                (10.0, 10.0, 0.0),
                (24.0, 10.0, 0.0),
                (50.0, 10.0, 0.0),
            ],
        ),
        player_id=player.id,
    )

    assert result.ok is False
    errors = [str(err or "").lower() for err in list(getattr(result, "errors", ()) or ())]
    assert any("within 12" in err for err in errors)
    assert unit in army.units
    assert unit.deployed is False
    assert len(unit.models) == 3


def test_convergence_deployment_splits_into_single_model_units():
    game, player, army, unit = _build_game_with_convergence(quantity=3)
    original_models = list(unit.models)
    request = _build_deployment_request(game, player, unit)
    option_id = request.options[0].option_id

    result = resolve_decision_command(
        game,
        request,
        option_id,
        result_payload=_deployment_payload(
            unit,
            [
                (10.0, 10.0, 0.0),
                (24.0, 10.0, 0.0),
                (38.0, 10.0, 0.0),
            ],
        ),
        player_id=player.id,
    )

    assert result.ok is True
    assert unit not in army.units

    split_units = [u for u in list(army.units or []) if str(getattr(u, "name", "") or "") == "Convergence Of Dominion"]
    assert len(split_units) == 3
    assert all(len(getattr(u, "models", []) or []) == 1 for u in split_units)
    assert all(bool(getattr(u, "deployed", False)) for u in split_units)
    assert all(str(getattr(u, "reserve_status", "") or "") == "deployed" for u in split_units)

    original_model_ids = {get_entity_id(model) for model in original_models}
    split_model_ids = {get_entity_id(split_unit.models[0]) for split_unit in split_units}
    assert split_model_ids == original_model_ids

    map_units = list(getattr(game.map, "units", []) or [])
    assert unit not in map_units
    for split_unit in split_units:
        assert split_unit in map_units
        location = split_unit.models[0].get_location()
        assert tuple(float(value) for value in split_unit.position) == (
            float(location[0]),
            float(location[1]),
            float(location[2]),
        )
