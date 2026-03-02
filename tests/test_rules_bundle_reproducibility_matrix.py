from __future__ import annotations

import copy

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.replay import replay_decision_records
from warhammer40k_ai.engine.ruleset import RulesetBundle
from warhammer40k_ai.engine.snapshot import load_game_snapshot
from warhammer40k_ai.engine.state_blob import canonical_omniscient_state, player_obs_state
from warhammer40k_ai.roster.player import Player


def _build_ruleset_bundle() -> RulesetBundle:
    return RulesetBundle.from_values(
        core_rules_id="core_rules_10e_2026_01_30",
        rules_commentary_id="rules_commentary_10e_2026_01_30",
        mission_pack_id="mission_pack_2026_gt",
        terrain_pack_id="terrain_pack_2026_open",
        dataslate_id="dataslate_2026_q1",
        points_id="points_2026_mfm_q1",
        faction_pack_id="faction_pack_2026_q1",
        detachment_pack_id="detachment_pack_2026_q1",
    )


def _build_game() -> tuple[Game, Player, RulesetBundle]:
    player = Player("P1")
    ruleset_bundle = _build_ruleset_bundle()
    game = Game(
        Battlefield(BattlefieldSize.STRIKE_FORCE),
        players=[player],
        ruleset_bundle=ruleset_bundle,
    )
    return game, player, ruleset_bundle


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


def test_rules_bundle_matrix_decision_record_logging_stability() -> None:
    game, player, ruleset_bundle = _build_game()
    request = _queue_confirmation(game, player)
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )
    apply_result = game.resolve_decision(result)
    assert apply_result.ok is True

    expected_atomic = ruleset_bundle.to_dict()
    expected_id = str(ruleset_bundle.rules_bundle_id)
    record = dict(game.decision_record_store.records[-1] or {})
    assert dict(request.context.get("rules_bundle", {}) or {}) == expected_atomic
    assert str(request.context.get("rules_bundle_id", "") or "") == expected_id
    assert dict(record.get("rules_bundle", {}) or {}) == expected_atomic
    assert str(record.get("rules_bundle_id", "") or "") == expected_id


def test_rules_bundle_matrix_snapshot_save_load_stability() -> None:
    game, _player, ruleset_bundle = _build_game()
    expected_atomic = ruleset_bundle.to_dict()
    expected_id = str(ruleset_bundle.rules_bundle_id)

    snapshot = game.save_snapshot()
    snapshot_ruleset = dict(dict(snapshot.get("game", {}) or {}).get("ruleset", {}) or {})
    assert snapshot_ruleset.get("rules_bundle_id") == expected_id
    for key, value in expected_atomic.items():
        assert snapshot_ruleset.get(key) == value

    loaded = load_game_snapshot(snapshot)
    assert loaded.ruleset_bundle is not None
    assert dict(loaded.ruleset_bundle.to_dict() or {}) == expected_atomic
    assert str(loaded.ruleset_bundle.rules_bundle_id or "") == expected_id

    round_trip_snapshot = loaded.save_snapshot()
    round_trip_ruleset = dict(dict(round_trip_snapshot.get("game", {}) or {}).get("ruleset", {}) or {})
    assert round_trip_ruleset.get("rules_bundle_id") == expected_id
    for key, value in expected_atomic.items():
        assert round_trip_ruleset.get(key) == value


def test_rules_bundle_matrix_state_blob_stability() -> None:
    game, player, ruleset_bundle = _build_game()
    expected = dict(ruleset_bundle.to_dict() or {})
    expected["rules_bundle_id"] = str(ruleset_bundle.rules_bundle_id)

    omniscient = canonical_omniscient_state(game)
    player_obs = player_obs_state(game, player.id)

    assert dict(omniscient.get("rules_bundle", {}) or {}) == expected
    assert dict(player_obs.get("rules_bundle", {}) or {}) == expected


def test_rules_bundle_matrix_strict_replay_round_trip_stability() -> None:
    game, player, ruleset_bundle = _build_game()
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

    expected_atomic = ruleset_bundle.to_dict()
    expected_id = str(ruleset_bundle.rules_bundle_id)
    decision_record = copy.deepcopy(game.decision_record_store.records[-1])
    event_tail = game.event_log.serialize_events(since_event_id=event_id_before)

    replayed_game, replay_results = replay_decision_records(
        snapshot_before,
        [decision_record],
        strict=True,
        event_tail=event_tail,
    )
    assert replay_results[0].ok is True
    replay_record = dict(replayed_game.decision_record_store.records[-1] or {})
    assert dict(decision_record.get("rules_bundle", {}) or {}) == expected_atomic
    assert str(decision_record.get("rules_bundle_id", "") or "") == expected_id
    assert dict(replay_record.get("rules_bundle", {}) or {}) == expected_atomic
    assert str(replay_record.get("rules_bundle_id", "") or "") == expected_id
