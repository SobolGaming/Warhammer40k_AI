from __future__ import annotations

from shapely.geometry import Polygon

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, TerrainArea, TerrainFeature, TerrainType
from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine import descriptor_compiler
from warhammer40k_ai.engine.descriptor_compiler import compile_descriptor_bundle
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.battlefield.objective_sites import ObjectiveSite
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.army_attachments import AttachmentBinding
from warhammer40k_ai.roster.army_build import (
    ArmyBlueprint,
    DetachmentSelection,
    EnhancementAssignment,
    RosterEntry,
    ValidatedMuster,
)
from warhammer40k_ai.roster.army_runtime import apply_validated_muster_to_army
from warhammer40k_ai.roster.player import Player


def _build_game() -> tuple[Game, Player]:
    player = Player("P1")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    return game, player


def _build_game_with_army_build() -> tuple[Game, Player]:
    army = Army.with_detachment("Space Marines", "Gladius Task Force", points_limit=2000)
    army.faction_id = "SM"
    validated_muster = ValidatedMuster(
        blueprint=ArmyBlueprint(
            faction="Space Marines",
            points_limit=2000,
            battle_size="Strike Force",
            detachments=[
                DetachmentSelection(
                    selection_id="detachment_alpha",
                    detachment_type="Gladius Task Force",
                    detachment_points_cost=2,
                ),
                DetachmentSelection(
                    selection_id="detachment_beta",
                    detachment_type="1st Company Task Force",
                    detachment_points_cost=3,
                ),
            ],
            detachment_points_budget=5,
            unit_entries=[
                RosterEntry(
                    entry_id="unit_captain",
                    name="Captain",
                    count=1,
                    detachment_selection_id="detachment_alpha",
                    is_warlord=True,
                ),
                RosterEntry(
                    entry_id="unit_bladeguard",
                    name="Bladeguard Veterans",
                    count=3,
                    detachment_selection_id="detachment_beta",
                ),
            ],
            enhancement_assignments=[
                EnhancementAssignment(
                    assignment_id="enhancement_1",
                    enhancement_name="Honours of Battle",
                    target_entry_id="unit_captain",
                    detachment_selection_id="detachment_alpha",
                )
            ],
            attachment_bindings=[
                AttachmentBinding(
                    binding_id="binding_1",
                    bodyguard_entry_id="unit_bladeguard",
                    leader_entry_id="unit_captain",
                )
            ],
            force_disposition="Assault",
            allowed_force_dispositions=["Assault", "Siege"],
            metadata={"source": "test"},
        ),
        faction_id="SM",
        detachment_points_spent=5,
    )
    apply_validated_muster_to_army(army, validated_muster)
    player = Player("P1", army=army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    return game, player


def test_descriptor_compiler_is_deterministic_for_same_state() -> None:
    game, _player = _build_game()
    first = compile_descriptor_bundle(game)
    second = compile_descriptor_bundle(game)

    assert first.bundle_id == second.bundle_id
    assert first.descriptor_ids() == second.descriptor_ids()
    assert first.descriptor_ids()["mission_descriptor_id"].startswith("mission_descriptor:")
    assert first.descriptor_ids()["deployment_descriptor_id"].startswith("deployment_descriptor:")
    assert first.descriptor_ids()["army_build_descriptor_id"].startswith("army_build_descriptor:")


def test_descriptor_compiler_reuses_static_terrain_and_tool_descriptors(monkeypatch) -> None:
    game, _player = _build_game()
    calls = {"terrain": 0, "tools": 0}
    original_terrain = descriptor_compiler.compile_terrain_descriptors
    original_tools = descriptor_compiler.compile_tool_descriptors

    def _compile_terrain(current_game):
        calls["terrain"] += 1
        return original_terrain(current_game)

    def _compile_tools(current_game):
        calls["tools"] += 1
        return original_tools(current_game)

    monkeypatch.setattr(descriptor_compiler, "compile_terrain_descriptors", _compile_terrain)
    monkeypatch.setattr(descriptor_compiler, "compile_tool_descriptors", _compile_tools)

    first = compile_descriptor_bundle(game)
    second = compile_descriptor_bundle(game)

    assert first.descriptor_ids()["terrain_descriptor_ids"] == second.descriptor_ids()["terrain_descriptor_ids"]
    assert first.descriptor_ids()["tool_descriptor_ids"] == second.descriptor_ids()["tool_descriptor_ids"]
    assert calls == {"terrain": 1, "tools": 1}


def test_descriptor_compiler_terrain_cache_honors_revision_change(monkeypatch) -> None:
    game, _player = _build_game()
    calls = {"terrain": 0}
    original_terrain = descriptor_compiler.compile_terrain_descriptors

    def _compile_terrain(current_game):
        calls["terrain"] += 1
        return original_terrain(current_game)

    monkeypatch.setattr(descriptor_compiler, "compile_terrain_descriptors", _compile_terrain)

    compile_descriptor_bundle(game)
    compile_descriptor_bundle(game)
    game.map.terrain_revision = 1
    compile_descriptor_bundle(game)

    assert calls["terrain"] == 2


def test_descriptor_compiler_dynamic_mission_descriptor_updates_with_turn() -> None:
    game, _player = _build_game()

    first = compile_descriptor_bundle(game)
    game.turn += 1
    second = compile_descriptor_bundle(game)

    assert first.descriptor_ids()["mission_descriptor_id"] != second.descriptor_ids()["mission_descriptor_id"]


def test_descriptor_compiler_emits_army_build_descriptor_from_validated_muster() -> None:
    game, _player = _build_game_with_army_build()

    bundle = compile_descriptor_bundle(game)
    payload = bundle.army_build_descriptor.payload

    assert bundle.army_build_descriptor.family == "ArmyBuildDescriptor"
    assert bundle.descriptor_ids()["army_build_descriptor_id"].startswith("army_build_descriptor:")
    assert payload["players"][0]["army_blueprint_hash"].startswith("sha256:")
    assert payload["players"][0]["primary_detachment_type"] == "Gladius Task Force"
    assert payload["players"][0]["detachment_points_summary"] == {
        "budget": 5,
        "spent": 5,
        "remaining": 0,
    }
    assert payload["players"][0]["attachment_bindings"][0]["binding_id"] == "binding_1"
    assert payload["players"][0]["validated_muster"]["faction_id"] == "SM"
    assert "legacy_single_detachment_adapter_used" not in payload["players"][0]["validated_muster"]
    assert "legacy_single_detachment_adapter_used" not in payload["players"][0]["build_metadata"]


def test_descriptor_compiler_normalizes_empty_detachment_points_summary() -> None:
    army = Army.with_detachment("Space Marines", "Gladius Task Force", points_limit=2000)
    army.faction_id = "SM"
    player = Player("P1", army=army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])

    bundle = compile_descriptor_bundle(game)
    payload = bundle.army_build_descriptor.payload

    assert payload["players"][0]["detachment_points_summary"] == {
        "budget": None,
        "spent": 0,
        "remaining": None,
    }


