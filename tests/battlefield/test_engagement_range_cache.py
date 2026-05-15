from types import SimpleNamespace

from warhammer40k_ai.battlefield import map as map_module
from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.engine.combat_timing import CombatEngagementState


def _profile():
    return SimpleNamespace(
        rules_bundle_id="test",
        edition_family="10e",
        engagement_range_horizontal=1.0,
        engagement_range_vertical=5.0,
        base_contact_epsilon=0.001,
    )


def _base(x: float, y: float, *, radius: float = 0.4, z: float = 0.0):
    return SimpleNamespace(
        x=float(x),
        y=float(y),
        z=float(z),
        facing=0.0,
        radius=float(radius),
        has_circular_base=False,
        get_longest_radius=lambda: float(radius),
    )


def _model(model_id: str, x: float, y: float, *, radius: float = 0.4):
    base = _base(x, y, radius=radius)
    return SimpleNamespace(
        _id=str(model_id),
        is_alive=True,
        model_base=base,
        get_location=lambda: (base.x, base.y, base.z, base.facing),
    )


def _unit(unit_id: str, model):
    return SimpleNamespace(
        _id=str(unit_id),
        name=str(unit_id),
        get_models_for_collision=lambda: [model],
    )


def test_engagement_range_reuses_pair_result_until_pose_changes(monkeypatch):
    game_map = Map(44, 60)
    source_model = _model("source-model", 0.0, 0.0)
    target_model = _model("target-model", 0.5, 0.0)
    source = _unit("source-unit", source_model)
    target = _unit("target-unit", target_model)
    calls = {"count": 0}

    def counted_engagement_state(*_args, **_kwargs):
        calls["count"] += 1
        return CombatEngagementState.ENGAGED

    monkeypatch.setattr(map_module, "geometry_profile_for_context", lambda **_kwargs: _profile())
    monkeypatch.setattr(map_module, "engagement_state_for_models", counted_engagement_state)

    assert game_map.is_within_engagement_range(source, target)
    assert game_map.is_within_engagement_range(source, target)
    assert calls["count"] == 1

    target_model.model_base.x = 0.6
    assert game_map.is_within_engagement_range(source, target)
    assert calls["count"] == 2


def test_engagement_range_skips_geometry_for_obviously_distant_models(monkeypatch):
    game_map = Map(44, 60)
    source = _unit("source-unit", _model("source-model", 0.0, 0.0))
    target = _unit("target-unit", _model("target-model", 20.0, 0.0))

    def unexpected_engagement_state(*_args, **_kwargs):
        raise AssertionError("distant models should be rejected before geometry")

    monkeypatch.setattr(map_module, "geometry_profile_for_context", lambda **_kwargs: _profile())
    monkeypatch.setattr(map_module, "engagement_state_for_models", unexpected_engagement_state)

    assert not game_map.is_within_engagement_range(source, target)
