from __future__ import annotations

from ..utility.entity_ids import get_entity_id


def _queue_fight_move_request(manager, *, fighting_unit, target_declarations, movement_type: str):
    from .decision_requests import queue_move_unit_request

    move_tag = str(movement_type or "").strip().lower()
    max_distance = 3.0
    try:
        override = fighting_unit.get_fight_phase_move_distance_override(move_tag)
        if override is not None:
            max_distance = float(override)
    except Exception:
        max_distance = 3.0
    context = {
        "phase_name": "FIGHT_PHASE",
        "phase_step": manager._fight_phase_step_name(),
        "selection_purpose": "FIGHT_MOVE",
        "fight_sequence_step": move_tag,
        "target_unit_ids": [
            str(get_entity_id(target_unit) or "")
            for target_unit in sorted(list(target_declarations or {}), key=lambda unit: str(get_entity_id(unit) or ""))
            if target_unit is not None
        ],
    }
    request = queue_move_unit_request(
        manager.game,
        fighting_unit,
        movement_type=move_tag,
        prompt=f"{move_tag.replace('_', ' ').title()} {getattr(fighting_unit, 'name', 'Unit')}",
        player_id=getattr(manager.active_player, "id", None),
        max_distance=max_distance,
        allow_skip=True,
        context=context,
    )
    ui_callback = getattr(manager, "on_movement_required", None)
    if request is not None and callable(ui_callback):
        try:
            ui_callback(move_tag, fighting_unit, lambda _completed: None, request)
        except TypeError:
            ui_callback(move_tag, fighting_unit, lambda _completed: None)
    return request


def _resolve_target_declaration_attacks(manager, fighting_unit, target_declarations) -> None:
    auto_decls = manager._auto_select_melee_weapons(manager._as_attached_view(fighting_unit))
    hits_by_target_total = {}
    hit_models_by_target_total = {}
    hit_models_by_target_psychic_total = {}
    killing_models_by_target_total = {}
    for target_unit, attacking_models in target_declarations.items():
        decls = list(auto_decls or [])
        if attacking_models:
            decls = [declaration for declaration in decls if declaration.get("model") in attacking_models]
        attack_summary = manager._resolve_melee_attacks(manager._as_attached_view(fighting_unit), target_unit, decls)
        for unit, hits in (attack_summary.get("hits_by_target") or {}).items():
            hits_by_target_total[unit] = int(hits_by_target_total.get(unit, 0) or 0) + int(hits or 0)
        for unit, models in (attack_summary.get("hit_models_by_target") or {}).items():
            if unit not in hit_models_by_target_total:
                hit_models_by_target_total[unit] = set()
            try:
                hit_models_by_target_total[unit].update(set(models or []))
            except Exception:
                pass
        for unit, models in (attack_summary.get("hit_models_by_target_psychic") or {}).items():
            if unit not in hit_models_by_target_psychic_total:
                hit_models_by_target_psychic_total[unit] = set()
            try:
                hit_models_by_target_psychic_total[unit].update(set(models or []))
            except Exception:
                pass
        for unit, models in (attack_summary.get("killing_models_by_target") or {}).items():
            if unit not in killing_models_by_target_total:
                killing_models_by_target_total[unit] = set()
            try:
                killing_models_by_target_total[unit].update(set(models or []))
            except Exception:
                pass
        try:
            if hasattr(manager.game, "event_system"):
                manager.game.event_system.publish(
                    "fight_attacks_resolved",
                    unit=fighting_unit,
                    target_unit=target_unit,
                    hits_by_target=attack_summary.get("hits_by_target"),
                    hit_models_by_target=attack_summary.get("hit_models_by_target"),
                    hit_models_by_target_psychic=attack_summary.get("hit_models_by_target_psychic"),
                    killing_models_by_target=attack_summary.get("killing_models_by_target"),
                )
        except Exception:
            pass
    if hits_by_target_total:
        manager.game._maybe_trigger_daemonic_poisons(
            attacker_unit=manager._as_attached_view(fighting_unit),
            hits_by_target=hits_by_target_total,
            hit_models_by_target=hit_models_by_target_total,
            phase="fight",
        )
    try:
        setattr(
            fighting_unit,
            "_gift_of_chaos_hit_models_by_target_psychic",
            dict(hit_models_by_target_psychic_total or {}),
        )
    except Exception:
        pass
    try:
        if hasattr(manager.game, "event_system"):
            manager.game.event_system.publish(
                "fight_attacks_resolved",
                unit=fighting_unit,
                target_unit=None,
                hits_by_target=hits_by_target_total,
                hit_models_by_target=hit_models_by_target_total,
                hit_models_by_target_psychic=hit_models_by_target_psychic_total,
                killing_models_by_target=killing_models_by_target_total,
            )
    except Exception:
        pass