def test_request_decision_injects_compiled_descriptor_ids() -> None:
    game, player = _build_game_with_army_build()
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm action?",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
    )

    game.request_decision(request)
    descriptor_ids = request.context["descriptor_ids"]

    assert descriptor_ids["mission_descriptor_id"].startswith("mission_descriptor:")
    assert descriptor_ids["deployment_descriptor_id"].startswith("deployment_descriptor:")
    assert descriptor_ids["army_build_descriptor_id"].startswith("army_build_descriptor:")
    assert isinstance(descriptor_ids["objective_descriptor_ids"], list)
    assert isinstance(descriptor_ids["terrain_descriptor_ids"], list)
    assert isinstance(descriptor_ids["tool_descriptor_ids"], list)
    assert request.context["descriptor_bundle_id"].startswith("descriptor_bundle:")


def test_record_resolution_without_context_uses_compiled_descriptor_ids() -> None:
    game, player = _build_game_with_army_build()
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm action?",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )
    record = game.decision_record_store.record_resolution(
        request=request,
        result=result,
        ok=True,
        errors=(),
        value=None,
        wall_clock_ms=1,
    )

    descriptor_ids = record["descriptor_ids"]
    assert descriptor_ids["mission_descriptor_id"].startswith("mission_descriptor:")
    assert descriptor_ids["deployment_descriptor_id"].startswith("deployment_descriptor:")
    assert descriptor_ids["army_build_descriptor_id"].startswith("army_build_descriptor:")
    assert isinstance(descriptor_ids["objective_descriptor_ids"], list)
    assert isinstance(descriptor_ids["terrain_descriptor_ids"], list)
    assert isinstance(descriptor_ids["tool_descriptor_ids"], list)


