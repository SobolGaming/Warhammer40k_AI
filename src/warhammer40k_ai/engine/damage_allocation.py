from __future__ import annotations

from typing import TYPE_CHECKING

from ..units.unit import get_roll
from ..utility.entity_ids import get_entity_id
from .decision_kinds import DECISION_ALLOCATE_DAMAGE, DECISION_SELECT_PRECISION_TARGET
from .decisions import DecisionOption, DecisionRequest

if TYPE_CHECKING:
    from .attack_resolution import AttackSequence


def resolve_save_target_model(manager, game: object, seq: AttackSequence, wound_instance: dict, attacker, target, profile) -> tuple[object | None, bool]:
    game_map = getattr(game, "map", None)
    target_model = None

    allocated_id = wound_instance.get("_allocated_model_id")
    if allocated_id:
        target_model = manager._resolve_model(game, allocated_id)

    precision_choices = dict(seq.context.get("precision_choice_by_save_index", {}) or {})
    if target_model is None and seq.save_index in precision_choices:
        chosen_id = precision_choices.get(seq.save_index)
        if chosen_id:
            target_model = manager._resolve_model(game, chosen_id)

    if target_model is None and seq.save_index not in precision_choices:
        try:
            precision_from_epic_challenge = False
            try:
                sr = getattr(attacker, "special_rules", None)
                if isinstance(sr, dict) and sr.get("epic_challenge_precision_active") is True:
                    parent = getattr(profile, "parent_wargear", None)
                    if parent is not None and callable(getattr(parent, "is_melee", None)) and parent.is_melee():
                        precision_from_epic_challenge = True
            except (AttributeError, TypeError, ValueError):
                precision_from_epic_challenge = False

            precision_from_templar_vows = False
            try:
                parent = getattr(profile, "parent_wargear", None)
                if parent is not None and callable(getattr(parent, "is_melee", None)) and parent.is_melee():
                    army = attacker.parent_unit.get_parent_army()
                    mgr = getattr(army, "templar_vows", None) if army is not None else None
                    if mgr is not None and mgr.melee_precision_against(attacker.parent_unit, target):
                        precision_from_templar_vows = True
            except (AttributeError, TypeError, ValueError):
                precision_from_templar_vows = False

            precision_from_assassins = False
            try:
                precision_from_assassins = bool(profile._assassins_poisons_applies(attacker))
            except (AttributeError, TypeError, ValueError):
                precision_from_assassins = False

            bonus_precision = bool(wound_instance.get("bonus_precision"))
            precision_allowed = bool(
                profile.is_precision()
                or precision_from_epic_challenge
                or precision_from_templar_vows
                or precision_from_assassins
                or bonus_precision
            )
            if precision_allowed and game_map is not None:
                root_getter = getattr(target, "get_attached_unit_root", None)
                root = root_getter() if callable(root_getter) else target
                has_attached_leaders = bool(getattr(root, "attached_leaders", []) or [])
                if has_attached_leaders:
                    get_collision = getattr(root, "get_models_for_collision", None)
                    all_models = list(get_collision() or []) if callable(get_collision) else list(getattr(root, "models", []) or [])
                    char_models = []
                    for model in all_models:
                        if not getattr(model, "is_alive", True):
                            continue
                        if not bool(getattr(model, "is_character", False)):
                            continue
                        if hasattr(game_map, "can_model_see_model") and callable(getattr(game_map, "can_model_see_model")):
                            if not game_map.can_model_see_model(attacker, model):
                                continue
                        char_models.append(model)
                    if char_models:
                        if not bool(getattr(game, "is_authoritative", True)):
                            return None, True
                        ordered = manager._sorted_models(char_models)
                        options = [
                            DecisionOption.create(
                                "Bodyguard (normal allocation)",
                                payload={"model_id": None, "action": "bodyguard"},
                            )
                        ]
                        allowed_ids: list[str] = []
                        for model in ordered:
                            model_id = get_entity_id(model)
                            allowed_ids.append(model_id)
                            options.append(
                                DecisionOption.create(getattr(model, "name", "CHARACTER"), payload={"model_id": model_id})
                            )
                        player_id = getattr(getattr(attacker.parent_unit.get_parent_army(), "player", None), "id", None)
                        request = DecisionRequest.create(
                            DECISION_SELECT_PRECISION_TARGET,
                            "Select PRECISION allocation target.",
                            player_id=player_id,
                            options=options,
                            context={
                                "sequence_id": int(seq.sequence_id),
                                "save_index": int(seq.save_index),
                                "selection_kind": "precision",
                                "attacker_model_id": wound_instance.get("attacker_model_id"),
                                "target_unit_id": seq.target_unit_id,
                                "unit_id": seq.target_unit_id,
                                "wargear_id": seq.wargear_id,
                                "profile_name": seq.profile_name,
                                "allowed_model_ids": list(allowed_ids),
                                "weapon_name": manager._weapon_display_name(profile),
                            },
                        )
                        seq.step = "precision_choice"
                        game.request_decision(request)
                        return None, True
        except (AttributeError, TypeError, ValueError, KeyError, IndexError):
            target_model = None

    if target_model is not None:
        try:
            if not bool(wound_instance.get("_imperial_agents_selfless_bodyguard_resolved")):
                target_army = target.get_parent_army() if hasattr(target, "get_parent_army") else None
                ia_mgr = getattr(target_army, "imperial_agents_detachments", None) if target_army is not None else None
                redirect_fn = getattr(ia_mgr, "selfless_bodyguard_redirect_models", None) if ia_mgr is not None else None
                if callable(redirect_fn):
                    redirect_models, redirect_source = redirect_fn(target, target_model, game=game)
                    if redirect_models:
                        wound_instance["_imperial_agents_selfless_bodyguard_resolved"] = True
                        roll = get_roll("D6")
                        wound_instance["_imperial_agents_selfless_bodyguard_roll"] = int(roll)
                        if roll >= 2:
                            if len(redirect_models) == 1:
                                target_model = redirect_models[0]
                                wound_instance["_allocated_model_id"] = get_entity_id(target_model)
                            else:
                                if not bool(getattr(game, "is_authoritative", True)):
                                    return None, True
                                ordered = manager._sorted_models(redirect_models)
                                options = []
                                allowed_ids = []
                                for model in ordered:
                                    model_id = get_entity_id(model)
                                    allowed_ids.append(model_id)
                                    options.append(
                                        DecisionOption.create(
                                            getattr(model, "name", "Model"),
                                            payload={"model_id": model_id},
                                        )
                                    )
                                if not options:
                                    return None, True
                                player_id = getattr(getattr(target_army, "player", None), "id", None)
                                source_name = str(redirect_source or "Selfless Bodyguard").strip() or "Selfless Bodyguard"
                                request = DecisionRequest.create(
                                    DECISION_ALLOCATE_DAMAGE,
                                    f"{source_name}: allocate attack to a bodyguard model.",
                                    player_id=player_id,
                                    options=options,
                                    context={
                                        "sequence_id": int(seq.sequence_id),
                                        "save_index": int(seq.save_index),
                                        "selection_kind": "selfless_bodyguard_redirect",
                                        "unit_id": seq.target_unit_id,
                                        "target_unit_id": seq.target_unit_id,
                                        "attacker_model_id": wound_instance.get("attacker_model_id"),
                                        "wargear_id": seq.wargear_id,
                                        "profile_name": seq.profile_name,
                                        "allowed_model_ids": list(allowed_ids),
                                        "reason": source_name,
                                        "damage_source": "attack",
                                        "weapon_name": manager._weapon_display_name(profile),
                                        "attacker_name": str(getattr(attacker, "name", "") or ""),
                                    },
                                )
                                seq.step = "damage_allocation_choice"
                                game.request_decision(request)
                                return None, True
        except (AttributeError, TypeError, ValueError, KeyError, IndexError):
            pass
        return target_model, False

    try:
        candidates = target.get_models_for_wound_allocation()
    except (AttributeError, TypeError):
        candidates = [model for model in (getattr(target, "models", []) or []) if getattr(model, "is_alive", True)]
    from ..utility.damage_allocation import DamageAllocationCtx, damage_allocation_choice

    choice = damage_allocation_choice(candidates)
    if choice.forced_model is not None:
        return choice.forced_model, False
    if choice.choice_models:
        if not bool(getattr(game, "is_authoritative", True)):
            return None, True
        ordered = manager._sorted_models(choice.choice_models)
        options = []
        allowed_ids = []
        for model in ordered:
            model_id = get_entity_id(model)
            allowed_ids.append(model_id)
            options.append(DecisionOption.create(getattr(model, "name", "Model"), payload={"model_id": model_id}))
        if not options:
            return None, True
        player_id = getattr(getattr(target.get_parent_army(), "player", None), "id", None)
        alloc_ctx = DamageAllocationCtx(
            reason="Allocate wound",
            damage_source="attack",
            weapon_name=manager._weapon_display_name(profile),
            attacker_name=str(getattr(attacker, "name", "") or ""),
        )
        request = DecisionRequest.create(
            DECISION_ALLOCATE_DAMAGE,
            alloc_ctx.reason or "Allocate wound",
            player_id=player_id,
            options=options,
            context={
                "sequence_id": int(seq.sequence_id),
                "save_index": int(seq.save_index),
                "selection_kind": "wound_allocation",
                "unit_id": seq.target_unit_id,
                "target_unit_id": seq.target_unit_id,
                "attacker_model_id": wound_instance.get("attacker_model_id"),
                "wargear_id": seq.wargear_id,
                "profile_name": seq.profile_name,
                "allowed_model_ids": list(allowed_ids),
                "reason": alloc_ctx.reason,
                "damage_source": alloc_ctx.damage_source,
                "weapon_name": alloc_ctx.weapon_name,
                "attacker_name": alloc_ctx.attacker_name,
            },
        )
        seq.step = "damage_allocation_choice"
        game.request_decision(request)
        return None, True
    return None, False


