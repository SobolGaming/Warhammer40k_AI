from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.movement import validate_move_unit_payload
from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        wounds: str = "2",
    ):
        slug = str(name or "unit").lower().replace(" ", "-")
        self.id = f"mock-{slug}"
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ADEPTUS ASTARTES"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "6",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _unit(name: str, *, keywords=None, faction_keywords=None, wounds: str = "2") -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(*, detachment: str = "Armoured Speartip"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
    marine_army = Army.with_detachment("Space Marines", detachment)
    marine_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    marine_player = Player("Marine Player", control=PlayerControl.REMOTE, army=marine_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(marine_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, marine_army, enemy_army


def _place(game: Game, unit: Unit, x: float, y: float, facing: float = 0.0) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, float(facing))
    if unit not in game.map.units:
        game.map.units.append(unit)


def _rapid_deployment_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_MOVE_UNIT:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("reactive_move_kind", "") or "") == "armoured_speartip_rapid_deployment":
            return request
    return None


def test_armoured_speartip_marks_only_large_non_aircraft_transports_as_heavy_transport():
    game, army, _enemy = _build_game()
    land_raider = _unit(
        "Land Raider",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds="16",
    )
    impulsor = _unit(
        "Impulsor",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds="11",
    )
    stormraven = _unit(
        "Stormraven Gunship",
        keywords=["VEHICLE", "TRANSPORT", "AIRCRAFT"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds="14",
    )
    army.add_unit(land_raider)
    army.add_unit(impulsor)
    army.add_unit(stormraven)
    game.rebuild_entity_registry()

    assert land_raider.has_keyword("HEAVY TRANSPORT") is True
    assert impulsor.has_keyword("HEAVY TRANSPORT") is False
    assert stormraven.has_keyword("HEAVY TRANSPORT") is False


def test_rapid_deployment_queues_d6_normal_move_after_disembarking_from_moved_transport(monkeypatch):
    game, army, _enemy = _build_game()
    intercessors = _unit("Intercessor Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    impulsor = _unit(
        "Impulsor",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds="11",
    )
    army.add_unit(intercessors)
    army.add_unit(impulsor)
    impulsor.round_state.moved_this_round = True
    impulsor.round_state.remained_stationary_this_round = False
    game.rebuild_entity_registry()

    def _roll(expr, **_kwargs):
        assert expr == "D6"
        return 4

    monkeypatch.setattr("warhammer40k_ai.rules.space_marines_detachments.get_roll", _roll)

    request = army.space_marines_detachments.queue_armoured_speartip_rapid_deployment_move(
        intercessors,
        transport_unit=impulsor,
        game=game,
        current_turn=1,
    )

    assert request is _rapid_deployment_request(game)
    context = dict(request.context or {})
    assert context["reactive_move_kind"] == "armoured_speartip_rapid_deployment"
    assert context["movement_type"] == "move"
    assert context["max_distance"] == 4
    assert context["allow_skip"] is True
    assert context["rapid_deployment_distance_roll"] == "D6"
    assert context["rapid_deployment_heavy_transport"] is False
    assert context["rapid_deployment_transport_unit_id"] == str(get_entity_id(impulsor) or "")


def test_rapid_deployment_queues_d3_plus_three_normal_move_after_heavy_transport_advance(monkeypatch):
    game, army, _enemy = _build_game()
    hellblasters = _unit("Hellblaster Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    land_raider = _unit(
        "Land Raider",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds="16",
    )
    army.add_unit(hellblasters)
    army.add_unit(land_raider)
    land_raider.round_state.moved_this_round = True
    land_raider.round_state.advanced_this_round = True
    game.rebuild_entity_registry()

    def _roll(expr, **_kwargs):
        assert expr == "D3+3"
        return 6

    monkeypatch.setattr("warhammer40k_ai.rules.space_marines_detachments.get_roll", _roll)

    request = army.space_marines_detachments.queue_armoured_speartip_rapid_deployment_move(
        hellblasters,
        transport_unit=land_raider,
        game=game,
        current_turn=1,
    )

    assert request is _rapid_deployment_request(game)
    context = dict(request.context or {})
    assert context["max_distance"] == 6
    assert context["rapid_deployment_distance_roll"] == "D3+3"
    assert context["rapid_deployment_heavy_transport"] is True


def test_rapid_deployment_requires_armoured_speartip_and_eligible_transport(monkeypatch):
    game, army, _enemy = _build_game(detachment="Gladius Task Force")
    intercessors = _unit("Intercessor Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    impulsor = _unit(
        "Impulsor",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds="11",
    )
    army.add_unit(intercessors)
    army.add_unit(impulsor)
    impulsor.round_state.moved_this_round = True
    game.rebuild_entity_registry()
    monkeypatch.setattr("warhammer40k_ai.rules.space_marines_detachments.get_roll", lambda *_a, **_k: 4)

    assert (
        army.space_marines_detachments.queue_armoured_speartip_rapid_deployment_move(
            intercessors,
            transport_unit=impulsor,
            game=game,
            current_turn=1,
        )
        is None
    )

    spearhead_game, spearhead_army, _ = _build_game()
    unit = _unit("Intercessor Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    stationary_transport = _unit(
        "Impulsor",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds="11",
    )
    aircraft = _unit(
        "Stormraven Gunship",
        keywords=["VEHICLE", "TRANSPORT", "AIRCRAFT"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds="14",
    )
    spearhead_army.add_unit(unit)
    spearhead_army.add_unit(stationary_transport)
    spearhead_army.add_unit(aircraft)
    aircraft.round_state.moved_this_round = True
    spearhead_game.rebuild_entity_registry()

    assert (
        spearhead_army.space_marines_detachments.queue_armoured_speartip_rapid_deployment_move(
            unit,
            transport_unit=stationary_transport,
            game=spearhead_game,
            current_turn=1,
        )
        is None
    )
    assert (
        spearhead_army.space_marines_detachments.queue_armoured_speartip_rapid_deployment_move(
            unit,
            transport_unit=aircraft,
            game=spearhead_game,
            current_turn=1,
        )
        is None
    )


def test_rapid_deployment_move_validation_enforces_rolled_max_distance(monkeypatch):
    game, army, _enemy = _build_game()
    intercessors = _unit("Intercessor Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    impulsor = _unit(
        "Impulsor",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds="11",
    )
    army.add_unit(intercessors)
    army.add_unit(impulsor)
    impulsor.round_state.moved_this_round = True
    impulsor.round_state.remained_stationary_this_round = False
    _place(game, intercessors, 0.0, 0.0)
    game.rebuild_entity_registry()
    monkeypatch.setattr("warhammer40k_ai.rules.space_marines_detachments.get_roll", lambda *_a, **_k: 4)

    request = army.space_marines_detachments.queue_armoured_speartip_rapid_deployment_move(
        intercessors,
        transport_unit=impulsor,
        game=game,
        current_turn=1,
    )
    model_id = str(get_entity_id(intercessors.models[0]) or "")
    option_payload = {"unit_id": str(get_entity_id(intercessors) or ""), "movement_type": "move"}

    assert validate_move_unit_payload(
        game,
        request,
        option_payload=option_payload,
        result_payload={
            "movement_type": "move",
            "model_positions": [{"model_id": model_id, "position": [4.0, 0.0, 0.0], "facing": 0.0}],
        },
    ) == ()
    errors = validate_move_unit_payload(
        game,
        request,
        option_payload=option_payload,
        result_payload={
            "movement_type": "move",
            "model_positions": [{"model_id": model_id, "position": [4.1, 0.0, 0.0], "facing": 0.0}],
        },
    )
    assert any('Rapid Deployment move cannot exceed 4"' in str(error) for error in errors)
