from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.event_log import DeterministicEventLog
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.utility import dice as dice_mod
from warhammer40k_ai.utility.game_context import game_context


def _game_with_seed(seed: int = 12345) -> Game:
    game = Game(Battlefield(width=60, height=44), players=[])
    game.random_source.seed(seed)
    return game


def _record_prior_decision(game: Game, action_id: str) -> None:
    game.event_log.record(
        "decision_resolved",
        actor_id="player:test",
        payload={
            "decision_id": "decision:charge-activation",
            "chosen_action_id": str(action_id),
        },
        validate_payload=False,
    )


def _legacy_dice_after_action(action_id: str) -> list[int]:
    game = _game_with_seed()
    _record_prior_decision(game, action_id)
    with game_context(game):
        return [dice_mod.get_dice_roll(6) for _ in range(12)]


def _managed_charge_roll_after_action(action_id: str) -> list[int]:
    game = _game_with_seed()
    game.auto_resolve_dice_rolls = False
    _record_prior_decision(game, action_id)
    request = game.request_dice_roll(
        player_id="player:test",
        spec={
            "dice_count": 2,
            "faces": 6,
            "roll_type": "charge",
            "reason": "Counterfactual charge roll",
            "unit_id": "unit:charger",
            "target_unit_ids": ["unit:target"],
            "sum_target": 7,
            "sum_op": "gte",
        },
        prompt="Counterfactual charge roll",
    )
    state = game.roll_manager.resolve_roll(game, int(request.context["roll_id"]))
    return [int(d.get("raw_value", d.get("value", 0)) or 0) for d in list(state.dice or [])]


def test_branch_scoped_legacy_dice_are_stable_for_identical_history() -> None:
    assert _legacy_dice_after_action("charge:unit-a") == _legacy_dice_after_action("charge:unit-a")


def test_branch_scoped_legacy_dice_change_after_divergent_history() -> None:
    assert _legacy_dice_after_action("charge:unit-a") != _legacy_dice_after_action("charge:unit-b")


def test_branch_scoped_managed_charge_roll_changes_after_divergent_history() -> None:
    assert _managed_charge_roll_after_action("charge:unit-a") == _managed_charge_roll_after_action("charge:unit-a")
    assert _managed_charge_roll_after_action("charge:unit-a") != _managed_charge_roll_after_action("charge:unit-b")


def test_replay_history_hash_uses_consumed_prefix_only() -> None:
    game = _game_with_seed()
    game.event_log.record("decision_resolved", payload={"decision_id": "one"}, validate_payload=False)
    game.event_log.record("decision_resolved", payload={"decision_id": "two"}, validate_payload=False)
    events = game.event_log.serialize_events()

    replay_a = Game(Battlefield(width=60, height=44), players=[])
    replay_a.event_log.detach()
    replay_a.event_log = DeterministicEventLog.from_payload(events, mode="replay")
    replay_a.event_log.attach(replay_a)
    replay_a.random_source.seed(12345)

    replay_b = Game(Battlefield(width=60, height=44), players=[])
    replay_b.event_log.detach()
    replay_b.event_log = DeterministicEventLog.from_payload(events[:1], mode="replay")
    replay_b.event_log.attach(replay_b)
    replay_b.random_source.seed(12345)

    replay_a.event_log.consume("decision_resolved")
    replay_b.event_log.consume("decision_resolved")

    assert replay_a.event_log.compute_history_hash() == replay_b.event_log.compute_history_hash()


def test_branch_scoped_rng_is_neutral_to_event_log_pruning() -> None:
    pruned = _game_with_seed()
    retained = _game_with_seed()
    pruned.event_log.max_events = 3
    retained.event_log.max_events = 0
    for idx in range(8):
        payload = {
            "decision_id": f"decision:{idx}",
            "chosen_action_id": f"action:{idx % 2}",
        }
        pruned.event_log.record("decision_resolved", payload=payload, validate_payload=False)
        retained.event_log.record("decision_resolved", payload=payload, validate_payload=False)

    assert pruned.event_log.dropped_through_event_id == 5
    assert retained.event_log.dropped_through_event_id == 0
    with game_context(pruned):
        pruned_rolls = [dice_mod.get_dice_roll(6) for _ in range(12)]
    with game_context(retained):
        retained_rolls = [dice_mod.get_dice_roll(6) for _ in range(12)]

    assert pruned.event_log.compute_history_hash() == retained.event_log.compute_history_hash()
    assert pruned_rolls == retained_rolls
