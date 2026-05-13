from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from warhammer40k_ai.battlefield.detection_markers import (
    DetectionMarker,
    VisibilityModifierQuery,
    VisibilityRangeModifier,
)
from warhammer40k_ai.battlefield.hidden_state import HiddenShootingExemption
from warhammer40k_ai.battlefield.map import Map, TerrainArea
from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.snapshot import load_game_snapshot, snapshot_game
from warhammer40k_ai.engine.state_blob import canonical_omniscient_state
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.utility.model_base import Base, BaseType


pytestmark = pytest.mark.preview


ADEPTA_SORORITAS_SOURCE = "wc_2026_05_11_adepta_sororitas_faction_focus"
ASTRA_MILITARUM_SOURCE = "wc_2026_05_06_astra_militarum_faction_focus"
SPACE_MARINES_SOURCE = "wc_2026_05_05_space_marines_faction_focus"
TAU_EMPIRE_SOURCE = "wc_2026_05_13_tau_empire_faction_focus"


class _StubPlayer:
    def __init__(self, game):
        self.game = game


class _StubArmy:
    def __init__(self, player):
        self.player = player


class _StubUnit:
    def __init__(self, unit_id: str, models: list[Model], army: _StubArmy) -> None:
        self._id = unit_id
        self.name = unit_id
        self.models = models
        self._army = army
        self.keywords = ["INFANTRY"]
        self.is_towering = False
        self.is_aircraft = False
        for model in self.models:
            model.set_parent_unit(self)

    @property
    def id(self) -> str:
        return self._id

    def get_parent_army(self):
        return self._army

    def has_any_keyword(self, keyword: str) -> bool:
        return str(keyword).strip().upper() in set(self.keywords)


def _make_model(model_id: str, x_pos: float, y_pos: float) -> Model:
    model = Model(
        name=model_id,
        movement=6,
        toughness=4,
        save=3,
        wounds=2,
        leadership=6,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 0.5),
    )
    model._id = model_id
    model.set_location(x_pos, y_pos, 0.0, 0.0)
    return model


def _hidden_visibility_fixture(*, attacker_x: float = 29.5) -> tuple[Map, _StubUnit, _StubUnit]:
    game_map = Map(width=60, height=44)
    game_map.preview_visibility_semantics_enabled = True
    game_map.preview_visibility_ruleset = "preview_11e_faction_focus_may2026"
    game = type("_StubGame", (), {"map": game_map})()
    player = _StubPlayer(game)
    army = _StubArmy(player)
    attacker = _StubUnit("unit:attacker", [_make_model("model:attacker", attacker_x, 12.0)], army)
    target = _StubUnit("unit:target", [_make_model("model:target", 12.0, 12.0)], army)
    target.terrain_hidden_eligible = True
    game_map.terrain_areas = [
        TerrainArea(
            Polygon([(8.0, 8.0), (16.0, 8.0), (16.0, 16.0), (8.0, 16.0)]),
            area_id="terrain_area:hidden",
            effect_tags=["HIDDEN_CAPABLE"],
            detection_range=15.0,
        )
    ]
    game_map.terrain_hidden_current_player_turn = "player:one:turn:1"
    game_map.units = [attacker, target]
    return game_map, attacker, target


@pytest.mark.parametrize(
    ("marker_label", "source_id"),
    [
        ("detected", SPACE_MARINES_SOURCE),
        ("condemned", ADEPTA_SORORITAS_SOURCE),
        ("designated", ASTRA_MILITARUM_SOURCE),
        ("prey_marked", TAU_EMPIRE_SOURCE),
    ],
)
def test_generic_detection_marker_labels_share_detection_range_delta(marker_label: str, source_id: str) -> None:
    game_map, attacker, target = _hidden_visibility_fixture()

    blocked = game_map.get_visibility_context_for_models(attacker.models[0], target.models[0])
    assert blocked["hidden_blocked"] is True

    game_map.add_detection_marker(
        DetectionMarker(
            marker_id=marker_label,
            source_unit_id=attacker.id,
            target_unit_id=target.id,
            detection_range_delta=3.0,
            duration="until_end_of_phase",
            source_provenance=(source_id,),
        )
    )

    context = game_map.get_visibility_context_for_models(attacker.models[0], target.models[0])

    assert context["visible"] is True
    assert context["hidden_detection_range_base"] == 15.0
    assert context["hidden_detection_range"] == 18.0
    assert context["detection_marker_delta"] == 3.0
    assert context["applied_detection_marker_ids"] == [marker_label]
    assert any(entry["code"] == "DETECTION_MARKER_DELTA_APPLIED" for entry in context["reason_trace"])