def resume_after_precision_choice(manager, game: object, seq: AttackSequence, save_index: int, model_id: str | None) -> None:
    if seq is None:
        return
    try:
        idx = int(save_index)
    except (TypeError, ValueError):
        return
    choices = dict(seq.context.get("precision_choice_by_save_index", {}) or {})
    choices[idx] = str(model_id) if model_id not in (None, "") else None
    seq.context["precision_choice_by_save_index"] = choices
    if model_id not in (None, "") and 0 <= idx < len(seq.wound_instances or []):
        try:
            seq.wound_instances[idx]["_allocated_model_id"] = str(model_id)
        except (TypeError, IndexError, KeyError):
            pass
    seq.step = "save_roll"
    seq.save_index = idx
    manager._request_next_save_roll(game, seq)


def resume_after_damage_allocation(manager, game: object, seq: AttackSequence, save_index: int, model_id: str | None) -> None:
    if seq is None:
        return
    try:
        idx = int(save_index)
    except (TypeError, ValueError):
        return
    if model_id not in (None, "") and 0 <= idx < len(seq.wound_instances or []):
        try:
            seq.wound_instances[idx]["_allocated_model_id"] = str(model_id)
        except (TypeError, IndexError, KeyError):
            pass
    seq.step = "save_roll"
    seq.save_index = idx
    manager._request_next_save_roll(game, seq)


