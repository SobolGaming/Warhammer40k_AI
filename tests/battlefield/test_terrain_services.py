from __future__ import annotations

from shapely.geometry import Polygon

import warhammer40k_ai.battlefield.terrain_visibility as terrain_visibility
from warhammer40k_ai.battlefield.map import Map, TerrainArea, TerrainFactory, TerrainFeature, TerrainType
from warhammer40k_ai.battlefield.terrain_runtime import iter_terrain_areas
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.utility.model_base import Base, BaseType


class _StubPlayer:
    def __init__(self, game):
        self.game = game


class _StubArmy:
    def __init__(self, player):
        self.player = player


class _StubUnit:
    def __init__(self, name: str, models: list[Model], army: _StubArmy, *, keywords: list[str] | None = None) -> None:
        self.name = name
        self.models = models
        self._army = army
        self.keywords = [str(keyword).upper() for keyword in list(keywords or [])]
        self.is_towering = False
        for model in self.models:
            model.set_parent_unit(self)

    def get_parent_army(self):
        return self._army

    def has_any_keyword(self, keyword: str) -> bool:
        return str(keyword).strip().upper() in set(self.keywords)


def _make_model(name: str, x_pos: float, y_pos: float, z_pos: float) -> Model:
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=2,
        leadership=6,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 0.5),
    )
    model.set_location(x_pos, y_pos, z_pos, 0.0)
    return model


def _build_units(attacker_pos: tuple[float, float, float], target_positions: list[tuple[float, float, float]], *, target_keywords: list[str] | None = None):
    game_map = Map(width=60, height=44)
    game = type("_StubGame", (), {"map": game_map})()
    player = _StubPlayer(game)
    army = _StubArmy(player)
    attacker = _make_model("attacker", *attacker_pos)
    attacker_unit = _StubUnit("attacker_unit", [attacker], army, keywords=["INFANTRY"])
    target_models = [_make_model(f"target_{index}", *position) for index, position in enumerate(target_positions)]
    target_unit = _StubUnit("target_unit", target_models, army, keywords=target_keywords or ["INFANTRY"])
    game_map.units = [attacker_unit, target_unit]
    return game_map, attacker, attacker_unit, target_unit


def test_authored_terrain_area_wins_over_feature_adapter_area() -> None:
    game_map = Map(width=60, height=44)
    feature = TerrainFeature(
        TerrainType.RUINS,
        Polygon([(10.0, 10.0), (16.0, 10.0), (16.0, 16.0), (10.0, 16.0)]),
        bounding_box={"min": (10.0, 10.0, 0.0), "max": (16.0, 16.0, 6.0)},
        traversal_rules={"provides_cover": True},
    )
    feature._id = "terrain_feature:authored"
    authored_area = TerrainArea(
        Polygon([(10.0, 10.0), (16.0, 10.0), (16.0, 16.0), (10.0, 16.0)]),
        area_id="terrain_area:authored",
        related_feature_ids=[feature.id],
        layout_slot_id="layout:authored",
    )
    game_map.terrain_features = [feature]
    game_map.terrain_areas = [authored_area]

    area_ids = [area.id for area in iter_terrain_areas(game_map)]

    assert area_ids == ["terrain_area:authored"]


def test_visibility_context_blocks_hidden_target_beyond_detection_range() -> None:
    game_map, attacker, _attacker_unit, target_unit = _build_units((40.0, 12.0, 0.0), [(12.0, 12.0, 0.0)])
    game_map.preview_visibility_semantics_enabled = True
    game_map.preview_visibility_ruleset = "test_preview"
    target_unit.terrain_hidden_active = True
    target_unit.terrain_hidden_eligible = True
    hidden_area = TerrainArea(
        Polygon([(8.0, 8.0), (16.0, 8.0), (16.0, 16.0), (8.0, 16.0)]),
        area_id="terrain_area:hidden",
        effect_tags=["HIDDEN_CAPABLE"],
        detection_range=15.0,
    )
    game_map.terrain_areas = [hidden_area]

    context = game_map.get_visibility_context_for_models(attacker, target_unit.models[0])

    assert context["visible"] is False
    assert context["hidden_state_active"] is True
    assert context["hidden_blocked"] is True
    assert context["hidden_detection_range"] == 15.0
    assert context["reason_trace"][1]["code"] == "HIDDEN_BLOCKED_BY_DETECTION_RANGE"


