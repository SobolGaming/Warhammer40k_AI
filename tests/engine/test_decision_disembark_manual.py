import pytest

from warhammer40k_ai.engine.command_kinds import CMD_RESOLVE_DECISION
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine.decision_kinds import DECISION_DISEMBARK
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, transport=""):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
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
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = transport


def _make_unit(name, *, abilities=None, keywords=None, transport=""):
    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        transport=transport,
    )
    return Unit(datasheet)


def test_disembark_decision_applies_manual_positions():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    army = Army.with_detachment("Test", "Detachment")
    player = Player("P1", PlayerControl.LOCAL, army)
    game = Game(bf, players=[player])

    transport = _make_unit("Transport", keywords=["Transport"], transport="Transport Capacity 10")
    passenger = _make_unit("Passengers", keywords=["Infantry"])

    army.add_unit(transport)
    army.add_unit(passenger)
    game.rebuild_entity_registry()

    transport.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    game.map.place_unit(transport)
    transport.transport_passengers = [passenger]
    passenger.embarked_in = transport

    unit_id = get_entity_id(passenger)
    transport_id = get_entity_id(transport)
    model = passenger.models[0]
    model_id = get_entity_id(model)

    positions = [{"model_id": model_id, "position": [12.5, 10.0, 0.0], "facing": 0.0}]
    disembark = DecisionOption.create("Disembark", payload={"unit_id": unit_id, "transport_id": transport_id})
    remain = DecisionOption.create("Remain", payload={"unit_id": unit_id, "transport_id": None})
    req = DecisionRequest.create(
        DECISION_DISEMBARK,
        "Disembark passengers",
        player_id=player.id,
        options=[disembark, remain],
        context={"unit_id": unit_id, "transport_id": transport_id},
    )
    game.request_decision(req)

    cmd = GameCommand.create(
        CMD_RESOLVE_DECISION,
        player_id=player.id,
        payload={
            "decision_id": req.decision_id,
            "option_id": disembark.option_id,
            "result_payload": {"model_positions": positions},
        },
    )
    result = game.apply_command(cmd)

    assert result.ok is True
    assert passenger.round_state.disembarked_this_round is True
    assert passenger.embarked_in is None
    assert passenger in game.map.units
    assert transport.transport_passengers == []
    loc = model.get_location()
    assert loc[0] == pytest.approx(12.5)


def test_disembark_decision_rejects_base_not_wholly_within_transport_range():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    army = Army.with_detachment("Test", "Detachment")
    player = Player("P1", PlayerControl.LOCAL, army)
    game = Game(bf, players=[player])

    transport = _make_unit("Transport", keywords=["Transport"], transport="Transport Capacity 10")
    passenger = _make_unit("Passengers", keywords=["Infantry"])

    army.add_unit(transport)
    army.add_unit(passenger)
    game.rebuild_entity_registry()

    transport.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    game.map.place_unit(transport)
    transport.transport_passengers = [passenger]
    passenger.embarked_in = transport

    unit_id = get_entity_id(passenger)
    transport_id = get_entity_id(transport)
    model = passenger.models[0]
    model_id = get_entity_id(model)

    # The model's closest edge is within 3", but the far side of its base is outside 3".
    positions = [{"model_id": model_id, "position": [13.5, 10.0, 0.0], "facing": 0.0}]
    disembark = DecisionOption.create("Disembark", payload={"unit_id": unit_id, "transport_id": transport_id})
    req = DecisionRequest.create(
        DECISION_DISEMBARK,
        "Disembark passengers",
        player_id=player.id,
        options=[disembark],
        context={"unit_id": unit_id, "transport_id": transport_id, "disembark_max_distance": 3.0},
    )
    game.request_decision(req)

    cmd = GameCommand.create(
        CMD_RESOLVE_DECISION,
        player_id=player.id,
        payload={
            "decision_id": req.decision_id,
            "option_id": disembark.option_id,
            "result_payload": {"model_positions": positions},
        },
    )
    result = game.apply_command(cmd)

    assert result.ok is False
    assert "wholly within disembark range" in " ".join(result.errors)
    assert passenger.embarked_in is transport
    assert passenger not in game.map.units