def _resolve_pending_mortals(manager, game: object, seq: AttackSequence) -> bool:
    """Resolve queued mortal wounds. Returns True if a decision was requested."""
    pending = dict(seq.pending_mortals or {})
    if not pending:
        return False

    if "mortal_queue" not in seq.context:
        queue: list[dict] = []
        for entries in list(pending.values()):
            for entry in list(entries or []):
                no_spill = bool(entry.get("no_spill", False))
                amount = int(entry.get("mortal_wound_amount", 0) or 0)
                if no_spill:
                    target_model = manager._resolve_model(game, entry.get("target_model_id"))
                    _apply_mortal_wound_instance(manager, game, entry, target_model)
                    continue
                if amount <= 0:
                    continue
                queue.append(
                    {
                        "target_unit_id": str(entry.get("target_unit_id", "") or ""),
                        "wargear_id": str(entry.get("wargear_id", "") or ""),
                        "profile_name": str(entry.get("profile_name", "") or ""),
                        "attacker_model_id": str(entry.get("attacker_model_id", "") or ""),
                        "attack_instance": dict(entry.get("attack_instance", {}) or {}),
                        "remaining": int(amount),
                        "initial_model_id": str(entry.get("target_model_id", "") or ""),
                        "current_model_id": None,
                        "allow_initial_model_outside_candidates": bool(entry.get("target_model_id")),
                    }
                )
        seq.pending_mortals = {}
        seq.context["mortal_queue"] = queue
        seq.context["mortal_queue_index"] = 0

    return _process_mortal_queue(manager, game, seq)


