from __future__ import annotations


def _maybe_clear_selected_to_shoot_rerolls(manager, game: object, unit_id: str) -> None:
    if not unit_id:
        return
    for sequence in list(manager.sequences.values()):
        if str(getattr(sequence, "attacker_unit_id", "") or "") == str(unit_id):
            if str(getattr(sequence, "step", "") or "") != "done":
                return
    unit = manager._resolve_unit(game, unit_id)
    if unit is None:
        return
    clear_shoot = getattr(unit, "clear_selected_to_shoot_rerolls", None)
    if callable(clear_shoot):
        clear_shoot()
    clear_action = getattr(unit, "clear_selected_to_action_reroll_choice", None)
    if callable(clear_action):
        clear_action(action="shoot")


def _mark_sequence_done(manager, game: object, sequence) -> None:
    sequence.step = "done"
    sequence.current_roll_id = None
    manager._maybe_clear_selected_to_shoot_rerolls(game, sequence.attacker_unit_id)
    manager._start_pending_sequence(game)


def _start_pending_sequence(manager, game: object) -> None:
    ordered = sorted(manager.sequences.values(), key=lambda sequence: int(getattr(sequence, "sequence_id", 0) or 0))
    for sequence in ordered:
        if str(getattr(sequence, "step", "") or "") != "done" and bool(getattr(sequence, "started", False)):
            return
    for sequence in ordered:
        if str(getattr(sequence, "step", "") or "") == "done":
            continue
        if bool(getattr(sequence, "started", False)):
            continue
        sequence.started = True
        if sequence.step == "attack_count":
            manager._request_attack_count_roll(game, sequence)
        else:
            manager._begin_hits(game, sequence)
        return
