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