def _process_mortal_queue(manager, game: object, seq: AttackSequence) -> bool:
    queue = list(seq.context.get("mortal_queue", []) or [])
    if not queue:
        seq.context.pop("mortal_queue", None)
        seq.context.pop("mortal_queue_index", None)
        return False
    try:
        start_idx = int(seq.context.get("mortal_queue_index", 0) or 0)
    except (TypeError, ValueError):
        start_idx = 0
    idx = max(0, start_idx)
    game_map = getattr(game, "map", None)
    from ..utility.damage_allocation import DamageAllocationCtx, damage_allocation_choice

    while idx < len(queue):
        entry = queue[idx]
        remaining = int(entry.get("remaining", 0) or 0)
        if remaining <= 0:
            idx += 1
            continue
        target_unit = manager._resolve_unit(game, entry.get("target_unit_id"))
        if target_unit is None:
            idx += 1
            continue
        current_model_id = entry.get("current_model_id") or entry.get("initial_model_id")
        allow_initial_outside = bool(entry.get("allow_initial_model_outside_candidates", False))

        while remaining > 0:
            if not target_unit.is_alive():
                remaining = 0
                break
            try:
                candidates = target_unit.get_models_for_wound_allocation()
            except (AttributeError, TypeError):
                candidates = [model for model in (getattr(target_unit, "models", []) or []) if getattr(model, "is_alive", True)]
            if not candidates:
                remaining = 0
                break

            current_model = None
            if current_model_id:
                current_model = manager._resolve_model(game, current_model_id)
                if current_model is not None:
                    if not getattr(current_model, "is_alive", True):
                        current_model = None
                    elif current_model not in candidates:
                        if allow_initial_outside:
                            try:
                                all_models = target_unit.get_models_for_collision()
                            except (AttributeError, TypeError):
                                all_models = list(candidates)
                            if current_model not in all_models:
                                current_model = None
                        else:
                            current_model = None
            if current_model is None:
                choice = damage_allocation_choice(candidates)
                if choice.forced_model is not None:
                    current_model = choice.forced_model
                elif choice.choice_models:
                    if not bool(getattr(game, "is_authoritative", True)):
                        return True
                    ordered = manager._sorted_models(choice.choice_models)
                    options = []
                    allowed_ids = []
                    for model in ordered:
                        model_id = get_entity_id(model)
                        allowed_ids.append(model_id)
                        options.append(DecisionOption.create(getattr(model, "name", "Model"), payload={"model_id": model_id}))
                    if not options:
                        return False
                    weapon_name = manager._weapon_display_name(
                        manager._resolve_profile(game, entry.get("wargear_id"), entry.get("profile_name"))
                    )
                    attacker_name = getattr(manager._resolve_model(game, entry.get("attacker_model_id")), "name", "") or ""
                    alloc_ctx = DamageAllocationCtx(
                        reason="Allocate mortal wound",
                        damage_source="attack",
                        weapon_name=weapon_name,
                        attacker_name=attacker_name,
                    )
                    player_id = getattr(getattr(target_unit.get_parent_army(), "player", None), "id", None)
                    request = DecisionRequest.create(
                        DECISION_ALLOCATE_DAMAGE,
                        alloc_ctx.reason or "Allocate mortal wound",
                        player_id=player_id,
                        options=options,
                        context={
                            "sequence_id": int(seq.sequence_id),
                            "mortal_entry_index": int(idx),
                            "selection_kind": "mortal_wound",
                            "unit_id": entry.get("target_unit_id"),
                            "allowed_model_ids": list(allowed_ids),
                            "remaining_wounds": int(remaining),
                            "reason": alloc_ctx.reason,
                            "damage_source": alloc_ctx.damage_source,
                            "weapon_name": alloc_ctx.weapon_name,
                            "attacker_name": alloc_ctx.attacker_name,
                        },
                    )
                    seq.step = "mortal_allocation_choice"
                    seq.context["mortal_queue_index"] = idx
                    game.request_decision(request)
                    return True
                else:
                    remaining = 0
                    break

            _apply_mortal_wound_instance(manager, game, entry, current_model)
            remaining -= 1
            current_model_id = get_entity_id(current_model)
            if not getattr(current_model, "is_alive", True):
                current_model_id = None

        entry["remaining"] = int(remaining)
        entry["current_model_id"] = current_model_id
        idx += 1
        seq.context["mortal_queue_index"] = idx

    seq.context.pop("mortal_queue", None)
    seq.context.pop("mortal_queue_index", None)
    return False


