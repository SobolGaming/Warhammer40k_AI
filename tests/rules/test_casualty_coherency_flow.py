from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_RESOLVE_COHERENCY
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game_mixins.reactive_decisions_mixin import GameReactiveDecisionsMixin
from warhammer40k_ai.engine.decision_requests import build_resolve_coherency_request
from warhammer40k_ai.units.unit_mixins.damage_death_mixin import DamageDeathMixin


class _DecisionQueueStub:
    def __init__(self) -> None:
        self._requests = []

    def add(self, request) -> None:
        self._requests.append(request)

    def pop(self, decision_id=None):
        if decision_id is None:
            return self._requests.pop(0) if self._requests else None
        for index, request in enumerate(list(self._requests)):
            if getattr(request, "decision_id", None) == decision_id:
                return self._requests.pop(index)
        return None

    def list(self):
        return list(self._requests)


class _PlayerStub:
    def __init__(self, player_id: str) -> None:
        self.id = player_id
        self.army = None
        self.game = None

    def get_army(self):
        return self.army


class _ArmyStub:
    def __init__(self, player: _PlayerStub) -> None:
        self.id = "army-1"
        self._id = "army-1"
        self.player = player
        self.units = []


class _BaseStub:
    def __init__(self, x: float) -> None:
        self.x = float(x)

    def coherency_distance(self, other: "_BaseStub") -> float:
        return abs(self.x - other.x) - 2.0


class _ModelStub:
    def __init__(self, model_id: str, name: str, x: float, parent_unit: "_UnitStub") -> None:
        self.id = model_id
        self._id = model_id
        self.name = name
        self.model_base = _BaseStub(x)
        self.parent_unit = parent_unit
        self.wounds = 1

    @property
    def is_alive(self) -> bool:
        return self.wounds > 0

    def die(self, game_map=None) -> None:
        self.parent_unit.remove_model(self, False, game_map=game_map)


class _UnitStub(DamageDeathMixin):
    def __init__(self, unit_id: str, army: _ArmyStub) -> None:
        self.id = unit_id
        self._id = unit_id
        self.name = "Coherency Test Unit"
        self.parent_army = army
        self.models = []
        self.models_lost = []
        self.round_state = SimpleNamespace(num_lost_models_this_round=0)
        self.attached_leaders = []
        self.attached_support_units = []
        self.is_leader = False

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_models(self):
        return list(self.models)

    def update_coherency(self) -> None:
        alive_count = len([model for model in self.models if model.is_alive])
        if alive_count <= 1:
            self.coherency_distance = 2.0
            self.required_neighbors = 0
        elif alive_count >= 7:
            self.coherency_distance = 2.0
            self.required_neighbors = 2
        else:
            self.coherency_distance = 2.0
            self.required_neighbors = 1

    def _invalidate_ability_cache(self) -> None:
        return None

    def _maybe_swap_horrors_datasheet(self) -> None:
        return None


class _CoherencyGame(GameReactiveDecisionsMixin):
    def __init__(self, unit: _UnitStub) -> None:
        self.phase = SimpleNamespace(name="SHOOTING_PHASE")
        self.turn = 2
        self.is_authoritative = True
        self.decision_queue = _DecisionQueueStub()
        self.players = [unit.parent_army.player]
        self.map = None

    def request_decision(self, request) -> None:
        self.decision_queue.add(request)


def _build_game():
    player = _PlayerStub("player-1")
    army = _ArmyStub(player)
    player.army = army
    unit = _UnitStub("unit-1", army)
    army.units = [unit]
    game = _CoherencyGame(unit)
    player.game = game
    unit.models = [
        _ModelStub("model-1", "Model 1", 0.0, unit),
        _ModelStub("model-2", "Model 2", 2.0, unit),
        _ModelStub("model-3", "Model 3", 4.0, unit),
    ]
    unit.update_coherency()
    return game, unit


def test_build_resolve_coherency_request_is_deterministic() -> None:
    _game, unit = _build_game()

    request = build_resolve_coherency_request(
        unit,
        context={
            "phase_name": "SHOOTING_PHASE",
            "coherency_failure_reason": "post_casualty",
            "required_until_coherent": True,
        },
    )

    assert request is not None
    assert request.decision_type == DECISION_RESOLVE_COHERENCY
    assert request.context["allowed_model_ids"] == ["model-1", "model-2", "model-3"]
    assert [opt.payload["model_id"] for opt in request.options] == ["model-1", "model-2", "model-3"]


def test_casualty_queues_post_casualty_resolve_coherency_request() -> None:
    game, unit = _build_game()
    middle = unit.models[1]

    middle.wounds = 0
    middle.die()

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_RESOLVE_COHERENCY
    assert request.context["coherency_failure_reason"] == "post_casualty"
    assert request.context["non_coherent_model_ids"] == ["model-1", "model-3"]
    assert request.context["allowed_model_ids"] == ["model-1", "model-3"]


def test_resolve_coherency_removes_one_model_and_ends_loop_when_coherent() -> None:
    game, unit = _build_game()
    middle = unit.models[1]

    middle.wounds = 0
    middle.die()
    request = game.decision_queue.list()[0]
    chosen = next(opt for opt in request.options if opt.payload.get("model_id") == "model-1")
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="player-1",
        option_id=chosen.option_id,
        payload={"model_ids": ["model-1"]},
    )

    apply_result = dispatch_decision(game, request, result)

    assert apply_result.ok is True
    assert [model.id for model in unit.models] == ["model-3"]
    assert list(game.decision_queue.list() or []) == []


def test_additional_casualty_refresh_clears_stale_coherency_request() -> None:
    game, unit = _build_game()
    middle = unit.models[1]
    first = unit.models[0]

    middle.wounds = 0
    middle.die()
    assert len(game.decision_queue.list()) == 1

    first.wounds = 0
    first.die()

    assert list(game.decision_queue.list() or []) == []


def test_active_coherency_request_is_not_refreshed_while_resolving() -> None:
    game, unit = _build_game()
    middle = unit.models[1]
    first = unit.models[0]

    middle.wounds = 0
    middle.die()
    request = game.decision_queue.list()[0]
    setattr(request, "_resolution_in_progress", True)

    first.wounds = 0
    first.die()

    assert game.decision_queue.list() == [request]
    assert getattr(game, "_deferred_post_casualty_coherency_recheck_unit_ids") == {unit.id}

    setattr(request, "_resolution_in_progress", False)
    game.decision_queue.pop(request.decision_id)
    game._drain_deferred_post_casualty_coherency_rechecks()

    assert list(game.decision_queue.list() or []) == []