def test_descriptor_compiler_emits_polygon_objective_site_semantics() -> None:
    game, _player = _build_game()
    feature = TerrainFeature(
        TerrainType.RUINS,
        Polygon([(8.0, 8.0), (14.0, 8.0), (14.0, 14.0), (8.0, 14.0)]),
        bounding_box={"min": (8.0, 8.0, 0.0), "max": (14.0, 14.0, 6.0)},
        traversal_rules={"provides_cover": True},
    )
    feature._id = "terrain_feature:test"
    terrain_area = TerrainArea(
        Polygon([(8.0, 8.0), (14.0, 8.0), (14.0, 14.0), (8.0, 14.0)]),
        area_id="terrain_area:test",
        effect_tags=["RUINS", "OBSCURING"],
        cover_mode="LEGACY_FEATURE_RULES",
        obscuring=True,
        related_feature_ids=[feature.id],
        layout_slot_id="layout:center_ruin",
    )
    game.map.terrain_features = [feature]
    game.map.terrain_areas = [terrain_area]
    site = ObjectiveSite.terrain_footprint(
        footprint=Polygon([(8.0, 8.0), (14.0, 8.0), (14.0, 14.0), (8.0, 14.0)]),
        feature_key=feature.id,
        feature_label="Central Ruin",
        terrain_area_id=terrain_area.id,
        layout_slot_id=terrain_area.layout_slot_id,
    )
    objective = Objective(
        name="Central Ruin Objective",
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="Control the ruin footprint",
        conditions=lambda game, point=site: point.primary_score_source().is_active(point.controlling_player),
        location=site,
    )
    game.map.objectives = [objective]
    game.objectives = [objective]

    bundle = compile_descriptor_bundle(game)
    objective_payload = bundle.objective_descriptors[0].payload
    terrain_payloads = {descriptor.payload["terrain_id"]: descriptor.payload for descriptor in bundle.terrain_descriptors}

    assert objective_payload["site_kind"] == "TERRAIN_FOOTPRINT"
    assert objective_payload["geometry"]["kind"] == "POLYGON_FOOTPRINT"
    assert objective_payload["geometry"]["terrain_area_id"] == terrain_area.id
    assert objective_payload["geometry"]["layout_slot_id"] == "layout:center_ruin"
    assert objective_payload["control_region"]["kind"] == "OBJECTIVE_CONTROL_FOOTPRINT"
    assert objective_payload["score_source_bindings"] == [f"score_source:objective:{objective.id}"]
    assert bundle.mission_descriptor.payload["primary_scoring_sources"] == [f"score_source:objective:{objective.id}"]
    assert terrain_payloads[feature.id]["terrain_runtime_kind"] == "FEATURE"
    assert terrain_payloads[terrain_area.id]["terrain_runtime_kind"] == "AREA"
    assert terrain_payloads[terrain_area.id]["terrain_area"]["layout_slot_id"] == "layout:center_ruin"


def test_descriptor_compiler_is_deterministic_when_terrain_areas_are_present() -> None:
    game, _player = _build_game()
    feature = TerrainFeature(
        TerrainType.RUINS,
        Polygon([(20.0, 20.0), (26.0, 20.0), (26.0, 26.0), (20.0, 26.0)]),
        bounding_box={"min": (20.0, 20.0, 0.0), "max": (26.0, 26.0, 6.0)},
        traversal_rules={"provides_cover": True},
    )
    feature._id = "terrain_feature:deterministic"
    game.map.terrain_features = [feature]
    game.map.terrain_areas = [
        TerrainArea(
            Polygon([(20.0, 20.0), (26.0, 20.0), (26.0, 26.0), (20.0, 26.0)]),
            area_id="terrain_area:deterministic",
            effect_tags=["RUINS", "OBSCURING"],
            cover_mode="LEGACY_FEATURE_RULES",
            obscuring=True,
            related_feature_ids=[feature.id],
            layout_slot_id="layout:deterministic",
        )
    ]

    first = compile_descriptor_bundle(game)
    second = compile_descriptor_bundle(game)

    assert first.bundle_id == second.bundle_id
    assert first.descriptor_ids()["terrain_descriptor_ids"] == second.descriptor_ids()["terrain_descriptor_ids"]