def _apply_mortal_wound_instance(manager, game: object, entry: dict, target_model) -> None:
    if target_model is None or not getattr(target_model, "is_alive", True):
        return
    profile = manager._resolve_profile(game, entry.get("wargear_id"), entry.get("profile_name"))
    attacker = manager._resolve_model(game, entry.get("attacker_model_id"))
    attack_instance = dict(entry.get("attack_instance", {}) or {})
    game_map = getattr(game, "map", None)
    if profile is not None and attacker is not None:
        apply_with_tracking = getattr(profile, "_apply_single_mortal_wound_with_tracking", None)
        if callable(apply_with_tracking):
            apply_with_tracking(
                target_model,
                attacker,
                attack_instance,
                game_map=game_map,
            )
            return
    take_damage = getattr(target_model, "take_damage", None)
    if not callable(take_damage):
        raise AttributeError("Target model does not implement take_damage for mortal wound resolution.")
    take_damage(
        1,
        is_mortal=True,
        weapon_profile=profile,
        game_map=game_map,
        damage_source="mortal",
    )


def resume_after_mortal_allocation(manager, game: object, seq: AttackSequence, entry_index: int, model_id: str | None) -> None:
    if seq is None:
        return
    queue = list(seq.context.get("mortal_queue", []) or [])
    if not queue:
        return
    try:
        idx = int(entry_index)
    except (TypeError, ValueError):
        idx = None
    if idx is None or idx < 0 or idx >= len(queue):
        return
    entry = queue[idx]
    if model_id:
        entry["current_model_id"] = str(model_id)
        model = manager._resolve_model(game, model_id)
        if model is not None:
            _apply_mortal_wound_instance(manager, game, entry, model)
            entry["remaining"] = max(0, int(entry.get("remaining", 0) or 0) - 1)
            if not getattr(model, "is_alive", True):
                entry["current_model_id"] = None
    seq.context["mortal_queue"] = queue
    seq.context["mortal_queue_index"] = idx
    if _process_mortal_queue(manager, game, seq):
        return
    if manager._request_hazardous_roll(game, seq):
        return
    manager._mark_sequence_done(game, seq)