def test_attack_scoped_detection_modifier_only_applies_to_active_shooting_unit() -> None:
    game_map, attacker, target = _hidden_visibility_fixture(attacker_x=32.0)
    modifier = VisibilityRangeModifier(
        modifier_id="while_shooting:+6",
        source_unit_id=attacker.id,
        target_unit_id=target.id,
        active_unit_id=attacker.id,
        scope="while_shooting",
        detection_range_delta=6.0,
        source_provenance=(ADEPTA_SORORITAS_SOURCE,),
    )

    inactive_query = VisibilityModifierQuery(
        source_unit_id=attacker.id,
        target_unit_id=target.id,
        active_shooting_unit_id="unit:other",
        attack_scoped_modifiers=(modifier,),
    )
    inactive = game_map.get_visibility_context_for_models(
        attacker.models[0],
        target.models[0],
        visibility_query=inactive_query,
    )
    assert inactive["hidden_blocked"] is True
    assert inactive["attack_scoped_detection_range_delta"] == 0.0

    active_query = VisibilityModifierQuery(
        source_unit_id=attacker.id,
        target_unit_id=target.id,
        active_shooting_unit_id=attacker.id,
        attack_scoped_modifiers=(modifier,),
    )
    active = game_map.get_visibility_context_for_models(
        attacker.models[0],
        target.models[0],
        visibility_query=active_query,
    )

    assert active["visible"] is True
    assert active["hidden_detection_range"] == 21.0
    assert active["attack_scoped_detection_range_delta"] == 6.0
    assert active["applied_visibility_modifier_ids"] == ["while_shooting:+6"]


def test_detection_markers_do_not_change_visibility_when_preview_gate_is_disabled() -> None:
    game_map, attacker, target = _hidden_visibility_fixture()
    game_map.preview_visibility_semantics_enabled = False
    game_map.add_detection_marker(
        DetectionMarker(
            marker_id="detected",
            source_unit_id=attacker.id,
            target_unit_id=target.id,
            detection_range_delta=3.0,
            duration="until_end_of_phase",
        )
    )

    context = game_map.get_visibility_context_for_models(attacker.models[0], target.models[0])

    assert context["preview_visibility_semantics_enabled"] is False
    assert context["hidden_state_active"] is False
    assert context["detection_marker_delta"] == 0.0
    assert context["applied_detection_marker_ids"] == []


def test_hidden_preserving_shooting_exemption_keeps_hidden_after_shooting() -> None:
    game_map, attacker, target = _hidden_visibility_fixture()
    target.terrain_hidden_last_shot_player_turn = "player:one:turn:1"

    cleared = game_map.get_visibility_context_for_models(attacker.models[0], target.models[0])
    assert cleared["hidden_state_active"] is False
    assert cleared["hidden_blocked"] is False

    game_map.add_hidden_shooting_exemption(
        HiddenShootingExemption(
            exemption_id="pathfinder_hidden_preserving_shooting",
            unit_id=target.id,
            source_id="preview:unit_rule",
            duration="current_player_turn",
            source_provenance=(TAU_EMPIRE_SOURCE,),
        )
    )

    preserved = game_map.get_visibility_context_for_models(attacker.models[0], target.models[0])

    assert preserved["hidden_state_active"] is True
    assert preserved["hidden_blocked"] is True
    assert preserved["hidden_shooting_exemption_ids"] == ["pathfinder_hidden_preserving_shooting"]


def test_detection_marker_and_hidden_exemption_are_snapshot_and_state_blob_visible() -> None:
    player = Player("Player One", army=Army.with_detachment("Chaos Daemons", "Test"))
    game = Game(Battlefield(width=60, height=44), players=[player])
    game.map.preview_visibility_semantics_enabled = True
    game.map.preview_visibility_ruleset = "preview_11e_faction_focus_may2026"
    game.map.add_detection_marker(
        DetectionMarker(
            marker_id="detected",
            source_unit_id="unit:source",
            target_unit_id="unit:target",
            detection_range_delta=3.0,
            duration="until_end_of_phase",
            source_detachment_id="detachment:preview",
            source_provenance=(SPACE_MARINES_SOURCE,),
        )
    )
    game.map.add_hidden_shooting_exemption(
        HiddenShootingExemption(
            exemption_id="stealth_hidden_preserving_shooting",
            unit_id="unit:target",
            source_id="rule:preview",
            duration="current_player_turn",
            source_provenance=(TAU_EMPIRE_SOURCE,),
        )
    )

    payload = snapshot_game(game)
    loaded = load_game_snapshot(payload)
    state_blob = canonical_omniscient_state(loaded)
    event_types = [event["type"] for event in payload["events"]]

    assert event_types == ["detection_marker_added", "hidden_shooting_exemption_added"]
    assert loaded.map.preview_visibility_semantics_enabled is True
    assert loaded.map.preview_visibility_ruleset == "preview_11e_faction_focus_may2026"
    assert loaded.map.detection_markers[0].to_dict()["marker_id"] == "detected"
    assert loaded.map.hidden_shooting_exemptions[0].to_dict()["exemption_id"] == "stealth_hidden_preserving_shooting"
    assert state_blob["detection_markers"][0]["target_unit_id"] == "unit:target"
    assert state_blob["hidden_shooting_exemptions"][0]["unit_id"] == "unit:target"
