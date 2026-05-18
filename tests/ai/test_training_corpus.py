from __future__ import annotations

from pathlib import Path

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.ml.training_corpus import (
    build_corpus_manifest,
    validate_self_play_corpus_batch,
)
from warhammer40k_ai.roster.player import Player


def _decision_record(*, game_id: str = "selfplay:test") -> dict:
    player = Player("P1")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
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
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )
    apply_result = game.resolve_decision(result)
    assert apply_result.ok is True
    record = dict(game.decision_record_store.records[-1])
    record["game_id"] = game_id
    record["turn_id"] = 1
    record["phase"] = "COMMAND_PHASE"
    record["wall_clock_ms"] = 7
    return record


def _report(*, game_id: str = "selfplay:test", diagnostics: bool = False) -> dict:
    result = {
        "game_id": game_id,
        "phase_steps": 1,
        "scoreboard": {"army_a": 12, "army_b": 9},
        "winner_army_label": "army_a",
        "replay_path": "",
        "snapshot_path": "",
    }
    if diagnostics:
        result["tool_action_probe_diagnostics"] = [
            {"severity": "WARNING", "tool_name": "TEST", "code": "diagnostic"}
        ]
    return {
        "player1_army": "army_a.txt",
        "player2_army": "army_b.txt",
        "games": [
            {
                "game_index": 0,
                "elapsed_seconds": 1.25,
                "result": result,
            }
        ],
    }


def test_validate_self_play_corpus_batch_accepts_schema_valid_records_without_replay_requirement() -> None:
    record = _decision_record()

    validation = validate_self_play_corpus_batch(
        records=[record],
        report=_report(),
        require_replay=False,
    )

    assert validation.accepted_game_count == 1
    assert validation.rejected_game_count == 0
    assert len(validation.accepted_records) == 1
    game = validation.games[0]
    assert game.accepted is True
    assert game.vp_delta == 3
    assert game.phase_timings[0]["decision_wall_clock_ms"] == 7


def test_validate_self_play_corpus_batch_rejects_engine_diagnostics() -> None:
    validation = validate_self_play_corpus_batch(
        records=[_decision_record()],
        report=_report(diagnostics=True),
        require_replay=False,
    )

    assert validation.accepted_game_count == 0
    assert validation.rejected_game_count == 1
    assert validation.accepted_records == ()
    assert validation.games[0].reasons == ("tool_action_probe_diagnostics:1",)


def test_validate_self_play_corpus_batch_rejects_mask_candidate_mismatch() -> None:
    record = _decision_record()
    record["mask"] = []

    validation = validate_self_play_corpus_batch(
        records=[record],
        report=_report(),
        require_replay=False,
    )

    assert validation.accepted_game_count == 0
    assert any(reason.startswith("decision_record_validation_errors:") for reason in validation.games[0].reasons)


def test_build_corpus_manifest_aggregates_accepted_game_phase_timings(tmp_path: Path) -> None:
    validation = validate_self_play_corpus_batch(
        records=[_decision_record()],
        report=_report(),
        require_replay=False,
    )

    manifest = build_corpus_manifest(
        source_tag="self_play",
        label_source="heuristic_headless_policy_v1",
        records_path=tmp_path / "records.json",
        training_manifest_path=tmp_path / "training_manifest.json",
        batches=[{"batch_index": 0}],
        games=validation.games,
        decision_record_count=1,
    )

    assert manifest["accepted_game_count"] == 1
    assert manifest["rejected_game_count"] == 0
    assert manifest["phase_timings"] == [
        {
            "battle_round": 1,
            "phase": "COMMAND_PHASE",
            "decision_count": 1,
            "decision_wall_clock_ms": 7,
            "mean_decision_wall_clock_ms": 7.0,
        }
    ]
