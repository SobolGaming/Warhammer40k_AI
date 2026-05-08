from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest
from shapely.geometry import Polygon

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory
from warhammer40k_ai.battlefield.objective_sites import ObjectiveSite
from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.fight_move import _positions_match
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.replay import replay_decision_records
from warhammer40k_ai.engine.replay_store import ReplayStoreReader
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.army_attachments import AttachmentBinding
from warhammer40k_ai.roster.army_build import ArmyBlueprint, DetachmentSelection, RosterEntry, ValidatedMuster
from warhammer40k_ai.roster.army_runtime import apply_validated_muster_to_army
from warhammer40k_ai.roster.player import Player


def _build_game() -> tuple[Game, Player]:
    player = Player("P1")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    return game, player


def _queue_confirmation(game: Game, player: Player) -> DecisionRequest:
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm?",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
    )
    game.request_decision(request)
    return request


class _ReplayEntityRegistry:
    def __init__(self, units: dict[str, object]) -> None:
        self._units = dict(units)

    def get(self, entity_id: str, *, kind: str | None = None) -> object | None:
        if kind != "unit":
            return None
        return self._units.get(str(entity_id))


def _replay_game_with_model_ids(model_ids: list[str]) -> object:
    unit = SimpleNamespace(
        id="unit:stable",
        models=[SimpleNamespace(id=model_id) for model_id in list(model_ids)],
    )
    return SimpleNamespace(entity_registry=_ReplayEntityRegistry({unit.id: unit}))


def test_replay_model_id_map_preserves_stable_ids_when_payload_order_differs() -> None:
    game = _replay_game_with_model_ids(["model:a", "model:b"])
    payload = {
        "context": {"unit_id": "unit:stable"},
        "options": [
            {
                "payload": {
                    "model_positions": [
                        {"model_id": "model:b", "position": [2.0, 0.0, 0.0]},
                        {"model_id": "model:a", "position": [1.0, 0.0, 0.0]},
                    ]
                }
            }
        ],
    }

    assert ReplayStoreReader._runtime_model_id_map(game, payload, {}) == {}


def test_replay_model_id_map_remaps_generated_ids_when_no_stable_ids_match() -> None:
    game = _replay_game_with_model_ids(["runtime:a", "runtime:b"])
    payload = {
        "context": {"unit_id": "unit:stable"},
        "options": [
            {
                "payload": {
                    "model_positions": [
                        {"model_id": "recorded:a", "position": [1.0, 0.0, 0.0]},
                        {"model_id": "recorded:b", "position": [2.0, 0.0, 0.0]},
                    ]
                }
            }
        ],
    }

    assert ReplayStoreReader._runtime_model_id_map(game, payload, {}) == {
        "recorded:a": "runtime:a",
        "recorded:b": "runtime:b",
    }


def test_fight_move_position_match_tolerates_replay_snapshot_rounding() -> None:
    assert _positions_match(
        {
            "model_id": "model:a",
            "position": [32.944, 20.05, 0.0],
            "facing": 1.5059,
        },
        {
            "model_id": "model:a",
            "position": [32.943725706299475, 20.05049485625641, 0.0],
            "facing": 1.505885938984541,
        },
    )


def _build_complex_replay_game() -> tuple[Game, Player]:
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
                    ),
                    DetachmentSelection(
                        selection_id="detachment_beta",
                        detachment_type="1st Company Task Force",
                        detachment_points_cost=1,
                    ),
                ],
                detachment_points_budget=4,
                unit_entries=[
                    RosterEntry(
                        entry_id="unit_captain",
                        name="Captain",
                        count=1,
                        detachment_selection_id="detachment_alpha",
                        is_warlord=True,
                    ),
                    RosterEntry(
                        entry_id="unit_veterans",
                        name="Bladeguard Veterans",
                        count=3,
                        detachment_selection_id="detachment_beta",
                    ),
                ],
                attachment_bindings=[
                    AttachmentBinding(
                        binding_id="binding_1",
                        bodyguard_entry_id="unit_veterans",
                        leader_entry_id="unit_captain",
                    )
                ],
                force_disposition="Assault",
                allowed_force_dispositions=["Assault", "Skirmish"],
            ),
            faction_id="SM",
            detachment_points_spent=3,
        ),
    )
    player = Player("P1", army=army)
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
        conditions=lambda current_game, point=site: point.primary_score_source().is_active(point.controlling_player),
        location=site,
    )
    game.map.objectives = [objective]
    game.objectives = [objective]
    return game, player