def test_visibility_context_allows_detection_range_override_for_hidden_target() -> None:
    game_map, attacker, _attacker_unit, target_unit = _build_units((20.0, 12.0, 0.0), [(12.0, 12.0, 0.0)])
    game_map.preview_visibility_semantics_enabled = True
    game_map.preview_visibility_ruleset = "test_preview"
    target_unit.terrain_hidden_active = True
    target_unit.terrain_hidden_eligible = True
    hidden_area = TerrainArea(
        Polygon([(8.0, 8.0), (16.0, 8.0), (16.0, 16.0), (8.0, 16.0)]),
        area_id="terrain_area:hidden_visible",
        effect_tags=["HIDDEN_CAPABLE"],
        detection_range=15.0,
    )
    game_map.terrain_areas = [hidden_area]

    context = game_map.get_visibility_context_for_models(attacker, target_unit.models[0])

    assert context["visible"] is True
    assert context["hidden_state_active"] is True
    assert context["detection_range_override_applies"] is True
    assert context["reason_trace"][1]["code"] == "DETECTION_RANGE_OVERRIDE_APPLIES"


def test_visibility_context_blocks_through_obscuring_area() -> None:
    game_map, attacker, _attacker_unit, target_unit = _build_units((8.0, 12.0, 0.0), [(28.0, 12.0, 0.0)])
    game_map.preview_visibility_semantics_enabled = True
    game_map.preview_visibility_ruleset = "test_preview"
    obscuring_area = TerrainArea(
        Polygon([(14.0, 8.0), (22.0, 8.0), (22.0, 16.0), (14.0, 16.0)]),
        area_id="terrain_area:obscuring",
        obscuring=True,
    )
    game_map.terrain_areas = [obscuring_area]

    context = game_map.get_visibility_context_for_models(attacker, target_unit.models[0])

    assert context["visible"] is False
    assert context["obscuring_state"] is True
    assert context["reason_trace"][0]["code"] == "OBSCURING_AREA_BLOCKS_VISIBILITY"


def test_visibility_context_leaves_preview_semantics_disabled_until_explicitly_enabled() -> None:
    game_map, attacker, _attacker_unit, target_unit = _build_units((40.0, 12.0, 0.0), [(12.0, 12.0, 0.0)])
    target_unit.terrain_hidden_active = True
    target_unit.terrain_hidden_eligible = True
    game_map.terrain_areas = [
        TerrainArea(
            Polygon([(8.0, 8.0), (16.0, 8.0), (16.0, 16.0), (8.0, 16.0)]),
            area_id="terrain_area:hidden_disabled",
            effect_tags=["HIDDEN_CAPABLE"],
            detection_range=15.0,
            obscuring=True,
        )
    ]

    context = game_map.get_visibility_context_for_models(attacker, target_unit.models[0])

    assert context["preview_visibility_semantics_enabled"] is False
    assert context["hidden_state_active"] is False
    assert context["hidden_blocked"] is False
    assert context["obscuring_state"] is False


def test_visibility_context_reuses_cached_model_pair_geometry(monkeypatch) -> None:
    game_map, attacker, _attacker_unit, target_unit = _build_units((8.0, 12.0, 0.0), [(28.0, 12.0, 0.0)])
    blocking_feature = TerrainFeature(
        TerrainType.HILLS_AND_SEALED_BUILDINGS,
        Polygon([(14.0, 8.0), (22.0, 8.0), (22.0, 16.0), (14.0, 16.0)]),
        bounding_box={"min": (14.0, 8.0, 0.0), "max": (22.0, 16.0, 3.0)},
    )
    game_map.add_terrain_feature(blocking_feature)
    call_count = {"segments": 0}
    original = terrain_visibility.VisibilityFrameContext.segment_is_blocked

    def _counted_segment(self, *args, **kwargs):
        call_count["segments"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(terrain_visibility.VisibilityFrameContext, "segment_is_blocked", _counted_segment)

    first = game_map.get_visibility_context_for_models(attacker, target_unit.models[0])
    first_call_count = int(call_count["segments"])
    assert first_call_count > 0

    first["reason_trace"].append({"code": "MUTATED_BY_TEST", "detail": "", "metadata": {}})
    call_count["segments"] = 0
    second = game_map.get_visibility_context_for_models(attacker, target_unit.models[0])

    assert call_count["segments"] == 0
    assert second["visible"] is first["visible"]
    assert all(entry.get("code") != "MUTATED_BY_TEST" for entry in second["reason_trace"])


def test_plunging_fire_context_reports_preview_height_query_separately_from_legacy_threshold() -> None:
    game_map, attacker, _attacker_unit, target_unit = _build_units((5.0, 5.0, 3.12), [(20.0, 20.0, 0.0)])
    ruins = TerrainFactory.create_ruins([(0, 0), (10, 0), (10, 10), (0, 10)], num_floors=2)
    game_map.add_terrain_feature(ruins)

    context = game_map.get_plunging_fire_context(attacker, target_unit)

    assert context["attacker_on_qualifying_elevated_section"] is True
    assert context["legacy_height_qualifies"] is False
    assert context["target_contains_ground_level_models"] is True
    assert context["target_all_ground_level_models"] is True
    assert context["applies"] is False
    assert context["reason_trace"][0]["code"] == "ATTACKER_ON_QUALIFYING_ELEVATED_SECTION"
