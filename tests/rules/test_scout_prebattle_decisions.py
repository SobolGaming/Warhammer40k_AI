from warhammer40k_ai.engine.decision_kinds import DECISION_SCOUT_MOVE
from warhammer40k_ai.engine import decision_requests
from warhammer40k_ai.engine.decision_requests import build_scout_move_request
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, model_count: int = 1, base_size: str = "32mm") -> None:
        model_count = max(1, int(model_count))
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        model_word = "Model" if model_count == 1 else "Models"
        self.datasheets_unit_composition = [{"description": f"{model_count} Test {model_word}"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "1",
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(name: str, scout_distance: float, *, model_count: int = 1, base_size: str = "32mm") -> Unit:
    unit = Unit(_MockDatasheet(name, model_count=model_count, base_size=base_size))
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


def test_scout_move_rejects_final_friendly_model_overlap():
    game, p1, _p2, unit1, _unit2 = _build_remote_only_game()
    blocker = _make_unit("Friendly Blocker", scout_distance=0.0)
    p1.get_army().add_unit(blocker)
    unit1.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    blocker.models[0].set_location(16.0, 10.0, 0.0, 0.0)
    game.map.units = [unit1, blocker]
    game.rebuild_entity_registry()
    option = DecisionOption.create(
        "Scout into blocker",
        payload={
            "unit_id": get_entity_id(unit1),
            "action": "scout",
            "destination": [16.0, 10.0, 0.0],
            "model_positions": [
                {
                    "model_id": get_entity_id(unit1.models[0]),
                    "position": [16.0, 10.0, 0.0],
                    "facing": 0.0,
                }
            ],
        },
    )
    request = DecisionRequest.create(
        DECISION_SCOUT_MOVE,
        "Scout move for Scout Unit A",
        player_id=p1.id,
        options=[option],
        context={"unit_id": get_entity_id(unit1), "selection_kind": "scout_move"},
    )
    game.request_decision(request)

    result = resolve_decision_command(game, request, option.option_id, player_id=p1.id)

    assert result.ok is False
    assert "friendly model" in " ".join(result.errors)


def test_scout_move_rejects_model_base_outside_battlefield():
    game, p1, _p2, unit1, _unit2 = _build_remote_only_game()
    unit1.models[0].set_location(10.0, 42.0, 0.0, 0.0)
    game.map.units = [unit1]
    game.rebuild_entity_registry()
    option = DecisionOption.create(
        "Scout off board",
        payload={
            "unit_id": get_entity_id(unit1),
            "action": "scout",
            "destination": [10.0, 44.0, 0.0],
            "model_positions": [
                {
                    "model_id": get_entity_id(unit1.models[0]),
                    "position": [10.0, 44.0, 0.0],
                    "facing": 0.0,
                }
            ],
        },
    )
    request = DecisionRequest.create(
        DECISION_SCOUT_MOVE,
        "Scout move for Scout Unit A",
        player_id=p1.id,
        options=[option],
        context={"unit_id": get_entity_id(unit1), "selection_kind": "scout_move"},
    )
    game.request_decision(request)

    result = resolve_decision_command(game, request, option.option_id, player_id=p1.id)

    assert result.ok is False
    assert "battlefield" in " ".join(result.errors)


def test_scout_request_filters_candidates_with_trailing_model_outside_battlefield(monkeypatch):
    game, p1, _p2, _unit1, _unit2 = _build_remote_only_game()
    unit = _make_unit("Scout Unit C", scout_distance=12.0, model_count=3, base_size="32mm")
    p1.get_army().add_unit(unit)
    for model, y in zip(unit.models, [35.0, 38.0, 41.0], strict=True):
        model.set_location(10.0, y, 0.0, 0.0)
    game.map.units = [unit]
    game.rebuild_entity_registry()

    monkeypatch.setattr(
        decision_requests,
        "_scout_candidate_destinations",
        lambda *_args, **_kwargs: [(10.0, 38.0, 0.0), (10.0, 34.0, 0.0)],
    )

    request = build_scout_move_request(game, unit)
    scout_options = [
        option
        for option in list(request.options or [])
        if str(dict(option.payload or {}).get("action", "") or "") == "scout"
    ]

    assert len(scout_options) == 1
    payload = dict(scout_options[0].payload or {})
    assert payload["destination"] == [10.0, 34.0, 0.0]
    assert len(payload["model_positions"]) == 3


def test_headless_scout_precheck_skips_final_friendly_model_overlap():
    game, p1, _p2, unit1, _unit2 = _build_remote_only_game()
    blocker = _make_unit("Friendly Blocker", scout_distance=0.0)
    p1.get_army().add_unit(blocker)
    unit1.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    blocker.models[0].set_location(16.0, 10.0, 0.0, 0.0)
    game.map.units = [unit1, blocker]
    game.rebuild_entity_registry()
    invalid_option = DecisionOption.create(
        "Scout into blocker",
        payload={
            "unit_id": get_entity_id(unit1),
            "action": "scout",
            "destination": [16.0, 10.0, 0.0],
            "model_positions": [
                {
                    "model_id": get_entity_id(unit1.models[0]),
                    "position": [16.0, 10.0, 0.0],
                    "facing": 0.0,
                }
            ],
        },
    )
    skip_option = DecisionOption.create(
        "Skip",
        payload={
            "unit_id": get_entity_id(unit1),
            "action": "skip",
            "skip": True,
        },
    )
    request = DecisionRequest.create(
        DECISION_SCOUT_MOVE,
        "Scout move for Scout Unit A",
        player_id=p1.id,
        options=[invalid_option, skip_option],
        context={"unit_id": get_entity_id(unit1), "selection_kind": "scout_move"},
    )

    assert (
        HeadlessPolicyDecisionController._candidate_passes_current_game_precheck(
            game,
            request,
            invalid_option.option_id,
        )
        is False
    )
    assert (
        HeadlessPolicyDecisionController._candidate_passes_current_game_precheck(
            game,
            request,
            skip_option.option_id,
        )
        is True
    )