def test_replay_decision_records_round_trip_matches_end_state() -> None:
    game, player = _build_game()
    request = _queue_confirmation(game, player)
    snapshot_before = game.save_snapshot()
    event_id_before = int(snapshot_before["events"][-1]["event_id"]) if snapshot_before.get("events") else 0

    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )
    apply_result = game.resolve_decision(result)
    assert apply_result.ok is True
    expected_snapshot = game.save_snapshot()
    decision_record = copy.deepcopy(game.decision_record_store.records[-1])
    event_tail = game.event_log.serialize_events(since_event_id=event_id_before)

    replayed_game, replay_results = replay_decision_records(
        snapshot_before,
        [decision_record],
        strict=True,
        event_tail=event_tail,
    )
    assert replay_results[0].ok is True
    replayed_snapshot = replayed_game.save_snapshot()

    expected_comp = dict(expected_snapshot)
    replayed_comp = dict(replayed_snapshot)
    expected_comp.pop("events", None)
    replayed_comp.pop("events", None)
    expected_blob = json.dumps(expected_comp, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    replayed_blob = json.dumps(replayed_comp, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert replayed_blob == expected_blob


def test_replay_decision_records_strict_mode_rejects_candidate_mismatch() -> None:
    game, player = _build_game()
    request = _queue_confirmation(game, player)
    snapshot_before = game.save_snapshot()
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )
    apply_result = game.resolve_decision(result)
    assert apply_result.ok is True

    bad_record = copy.deepcopy(game.decision_record_store.records[-1])
    bad_record["candidates"][0]["action_id"] = "tampered-action-id"

    with pytest.raises(ValueError, match="strict replay mismatch"):
        replay_decision_records(snapshot_before, [bad_record], strict=True)


def test_decision_record_preserves_request_context_for_replay_audit() -> None:
    game, player = _build_game()
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm round-start ability?",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
        context={
            "ability": "zealous_litanies",
            "ability_name": "Zealous Litanies",
            "army_id": "army:bt",
            "battle_round": 3,
            "allowed_choice_keys": {"RITE_OF_PERFERVID_WRATH", "CHORUS_OF_RELENTLESS_HATE"},
        },
    )
    game.request_decision(request)

    apply_result = game.resolve_decision(
        DecisionResult(
            decision_id=request.decision_id,
            player_id=player.id,
            option_id=request.options[0].option_id,
            payload={},
        )
    )

    assert apply_result.ok is True
    record = game.decision_record_store.records[-1]
    assert record["request_context"]["ability"] == "zealous_litanies"
    assert record["request_context"]["battle_round"] == 3
    assert record["request_context"]["allowed_choice_keys"] == [
        "CHORUS_OF_RELENTLESS_HATE",
        "RITE_OF_PERFERVID_WRATH",
    ]


def test_replay_decision_records_round_trip_preserves_army_build_and_objective_site_provenance() -> None:
    game, player = _build_complex_replay_game()
    request = _queue_confirmation(game, player)
    snapshot_before = game.save_snapshot()
    event_id_before = int(snapshot_before["events"][-1]["event_id"]) if snapshot_before.get("events") else 0

    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )
    apply_result = game.resolve_decision(result)
    assert apply_result.ok is True
    decision_record = copy.deepcopy(game.decision_record_store.records[-1])
    event_tail = game.event_log.serialize_events(since_event_id=event_id_before)

    army_build_state = dict(decision_record.get("omniscient_state", {}).get("army_build_state", {}) or {})
    assert army_build_state["players"][0]["force_disposition"] == "Assault"
    assert len(list(army_build_state["players"][0]["detachments"] or [])) == 2
    assert army_build_state["players"][0]["attachment_bindings"][0]["binding_id"] == "binding_1"
    assert decision_record["omniscient_state"]["control_regions"][0]["kind"] == "OBJECTIVE_CONTROL_FOOTPRINT"
    assert decision_record["omniscient_state"]["scoring_surfaces"][0]["score_source_id"].startswith(
        "score_source:objective:"
    )

    replayed_game, replay_results = replay_decision_records(
        snapshot_before,
        [decision_record],
        strict=True,
        event_tail=event_tail,
    )
    assert replay_results[0].ok is True
    replayed_state = replayed_game.decision_record_store.records[-1]["omniscient_state"]
    assert replayed_state["army_build_state"] == decision_record["omniscient_state"]["army_build_state"]
    assert replayed_state["control_regions"][0]["kind"] == "OBJECTIVE_CONTROL_FOOTPRINT"
    assert replayed_state["control_regions"][0]["feature_key"] == "terrain_feature:central_ruin"
    assert replayed_state["scoring_surfaces"][0]["score_source_id"] == decision_record["omniscient_state"]["scoring_surfaces"][0]["score_source_id"]
