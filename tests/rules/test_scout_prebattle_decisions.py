from warhammer40k_ai.engine.decision_kinds import DECISION_SCOUT_MOVE
from warhammer40k_ai.engine.decision_requests import build_scout_move_request
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name: str) -> None:
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "1",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(name: str, scout_distance: float) -> Unit:
    unit = Unit(_MockDatasheet(name))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.scout_move_made = False
    unit.has_scout = lambda: (True, float(scout_distance))
    return unit


def _pending_scout_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_SCOUT_MOVE
    ]


def _build_remote_only_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    p1 = Player("P1", PlayerControl.REMOTE, None)
    p2 = Player("P2", PlayerControl.REMOTE, None)
    game.add_player(p1)
    game.add_player(p2)

    a1 = Army.with_detachment("Army 1", "Detachment 1")
    a2 = Army.with_detachment("Army 2", "Detachment 2")
    p1.set_army(a1)
    p2.set_army(a2)

    unit1 = _make_unit("Scout Unit A", scout_distance=6.0)
    unit2 = _make_unit("Scout Unit B", scout_distance=8.0)
    a1.add_unit(unit1)
    a2.add_unit(unit2)
    return game, p1, p2, unit1, unit2


def test_remote_only_scout_moves_queue_decisions_in_turn_order():
    game, p1, p2, unit1, unit2 = _build_remote_only_game()
    game.first_turn_player_index = 1

    game._handle_scout_moves()

    pending = _pending_scout_requests(game)
    assert len(pending) == 2
    assert [req.player_id for req in pending] == [p2.id, p1.id]
    assert [req.context.get("unit_id") for req in pending] == [unit2.id, unit1.id]
    assert unit1.scout_move_made is False
    assert unit2.scout_move_made is False


def test_remote_only_scout_move_request_queue_is_deduplicated():
    game, _p1, _p2, _unit1, _unit2 = _build_remote_only_game()
    game.first_turn_player_index = 0

    game._handle_scout_moves()
    first_ids = [req.decision_id for req in _pending_scout_requests(game)]

    game._handle_scout_moves()
    second_ids = [req.decision_id for req in _pending_scout_requests(game)]

    assert len(second_ids) == 2
    assert second_ids == first_ids


def test_headless_scout_move_applies_generated_model_positions_without_pathfinding():
    game, p1, _p2, unit1, unit2 = _build_remote_only_game()
    unit2.models[0].set_location(50.0, 40.0, 0.0, 0.0)
    game.map.units = [unit1, unit2]
    game.rebuild_entity_registry()
    request = build_scout_move_request(game, unit1)
    scout_option = next(
        option
        for option in list(request.options or [])
        if str(dict(option.payload or {}).get("action", "") or "") == "scout"
    )
    payload = dict(scout_option.payload or {})
    model_positions = list(payload.get("model_positions") or [])
    assert model_positions

    def fail_slow_scout_move(*_args, **_kwargs):
        raise AssertionError("generated scout model positions should avoid unit.scout_move pathfinding")

    unit1.scout_move = fail_slow_scout_move

    result = resolve_decision_command(game, request, scout_option.option_id, player_id=p1.id)

    assert bool(result.ok) is True
    assert unit1.scout_move_made is True
    expected_position = model_positions[0]["position"]
    actual_position = unit1.models[0].get_location()
    assert [round(float(value), 6) for value in actual_position[:3]] == [
        round(float(value), 6) for value in expected_position
    ]
