from __future__ import annotations

import json

from shapely.geometry import Polygon

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory
from warhammer40k_ai.battlefield.objective_sites import ObjectiveSite
from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.mission_cards import SecondaryMissionCard
from warhammer40k_ai.engine.state_blob import canonical_omniscient_state, player_obs_state
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


def _game_with_army_build_state() -> tuple[Game, Player]:
    army = Army.with_detachment("Space Marines", "Gladius Task Force", points_limit=2000)
    army.faction_id = "SM"
    apply_validated_muster_to_army(
        army,
        ValidatedMuster(
            blueprint=ArmyBlueprint(
                faction="Space Marines",
                points_limit=2000,
                detachments=[
                    DetachmentSelection(
                        selection_id="detachment_alpha",
                        detachment_type="Gladius Task Force",
                        detachment_points_cost=2,
                    )
                ],
                detachment_points_budget=3,
                unit_entries=[
                    RosterEntry(
                        entry_id="unit_captain",
                        name="Captain",
                        count=1,
                        detachment_selection_id="detachment_alpha",
                        is_warlord=True,
                    )
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
                        bodyguard_entry_id="unit_captain",
                        leader_entry_id="unit_captain",
                    )
                ],
                force_disposition="Assault",
                allowed_force_dispositions=["Assault"],
            ),
            faction_id="SM",
            detachment_points_spent=2,
        ),
    )
    player = Player("P1", army=army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    return game, player


def test_canonical_state_blob_is_stable_under_serialization() -> None:
    p1 = Player("P1")
    p2 = Player("P2")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p2, p1])

    state_a = canonical_omniscient_state(game)
    state_b = canonical_omniscient_state(game)
    blob_a = json.dumps(state_a, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    blob_b = json.dumps(state_b, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    assert blob_a == blob_b
    player_ids = [entry["player_id"] for entry in state_a["players"]]
    assert player_ids == sorted(player_ids)


def test_player_perspective_state_hides_opponent_secondaries() -> None:
    p1 = Player("P1")
    p2 = Player("P2")
    p1.active_secondaries = [SecondaryMissionCard(name="Secure Home")]
    p2.active_secondaries = [SecondaryMissionCard(name="Hidden Plan")]
    p2.discarded_secondaries = [SecondaryMissionCard(name="Other Hidden Plan")]
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])

    obs = player_obs_state(game, p1.id)
    entries = {entry["player_id"]: entry for entry in obs["players"]}
    own = entries[p1.id]
    enemy = entries[p2.id]

    assert "active_secondary_names" in own
    assert "active_secondary_names" not in enemy
    assert enemy["active_secondary_count"] == 1
    assert enemy["discarded_secondary_count"] == 1


def test_state_blob_includes_army_build_state_and_descriptor_id() -> None:
    game, player = _game_with_army_build_state()

    omniscient = canonical_omniscient_state(game)
    observed = player_obs_state(game, player.id)
    army_build = dict(omniscient.get("army_build_state", {}) or {})

    assert str(omniscient.get("state_blob_version", "") or "") == "1.3.0"
    assert army_build["army_build_descriptor_id"].startswith("army_build_descriptor:")
    assert army_build["players"][0]["primary_detachment_type"] == "Gladius Task Force"
    assert army_build["players"][0]["detachment_points_summary"] == {
        "budget": 3,
        "spent": 2,
        "remaining": 1,
    }
    assert army_build["players"][0]["force_disposition"] == "Assault"
    assert observed["army_build_state"] == omniscient["army_build_state"]


def test_state_blob_includes_polygon_objective_sites_and_score_surfaces() -> None:
    player = Player("P1", army=Army.with_detachment("Chaos Daemons", "Test"))
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    site = ObjectiveSite.terrain_footprint(
        footprint=Polygon([(10.0, 10.0), (16.0, 10.0), (16.0, 16.0), (10.0, 16.0)]),
        feature_key="terrain_feature:central_ruin",
        feature_label="Central Ruin",
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
    site.sticky_controller = player
    site.sticky_minimum_control = 5

    state = canonical_omniscient_state(game)

    assert str(state.get("state_blob_version", "") or "") == "1.3.0"
    assert state["objectives"][0]["geometry"]["kind"] == "POLYGON_FOOTPRINT"
    assert state["objectives"][0]["sticky_minimum_control"] == 5
    assert state["control_regions"][0]["kind"] == "OBJECTIVE_CONTROL_FOOTPRINT"
    assert state["scoring_surfaces"][0]["score_source_id"] == f"score_source:objective:{objective.id}"
