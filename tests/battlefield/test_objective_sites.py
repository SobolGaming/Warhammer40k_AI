from __future__ import annotations

from shapely.geometry import Point, Polygon

from warhammer40k_ai.battlefield import control_queries
from warhammer40k_ai.battlefield.control_queries import objective_control_cache_scope
from warhammer40k_ai.battlefield.objective_sites import Objective, ObjectiveCategory, ObjectiveSite


class _FakeBase:
    def __init__(self, x: float, y: float, radius: float = 1.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = 0.0
        self._radius = float(radius)
        self.has_circular_base = True

    def get_radius(self) -> float:
        return float(self._radius)

    def get_base_shape(self):
        return Point(self.x, self.y).buffer(self._radius)


class _FakeModel:
    def __init__(self, x: float, y: float, *, objective_control: int = 1) -> None:
        self.model_base = _FakeBase(x, y)
        self.objective_control = int(objective_control)
        self.is_alive = True


class _CountingObjectiveControlModel:
    def __init__(self, x: float, y: float, *, objective_control: int = 1) -> None:
        self.model_base = _FakeBase(x, y)
        self._objective_control = int(objective_control)
        self.objective_control_reads = 0
        self.is_alive = True

    @property
    def objective_control(self) -> int:
        self.objective_control_reads += 1
        return int(self._objective_control)


class _FakeUnit:
    def __init__(self, model: _FakeModel) -> None:
        self.models = [model]
        self.deployed = True
        self.is_leader = False
        self.attached_to = None

    def is_alive(self) -> bool:
        return True

    def get_models_for_collision(self):
        return list(self.models)


class _FakeArmy:
    def __init__(self, unit: _FakeUnit) -> None:
        self.units = [unit]


class _FakePlayer:
    def __init__(self, name: str, unit: _FakeUnit) -> None:
        self.name = str(name)
        self.id = f"player:{name.lower()}"
        self.army = _FakeArmy(unit)


class _FakeGame:
    def __init__(self, players) -> None:
        self.players = list(players)
        self.event_system = None


def test_marker_objective_site_binds_control_region_and_score_source_ids() -> None:
    site = ObjectiveSite(10.0, 12.0, 0.0, control_radius=3.0)
    objective = Objective(
        name="Alpha",
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="Control Alpha",
        conditions=lambda game: True,
        location=site,
    )

    entry = site.to_state_entry(objective_id=objective.id)

    assert entry["site_kind"] == "MARKER"
    assert entry["geometry"]["kind"] == "MARKER"
    assert entry["control_region"]["region_id"] == f"region:objective:{objective.id}"
    assert entry["score_sources"][0]["score_source_id"] == f"score_source:objective:{objective.id}"


def test_marker_objective_centroid_uses_center_without_shapely_point(monkeypatch) -> None:
    site = ObjectiveSite(10.0, 12.0, 0.0, control_radius=3.0)

    def _raise_if_called(*_args, **_kwargs):
        raise RecursionError("Point construction should not be needed for radius centroid")

    monkeypatch.setattr(control_queries, "Point", _raise_if_called)

    entry = site.to_state_entry(objective_id="objective:test")

    assert entry["geometry"]["position"] == [10.0, 12.0, 0.0]


def test_terrain_footprint_objective_site_uses_polygon_control_region() -> None:
    site = ObjectiveSite.terrain_footprint(
        footprint=Polygon([(8.0, 8.0), (14.0, 8.0), (14.0, 14.0), (8.0, 14.0)]),
        terrain_area_id="terrain_area:central_ruin",
        layout_slot_id="layout:center_ruin",
        metadata={"fixture": "terrain_footprint"},
    )
    objective = Objective(
        name="Central Ruin",
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="Control the ruin footprint",
        conditions=lambda game, point=site: point.primary_score_source().is_active(point.controlling_player),
        location=site,
    )
    player = _FakePlayer("Controller", _FakeUnit(_FakeModel(10.0, 10.0, objective_control=2)))
    site.update_control(_FakeGame([player]))

    entry = site.to_state_entry(objective_id=objective.id)

    assert site.controlling_player is player
    assert entry["geometry"]["kind"] == "POLYGON_FOOTPRINT"
    assert entry["geometry"]["terrain_area_id"] == "terrain_area:central_ruin"
    assert entry["geometry"]["layout_slot_id"] == "layout:center_ruin"
    assert entry["control_region"]["kind"] == "OBJECTIVE_CONTROL_FOOTPRINT"
    assert entry["control_region"]["terrain_area_id"] == "terrain_area:central_ruin"
    assert entry["control_region"]["layout_slot_id"] == "layout:center_ruin"
    assert "footprint" in entry["geometry"]


def test_objective_control_cache_scope_reuses_model_oc_between_objectives() -> None:
    model = _CountingObjectiveControlModel(10.0, 10.0, objective_control=2)
    player = _FakePlayer("Controller", _FakeUnit(model))
    game = _FakeGame([player])
    first_site = ObjectiveSite(10.0, 10.0, 0.0, control_radius=3.0)
    second_site = ObjectiveSite(10.0, 10.0, 0.0, control_radius=3.0)

    with objective_control_cache_scope(game):
        first_site.update_control(game)
        second_site.update_control(game)

    assert first_site.controlling_player is player
    assert second_site.controlling_player is player
    assert model.objective_control_reads == 1
    assert not hasattr(game, "_objective_control_model_oc_cache")
    assert not hasattr(game, "_objective_control_nurgles_gift_cache")


def test_score_source_vp_evaluation_is_independent_of_site_shape() -> None:
    marker_site = ObjectiveSite(5.0, 5.0, 0.0, control_radius=3.0)
    marker_objective = Objective(
        name="Marker",
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="Marker objective",
        conditions=lambda game: True,
        location=marker_site,
    )
    polygon_site = ObjectiveSite.terrain_footprint(
        footprint=Polygon([(20.0, 20.0), (26.0, 20.0), (26.0, 26.0), (20.0, 26.0)])
    )
    polygon_objective = Objective(
        name="Footprint",
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="Footprint objective",
        conditions=lambda game: True,
        location=polygon_site,
    )
    player = _FakePlayer("Scorer", _FakeUnit(_FakeModel(0.0, 0.0)))

    marker_site.controlling_player = player
    polygon_site.controlling_player = player

    assert marker_site.primary_score_source().score_source_id == f"score_source:objective:{marker_objective.id}"
    assert polygon_site.primary_score_source().score_source_id == f"score_source:objective:{polygon_objective.id}"
    assert marker_site.primary_score_source().score_value(player) == 5
    assert polygon_site.primary_score_source().score_value(player) == 5
