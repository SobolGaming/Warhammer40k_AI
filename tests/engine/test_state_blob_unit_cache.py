from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine import state_blob_units


class _FakeBase:
    has_circular_base = True

    def __init__(self, x: float, y: float) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = 0.0

    def get_radius(self) -> float:
        return 1.0


def _unit(unit_id: str, x: float, y: float) -> SimpleNamespace:
    model = SimpleNamespace(
        id=f"{unit_id}:model",
        model_base=_FakeBase(x, y),
        is_alive=True,
        _movement=6,
    )
    return SimpleNamespace(
        id=unit_id,
        name=unit_id,
        models=[model],
        reserve_status="",
        special_rules={},
    )


def _unit_with_models(unit_id: str, positions: list[tuple[float, float]], *, movement: float = 0.0) -> SimpleNamespace:
    models = []
    for index, (x, y) in enumerate(positions):
        models.append(
            SimpleNamespace(
                id=f"{unit_id}:model:{index}",
                model_base=_FakeBase(x, y),
                is_alive=True,
                _movement=float(movement),
            )
        )
    return SimpleNamespace(
        id=unit_id,
        name=unit_id,
        models=models,
        reserve_status="deployed",
        special_rules={},
        deployed=True,
        is_embarked=False,
    )


def _objective(objective_id: str, x: float, y: float, *, control_radius: float = 3.0) -> SimpleNamespace:
    return SimpleNamespace(
        id=objective_id,
        name=objective_id,
        points=5,
        location=SimpleNamespace(
            id=f"{objective_id}:site",
            x=float(x),
            y=float(y),
            z=0.0,
            control_radius=float(control_radius),
            controlling_player=None,
            sticky_controller=None,
            sticky_minimum_control=0,
            removed=False,
        ),
    )


def test_unit_entries_runtime_cache_reuses_engagement_between_viewers(monkeypatch) -> None:
    p1_unit = _unit("unit:p1", 0.0, 0.0)
    p2_unit = _unit("unit:p2", 10.0, 0.0)
    p1 = SimpleNamespace(id="player:p1", army=SimpleNamespace(units=[p1_unit]))
    p2 = SimpleNamespace(id="player:p2", army=SimpleNamespace(units=[p2_unit]))
    game = SimpleNamespace(
        players=[p1, p2],
        map=SimpleNamespace(objectives=[]),
        _state_blob_units_runtime_cache={},
    )
    engagement_calls: list[str] = []

    def _fake_engagement(unit, enemy_units, **_kwargs) -> bool:
        engagement_calls.append(str(unit.id))
        return False

    monkeypatch.setattr(state_blob_units, "is_unit_in_engagement_range", _fake_engagement)

    state_blob_units.unit_entries(game, viewer_id=str(p1.id), include_hidden=False)
    state_blob_units.unit_entries(game, viewer_id=str(p2.id), include_hidden=False)

    assert engagement_calls == ["unit:p1", "unit:p2"]


def test_unit_entries_runtime_cache_reuses_view_payload(monkeypatch) -> None:
    unit = _unit("unit:p1", 0.0, 0.0)
    player = SimpleNamespace(id="player:p1", army=SimpleNamespace(units=[unit]))
    game = SimpleNamespace(
        players=[player],
        map=SimpleNamespace(objectives=[]),
        _state_blob_units_runtime_cache={},
    )

    first = state_blob_units.unit_entries(game, viewer_id=str(player.id), include_hidden=False)

    def unexpected_model_positions(*_args, **_kwargs):
        raise AssertionError("cached unit entries should not rebuild model positions")

    monkeypatch.setattr(state_blob_units, "model_position_entries", unexpected_model_positions)
    second = state_blob_units.unit_entries(game, viewer_id=str(player.id), include_hidden=False)

    assert second == first
    assert second is not first


def test_unit_entries_export_model_positions_not_unit_centroids() -> None:
    long_unit = _unit_with_models(
        "unit:long",
        [(float(index * 2), 0.0) for index in range(20)],
        movement=0.0,
    )
    player = SimpleNamespace(id="player:p1", army=SimpleNamespace(units=[long_unit]))
    game = SimpleNamespace(
        players=[player],
        map=SimpleNamespace(objectives=[_objective("objective:near-first-model", 0.0, 0.0)]),
        _state_blob_units_runtime_cache={},
    )

    entry = state_blob_units.unit_entries(game, viewer_id=str(player.id), include_hidden=False)[0]

    assert "position" not in entry
    assert len(entry["model_positions"]) == 20
    assert entry["score_source_ids_in_range"] == ["score_source:objective:objective:near-first-model"]
    assert entry["threat_flags"]["can_reach_score_source_this_turn"] is True
    assert entry["threat_flags"]["nearest_score_source_base_distance"] == 0.0


def test_unit_entries_engagement_uses_exact_model_bases_for_interspersed_shapes() -> None:
    first = _unit_with_models("unit:first", [(0.0, 0.0), (10.0, 0.0)])
    second = _unit_with_models("unit:second", [(4.0, 0.0), (6.0, 0.0)])
    p1 = SimpleNamespace(id="player:p1", army=SimpleNamespace(units=[first]))
    p2 = SimpleNamespace(id="player:p2", army=SimpleNamespace(units=[second]))
    game = SimpleNamespace(
        players=[p1, p2],
        map=SimpleNamespace(objectives=[]),
        _state_blob_units_runtime_cache={},
    )

    entries = {
        str(entry["unit_id"]): entry
        for entry in state_blob_units.unit_entries(game, viewer_id=str(p1.id), include_hidden=False)
    }

    assert entries["unit:first"]["in_engagement_range"] is False
    assert entries["unit:second"]["in_engagement_range"] is False
    assert "position" not in entries["unit:first"]
    assert "position" not in entries["unit:second"]
