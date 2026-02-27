from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.attack_resolution import AttackResolutionManager, AttackSequence


def _make_seq(seq_id: int, step: str) -> AttackSequence:
    return AttackSequence(
        sequence_id=seq_id,
        attacker_unit_id="attacker",
        target_unit_id="target",
        wargear_id="wargear",
        profile_name="default",
        model_ids=["model-1"],
        step=step,
    )


def test_queue_attack_declarations_starts_only_first_sequence_until_done() -> None:
    manager = AttackResolutionManager()
    queued_sequences = [_make_seq(1, "attack_count"), _make_seq(2, "hits")]
    started: list[tuple[str, int]] = []

    manager._build_sequence = lambda _g, _d, out_of_phase=False: queued_sequences.pop(0) if queued_sequences else None
    manager._request_attack_count_roll = lambda _g, seq: started.append(("attack_count", int(seq.sequence_id)))
    manager._begin_hits = lambda _g, seq: started.append(("hits", int(seq.sequence_id)))
    manager._maybe_clear_selected_to_shoot_rerolls = lambda _g, _unit_id: None

    game = SimpleNamespace()
    ok = manager.queue_attack_declarations(game, [{}, {}], out_of_phase=False)

    assert ok is True
    assert started == [("attack_count", 1)]
    assert bool(manager.sequences[1].started) is True
    assert bool(manager.sequences[2].started) is False

    manager._mark_sequence_done(game, manager.sequences[1])

    assert started == [("attack_count", 1), ("hits", 2)]
    assert bool(manager.sequences[2].started) is True


def test_sequential_queue_calls_keep_second_sequence_pending_until_first_done() -> None:
    manager = AttackResolutionManager()
    queued_sequences = [_make_seq(1, "hits"), _make_seq(2, "attack_count")]
    started: list[tuple[str, int]] = []

    manager._build_sequence = lambda _g, _d, out_of_phase=False: queued_sequences.pop(0) if queued_sequences else None
    manager._begin_hits = lambda _g, seq: started.append(("hits", int(seq.sequence_id)))
    manager._request_attack_count_roll = lambda _g, seq: started.append(("attack_count", int(seq.sequence_id)))
    manager._maybe_clear_selected_to_shoot_rerolls = lambda _g, _unit_id: None

    game = SimpleNamespace()
    first_ok = manager.queue_attack_declarations(game, [{}], out_of_phase=False)
    second_ok = manager.queue_attack_declarations(game, [{}], out_of_phase=False)

    assert first_ok is True
    assert second_ok is True
    assert started == [("hits", 1)]
    assert bool(manager.sequences[1].started) is True
    assert bool(manager.sequences[2].started) is False

    manager._mark_sequence_done(game, manager.sequences[1])

    assert started == [("hits", 1), ("attack_count", 2)]
    assert bool(manager.sequences[2].started) is True