def _process_hazardous_failures(manager, game: object, seq: AttackSequence) -> bool:
    remaining = int(seq.context.get("hazardous_failures_remaining", 0) or 0)
    if remaining <= 0:
        seq.context["hazardous_done"] = True
        return False
    profile = manager._resolve_profile(game, seq.wargear_id, seq.profile_name)
    attacker_unit = manager._resolve_unit(game, seq.attacker_unit_id)
    if profile is None or attacker_unit is None:
        seq.context["hazardous_done"] = True
        return False
    try:
        root_unit = attacker_unit.get_attached_unit_root()
    except AttributeError:
        root_unit = attacker_unit
    pain_hazardous = bool(seq.context.get("hazardous_pain_melee_non_character", False))
    target_melee_all = bool(seq.context.get("hazardous_target_melee_all", False))
    target_ranged_all = bool(seq.context.get("hazardous_target_ranged_all", False))
    from ..utility.hazardous import collect_hazardous_eligible_models
    from ..utility.damage_allocation import DamageAllocationCtx, hazardous_allocation_choice

    game_map = getattr(game, "map", None)
    while remaining > 0:
        eligible = collect_hazardous_eligible_models(
            root_unit,
            include_melee_non_character=pain_hazardous,
            include_melee_all=target_melee_all,
            include_ranged_all=target_ranged_all,
        )
        if not eligible:
            for model_id in list(seq.model_ids or []):
                model = manager._resolve_model(game, model_id)
                if model is not None and getattr(model, "is_alive", False):
                    eligible = [model]
                    break
        if not eligible:
            remaining = 0
            break
        choice = hazardous_allocation_choice(eligible)
        if choice.forced_model is not None:
            forced_take_damage = getattr(choice.forced_model, "take_damage", None)
            if not callable(forced_take_damage):
                raise AttributeError("Forced hazardous model does not implement take_damage.")
            forced_take_damage(
                3,
                is_mortal=True,
                weapon_profile=profile,
                game_map=game_map,
                damage_source="hazardous",
            )
            remaining -= 1
            continue
        if choice.choice_models:
            if not bool(getattr(game, "is_authoritative", True)):
                return True
            ordered = manager._sorted_models(choice.choice_models)
            options = []
            allowed_ids = []
            for model in ordered:
                model_id = get_entity_id(model)
                allowed_ids.append(model_id)
                options.append(DecisionOption.create(getattr(model, "name", "Model"), payload={"model_id": model_id}))
            if not options:
                return False
            player_id = getattr(getattr(root_unit.get_parent_army(), "player", None), "id", None)
            alloc_ctx = DamageAllocationCtx(reason="HAZARDOUS failed test - select model", damage_source="hazardous")
            request = DecisionRequest.create(
                DECISION_ALLOCATE_DAMAGE,
                alloc_ctx.reason or "HAZARDOUS - Select Model",
                player_id=player_id,
                options=options,
                context={
                    "sequence_id": int(seq.sequence_id),
                    "selection_kind": "hazardous",
                    "unit_id": seq.attacker_unit_id,
                    "allowed_model_ids": list(allowed_ids),
                    "remaining_wounds": int(remaining),
                    "reason": alloc_ctx.reason,
                    "damage_source": alloc_ctx.damage_source,
                },
            )
            seq.step = "hazardous_allocation"
            game.request_decision(request)
            seq.context["hazardous_failures_remaining"] = int(remaining)
            return True
        remaining = 0
        break

    seq.context["hazardous_failures_remaining"] = int(remaining)
    if remaining <= 0:
        seq.context["hazardous_done"] = True
    return False


def resume_after_hazardous_allocation(manager, game: object, seq: AttackSequence, model_id: str | None) -> None:
    if seq is None:
        return
    remaining = int(seq.context.get("hazardous_failures_remaining", 0) or 0)
    if remaining <= 0:
        seq.context["hazardous_done"] = True
        manager._mark_sequence_done(game, seq)
        return
    profile = manager._resolve_profile(game, seq.wargear_id, seq.profile_name)
    game_map = getattr(game, "map", None)
    if profile is None:
        seq.context["hazardous_done"] = True
        manager._mark_sequence_done(game, seq)
        return
    model = manager._resolve_model(game, model_id) if model_id else None
    if model is not None:
        take_damage = getattr(model, "take_damage", None)
        if not callable(take_damage):
            raise AttributeError("Hazardous allocation model does not implement take_damage.")
        take_damage(
            3,
            is_mortal=True,
            weapon_profile=profile,
            game_map=game_map,
            damage_source="hazardous",
        )
        remaining -= 1
        seq.context["hazardous_failures_remaining"] = int(max(0, remaining))
    if _process_hazardous_failures(manager, game, seq):
        return
    manager._mark_sequence_done(game, seq)
