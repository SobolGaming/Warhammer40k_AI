from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import register_decision_handler
from ..decision_kinds import (
    DECISION_CHOOSE_BLESSINGS,
    DECISION_CHOOSE_BLOOD_TITHE,
    DECISION_CHOOSE_IDOL_OF_KHORNE,
    DECISION_SELECT_VESSEL_OF_WRATH_MODELS,
    DECISION_SELECT_REALM_OF_CHAOS_UNITS,
    DECISION_CHOOSE_VESSEL_OF_WRATH_BLESSING,
    DECISION_CHOOSE_RITUALS,
    DECISION_CHOOSE_CHIVALRIC_OATH,
    DECISION_CHOOSE_START_OF_BATTLE_KEYWORD,
    DECISION_CHOOSE_DAEMONIC_ALLEGIANCE,
    DECISION_CHOOSE_DARK_PACT,
    DECISION_CHOOSE_DOCTRINA,
    DECISION_CHOOSE_COMBAT_DOCTRINE,
    DECISION_CHOOSE_GRAND_COVEN,
    DECISION_CHOOSE_COMBAT_DRUGS,
    DECISION_CHOOSE_HYPER_ADAPTATION,
    DECISION_CHOOSE_FRENZY_TARGET,
    DECISION_CHOOSE_HARBINGER,
    DECISION_CHOOSE_MARTIAL_KATAH,
    DECISION_CHOOSE_MOMENT_SHACKLE,
    DECISION_CHOOSE_PATH_OF_WARRIOR,
    DECISION_CHOOSE_CRUEL_AMUSEMENT,
    DECISION_CHOOSE_MASTER_OF_MAGICKS,
    DECISION_CHOOSE_HARBINGER_OF_DEATH,
    DECISION_CHOOSE_DANCE_OF_DEATH,
    DECISION_CHOOSE_LIMB_FROM_LIMB,
    DECISION_CHOOSE_RED_WRATH,
    DECISION_USE_MIRACLE_DIE,
    DECISION_CHOOSE_PLAGUE,
    DECISION_CHOOSE_PLEDGE,
    DECISION_CHOOSE_QUARRY,
    DECISION_CHOOSE_HYSTERICAL_FRENZY_PSYKER,
    DECISION_CHOOSE_GIFT_OF_CHAOS_TARGET,
    DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
    DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET,
    DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET,
    DECISION_CHOOSE_POST_SHOOT_MORTAL_WOUNDS_TARGET,
    DECISION_CHOOSE_POST_SHOOT_WRACKED_AGONIES_TARGET,
    DECISION_CHOOSE_POST_SHOOT_AFLAME_TARGET,
    DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET,
    DECISION_SELECT_UNLEASH_HELL_VEHICLE,
    DECISION_CHOOSE_POST_SHOOT_LEADERSHIP_DEBUFF_TARGET,
    DECISION_CHOOSE_DAEMONIC_POISONS_TARGET,
    DECISION_DISCARD_SECONDARY,
    DECISION_CHOOSE_SHADOW_FORM,
    DECISION_CHOOSE_VOW,
    DECISION_ISSUE_ORDER,
    DECISION_CHOOSE_WRATHFUL_PRESENCE,
    DECISION_CHOOSE_DAEMON_PRIMARCH_SLAANESH,
    DECISION_CHOOSE_WARMASTER_ABILITY,
    DECISION_CHOOSE_ASPECT,
    DECISION_USE_LEADING_UNMODIFIED_SIX,
    DECISION_USE_MODEL_UNMODIFIED_SIX,
    DECISION_SELECT_SETUP_REACTIVE_TARGET,
    DECISION_CHOOSE_SETUP_REACTIVE_ACTION,
    DECISION_SELECT_RISE_TO_CHALLENGE,
    DECISION_SELECT_REVERBERATING_SUMMONS_UNIT,
    DECISION_CHOOSE_HIT_MODIFIER_IGNORES,
    DECISION_CHOOSE_SKILL_MODIFIER_IGNORES,
    DECISION_CHOOSE_MOVE_MODIFIER_IGNORES,
    DECISION_CHOOSE_ADVANCE_MODIFIER_IGNORES,
    DECISION_CHOOSE_CHARGE_MODIFIER_IGNORES,
    DECISION_CHOOSE_BATTLE_FOCUS_MANEUVER,
    DECISION_CHOOSE_POWER_FROM_PAIN_OPTION,
    DECISION_CHOOSE_MALEFIC_SURGE_UNIT,
    DECISION_CHOOSE_MALEFIC_SURGE_ABILITY,
)
from ..decisions import DecisionRequest, DecisionResult
from ...utility.entity_ids import get_entity_id
from ._helpers import (
    get_objective,
    is_skip_choice,
    resolve_model,
    resolve_player,
    resolve_unit,
    validate_option_choice,
)
from ._ability_common import (
    _log_action_for_players,
    _option_label,
    _option_payload,
    _resolve_army,
    _resolve_player,
)


def _validate_choose_blessings(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    ctx_data = None
    if isinstance(getattr(result, "payload", None), dict):
        payload_ctx = result.payload.get("ctx")
        if isinstance(payload_ctx, dict):
            ctx_data = payload_ctx
    if ctx_data is None:
        ctx_data = request.context.get("ctx") or request.context.get("roll_context")
    if not isinstance(ctx_data, dict):
        return ("Blessings decision requires ctx in request context.",)
    selected = result.payload.get("selected_blessings") or result.payload.get("choices")
    if selected is None:
        selected = []
    if not isinstance(selected, list):
        return ("Blessings selection requires choices list.",)
    army = _resolve_army(game, request, _option_payload(request, result))
    if army is None or getattr(army, "blessings_of_khorne", None) is None:
        return ("Blessings manager not found.",)
    return ()


def _apply_choose_blessings(game: object, request: DecisionRequest, result: DecisionResult):
    from ...rules.blessings_of_khorne import BlessingsRollContext, BlessingsTiming

    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Blessings army not found.")
    mgr = getattr(army, "blessings_of_khorne", None)
    if mgr is None:
        raise RuntimeError("Blessings manager not found.")
    ctx_data = None
    if isinstance(getattr(result, "payload", None), dict):
        payload_ctx = result.payload.get("ctx")
        if isinstance(payload_ctx, dict):
            ctx_data = payload_ctx
    if ctx_data is None:
        ctx_data = dict(request.context.get("ctx") or request.context.get("roll_context") or {})
    if hasattr(mgr, "deserialize_ctx_payload"):
        ctx = mgr.deserialize_ctx_payload(ctx_data)
    else:
        timing_val = ctx_data.get("timing")
        if isinstance(timing_val, BlessingsTiming):
            timing = timing_val
        else:
            timing_name = str(timing_val or "").strip()
            try:
                timing = BlessingsTiming[timing_name]
            except Exception:
                try:
                    timing = BlessingsTiming(timing_name)
                except Exception as exc:
                    raise RuntimeError("Blessings timing invalid.") from exc
        ctx = BlessingsRollContext(
            timing=timing,
            battle_round=int(ctx_data.get("battle_round", 0) or 0),
            dice=list(ctx_data.get("dice", []) or []),
            rerolls_allowed=int(ctx_data.get("rerolls_allowed", 0) or 0),
            rerolled_indices=list(ctx_data.get("rerolled_indices", []) or []),
            max_activations=int(ctx_data.get("max_activations", 0) or 0),
            counts_toward_baseline_limit=bool(ctx_data.get("counts_toward_baseline_limit", False)),
            already_active_keys=set(ctx_data.get("already_active_keys", []) or []),
            reborn_in_blood_available=bool(ctx_data.get("reborn_in_blood_available", False)),
        )
    selected = result.payload.get("selected_blessings") or result.payload.get("choices") or []
    use_reborn = bool(result.payload.get("use_reborn", False))
    applied = mgr.apply_choice(ctx, selected_blessing_keys=list(selected), use_reborn_in_blood=use_reborn)
    try:
        names = []
        for k in list(selected or []):
            d = None
            try:
                d = mgr.definitions.get(str(k).strip().upper())
            except Exception:
                d = None
            if d is None:
                for dk, dv in getattr(mgr, "definitions", {}).items():
                    if str(getattr(dv, "name", "") or "").strip().lower() == str(k).strip().lower():
                        d = dv
                        break
            names.append(getattr(d, "name", None) or str(k))
        if use_reborn:
            names.append("Reborn in Blood")
        if not names:
            names_text = "no blessings activated"
        else:
            names_text = ", ".join(names)
        dice = list(getattr(ctx, "dice", []) or [])
        dice_text = ", ".join(str(int(d)) for d in dice) if dice else "?"
        timing_label = getattr(getattr(ctx, "timing", None), "name", None) or str(getattr(ctx, "timing", "") or "").strip()
        if timing_label and timing_label != BlessingsTiming.START_OF_BATTLE_ROUND.name:
            prefix = f"Blessings of Khorne ({timing_label}): "
        else:
            prefix = "Blessings of Khorne: "
        player = getattr(army, "player", None)
        _log_action_for_players(game, player, f"{prefix}{names_text} (dice: {dice_text})")
    except Exception:
        pass
    if getattr(ctx, "timing", None) == BlessingsTiming.START_OF_BATTLE_ROUND:
        det_mgr = getattr(army, "world_eaters_detachments", None)
        if det_mgr is not None and getattr(det_mgr, "is_vessels_of_wrath", lambda: False)():
            br = int(getattr(ctx, "battle_round", 0) or 0)
            det_mgr.prompt_wrath_of_khorne_model_selection(
                game=game,
                player=getattr(army, "player", None),
                battle_round=br,
                source="Blessings of Khorne",
            )
    return applied


def _validate_choose_blood_tithe(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    ability_key = payload.get("ability_key") or payload.get("choice_key") or payload.get("key")
    if ability_key is None:
        return ("Blood Tithe selection requires ability_key.",)
    army = _resolve_army(game, request, payload)
    if army is None or getattr(army, "blood_tithe", None) is None:
        return ("Blood Tithe manager not found.",)
    return ()


def _apply_choose_blood_tithe(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Blood Tithe army not found.")
    mgr = getattr(army, "blood_tithe", None)
    if mgr is None:
        raise RuntimeError("Blood Tithe manager not found.")
    ability_key = payload.get("ability_key") or payload.get("choice_key") or payload.get("key")
    timing = str(request.context.get("timing", "") or payload.get("timing", "") or "")
    player = _resolve_player(game, request, payload)
    return bool(mgr.activate_blood_tithe(str(ability_key), game=game, player=player, timing=timing))


def _validate_choose_idol_of_khorne(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    ability_key = payload.get("ability_key") or payload.get("choice_key") or payload.get("key")
    if ability_key is None:
        return ("Idols of Khorne selection requires ability_key.",)
    army = _resolve_army(game, request, payload)
    if army is None or getattr(army, "world_eaters_detachments", None) is None:
        return ("Idols of Khorne manager not found.",)
    mgr = getattr(army, "world_eaters_detachments", None)
    if mgr is None or not getattr(mgr, "is_cult_of_blood", lambda: False)():
        return ("Idols of Khorne requires Cult of Blood detachment.",)
    available = {ab.key for ab in list(mgr.get_available_idols_of_khorne() or [])}
    if str(ability_key).strip().upper() not in available:
        return ("Idols of Khorne ability already used or invalid.",)
    return ()


def _apply_choose_idol_of_khorne(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Idols of Khorne army not found.")
    mgr = getattr(army, "world_eaters_detachments", None)
    if mgr is None:
        raise RuntimeError("Idols of Khorne manager not found.")
    ability_key = payload.get("ability_key") or payload.get("choice_key") or payload.get("key")
    player = _resolve_player(game, request, payload)
    applied = bool(mgr.activate_idol_of_khorne(str(ability_key), game=game, player=player))
    if applied:
        try:
            label = _option_label(request, result) or str(ability_key)
            _log_action_for_players(game, player, f"Idols of Khorne: selected {label}.")
        except Exception:
            pass
    return applied


def _validate_select_vessel_of_wrath_models(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    model_ids = result.payload.get("model_ids")
    if not isinstance(model_ids, list) or not model_ids:
        return ("Wrath of Khorne requires model_ids.",)
    ctx = getattr(request, "context", {}) or {}
    max_models = ctx.get("max_models")
    if max_models is not None and len(model_ids) > int(max_models):
        return ("Too many models selected for Wrath of Khorne.",)
    allowed_ids = {str(v) for v in list(ctx.get("allowed_model_ids") or []) if v is not None}
    seen: set[str] = set()
    for mid in list(model_ids or []):
        mid = str(mid or "")
        if not mid:
            return ("Wrath of Khorne requires valid model_ids.",)
        if mid in seen:
            return ("Wrath of Khorne model_ids must be unique.",)
        seen.add(mid)
        if allowed_ids and mid not in allowed_ids:
            return ("Wrath of Khorne model is not eligible.",)
        if resolve_model(game, mid) is None:
            return ("Wrath of Khorne model not found.",)
    return ()


def _apply_select_vessel_of_wrath_models(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Wrath of Khorne army not found.")
    mgr = getattr(army, "world_eaters_detachments", None)
    if mgr is None:
        raise RuntimeError("Wrath of Khorne manager not found.")
    ctx = getattr(request, "context", {}) or {}
    battle_round = int(ctx.get("battle_round", 0) or getattr(game, "turn", 0) or 0)
    model_ids = list(result.payload.get("model_ids") or [])
    applied = bool(mgr.apply_wrath_of_khorne_models(model_ids, battle_round=battle_round))
    if applied:
        mgr.prompt_wrath_of_khorne_blessing_selection(
            game=game,
            player=getattr(army, "player", None),
            battle_round=battle_round,
            source="Wrath of Khorne",
        )
        player = getattr(army, "player", None)
        _log_action_for_players(game, player, f"Wrath of Khorne: selected {len(model_ids)} model(s).")
    return applied


def _validate_select_realm_of_chaos_units(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    unit_ids = result.payload.get("unit_ids")
    if not isinstance(unit_ids, list) or not unit_ids:
        return ("The Realm of Chaos requires unit_ids.",)
    ctx = getattr(request, "context", {}) or {}
    max_units = ctx.get("max_units")
    if max_units is not None and len(unit_ids) > int(max_units):
        return ("Too many units selected for The Realm of Chaos.",)
    allowed_ids = {str(v) for v in list(ctx.get("allowed_unit_ids") or []) if v is not None}
    outside_ids = {str(v) for v in list(ctx.get("outside_shadow_unit_ids") or []) if v is not None}
    seen: set[str] = set()
    outside_selected = 0
    for uid in list(unit_ids or []):
        uid = str(uid or "")
        if not uid:
            return ("The Realm of Chaos requires valid unit_ids.",)
        if uid in seen:
            return ("The Realm of Chaos unit_ids must be unique.",)
        seen.add(uid)
        if allowed_ids and uid not in allowed_ids:
            return ("The Realm of Chaos unit is not eligible.",)
        if uid in outside_ids:
            outside_selected += 1
        if resolve_unit(game, uid) is None:
            return ("The Realm of Chaos unit not found.",)
    if outside_selected and len(seen) > 1:
        return ("Only one unit can be selected if it is outside the Shadow of Chaos.",)

    ability_key = str(ctx.get("ability", "") or "").strip().lower()
    if ability_key == "ride_the_wind_end_of_opponent_turn":
        player = resolve_player(game, request.player_id)
        if player is None:
            return ("Ride the Wind requires a player.",)
        army = getattr(player, "get_army", lambda: None)()
        if army is None:
            return ("Ride the Wind requires an army.",)
        mgr = getattr(army, "aeldari_detachments", None)
        if mgr is None or not getattr(mgr, "is_windrider_host", lambda: False)():
            return ("Ride the Wind requires a Windrider Host detachment.",)
        turn_ending_player_id = str(ctx.get("turn_ending_player_id", "") or "")
        turn_ending_player = resolve_player(game, turn_ending_player_id) if turn_ending_player_id else None
        candidates_fn = getattr(mgr, "ride_the_wind_end_of_opponent_turn_candidates", None)
        if not callable(candidates_fn):
            return ("Ride the Wind candidate resolver is unavailable.",)
        candidates = list(
            candidates_fn(
                game=game,
                turn_ending_player=turn_ending_player,
                game_map=getattr(game, "map", None),
            ) or []
        )
        candidate_ids = {str(get_entity_id(unit) or "") for unit in list(candidates or []) if unit is not None}
        for uid in seen:
            if uid not in candidate_ids:
                return ("Ride the Wind selection contains an ineligible unit.",)
        max_units_fn = getattr(mgr, "ride_the_wind_end_of_opponent_turn_max_units", None)
        max_units_allowed = int(max_units_fn(game=game) or 0) if callable(max_units_fn) else int(max_units or 0)
        if len(seen) > max(0, int(max_units_allowed)):
            return ("Too many units selected for Ride the Wind.",)
        resolved_fn = getattr(mgr, "ride_the_wind_phase_already_resolved", None)
        if callable(resolved_fn) and bool(resolved_fn(game=game, turn_ending_player_id=turn_ending_player_id)):
            return ("Ride the Wind has already resolved this end-of-turn window.",)
    return ()


def _apply_select_realm_of_chaos_units(game: object, request: DecisionRequest, result: DecisionResult):
    ctx = dict(getattr(request, "context", {}) or {})
    ability_key = str(ctx.get("ability", "") or "").strip().lower()

    if ability_key == "ride_the_wind_end_of_opponent_turn":
        player = resolve_player(game, request.player_id)
        if player is None:
            raise RuntimeError("Ride the Wind player not found.")
        army = getattr(player, "get_army", lambda: None)()
        if army is None:
            raise RuntimeError("Ride the Wind army not found.")
        mgr = getattr(army, "aeldari_detachments", None)
        if mgr is None:
            raise RuntimeError("Ride the Wind detachment manager not found.")

        turn_ending_player_id = str(ctx.get("turn_ending_player_id", "") or "")
        turn_ending_player = resolve_player(game, turn_ending_player_id) if turn_ending_player_id else None

        moved_units = []
        if not is_skip_choice(request, result):
            unit_ids = sorted({str(uid or "") for uid in list(result.payload.get("unit_ids") or []) if str(uid or "").strip()})
            candidates_fn = getattr(mgr, "ride_the_wind_end_of_opponent_turn_candidates", None)
            candidates = list(
                candidates_fn(
                    game=game,
                    turn_ending_player=turn_ending_player,
                    game_map=getattr(game, "map", None),
                ) or []
            ) if callable(candidates_fn) else []
            by_id = {str(get_entity_id(unit) or ""): unit for unit in list(candidates or []) if unit is not None}
            game_map = getattr(game, "map", None)
            for uid in unit_ids:
                unit = by_id.get(uid)
                if unit is None:
                    continue
                moved = unit.enter_strategic_reserves_midgame(
                    game=game,
                    game_map=game_map,
                    reason="Ride the Wind",
                )
                if moved:
                    moved_units.append(unit)

            if moved_units:
                labels = ", ".join(str(getattr(unit, "name", "Unit") or "Unit") for unit in list(moved_units or []))
                _log_action_for_players(game, player, f"Ride the Wind: {labels} placed into Strategic Reserves.")

        mark_fn = getattr(mgr, "mark_ride_the_wind_phase_resolved", None)
        if callable(mark_fn):
            mark_fn(game=game, turn_ending_player_id=turn_ending_player_id)
        return moved_units

    if is_skip_choice(request, result):
        return None
    unit_ids = list(result.payload.get("unit_ids") or [])
    units = []
    for uid in unit_ids:
        unit = resolve_unit(game, str(uid))
        if unit is not None:
            units.append(unit)
    return units


def _validate_choose_vessel_of_wrath_blessing(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    payload = _option_payload(request, result)
    blessing_key = payload.get("blessing_key") or payload.get("key")
    if blessing_key is None:
        return ("Wrath of Khorne blessing selection requires blessing_key.",)
    army = _resolve_army(game, request, payload)
    if army is None:
        return ("Wrath of Khorne army not found.",)
    mgr = getattr(army, "world_eaters_detachments", None)
    if mgr is None or not getattr(mgr, "is_vessels_of_wrath", lambda: False)():
        return ("Wrath of Khorne requires Vessels of Wrath detachment.",)
    bless_mgr = getattr(army, "blessings_of_khorne", None)
    if bless_mgr is None:
        return ("Blessings of Khorne manager not found.",)
    key = str(blessing_key).strip().upper()
    if key not in getattr(bless_mgr, "definitions", {}):
        return ("Invalid Blessing of Khorne selection.",)
    if key in set(getattr(bless_mgr, "active_blessing_keys", set()) or set()):
        return ("Blessing already active for the army.",)
    ctx = getattr(request, "context", {}) or {}
    battle_round = int(ctx.get("battle_round", 0) or getattr(game, "turn", 0) or 0)
    if not getattr(mgr, "has_active_wrath_of_khorne_models", lambda **_k: False)(battle_round=battle_round):
        return ("No Vessels of Wrath selected this battle round.",)
    return ()


def _apply_choose_vessel_of_wrath_blessing(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Wrath of Khorne army not found.")
    mgr = getattr(army, "world_eaters_detachments", None)
    if mgr is None:
        raise RuntimeError("Wrath of Khorne manager not found.")
    ctx = getattr(request, "context", {}) or {}
    battle_round = int(ctx.get("battle_round", 0) or getattr(game, "turn", 0) or 0)
    blessing_key = payload.get("blessing_key") or payload.get("key")
    applied = bool(mgr.apply_wrath_of_khorne_blessing(str(blessing_key), battle_round=battle_round))
    if applied:
        player = getattr(army, "player", None)
        label = _option_label(request, result) or str(blessing_key)
        _log_action_for_players(game, player, f"Wrath of Khorne: bonus blessing {label}.")
    return applied


def _validate_choose_ritual(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    ritual_key = payload.get("ritual_key") or result.payload.get("ritual_key")
    caster_val = payload.get("caster_model_id") or result.payload.get("caster_model_id")
    if ritual_key is None or caster_val is None:
        return ("Cabal ritual requires ritual_key and caster_model_id.",)
    if resolve_model(game, caster_val) is None:
        return ("Cabal caster model not found.",)
    target_val = result.payload.get("target_unit_id")
    if target_val is not None and resolve_unit(game, target_val) is None:
        return ("Cabal target unit not found.",)
    army = _resolve_army(game, request, payload)
    if army is None or getattr(army, "cabal_of_sorcerers", None) is None:
        return ("Cabal manager not found.",)
    return ()


def _apply_choose_ritual(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Cabal army not found.")
    mgr = getattr(army, "cabal_of_sorcerers", None)
    if mgr is None:
        raise RuntimeError("Cabal manager not found.")
    ritual_key = payload.get("ritual_key") or result.payload.get("ritual_key")
    caster_model = resolve_model(game, payload.get("caster_model_id") or result.payload.get("caster_model_id"))
    target_unit = resolve_unit(game, result.payload.get("target_unit_id"))
    rolls = result.payload.get("rolls")
    channel_decision = result.payload.get("channel_decision")
    mortal_roll = result.payload.get("mortal_roll")
    return mgr.attempt_ritual(
        game,
        caster_model=caster_model,
        ritual_key=str(ritual_key),
        target_unit=target_unit,
        rolls=list(rolls or []),
        channel_decision=channel_decision,
        mortal_roll=mortal_roll,
    )


def _validate_choose_chivalric(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None or getattr(army, "code_chivalric", None) is None:
        return ("Code Chivalric manager not found.",)
    return ()


def _apply_choose_chivalric(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Code Chivalric army not found.")
    mgr = getattr(army, "code_chivalric", None)
    if mgr is None:
        raise RuntimeError("Code Chivalric manager not found.")
    kind = str(request.context.get("oath_kind", "") or payload.get("oath_kind", "") or "").strip().lower()
    if kind not in ("deed", "quality"):
        raise RuntimeError("Code Chivalric decision missing oath_kind.")
    choice_key = payload.get("choice_key") or payload.get("key")
    is_random = bool(payload.get("random", False))
    player = _resolve_player(game, request, payload)
    if is_random or str(choice_key or "").strip().upper() == "ROLL":
        if kind == "deed":
            return mgr.roll_deed(game=game, player=player)
        return mgr.roll_quality()
    if kind == "deed":
        mgr.select_deed(choice_key, game=game, player=player)
        return {"selected": str(choice_key)}
    mgr.select_quality(choice_key, random=False)
    return {"selected": str(choice_key)}


def _validate_choose_daemonic_allegiance(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id") or payload.get("unit")
    keyword = payload.get("keyword") or payload.get("choice_key") or payload.get("key")
    if unit_val is None or keyword is None:
        return ("Daemonic Allegiance requires unit_id and keyword.",)
    if resolve_unit(game, unit_val) is None:
        return ("Daemonic Allegiance unit not found.",)
    return ()


def _apply_choose_daemonic_allegiance(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    unit = resolve_unit(game, payload.get("unit_id") or payload.get("unit"))
    if unit is None:
        raise RuntimeError("Daemonic Allegiance unit not found.")
    keyword = payload.get("keyword") or payload.get("choice_key") or payload.get("key")
    return bool(unit.apply_daemonic_allegiance_selection(str(keyword)))


def _validate_choose_dark_pact(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id") or payload.get("unit")
    choice = payload.get("choice") or payload.get("choice_key") or payload.get("key")
    if unit_val is None or choice is None:
        return ("Dark Pact requires unit_id and choice.",)
    unit = resolve_unit(game, unit_val)
    if unit is None:
        return ("Dark Pact unit not found.",)
    empyric_choice = payload.get("empyric_wellspring_choice")
    has_empyric_field = str(empyric_choice or "").strip() != ""
    requires_empyric = False
    requires_fn = getattr(unit, "dark_pacts_requires_empyric_wellspring_choice", None)
    if callable(requires_fn):
        requires_empyric = bool(requires_fn())
    if requires_empyric:
        key = str(empyric_choice or "").strip().upper()
        if key not in ("LEAPING_WARPFLAME", "MONSTROUS_MANIFESTATION"):
            return ("Empyric Wellspring selection requires Leaping Warpflame or Monstrous Manifestation.",)
    elif has_empyric_field:
        return ("Empyric Wellspring selection is invalid for this unit.",)
    return ()


def _apply_choose_dark_pact(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    unit = resolve_unit(game, payload.get("unit_id") or payload.get("unit"))
    if unit is None:
        raise RuntimeError("Dark Pact unit not found.")
    choice = payload.get("choice") or payload.get("choice_key") or payload.get("key")
    empyric_choice = payload.get("empyric_wellspring_choice")
    phase_name = str(payload.get("phase_name", "") or request.context.get("phase_name", "") or "")
    trigger = str(payload.get("trigger", "") or request.context.get("trigger", "") or "")
    apply_fn = getattr(unit, "apply_dark_pacts_choice", None)
    if not callable(apply_fn):
        raise RuntimeError("Dark Pact apply hook missing.")
    return bool(
        apply_fn(
            game,
            choice=str(choice),
            phase_name=phase_name,
            trigger=trigger,
            empyric_wellspring_choice=(
                str(empyric_choice).strip().upper() if str(empyric_choice or "").strip() else None
            ),
        )
    )


def _validate_choose_path_of_warrior(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id") or payload.get("unit")
    choice = payload.get("choice_key") or payload.get("choice") or payload.get("key")
    if unit_val is None or choice is None:
        return ("Path of the Warrior requires unit_id and choice.",)
    unit = resolve_unit(game, unit_val)
    if unit is None:
        return ("Path of the Warrior unit not found.",)
    if str(choice or "").strip().upper() not in ("HIT", "WOUND", "BOTH"):
        return ("Path of the Warrior choice must be HIT or WOUND.",)
    try:
        root = unit.get_attached_unit_root()
    except Exception:
        root = unit
    try:
        army = root.get_parent_army()
    except Exception:
        army = None
    mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
    if mgr is None or not getattr(mgr, "path_of_the_warrior_applies", lambda _u: False)(root):
        return ("Path of the Warrior is not applicable for this unit.",)
    return ()


def _apply_choose_path_of_warrior(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    unit = resolve_unit(game, payload.get("unit_id") or payload.get("unit"))
    if unit is None:
        raise RuntimeError("Path of the Warrior unit not found.")
    choice = payload.get("choice_key") or payload.get("choice") or payload.get("key")
    phase_name = str(payload.get("phase_name", "") or request.context.get("phase_name", "") or "")
    apply_fn = getattr(unit, "apply_path_of_warrior_choice", None)
    if not callable(apply_fn):
        raise RuntimeError("Path of the Warrior apply hook missing.")
    return bool(apply_fn(game, choice=str(choice), phase_name=phase_name))


def _parse_cruel_amusement_choices(payload: dict, request: DecisionRequest) -> list[str]:
    raw = payload.get("choices")
    if isinstance(raw, (list, tuple, set)):
        vals = list(raw)
    else:
        single = payload.get("choice") or payload.get("choice_key") or payload.get("key")
        if isinstance(single, (list, tuple, set)):
            vals = list(single)
        elif single is None:
            vals = []
        else:
            vals = [single]
    out: list[str] = []
    for value in list(vals or []):
        key = str(value or "").strip().upper()
        if not key:
            continue
        out.append(key)
    if not out:
        fallback = request.context.get("choice")
        if fallback:
            out = [str(fallback or "").strip().upper()]
    return out


def _cruel_amusement_model_has_fanged_leer(model) -> bool:
    if model is None:
        return False
    model_id = str(get_entity_id(model) or getattr(model, "id", getattr(model, "_id", "")) or "")
    parent = getattr(model, "parent_unit", None)
    if parent is None:
        return False
    try:
        root = parent.get_attached_unit_root()
    except Exception:
        root = parent
    if root is None:
        return False
    try:
        members = list(root.get_attached_unit_members() or [])
    except Exception:
        members = [root]
    if not members:
        members = [root]
    for member in list(members or []):
        sr = getattr(member, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("enhancement_fanged_leer")):
            continue
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
        if bearer_id and model_id and bearer_id != model_id:
            continue
        return True
    return False


def _validate_choose_cruel_amusement(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    model_val = payload.get("model_id") or payload.get("model") or request.context.get("model_id")
    if model_val is None:
        return ("Cruel Amusement requires model_id and choice.",)
    model = resolve_model(game, model_val)
    if model is None:
        return ("Cruel Amusement model not found.",)

    choices = _parse_cruel_amusement_choices(payload, request)
    if not choices:
        return ("Cruel Amusement requires model_id and choice.",)
    if len(set(choices)) != len(choices):
        return ("Cruel Amusement choices must be unique.",)
    if len(choices) > 2:
        return ("Cruel Amusement can select at most two abilities.",)

    valid_choices = {"IGNORES_COVER", "PRECISION", "SUSTAINED_HITS_3"}
    if any(choice_key not in valid_choices for choice_key in choices):
        return ("Cruel Amusement choice must be Ignores Cover, Precision, or Sustained Hits 3.",)
    if len(choices) > 1 and not _cruel_amusement_model_has_fanged_leer(model):
        return ("Selecting two Cruel Amusement abilities requires Fanged Leer on the bearer.",)
    return ()


def _apply_choose_cruel_amusement(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    model = resolve_model(game, payload.get("model_id") or payload.get("model") or request.context.get("model_id"))
    if model is None:
        raise RuntimeError("Cruel Amusement model not found.")
    choices = _parse_cruel_amusement_choices(payload, request)
    if not choices:
        raise RuntimeError("Cruel Amusement choice invalid.")

    keyword_map = {
        "IGNORES_COVER": ["IGNORES COVER"],
        "PRECISION": ["PRECISION"],
        "SUSTAINED_HITS_3": ["SUSTAINED HITS 3"],
    }
    all_keywords: list[str] = []
    for choice_key in choices:
        keywords = keyword_map.get(str(choice_key or "").strip().upper())
        if not keywords:
            raise RuntimeError("Cruel Amusement choice invalid.")
        for kw in list(keywords or []):
            if kw not in all_keywords:
                all_keywords.append(kw)

    weapon_name = str(payload.get("weapon_name") or request.context.get("weapon_name") or "shrieker cannon").strip()
    ability_name = str(payload.get("ability_name") or request.context.get("ability_name") or "Cruel Amusement").strip()
    model_id = getattr(model, "id", None) or getattr(model, "_id", None)
    key = f"cruel_amusement:{model_id or ''}"
    if hasattr(model, "set_temporary_weapon_keyword_bonuses"):
        model.set_temporary_weapon_keyword_bonuses(
            key=key,
            weapon_name=weapon_name,
            keywords=list(all_keywords),
            source=ability_name,
            expires_phase="SHOOTING_PHASE",
            attack_type="ranged",
        )
    try:
        unit = getattr(model, "parent_unit", None)
        if unit is not None:
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
        else:
            root = None
        player = None
        if root is not None:
            army = root.get_parent_army()
            player = getattr(army, "player", None) if army is not None else None
        label_map = {
            "IGNORES_COVER": "Ignores Cover",
            "PRECISION": "Precision",
            "SUSTAINED_HITS_3": "Sustained Hits 3",
        }
        labels = [label_map.get(key, str(key or "").title()) for key in list(choices or [])]
        label_text = " + ".join(labels) if labels else "a selection"
        _log_action_for_players(
            game,
            player,
            f"{ability_name}: {getattr(model, 'name', 'Model')} grants {label_text} to {weapon_name}.",
        )
    except Exception:
        pass
    return "+".join(str(choice or "") for choice in choices)


def _validate_choose_master_of_magicks(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    model_val = payload.get("model_id") or payload.get("model") or request.context.get("model_id")
    choice = payload.get("choice") or payload.get("choice_key") or payload.get("key")
    if model_val is None or not choice:
        return ("Master of Magicks requires model_id and choice.",)
    model = resolve_model(game, model_val)
    if model is None:
        return ("Master of Magicks model not found.",)
    choice_key = str(choice or "").strip().upper()
    if choice_key not in ("IGNORES_COVER", "LETHAL_HITS", "SUSTAINED_HITS_D3"):
        return ("Master of Magicks choice must be Ignores Cover, Lethal Hits, or Sustained Hits D3.",)
    return ()


def _apply_choose_master_of_magicks(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    model = resolve_model(game, payload.get("model_id") or payload.get("model") or request.context.get("model_id"))
    if model is None:
        raise RuntimeError("Master of Magicks model not found.")
    choice = payload.get("choice") or payload.get("choice_key") or payload.get("key")
    choice_key = str(choice or "").strip().upper()
    keyword_map = {
        "IGNORES_COVER": ["IGNORES COVER"],
        "LETHAL_HITS": ["LETHAL HITS"],
        "SUSTAINED_HITS_D3": ["SUSTAINED HITS D3"],
    }
    keywords = keyword_map.get(choice_key)
    if not keywords:
        raise RuntimeError("Master of Magicks choice invalid.")
    weapon_name = str(payload.get("weapon_name") or request.context.get("weapon_name") or "bolt of change").strip()
    ability_name = str(payload.get("ability_name") or request.context.get("ability_name") or "Master of Magicks").strip()
    model_id = getattr(model, "id", None) or getattr(model, "_id", None)
    key = f"master_of_magicks:{model_id or ''}"
    if hasattr(model, "set_temporary_weapon_keyword_bonuses"):
        model.set_temporary_weapon_keyword_bonuses(
            key=key,
            weapon_name=weapon_name,
            keywords=list(keywords),
            source=ability_name,
            expires_phase="SHOOTING_PHASE",
            attack_type="ranged",
        )
    try:
        unit = getattr(model, "parent_unit", None)
        if unit is not None:
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
        else:
            root = None
        player = None
        if root is not None:
            army = root.get_parent_army()
            player = getattr(army, "player", None) if army is not None else None
        label = {
            "IGNORES_COVER": "Ignores Cover",
            "LETHAL_HITS": "Lethal Hits",
            "SUSTAINED_HITS_D3": "Sustained Hits D3",
        }.get(choice_key, choice_key.title())
        _log_action_for_players(
            game,
            player,
            f"{ability_name}: {getattr(model, 'name', 'Model')} grants {label} to {weapon_name}.",
        )
    except Exception:
        pass
    return str(choice_key)


def _validate_choose_harbinger_of_death(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    model_val = payload.get("model_id") or payload.get("model") or request.context.get("model_id")
    choice = payload.get("choice") or payload.get("choice_key") or payload.get("key")
    if model_val is None or not choice:
        return ("Harbinger of Death requires model_id and choice.",)
    model = resolve_model(game, model_val)
    if model is None:
        return ("Harbinger of Death model not found.",)
    choice_key = str(choice or "").strip().upper()
    if choice_key not in ("LETHAL_HITS", "PRECISION", "SUSTAINED_HITS_1"):
        return ("Harbinger of Death choice must be Lethal Hits, Precision, or Sustained Hits 1.",)
    return ()


def _apply_choose_harbinger_of_death(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    model = resolve_model(game, payload.get("model_id") or payload.get("model") or request.context.get("model_id"))
    if model is None:
        raise RuntimeError("Harbinger of Death model not found.")
    choice = payload.get("choice") or payload.get("choice_key") or payload.get("key")
    choice_key = str(choice or "").strip().upper()
    keyword_map = {
        "LETHAL_HITS": ["LETHAL HITS"],
        "PRECISION": ["PRECISION"],
        "SUSTAINED_HITS_1": ["SUSTAINED HITS 1"],
    }
    keywords = keyword_map.get(choice_key)
    if not keywords:
        raise RuntimeError("Harbinger of Death choice invalid.")
    weapon_name = str(payload.get("weapon_name") or request.context.get("weapon_name") or "hellforged").strip() or "hellforged"
    ability_name = str(payload.get("ability_name") or request.context.get("ability_name") or "Harbinger of Death").strip()
    model_id = getattr(model, "id", None) or getattr(model, "_id", None)
    key = f"harbinger_of_death:{model_id or ''}"
    if hasattr(model, "set_temporary_weapon_keyword_bonuses"):
        model.set_temporary_weapon_keyword_bonuses(
            key=key,
            weapon_name=weapon_name,
            keywords=list(keywords),
            source=ability_name,
            expires_phase="FIGHT_PHASE",
            attack_type="melee",
        )
    try:
        unit = getattr(model, "parent_unit", None)
        if unit is not None:
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
        else:
            root = None
        player = None
        if root is not None:
            army = root.get_parent_army()
            player = getattr(army, "player", None) if army is not None else None
        label = {
            "LETHAL_HITS": "Lethal Hits",
            "PRECISION": "Precision",
            "SUSTAINED_HITS_1": "Sustained Hits 1",
        }.get(choice_key, choice_key.title())
        _log_action_for_players(
            game,
            player,
            f"{ability_name}: {getattr(model, 'name', 'Model')} grants {label} to {weapon_name}.",
        )
    except Exception:
        pass
    return str(choice_key)


def _validate_choose_hysterical_frenzy(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    model_id = payload.get("model_id") or request.context.get("model_id")
    target_id = payload.get("target_unit_id") or request.context.get("target_unit_id")
    if not model_id or not target_id:
        return ("Hysterical Frenzy requires model_id and target_unit_id.",)
    model = resolve_model(game, model_id)
    if model is None:
        return (f"Hysterical Frenzy model not found: {model_id}",)
    target = resolve_unit(game, target_id)
    if target is None:
        return (f"Hysterical Frenzy target unit not found: {target_id}",)
    if hasattr(model, "is_alive") and not model.is_alive:
        return ("Selected Hysterical Frenzy Psyker is not alive.",)
    if hasattr(target, "is_alive") and not target.is_alive():
        return ("Selected Hysterical Frenzy target unit is not alive.",)
    if hasattr(model, "has_any_keyword") and not model.has_any_keyword("PSYKER"):
        return ("Selected model is not a Psyker.",)
    if hasattr(target, "has_any_keyword"):
        if not (target.has_any_keyword("SLAANESH") and target.has_any_keyword("LEGIONES DAEMONICA")):
            return ("Target unit is not a SLAANESH LEGIONES DAEMONICA unit.",)
    eff = getattr(model, "_temporary_effects", None)
    if isinstance(eff, dict):
        entry = eff.get("hysterical_frenzy_used")
        exp = str((entry or {}).get("expires_phase", "") or "").strip().upper()
        if exp == "FIGHT_PHASE":
            return ("Selected Psyker has already used Hysterical Frenzy this phase.",)
    try:
        range_value = int(payload.get("range") or request.context.get("range") or 0)
    except Exception:
        range_value = 0
    if range_value > 0:
        source_unit = resolve_unit(game, payload.get("source_unit_id") or request.context.get("source_unit_id"))
        if source_unit is None:
            source_unit = getattr(model, "parent_unit", None)
        within_fn = getattr(source_unit, "_model_within_range_of_unit", None) if source_unit is not None else None
        if callable(within_fn):
            if not within_fn(model, target, float(range_value)):
                return ("Selected Psyker is not within range of the target unit.",)
    return ()


def _apply_choose_hysterical_frenzy(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    model_id = payload.get("model_id") or request.context.get("model_id")
    target_id = payload.get("target_unit_id") or request.context.get("target_unit_id")
    model = resolve_model(game, model_id)
    target = resolve_unit(game, target_id)
    if model is None or target is None:
        raise RuntimeError("Hysterical Frenzy requires a valid model and target unit.")
    target_root = target.get_attached_unit_root() if hasattr(target, "get_attached_unit_root") else target
    ability_name = str(payload.get("ability_name") or request.context.get("ability_name") or "Hysterical Frenzy").strip()
    sr = getattr(target_root, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    sr["hysterical_frenzy_active"] = True
    sr["hysterical_frenzy_expires_phase"] = "FIGHT_PHASE"
    sr["hysterical_frenzy_source"] = ability_name or "Hysterical Frenzy"
    sr["hysterical_frenzy_threshold"] = 4
    target_root.special_rules = sr
    if not isinstance(getattr(model, "_temporary_effects", None), dict):
        model._temporary_effects = {}
    model._temporary_effects["hysterical_frenzy_used"] = {
        "expires_phase": "FIGHT_PHASE",
        "source": ability_name or "Hysterical Frenzy",
    }
    source_unit = getattr(model, "parent_unit", None)
    root = source_unit.get_attached_unit_root() if source_unit is not None and hasattr(source_unit, "get_attached_unit_root") else source_unit
    player = None
    if root is not None:
        army = root.get_parent_army()
        player = getattr(army, "player", None) if army is not None else None
    _log_action_for_players(
        game,
        player,
        f"{ability_name}: {getattr(model, 'name', 'Psyker')} empowers {getattr(target_root, 'name', 'Unit')}.",
    )
    return {"model_id": model_id, "target_unit_id": target_id}


def _validate_choose_gift_of_chaos_target(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    payload = _option_payload(request, result)
    target_id = payload.get("target_unit_id") or request.context.get("target_unit_id")
    if not target_id:
        return ("Gift of Chaos requires target_unit_id.",)
    target = resolve_unit(game, target_id)
    if target is None:
        return (f"Gift of Chaos target unit not found: {target_id}",)
    if hasattr(target, "is_alive") and not target.is_alive():
        return ("Gift of Chaos target unit is not alive.",)
    model_id = payload.get("model_id") or request.context.get("model_id")
    if not model_id:
        return ("Gift of Chaos requires model_id.",)
    model = resolve_model(game, model_id)
    if model is None:
        return (f"Gift of Chaos model not found: {model_id}",)
    return ()


def _apply_choose_gift_of_chaos_target(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    target_id = payload.get("target_unit_id") or request.context.get("target_unit_id")
    attacker_id = payload.get("attacker_unit_id") or request.context.get("attacker_unit_id")
    model_id = payload.get("model_id") or request.context.get("model_id")
    target = resolve_unit(game, target_id)
    attacker = resolve_unit(game, attacker_id)
    model = resolve_model(game, model_id)
    if target is None or attacker is None or model is None:
        raise RuntimeError("Gift of Chaos requires valid attacker, model, and target.")
    ability_name = str(payload.get("ability_name") or request.context.get("ability_name") or "Gift of Chaos").strip()
    army = attacker.get_parent_army() if hasattr(attacker, "get_parent_army") else None
    player = getattr(army, "player", None) if army is not None else None
    apply_fn = getattr(game, "_apply_gift_of_chaos", None)
    if not callable(apply_fn):
        raise RuntimeError("Gift of Chaos resolution is unavailable.")
    apply_fn(
        source_unit=attacker,
        model=model,
        target_unit=target,
        ability_name=ability_name or "Gift of Chaos",
        player=player,
    )
    return {"model_id": model_id, "target_unit_id": target_id}


def _validate_choose_dance_of_death(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id") or payload.get("unit") or request.context.get("unit_id")
    choice = payload.get("choice") or payload.get("choice_key") or payload.get("key")
    if unit_val is None or not choice:
        return ("Dance of Death requires unit_id and choice.",)
    unit = resolve_unit(game, unit_val)
    if unit is None:
        return ("Dance of Death unit not found.",)
    choice_key = str(choice or "").strip().upper()
    if choice_key not in ("HERO", "VILLAIN", "TRICKSTER"):
        return ("Dance of Death choice must be HERO, VILLAIN, or TRICKSTER.",)
    try:
        if hasattr(unit, "has_dance_of_death") and not unit.has_dance_of_death():
            return ("Dance of Death is not applicable for this unit.",)
    except Exception:
        pass
    return ()


def _apply_choose_dance_of_death(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    unit = resolve_unit(game, payload.get("unit_id") or payload.get("unit") or request.context.get("unit_id"))
    if unit is None:
        raise RuntimeError("Dance of Death unit not found.")
    choice = payload.get("choice") or payload.get("choice_key") or payload.get("key")
    choice_key = str(choice or "").strip().upper()
    phase_name = str(request.context.get("phase_name", "") or payload.get("phase_name", "") or "FIGHT_PHASE")
    set_fn = getattr(unit, "set_dance_of_death_choice", None)
    if not callable(set_fn):
        raise RuntimeError("Dance of Death apply hook missing.")
    set_fn(choice_key, phase_name=phase_name)
    try:
        player = getattr(unit.get_parent_army(), "player", None)
        label = {
            "HERO": "Hero's Prowess",
            "VILLAIN": "Villain's Doom",
            "TRICKSTER": "Trickster's Grace",
        }.get(choice_key, choice_key.title())
        _log_action_for_players(
            game,
            player,
            f"Dance of Death: {getattr(unit, 'name', 'Unit')} chose {label}.",
        )
    except Exception:
        pass
    return str(choice_key)


def _validate_choose_doctrina(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    choice = payload.get("choice_key") or payload.get("key")
    if choice is None:
        return ("Doctrina selection requires choice_key.",)
    army = _resolve_army(game, request, payload)
    if army is None or getattr(army, "doctrina_imperatives", None) is None:
        return ("Doctrina manager not found.",)
    return ()


def _apply_choose_doctrina(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Doctrina army not found.")
    mgr = getattr(army, "doctrina_imperatives", None)
    if mgr is None:
        raise RuntimeError("Doctrina manager not found.")
    choice = payload.get("choice_key") or payload.get("key")
    battle_round = request.context.get("battle_round")
    applied = bool(mgr.select_imperative(choice, battle_round=battle_round))
    try:
        player = getattr(army, "player", None)
        label = _option_label(request, result) or str(choice)
        if label:
            _log_action_for_players(game, player, f"Doctrina Imperatives: {label} (Battle Round {battle_round})")
    except Exception:
        pass
    return applied


def _validate_choose_combat_doctrine(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    choice = payload.get("choice_key") or payload.get("key")
    if choice is None:
        return ("Combat Doctrine selection requires choice_key.",)
    army = _resolve_army(game, request, payload)
    if army is None or getattr(army, "combat_doctrines", None) is None:
        return ("Combat Doctrines manager not found.",)
    mgr = getattr(army, "combat_doctrines", None)
    if mgr is None:
        return ("Combat Doctrines manager not found.",)
    if not bool(getattr(mgr, "can_select_now", lambda **_k: False)(game=game)):
        return ("Combat Doctrines cannot be selected right now.",)
    available = list(getattr(mgr, "get_available_doctrines", lambda: [])() or [])
    available_keys = {str(getattr(opt, "key", "") or "").strip().upper() for opt in available}
    choice_key = str(choice or "").strip().upper()
    if available_keys and choice_key not in available_keys:
        return (f"Combat Doctrine '{choice}' is not currently available.",)
    return ()


def _apply_choose_combat_doctrine(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Combat Doctrines army not found.")
    mgr = getattr(army, "combat_doctrines", None)
    if mgr is None:
        raise RuntimeError("Combat Doctrines manager not found.")
    choice = payload.get("choice_key") or payload.get("key")
    battle_round = request.context.get("battle_round")
    applied = bool(mgr.select_doctrine(choice, battle_round=battle_round))
    try:
        player = getattr(army, "player", None)
        label = _option_label(request, result) or str(choice)
        if label:
            _log_action_for_players(game, player, f"Combat Doctrines: {label} (Battle Round {battle_round})")
    except Exception:
        pass
    return applied


def _validate_choose_grand_coven(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    choice = payload.get("choice_key") or payload.get("key")
    if choice is None:
        return ("Grand Coven selection requires choice_key.",)
    army = _resolve_army(game, request, payload)
    if army is None or getattr(army, "thousand_sons_detachments", None) is None:
        return ("Grand Coven manager not found.",)
    return ()


def _apply_choose_grand_coven(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Grand Coven army not found.")
    mgr = getattr(army, "thousand_sons_detachments", None)
    if mgr is None:
        raise RuntimeError("Grand Coven manager not found.")
    choice = payload.get("choice_key") or payload.get("key")
    battle_round = request.context.get("battle_round")
    applied = bool(mgr.select_grand_coven(choice, battle_round=battle_round))
    try:
        player = getattr(army, "player", None)
        label = _option_label(request, result) or str(choice)
        if label:
            _log_action_for_players(game, player, f"Kindred Sorcery: {label} (Battle Round {battle_round})")
    except Exception:
        pass
    return applied


def _validate_choose_combat_drugs(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    choice = payload.get("choice_key") or payload.get("key")
    if choice is None and not bool(payload.get("random", False)):
        return ("Combat Drugs selection requires choice_key.",)
    army = _resolve_army(game, request, payload)
    if army is None or getattr(army, "drukhari_detachments", None) is None:
        return ("Combat Drugs manager not found.",)
    return ()


def _apply_choose_combat_drugs(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Combat Drugs army not found.")
    mgr = getattr(army, "drukhari_detachments", None)
    if mgr is None:
        raise RuntimeError("Combat Drugs manager not found.")
    choice = payload.get("choice_key") or payload.get("key")
    battle_round = request.context.get("battle_round")
    applied = None
    pharmacophex_results = []
    if bool(payload.get("random", False)) or str(choice or "").strip().upper() == "ROLL":
        applied = mgr.roll_combat_drugs(battle_round=battle_round)
    else:
        applied = bool(mgr.select_combat_drug(choice, battle_round=battle_round))
    if applied:
        trigger_pharmacophex = getattr(mgr, "trigger_pharmacophex_roll", None)
        if callable(trigger_pharmacophex):
            pharmacophex_results = list(trigger_pharmacophex(battle_round=battle_round, game=game) or [])
    try:
        player = getattr(army, "player", None)
        if isinstance(applied, dict):
            selected = [getattr(d, "name", None) or getattr(d, "key", None) for d in list(applied.get("selected", []) or [])]
            selected = [str(s) for s in selected if s]
            rolls = list(applied.get("rolls", []) or [])
            if selected:
                label = ", ".join(selected)
            else:
                label = _option_label(request, result) or "Roll"
            roll_text = ", ".join(str(int(r)) for r in rolls) if rolls else "?"
            _log_action_for_players(game, player, f"Combat Drugs: {label} (dice: {roll_text})")
        else:
            label = _option_label(request, result) or str(choice)
            if label:
                _log_action_for_players(game, player, f"Combat Drugs: {label} (Battle Round {battle_round})")
        for entry in pharmacophex_results:
            if not isinstance(entry, dict):
                continue
            unit = entry.get("unit")
            uname = str(getattr(unit, "name", "") or "Unit").strip()
            selected_name = str(entry.get("selected_name", "") or "").strip()
            selected_key = str(entry.get("selected_key", "") or "").strip().upper()
            try:
                roll = int(entry.get("roll", 0) or 0)
            except Exception:
                roll = 0
            applied_extra = bool(entry.get("applied", False))
            if not selected_name and selected_key:
                selected_name = selected_key.title()
            if applied_extra:
                _log_action_for_players(
                    game,
                    player,
                    f"Pharmacophex ({uname}): {selected_name or selected_key} (dice: {roll}).",
                )
            elif selected_name or selected_key:
                _log_action_for_players(
                    game,
                    player,
                    f"Pharmacophex ({uname}): {selected_name or selected_key} already active; no additional effect (dice: {roll}).",
                )
    except Exception:
        pass
    return applied


def _validate_choose_hyper_adaptation(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    choice = payload.get("choice_key") or payload.get("key")
    if choice is None:
        return ("Hyper-adaptations selection requires choice_key.",)
    army = _resolve_army(game, request, payload)
    if army is None or getattr(army, "tyranids_detachments", None) is None:
        return ("Hyper-adaptations manager not found.",)
    return ()


def _apply_choose_hyper_adaptation(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Hyper-adaptations army not found.")
    mgr = getattr(army, "tyranids_detachments", None)
    if mgr is None:
        raise RuntimeError("Hyper-adaptations manager not found.")
    choice = payload.get("choice_key") or payload.get("key")
    battle_round = request.context.get("battle_round")
    applied = bool(mgr.select_hyper_adaptation(choice, battle_round=battle_round))
    try:
        player = getattr(army, "player", None)
        label = _option_label(request, result) or str(choice)
        if label:
            _log_action_for_players(game, player, f"Hyper-adaptations: {label} (Battle Round {battle_round})")
    except Exception:
        pass
    return applied


def _validate_choose_frenzy(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    if is_skip_choice(request, result):
        return ()
    return validate_option_choice(request, result)


def _apply_choose_frenzy(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    return dict(payload or {})


def _validate_choose_limb_from_limb(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    if is_skip_choice(request, result):
        return ()
    return validate_option_choice(request, result)


def _apply_choose_limb_from_limb(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    return dict(payload or {})


def _validate_choose_red_wrath(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    if is_skip_choice(request, result):
        return ()
    return validate_option_choice(request, result)


def _apply_choose_red_wrath(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    return dict(payload or {})


def _validate_choose_harbinger(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None or getattr(army, "harbingers_of_dread", None) is None:
        return ("Harbingers manager not found.",)
    return ()


def _apply_choose_harbinger(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Harbingers army not found.")
    mgr = getattr(army, "harbingers_of_dread", None)
    if mgr is None:
        raise RuntimeError("Harbingers manager not found.")
    choice = payload.get("choice_key") or payload.get("key")
    battle_round = request.context.get("battle_round")
    applied = None
    if bool(payload.get("random", False)) or str(choice or "").strip().upper() == "ROLL":
        rolls = payload.get("rolls")
        selected_keys = payload.get("selected_keys")
        if rolls or selected_keys:
            applied = mgr.apply_roll_results(rolls=rolls, selected_keys=selected_keys, battle_round=battle_round)
        else:
            applied = mgr.roll_dread_abilities(battle_round=battle_round)
    else:
        applied = bool(mgr.select_dread_ability(choice, battle_round=battle_round))
    try:
        player = getattr(army, "player", None)
        if isinstance(applied, dict):
            selected = [getattr(d, "name", None) or getattr(d, "key", None) for d in list(applied.get("selected", []) or [])]
            selected = [str(s) for s in selected if s]
            rolls_list = list(applied.get("rolls", []) or [])
            if selected:
                label = ", ".join(selected)
            else:
                label = _option_label(request, result) or "Roll"
            roll_text = ", ".join(str(int(r)) for r in rolls_list) if rolls_list else "?"
            _log_action_for_players(game, player, f"Harbingers of Dread: {label} (dice: {roll_text})")
        else:
            label = _option_label(request, result) or str(choice)
            if label:
                _log_action_for_players(game, player, f"Harbingers of Dread: {label} (Battle Round {battle_round})")
    except Exception:
        pass
    return applied


def _validate_choose_martial_katah(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id") or payload.get("unit")
    choice = payload.get("choice_key") or payload.get("key")
    if unit_val is None or choice is None:
        return ("Martial Ka'tah requires unit_id and choice.",)
    unit = resolve_unit(game, unit_val)
    if unit is None:
        return ("Martial Ka'tah unit not found.",)
    choice_norm = str(choice or "").strip().upper()
    selection_kind = str(request.context.get("selection_kind", "") or payload.get("selection_kind", "") or "")
    if choice_norm == "BOTH":
        if selection_kind == "exquisite_swordsmanship":
            return ("Master of the Stances cannot be used for Exquisite Swordsmanship.",)
        spec = getattr(unit, "master_of_stances_spec", lambda: None)()
        if not spec:
            return ("Master of the Stances not available.",)
        ability_key = str(payload.get("ability_key") or spec.get("ability_key") or "master_of_stances").strip().lower()
        model_id = str(payload.get("model_id") or spec.get("model_id") or "")
        if model_id:
            model = resolve_model(game, model_id)
            if model is None:
                return ("Master of the Stances model not found.",)
            if getattr(model, "has_used_once_per_battle", lambda _k: False)(ability_key):
                return ("Master of the Stances already used.",)
    return ()


def _apply_choose_martial_katah(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    unit = resolve_unit(game, payload.get("unit_id") or payload.get("unit"))
    if unit is None:
        raise RuntimeError("Martial Ka'tah unit not found.")
    choice = payload.get("choice_key") or payload.get("key")
    choice_norm = str(choice or "").strip().upper()
    selection_kind = str(request.context.get("selection_kind", "") or payload.get("selection_kind", "") or "")
    if selection_kind == "exquisite_swordsmanship":
        unit.set_exquisite_swordsmanship_choice(str(choice))
    else:
        if choice_norm == "BOTH":
            spec = getattr(unit, "master_of_stances_spec", lambda: None)()
            ability_name = ""
            if isinstance(spec, dict):
                ability_name = str(spec.get("source") or "Master of the Stances").strip()
            ability_key = str(payload.get("ability_key") or (spec.get("ability_key") if isinstance(spec, dict) else "") or "master_of_stances").strip().lower()
            model_id = str(payload.get("model_id") or (spec.get("model_id") if isinstance(spec, dict) else "") or "")
            if model_id:
                model = resolve_model(game, model_id)
                if model is not None:
                    getattr(model, "mark_used_once_per_battle", lambda _k, **_kw: None)(
                        ability_key,
                        ability_name=ability_name or "Master of the Stances",
                        source="datasheet",
                    )
        unit.set_martial_katah_choice(str(choice))
    return str(choice)


def _validate_choose_moment_shackle(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id") or request.context.get("unit_id")
    model_val = payload.get("model_id") or request.context.get("model_id")
    choice = payload.get("choice") or payload.get("choice_key") or payload.get("key")
    if not unit_val or not model_val or not choice:
        return ("Moment Shackle requires unit_id, model_id, and choice.",)
    unit = resolve_unit(game, unit_val)
    if unit is None:
        return ("Moment Shackle unit not found.",)
    model = resolve_model(game, model_val)
    if model is None:
        return ("Moment Shackle model not found.",)
    spec = getattr(unit, "model_moment_shackle_spec", lambda _m: None)(model)
    if not spec:
        return ("Moment Shackle not available.",)
    ability_key = str(payload.get("ability_key") or spec.get("ability_key") or "moment_shackle").strip().lower()
    if getattr(model, "has_used_once_per_battle", lambda _k: False)(ability_key):
        return ("Moment Shackle already used.",)
    choice_norm = str(choice or "").strip().lower()
    if choice_norm not in ("attacks", "attack", "invuln", "invulnerable", "invulnerable_save"):
        return ("Moment Shackle choice must be attacks or invulnerable save.",)
    return ()


def _apply_choose_moment_shackle(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    unit = resolve_unit(game, payload.get("unit_id") or request.context.get("unit_id"))
    model = resolve_model(game, payload.get("model_id") or request.context.get("model_id"))
    if unit is None or model is None:
        raise RuntimeError("Moment Shackle unit/model not found.")
    spec = getattr(unit, "model_moment_shackle_spec", lambda _m: None)(model)
    if not spec:
        raise RuntimeError("Moment Shackle not available.")
    ability_name = str(spec.get("source") or "Moment Shackle").strip() or "Moment Shackle"
    ability_key = str(payload.get("ability_key") or spec.get("ability_key") or "moment_shackle").strip().lower()
    choice = payload.get("choice") or payload.get("choice_key") or payload.get("key")
    choice_norm = str(choice or "").strip().lower()
    if choice_norm in ("attacks", "attack"):
        weapon_name = str(payload.get("weapon_name") or spec.get("weapon_name") or "Watcher's Axe").strip()
        try:
            attacks = int(payload.get("attacks", spec.get("attacks", 0)) or 0)
        except Exception:
            attacks = int(spec.get("attacks", 0) or 0)
        getattr(model, "set_temporary_weapon_attacks_override", lambda **_kw: None)(
            key=f"{ability_key}:attacks",
            weapon_name=weapon_name,
            attacks_value=int(attacks or 0),
            source=ability_name,
            expires_phase="FIGHT_PHASE",
        )
    elif choice_norm in ("invuln", "invulnerable", "invulnerable_save"):
        try:
            invuln = int(payload.get("invuln", spec.get("invuln", 0)) or 0)
        except Exception:
            invuln = int(spec.get("invuln", 0) or 0)
        getattr(model, "set_temporary_invulnerable_save", lambda **_kw: None)(
            key=f"{ability_key}:invuln",
            value=int(invuln or 0),
            source=ability_name,
            expires_phase="FIGHT_PHASE",
        )
    getattr(model, "mark_used_once_per_battle", lambda _k, **_kw: None)(
        ability_key,
        ability_name=ability_name,
        source="datasheet",
    )
    try:
        player = getattr(getattr(unit, "get_parent_army", lambda: None)(), "player", None)
    except Exception:
        player = None
    try:
        choice_label = _option_label(request, result) or str(choice)
        mname = str(getattr(model, "name", "Model") or "Model")
        if choice_label:
            _log_action_for_players(game, player, f"{ability_name}: {mname} selected {choice_label}.")
    except Exception:
        pass
    return str(choice)


def _validate_use_miracle_die(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    if is_skip_choice(request, result):
        return ()
    return validate_option_choice(request, result)


def _apply_use_miracle_die(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    value = payload.get("die_value", payload.get("value"))
    if value is None:
        return None
    return int(value)


def _validate_choose_plague(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    choice = payload.get("choice_key") or payload.get("key")
    if choice is None:
        return ("Plague choice requires key.",)
    army = _resolve_army(game, request, payload)
    if army is None or getattr(army, "nurgles_gift", None) is None:
        return ("Nurgle's Gift manager not found.",)
    return ()


def _apply_choose_plague(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Nurgle's Gift army not found.")
    mgr = getattr(army, "nurgles_gift", None)
    if mgr is None:
        raise RuntimeError("Nurgle's Gift manager not found.")
    choice = payload.get("choice_key") or payload.get("key")
    mgr.active_plague_key = str(choice)
    return str(choice)


def _validate_choose_start_of_battle_keyword(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    payload = _option_payload(request, result)
    keyword = payload.get("keyword") or _option_label(request, result)
    if not keyword:
        return ("Start-of-battle keyword selection requires keyword.",)
    model = resolve_model(game, payload.get("model_id") or request.context.get("model_id"))
    if model is None:
        return ("Start-of-battle keyword selection model not found.",)
    unit = getattr(model, "parent_unit", None)
    if unit is None:
        unit = resolve_unit(game, payload.get("unit_id") or request.context.get("unit_id"))
    if unit is None:
        return ("Start-of-battle keyword selection unit not found.",)
    ability_key = payload.get("ability_key") or request.context.get("ability_key")
    specs = unit.model_start_of_battle_keyword_reroll_ones_specs(model) if hasattr(unit, "model_start_of_battle_keyword_reroll_ones_specs") else []
    if not specs:
        return ("Start-of-battle keyword selection ability not found.",)
    if ability_key:
        for spec in list(specs or []):
            if str(spec.get("ability_key", "") or "").strip().lower() == str(ability_key).strip().lower():
                if str(keyword).strip().upper() not in {str(k).strip().upper() for k in (spec.get("keywords", []) or [])}:
                    return ("Selected keyword is not valid for this ability.",)
                return ()
        return ("Start-of-battle keyword selection ability key not found.",)
    return ()


def _apply_choose_start_of_battle_keyword(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    keyword = payload.get("keyword") or _option_label(request, result)
    if not keyword:
        raise RuntimeError("Start-of-battle keyword selection requires keyword.")
    model = resolve_model(game, payload.get("model_id") or request.context.get("model_id"))
    if model is None:
        raise RuntimeError("Start-of-battle keyword selection model not found.")
    unit = getattr(model, "parent_unit", None)
    if unit is None:
        unit = resolve_unit(game, payload.get("unit_id") or request.context.get("unit_id"))
    if unit is None:
        raise RuntimeError("Start-of-battle keyword selection unit not found.")
    source = payload.get("ability_name") or request.context.get("ability_name") or "Start of battle keyword selection"
    ability_key = payload.get("ability_key") or request.context.get("ability_key")
    applied = False
    try:
        applied = bool(
            unit.apply_start_of_battle_keyword_reroll_choice(
                model,
                keyword=str(keyword),
                source=str(source),
                ability_key=str(ability_key or ""),
            )
        )
    except Exception:
        applied = False
    try:
        player = getattr(getattr(unit, "get_parent_army", lambda: None)(), "player", None)
    except Exception:
        player = None
    try:
        mname = str(getattr(model, "name", "Model") or "Model")
        if applied:
            _log_action_for_players(game, player, f"{mname} selected {str(keyword).upper()} for {source}.")
    except Exception:
        pass
    return str(keyword)


def _resolve_emperors_children_manager(army: object):
    if army is None:
        return None
    mgr = getattr(army, "emperors_children", None)
    if mgr is not None:
        return mgr
    return getattr(army, "emperors_children_detachments", None)


def _validate_choose_pledge(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    value = payload.get("pledge_value", payload.get("value"))
    if value is None:
        return ("Pledge selection requires value.",)
    army = _resolve_army(game, request, payload)
    mgr = _resolve_emperors_children_manager(army)
    if mgr is None:
        return ("Emperor's Children manager not found.",)
    if not getattr(mgr, "is_coterie_of_conceited", lambda: False)():
        return ("Pledges to the Dark Prince requires Coterie of the Conceited.",)
    if not getattr(mgr, "warlord_on_battlefield", lambda: False)():
        return ("Pledges to the Dark Prince requires your warlord on the battlefield.",)
    return ()


def _apply_choose_pledge(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Emperor's Children army not found.")
    mgr = _resolve_emperors_children_manager(army)
    if mgr is None:
        raise RuntimeError("Emperor's Children manager not found.")
    value = payload.get("pledge_value", payload.get("value"))
    battle_round = request.context.get("battle_round")
    max_value = request.context.get("max_value")
    return int(mgr.set_pledge_target(int(value), battle_round=battle_round, max_value=max_value))


def _resurrection_orb_unit_on_battlefield(unit) -> bool:
    if unit is None:
        return False
    is_alive_fn = getattr(unit, "is_alive", None)
    if callable(is_alive_fn):
        if not bool(is_alive_fn()):
            return False
    elif getattr(unit, "is_alive", True) is False:
        return False
    if not bool(getattr(unit, "deployed", True)):
        return False
    if str(getattr(unit, "reserve_status", "deployed") or "deployed") != "deployed":
        return False
    in_reserves_fn = getattr(unit, "is_in_reserves", None)
    if callable(in_reserves_fn) and bool(in_reserves_fn()):
        return False
    if bool(getattr(unit, "embarked_in", None)) or bool(getattr(unit, "is_embarked", False)):
        return False
    return True


def _resurrection_orb_army_used_this_turn(army, *, turn: int, turn_owner_id: str) -> bool:
    if army is None:
        return False
    for unit in list(getattr(army, "units", []) or []):
        if unit is None:
            continue
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            continue
        try:
            used_turn = int(sr.get("resurrection_orb_used_turn", -1))
        except (TypeError, ValueError):
            continue
        if used_turn != int(turn):
            continue
        used_owner = str(sr.get("resurrection_orb_used_turn_owner", "") or "")
        if turn_owner_id and used_owner and used_owner != turn_owner_id:
            continue
        return True
    return False


def _mark_resurrection_orb_used_this_turn(source_unit, *, turn: int, turn_owner_id: str) -> None:
    if source_unit is None:
        return
    sr = getattr(source_unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    updated = dict(sr)
    updated["resurrection_orb_used_turn"] = int(turn)
    updated["resurrection_orb_used_turn_owner"] = str(turn_owner_id or "")
    source_unit.special_rules = updated


def _validate_choose_quarry(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    ctx = dict(getattr(request, "context", {}) or {})
    ability = str(ctx.get("ability", "") or "")
    if ability == "resurrection_orb":
        payload = _option_payload(request, result)
        source_unit = resolve_unit(
            game,
            payload.get("source_unit_id")
            or ctx.get("source_unit_id")
            or payload.get("unit_id")
            or ctx.get("unit_id"),
        )
        if source_unit is None:
            return ("Resurrection Orb source unit was not found.",)
        if bool(getattr(source_unit, "has_used_unit_once_per_battle", lambda _k: False)("resurrection_orb")):
            return ("Resurrection Orb has already been used by this bearer.",)

        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None or not _resurrection_orb_unit_on_battlefield(source_root):
            return ("Resurrection Orb source unit must be on the battlefield.",)

        current_player = getattr(game, "get_current_player", lambda: None)()
        turn_owner_id = str(getattr(current_player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        source_army = source_unit.get_parent_army() if hasattr(source_unit, "get_parent_army") else None
        if _resurrection_orb_army_used_this_turn(source_army, turn=turn, turn_owner_id=turn_owner_id):
            return ("Resurrection Orb has already resurrected a unit this turn.",)

        bearer_model = resolve_model(game, payload.get("bearer_model_id") or ctx.get("bearer_model_id"))
        if bearer_model is None:
            return ("Resurrection Orb bearer model was not found.",)
        bearer_alive = getattr(bearer_model, "is_alive", False)
        if not bool(bearer_alive() if callable(bearer_alive) else bearer_alive):
            return ("Resurrection Orb bearer model is not alive.",)
        if getattr(bearer_model, "parent_unit", None) is not source_unit:
            return ("Resurrection Orb bearer model is not part of the source unit.",)

        variant = str(ctx.get("resurrection_orb_variant", "") or "").strip().lower()
        if variant not in ("nearby", "leading"):
            return ("Resurrection Orb context is missing a supported variant.",)
        if is_skip_choice(request, result):
            return ()

        target_unit = resolve_unit(
            game,
            payload.get("target_unit_id") or payload.get("unit_id") or ctx.get("target_unit_id"),
        )
        if target_unit is None:
            return ("Resurrection Orb target unit was not found.",)
        target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        if target_root is None:
            return ("Resurrection Orb target unit was not found.",)
        if not _resurrection_orb_unit_on_battlefield(target_root):
            return ("Resurrection Orb target unit must be on the battlefield.",)

        target_id = str(get_entity_id(target_root) or "")
        allowed_ids = {str(val) for val in list(ctx.get("allowed_target_unit_ids", []) or []) if str(val)}
        if allowed_ids and target_id not in allowed_ids:
            return ("Resurrection Orb target is not an eligible unit.",)

        target_army = target_root.get_parent_army() if hasattr(target_root, "get_parent_army") else None
        if source_army is not None and target_army is not None and source_army is not target_army:
            return ("Resurrection Orb requires selecting a friendly unit.",)

        has_rp = getattr(target_root, "attached_unit_has_reanimation_protocols", None)
        if callable(has_rp) and not bool(has_rp()):
            return ("Resurrection Orb target must have Reanimation Protocols.",)

        if variant == "leading":
            if not bool(getattr(source_unit, "is_attached_leader", False)):
                return ("Resurrection Orb (leading variant) requires the bearer to be leading a unit.",)
            if target_root is not source_root:
                return ("Resurrection Orb (leading variant) can only target the bearer's unit.",)
        else:
            has_any_keyword = getattr(target_root, "has_any_keyword", None)
            if not callable(has_any_keyword):
                return ("Resurrection Orb target keyword resolver is unavailable.",)
            if not bool(has_any_keyword("NECRONS")):
                return ("Resurrection Orb target must be a friendly NECRONS unit.",)
            if not bool(has_any_keyword("INFANTRY") or has_any_keyword("MOUNTED")):
                return ("Resurrection Orb target must be a friendly NECRONS INFANTRY or MOUNTED unit.",)
            in_range_fn = getattr(game, "_unit_within_range_of_model", None)
            if callable(in_range_fn):
                if not bool(in_range_fn(bearer_model, target_root, range_value=6.0)):
                    return ("Resurrection Orb target must be within 6\" of the bearer.",)
        return ()
    if ability == "voice_of_triarch":
        if is_skip_choice(request, result):
            return ("Voice of the Triarch selection cannot be skipped.",)
        payload = _option_payload(request, result)
        source_unit = resolve_unit(
            game,
            payload.get("source_unit_id")
            or ctx.get("source_unit_id")
            or payload.get("unit_id")
            or ctx.get("unit_id"),
        )
        if source_unit is None:
            return ("Voice of the Triarch source unit was not found.",)
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None:
            return ("Voice of the Triarch source unit was not found.",)
        if not _resurrection_orb_unit_on_battlefield(source_root):
            return ("Voice of the Triarch source unit must be on the battlefield.",)
        from ...rules.necrons_voice_of_triarch import VOICE_OF_TRIARCH_BY_KEY, unit_has_voice_of_triarch_ability

        if not bool(unit_has_voice_of_triarch_ability(source_root)):
            return ("Voice of the Triarch source unit does not have Voice of the Triarch.",)

        choice_key = str(payload.get("choice_key", "") or "").strip().upper()
        if not choice_key:
            return ("Voice of the Triarch requires selecting one Triarch ability.",)
        allowed_keys = {str(val).strip().upper() for val in list(ctx.get("allowed_choice_keys", []) or []) if str(val).strip()}
        if allowed_keys and choice_key not in allowed_keys:
            return ("Voice of the Triarch selected ability is not an eligible choice.",)
        if choice_key not in VOICE_OF_TRIARCH_BY_KEY:
            return ("Voice of the Triarch selected ability is not supported.",)
        battle_round = int(getattr(game, "turn", 0) or 0)
        try:
            required_round = int(ctx.get("battle_round", 0) or 0)
        except (TypeError, ValueError):
            required_round = 0
        if required_round > 0 and battle_round != required_round:
            return ("Voice of the Triarch selection is no longer valid for this battle round.",)
        return ()
    if ability == "decoy_targets":
        payload = _option_payload(request, result)
        if is_skip_choice(request, result):
            return ()

        source_unit = resolve_unit(
            game,
            payload.get("source_unit_id") or ctx.get("source_unit_id") or payload.get("unit_id") or ctx.get("unit_id"),
        )
        if source_unit is None:
            return ("Decoy Targets source unit was not found.",)
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None:
            return ("Decoy Targets source unit was not found.",)

        checker = getattr(game, "_unit_on_battlefield_for_reposition", None)

        def _unit_on_battlefield(unit) -> bool:
            if unit is None:
                return False
            if callable(checker):
                return bool(checker(unit))
            try:
                if not unit.is_alive() or not bool(getattr(unit, "deployed", False)):
                    return False
            except Exception:
                return False
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    return False
            except Exception:
                pass
            return True

        def _model_alive(model) -> bool:
            if model is None:
                return False
            try:
                alive_attr = getattr(model, "is_alive", True)
                return bool(alive_attr() if callable(alive_attr) else alive_attr)
            except Exception:
                return False

        if not _unit_on_battlefield(source_root):
            return ("Decoy Targets source unit must be on the battlefield.",)

        try:
            source_members = list(source_root.get_attached_unit_members() or [])
        except Exception:
            source_members = [source_root]
        if not source_members:
            source_members = [source_root]
        enhancement_source = None
        enhancement_sr = None
        for member in list(source_members or []):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("enhancement_decoy_targets", False)):
                continue
            enhancement_source = member
            enhancement_sr = sr
            break
        if enhancement_source is None or not isinstance(enhancement_sr, dict):
            return ("Decoy Targets enhancement is not active on the source unit.",)

        try:
            max_uses = int(enhancement_sr.get("enhancement_decoy_targets_max_uses", 2) or 2)
        except Exception:
            max_uses = 2
        try:
            used_count = int(enhancement_sr.get("enhancement_decoy_targets_used_count", 0) or 0)
        except Exception:
            used_count = 0
        if used_count >= max(1, max_uses):
            return ("Decoy Targets has no uses remaining this battle.",)

        try:
            per_round_limit = int(enhancement_sr.get("enhancement_decoy_targets_per_battle_round_limit", 1) or 1)
        except Exception:
            per_round_limit = 1
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        try:
            used_round = int(enhancement_sr.get("enhancement_decoy_targets_used_battle_round", 0) or 0)
        except Exception:
            used_round = 0
        if used_round == current_turn:
            try:
                used_round_count = int(
                    enhancement_sr.get("enhancement_decoy_targets_used_this_battle_round_count", 0) or 0
                )
            except Exception:
                used_round_count = 0
        else:
            used_round_count = 0
        if used_round_count >= max(1, per_round_limit):
            return ("Decoy Targets has already been used this battle round.",)

        source_model_id = str(
            payload.get("source_model_id") or ctx.get("source_model_id") or enhancement_sr.get("enhancement_bearer_model_id", "") or ""
        )
        source_model = resolve_model(game, source_model_id) if source_model_id else None
        if source_model is None:
            get_bearer = getattr(enhancement_source, "_get_enhancement_bearer_model", None)
            source_model = get_bearer() if callable(get_bearer) else None
        if source_model is None:
            return ("Decoy Targets bearer model was not found.",)
        if not _model_alive(source_model):
            return ("Decoy Targets bearer model is not alive.",)
        source_model_parent = getattr(source_model, "parent_unit", None)
        source_model_root = (
            source_model_parent.get_attached_unit_root()
            if source_model_parent is not None and hasattr(source_model_parent, "get_attached_unit_root")
            else source_model_parent
        )
        if source_model_root is not source_root:
            return ("Decoy Targets bearer model is not part of the source unit.",)

        try:
            source_models = [m for m in list(getattr(source_root, "models", []) or []) if _model_alive(m)]
        except Exception:
            source_models = []
        if len(source_models) != 1:
            return ("Decoy Targets requires a single-model source unit.",)

        target_model = resolve_model(game, payload.get("target_model_id") or payload.get("model_id"))
        if target_model is None:
            return ("Decoy Targets target model was not found.",)
        target_model_id = str(get_entity_id(target_model) or getattr(target_model, "id", getattr(target_model, "_id", "")) or "")
        source_model_id_resolved = str(
            get_entity_id(source_model) or getattr(source_model, "id", getattr(source_model, "_id", "")) or ""
        )
        if target_model_id and source_model_id_resolved and target_model_id == source_model_id_resolved:
            return ("Decoy Targets requires selecting a different friendly model.",)
        target_parent = getattr(target_model, "parent_unit", None)
        if target_parent is None:
            return ("Decoy Targets target model has no parent unit.",)
        target_root = target_parent.get_attached_unit_root() if hasattr(target_parent, "get_attached_unit_root") else target_parent
        if target_root is None:
            return ("Decoy Targets target unit was not found.",)
        if not _unit_on_battlefield(target_root):
            return ("Decoy Targets target model must be on the battlefield.",)

        source_army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
        target_army = target_root.get_parent_army() if hasattr(target_root, "get_parent_army") else None
        if source_army is not None and target_army is not None and source_army is not target_army:
            return ("Decoy Targets requires selecting a friendly model.",)

        has_infantry = False
        if hasattr(target_root, "has_any_keyword"):
            has_infantry = bool(target_root.has_any_keyword("INFANTRY"))
        elif hasattr(target_root, "has_keyword"):
            has_infantry = bool(target_root.has_keyword("INFANTRY"))
        if not has_infantry:
            return ("Decoy Targets target model must be from a friendly INFANTRY unit.",)

        from ...utility.aura_utils import model_within_engagement_range_of_unit

        game_map = getattr(game, "map", None)
        enemy_units = []
        if game_map is not None and hasattr(game_map, "get_enemy_units"):
            try:
                enemy_units = list(game_map.get_enemy_units(target_root) or [])
            except Exception:
                enemy_units = []
        for enemy in list(enemy_units or []):
            if enemy is None:
                continue
            enemy_root = enemy.get_attached_unit_root() if hasattr(enemy, "get_attached_unit_root") else enemy
            if enemy_root is None:
                continue
            if not _unit_on_battlefield(enemy_root):
                continue
            if model_within_engagement_range_of_unit(target_model, enemy_root):
                return ("Decoy Targets target model must not be within Engagement Range of enemy units.",)

        try:
            target_pos = target_model.get_location()
        except Exception:
            return ("Decoy Targets target model position is unavailable.",)
        find_pos = getattr(game, "_find_closest_valid_reposition_position", None)
        if callable(find_pos):
            placement = find_pos(source_root, target_pos, game_map=getattr(game, "map", None))
            if not placement:
                return ("Decoy Targets cannot set up the bearer near the selected model.",)
        return ()
    if ability == "strike_swiftly":
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return ("Strike Swiftly source unit was not found.",)
        source_army = getattr(source_unit, "get_parent_army", lambda: None)()
        mgr = getattr(source_army, "tau_empire_detachments", None) if source_army is not None else None
        if mgr is None or not bool(getattr(mgr, "is_montka", lambda: False)()):
            return ("Strike Swiftly requires a T'au Empire Mont'ka army.",)
        if is_skip_choice(request, result):
            return ()

        selected_vals = payload.get("selected_unit_ids")
        if not isinstance(selected_vals, list):
            selected_vals = []
        if not selected_vals:
            one_target = payload.get("target_unit_id") or payload.get("unit_id")
            if one_target:
                selected_vals = [one_target]

        selected_ids = [str(v or "").strip() for v in list(selected_vals or []) if str(v or "").strip()]
        if len(selected_ids) > 2:
            return ("Strike Swiftly can select at most two units.",)
        if len(selected_ids) != len(set(selected_ids)):
            return ("Strike Swiftly selected_unit_ids must be unique.",)

        selectable = list(getattr(mgr, "strike_swiftly_selectable_units")(source_unit, game=game) or [])
        allowed_ids = {str(get_entity_id(unit) or "") for unit in selectable}
        for unit_id in selected_ids:
            if unit_id not in allowed_ids:
                return ("Strike Swiftly selection includes an ineligible unit.",)
        return ()
    if ability in (
        "imperial_knights_iron_chalice",
        "imperial_knights_evanescent_ion",
        "imperial_knights_judicants_helm",
        "imperial_knights_lancers_sigil",
    ):
        if is_skip_choice(request, result):
            return ("This Imperial Knights enhancement selection cannot be skipped.",)
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return ("Imperial Knights source unit was not found.",)
        target_unit = resolve_unit(game, payload.get("target_unit_id") or payload.get("unit_id") or ctx.get("target_unit_id"))
        if target_unit is None:
            return ("Imperial Knights target unit was not found.",)
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        if source_root is None or target_root is None:
            return ("Imperial Knights source/target unit root was not found.",)
        if target_root is source_root:
            return ("Imperial Knights enhancement requires selecting another unit.",)
        if not bool(getattr(source_root, "has_any_keyword", lambda _k: False)("IMPERIAL KNIGHTS")):
            return ("Imperial Knights source must have the IMPERIAL KNIGHTS keyword.",)
        if not bool(getattr(target_root, "has_any_keyword", lambda _k: False)("IMPERIAL KNIGHTS")):
            return ("Imperial Knights target must have the IMPERIAL KNIGHTS keyword.",)
        model = resolve_model(game, ctx.get("model_id"))
        if model is None:
            return ("Imperial Knights bearer model was not found.",)
        try:
            range_inches = float(ctx.get("range", 12) or 12)
        except (TypeError, ValueError):
            range_inches = 12.0
        in_range_fn = getattr(game, "_unit_within_range_of_model", None)
        if callable(in_range_fn):
            if not bool(in_range_fn(model, target_root, range_value=float(range_inches))):
                return ("Imperial Knights target is out of range.",)
        can_see_fn = getattr(game, "_model_can_see_unit", None)
        if callable(can_see_fn):
            if not bool(can_see_fn(model, target_root, game_map=getattr(game, "map", None))):
                return ("Imperial Knights target must be visible to the bearer.",)
        return ()
    if ability in (
        "aeldari_light_of_clarity_target",
        "aeldari_stave_of_kurnous_target",
        "aeldari_rune_of_mists_target",
    ):
        if is_skip_choice(request, result):
            return ("This Spirit Conclave enhancement selection cannot be skipped.",)
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return ("Spirit Conclave source unit was not found.",)
        source_army = getattr(source_unit, "get_parent_army", lambda: None)()
        mgr = getattr(source_army, "aeldari_detachments", None) if source_army is not None else None
        if mgr is None or not bool(getattr(mgr, "is_spirit_conclave", lambda: False)()):
            return ("This selection requires an Aeldari Spirit Conclave army.",)
        source_sr = getattr(source_unit, "special_rules", None)
        if not isinstance(source_sr, dict):
            source_sr = {}
        if ability == "aeldari_light_of_clarity_target" and not bool(source_sr.get("enhancement_light_of_clarity")):
            return ("Source unit does not have Light of Clarity.",)
        if ability == "aeldari_stave_of_kurnous_target" and not bool(source_sr.get("enhancement_stave_of_kurnous")):
            return ("Source unit does not have Stave of Kurnous.",)
        if ability == "aeldari_rune_of_mists_target" and not bool(source_sr.get("enhancement_rune_of_mists")):
            return ("Source unit does not have Rune of Mists.",)

        target_unit = resolve_unit(game, payload.get("target_unit_id") or payload.get("unit_id") or ctx.get("target_unit_id"))
        if target_unit is None:
            return ("Spirit Conclave target unit was not found.",)
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        if source_root is None or target_root is None:
            return ("Spirit Conclave source/target root was not found.",)
        if source_root.get_parent_army() is not target_root.get_parent_army():
            return ("Spirit Conclave target must be a friendly unit.",)
        has_wraith_construct = False
        try:
            has_wraith_construct = bool(target_root.has_any_keyword("WRAITH CONSTRUCT") or target_root.has_keyword("WRAITH CONSTRUCT"))
        except Exception:
            has_wraith_construct = False
        if not has_wraith_construct:
            return ("Spirit Conclave target must have the WRAITH CONSTRUCT keyword.",)
        if ability == "aeldari_stave_of_kurnous_target":
            exclude_titanic = bool(ctx.get("exclude_titanic", True))
            if exclude_titanic:
                is_titanic = False
                try:
                    is_titanic = bool(target_root.has_any_keyword("TITANIC") or target_root.has_keyword("TITANIC"))
                except Exception:
                    is_titanic = False
                if is_titanic:
                    return ("Stave of Kurnous cannot target TITANIC units.",)
        model = resolve_model(game, ctx.get("model_id"))
        if model is None:
            return ("Spirit Conclave bearer model was not found.",)
        try:
            range_inches = float(ctx.get("range", 12) or 12)
        except (TypeError, ValueError):
            range_inches = 12.0
        in_range_fn = getattr(game, "_unit_within_range_of_model", None)
        if callable(in_range_fn):
            if not bool(in_range_fn(model, target_root, range_value=float(range_inches))):
                return ("Spirit Conclave target is out of range.",)
        return ()
    if ability == "aeldari_lucid_eye_fate_die":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return ("Lucid Eye source unit was not found.",)
        source_army = getattr(source_unit, "get_parent_army", lambda: None)()
        mgr = getattr(source_army, "aeldari_detachments", None) if source_army is not None else None
        if mgr is None or not bool(getattr(mgr, "is_seer_council", lambda: False)()):
            return ("Lucid Eye requires an Aeldari Seer Council army.",)
        source_sr = getattr(source_unit, "special_rules", None)
        if not isinstance(source_sr, dict) or not bool(source_sr.get("enhancement_lucid_eye")):
            return ("Lucid Eye source unit does not have Lucid Eye.",)
        if is_skip_choice(request, result):
            return ()
        payload = _option_payload(request, result)
        die_index = payload.get("die_index")
        delta = payload.get("delta")
        try:
            die_index = int(die_index)
        except Exception:
            return ("Lucid Eye selection requires die_index.",)
        try:
            delta = int(delta)
        except Exception:
            return ("Lucid Eye selection requires delta.",)
        if delta not in (-1, 1):
            return ("Lucid Eye delta must be -1 or +1.",)
        preview = getattr(mgr, "preview_seer_council_lucid_eye_adjustments", None)
        if not callable(preview):
            return ("Lucid Eye manager support is unavailable.",)
        options = list(preview() or [])
        if not any(
            int(entry.get("die_index", -1)) == int(die_index) and int(entry.get("delta", 0)) == int(delta)
            for entry in options
        ):
            return ("Lucid Eye selection is not a legal Fate die adjustment.",)
        return ()
    if ability == "data_spike":
        if is_skip_choice(request, result):
            return ()
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("attacker_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return ("Data-spike source unit was not found.",)
        target_unit = resolve_unit(game, payload.get("target_unit_id") or ctx.get("target_unit_id"))
        if target_unit is None:
            return ("Data-spike target unit was not found.",)

        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        if source_root is None or target_root is None:
            return ("Data-spike source/target unit root was not found.",)
        if source_root is target_root:
            return ("Data-spike target must be an enemy VEHICLE unit.",)

        source_army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
        target_army = target_root.get_parent_army() if hasattr(target_root, "get_parent_army") else None
        if source_army is not None and target_army is not None and source_army is target_army:
            return ("Data-spike target must be an enemy VEHICLE unit.",)

        is_vehicle = False
        if hasattr(target_root, "has_any_keyword"):
            is_vehicle = bool(target_root.has_any_keyword("VEHICLE"))
        elif hasattr(target_root, "has_keyword"):
            is_vehicle = bool(target_root.has_keyword("VEHICLE"))
        if not is_vehicle:
            return ("Data-spike target must have the VEHICLE keyword.",)

        game_map = getattr(game, "map", None)
        in_engagement = bool(
            game_map is not None
            and hasattr(game_map, "is_within_engagement_range")
            and game_map.is_within_engagement_range(source_root, target_root)
        )
        if not in_engagement:
            return ("Data-spike target must be within Engagement Range of the source unit.",)
        return ()
    if ability == "rad_bombardment":
        if is_skip_choice(request, result):
            return ("Rad-bombardment cannot be skipped.",)
        payload = _option_payload(request, result)
        source_army = _resolve_army(game, request, payload)
        if source_army is None:
            return ("Rad-bombardment army not found.",)
        mgr = getattr(source_army, "adeptus_mechanicus_detachments", None)
        if mgr is None or not bool(getattr(mgr, "is_rad_zone_corps", lambda: False)()):
            return ("Rad-bombardment requires a Rad-Zone Corps army.",)

        try:
            battle_round = int(ctx.get("battle_round", 0) or getattr(game, "turn", 0) or 0)
        except Exception:
            battle_round = int(getattr(game, "turn", 0) or 0)
        if battle_round != 1:
            return ("Rad-bombardment Bombardment is only resolved in battle round 1.",)

        choice = str(payload.get("rad_bombardment_choice", "") or "").strip().lower()
        if choice not in ("stand_firm", "take_cover"):
            return ("Rad-bombardment choice must be Stand Firm or Take Cover.",)

        target_unit = resolve_unit(game, payload.get("target_unit_id") or ctx.get("target_unit_id"))
        if target_unit is None:
            return ("Rad-bombardment target unit was not found.",)
        player = _resolve_player(game, request, payload)
        if player is None:
            return ("Rad-bombardment opponent player was not found.",)
        player_id = str(getattr(player, "id", "") or "")
        if not player_id:
            return ("Rad-bombardment opponent player id was not found.",)

        target_army = target_unit.get_parent_army() if hasattr(target_unit, "get_parent_army") else None
        get_army = getattr(player, "get_army", None)
        player_army = get_army() if callable(get_army) else getattr(player, "army", None)
        if target_army is not None and player_army is not None and target_army is not player_army:
            return ("Rad-bombardment target must belong to the opposing player.",)

        in_zone = getattr(mgr, "unit_within_player_deployment_zone", None)
        if not callable(in_zone) or not bool(in_zone(target_unit, player_id, game=game)):
            return ("Rad-bombardment target must be within the opponent deployment zone.",)
        return ()
    if ability == "vanguard_of_dark_city":
        if is_skip_choice(request, result):
            return ("Vanguard of the Dark City selection cannot be skipped.",)
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return ("Vanguard of the Dark City source unit was not found.",)
        has_vanguard = getattr(source_unit, "has_vanguard_of_dark_city", None)
        if not callable(has_vanguard) or not bool(has_vanguard()):
            return ("Vanguard of the Dark City is not active on the selected source unit.",)
        mode = str(payload.get("vanguard_mode", "") or "").strip().lower()
        if mode not in ("masters_of_the_shadowed_sky", "speed_of_the_kill", "visions_of_butchery"):
            return ("Vanguard of the Dark City choice must be Masters of the Shadowed Sky, Speed of the Kill, or Visions of Butchery.",)
        return ()
    if ability == "void_mine":
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return ("Void Mine source unit was not found.",)
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None:
            return ("Void Mine source unit was not found.",)
        if bool(getattr(source_root, "has_used_unit_once_per_battle", lambda _k: False)("void_mine")):
            return ("Void Mine has already been used this battle.",)
        if is_skip_choice(request, result):
            return ()
        target_model_id = str(payload.get("target_model_id") or payload.get("model_id") or "").strip()
        if not target_model_id:
            return ("Void Mine selection requires target_model_id.",)
        candidate_ids = [str(v or "").strip() for v in list(ctx.get("candidate_model_ids", []) or []) if str(v or "").strip()]
        if candidate_ids and target_model_id not in candidate_ids:
            return ("Void Mine target model is not a legal moved-over candidate.",)
        target_model = resolve_model(game, target_model_id)
        if target_model is None:
            return ("Void Mine target model was not found.",)
        try:
            if not bool(getattr(target_model, "is_alive", False)):
                return ("Void Mine target model must be alive.",)
        except Exception:
            return ("Void Mine target model must be alive.",)
        source_army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
        target_parent = getattr(target_model, "parent_unit", None)
        target_root = (
            target_parent.get_attached_unit_root()
            if target_parent is not None and hasattr(target_parent, "get_attached_unit_root")
            else target_parent
        )
        target_army = target_root.get_parent_army() if target_root is not None and hasattr(target_root, "get_parent_army") else None
        if source_army is not None and target_army is not None and source_army is target_army:
            return ("Void Mine target model must belong to an enemy unit.",)
        return ()
    if is_skip_choice(request, result):
        return ()
    if ability not in ("strategic_conqueror", "archons_will_objective"):
        return ()
    payload = _option_payload(request, result)
    source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
    if source_unit is None:
        return ("Source unit was not found.",)
    objective_id = payload.get("objective_id") or ctx.get("objective_id")
    if not objective_id:
        if ability == "archons_will_objective":
            return ("Archon's Will selection requires objective_id.",)
        return ("Strategic Conqueror selection requires objective_id.",)
    if get_objective(game, str(objective_id or "")) is None:
        if ability == "archons_will_objective":
            return ("Archon's Will selected objective marker was not found.",)
        return ("Selected objective marker was not found.",)
    return ()


def _apply_choose_quarry(game: object, request: DecisionRequest, result: DecisionResult):
    ctx = dict(getattr(request, "context", {}) or {})
    ability = str(ctx.get("ability", "") or "")
    if ability == "resurrection_orb":
        payload = _option_payload(request, result)
        source_unit = resolve_unit(
            game,
            payload.get("source_unit_id")
            or ctx.get("source_unit_id")
            or payload.get("unit_id")
            or ctx.get("unit_id"),
        )
        if source_unit is None:
            return None
        if bool(getattr(source_unit, "has_used_unit_once_per_battle", lambda _k: False)("resurrection_orb")):
            return None

        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None or not _resurrection_orb_unit_on_battlefield(source_root):
            return None
        source_army = source_unit.get_parent_army() if hasattr(source_unit, "get_parent_army") else None
        player = _resolve_player(game, request, payload)
        if player is None and source_army is not None:
            player = getattr(source_army, "player", None)

        current_player = getattr(game, "get_current_player", lambda: None)()
        turn_owner_id = str(getattr(current_player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        if _resurrection_orb_army_used_this_turn(source_army, turn=turn, turn_owner_id=turn_owner_id):
            return None

        ability_name = str(ctx.get("ability_name", "") or "Resurrection Orb").strip() or "Resurrection Orb"
        if is_skip_choice(request, result):
            _log_action_for_players(game, player, f"{ability_name}: selected none.")
            return None

        bearer_model = resolve_model(game, payload.get("bearer_model_id") or ctx.get("bearer_model_id"))
        if bearer_model is None:
            return None
        bearer_alive = getattr(bearer_model, "is_alive", False)
        if not bool(bearer_alive() if callable(bearer_alive) else bearer_alive):
            return None
        if getattr(bearer_model, "parent_unit", None) is not source_unit:
            return None

        target_unit = resolve_unit(
            game,
            payload.get("target_unit_id") or payload.get("unit_id") or ctx.get("target_unit_id"),
        )
        if target_unit is None:
            return None
        target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        if target_root is None or not _resurrection_orb_unit_on_battlefield(target_root):
            return None
        target_id = str(get_entity_id(target_root) or "")
        allowed_ids = {str(val) for val in list(ctx.get("allowed_target_unit_ids", []) or []) if str(val)}
        if allowed_ids and target_id not in allowed_ids:
            return None

        variant = str(ctx.get("resurrection_orb_variant", "") or "").strip().lower()
        if variant == "leading":
            if not bool(getattr(source_unit, "is_attached_leader", False)):
                return None
            if target_root is not source_root:
                return None
        elif variant == "nearby":
            has_any_keyword = getattr(target_root, "has_any_keyword", None)
            if not callable(has_any_keyword):
                return None
            if not bool(has_any_keyword("NECRONS")):
                return None
            if not bool(has_any_keyword("INFANTRY") or has_any_keyword("MOUNTED")):
                return None
            in_range_fn = getattr(game, "_unit_within_range_of_model", None)
            if callable(in_range_fn):
                if not bool(in_range_fn(bearer_model, target_root, range_value=6.0)):
                    return None
        else:
            return None

        has_rp = getattr(target_root, "attached_unit_has_reanimation_protocols", None)
        if callable(has_rp) and not bool(has_rp()):
            return None

        from ...utility.dice import get_roll

        reanimated_wounds = max(0, int(get_roll("D6") or 0))
        game_map = getattr(game, "map", None)
        provider = getattr(game_map, "reanimation_allocation_provider", None) if game_map is not None else None
        is_human = bool(getattr(player, "has_control", lambda: False)()) if player is not None else False
        target_root.apply_reanimation_protocols(
            int(reanimated_wounds),
            game_map=game_map,
            is_human=is_human,
            provider=provider,
        )

        getattr(source_unit, "mark_unit_once_per_battle_used", lambda _k, **_kw: None)(
            "resurrection_orb",
            ability_name=ability_name,
        )
        _mark_resurrection_orb_used_this_turn(
            source_unit,
            turn=int(turn),
            turn_owner_id=turn_owner_id,
        )
        _log_action_for_players(
            game,
            player,
            f"{ability_name}: {getattr(target_root, 'name', 'Unit')} activates Reanimation Protocols and reanimates D6 wounds (roll {int(reanimated_wounds)}).",
        )
        return {
            "source_unit_id": str(get_entity_id(source_unit) or ""),
            "target_unit_id": str(get_entity_id(target_root) or ""),
            "reanimated_wounds": int(reanimated_wounds),
        }
    if ability == "decoy_targets":
        payload = _option_payload(request, result)
        source_unit = resolve_unit(
            game,
            payload.get("source_unit_id") or ctx.get("source_unit_id") or payload.get("unit_id") or ctx.get("unit_id"),
        )
        if source_unit is None:
            return None
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None:
            return None

        checker = getattr(game, "_unit_on_battlefield_for_reposition", None)

        def _unit_on_battlefield(unit) -> bool:
            if unit is None:
                return False
            if callable(checker):
                return bool(checker(unit))
            try:
                if not unit.is_alive() or not bool(getattr(unit, "deployed", False)):
                    return False
            except Exception:
                return False
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    return False
            except Exception:
                pass
            return True

        def _model_alive(model) -> bool:
            if model is None:
                return False
            try:
                alive_attr = getattr(model, "is_alive", True)
                return bool(alive_attr() if callable(alive_attr) else alive_attr)
            except Exception:
                return False

        if not _unit_on_battlefield(source_root):
            return None

        try:
            source_members = list(source_root.get_attached_unit_members() or [])
        except Exception:
            source_members = [source_root]
        if not source_members:
            source_members = [source_root]
        enhancement_source = None
        enhancement_sr = None
        for member in list(source_members or []):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("enhancement_decoy_targets", False)):
                continue
            enhancement_source = member
            enhancement_sr = sr
            break
        if enhancement_source is None or not isinstance(enhancement_sr, dict):
            return None

        try:
            max_uses = int(enhancement_sr.get("enhancement_decoy_targets_max_uses", 2) or 2)
        except Exception:
            max_uses = 2
        try:
            used_count = int(enhancement_sr.get("enhancement_decoy_targets_used_count", 0) or 0)
        except Exception:
            used_count = 0
        if used_count >= max(1, max_uses):
            return None
        try:
            per_round_limit = int(enhancement_sr.get("enhancement_decoy_targets_per_battle_round_limit", 1) or 1)
        except Exception:
            per_round_limit = 1
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        try:
            used_round = int(enhancement_sr.get("enhancement_decoy_targets_used_battle_round", 0) or 0)
        except Exception:
            used_round = 0
        if used_round == current_turn:
            try:
                used_round_count = int(
                    enhancement_sr.get("enhancement_decoy_targets_used_this_battle_round_count", 0) or 0
                )
            except Exception:
                used_round_count = 0
        else:
            used_round_count = 0
        if used_round_count >= max(1, per_round_limit):
            return None

        source_model_id = str(
            payload.get("source_model_id") or ctx.get("source_model_id") or enhancement_sr.get("enhancement_bearer_model_id", "") or ""
        )
        source_model = resolve_model(game, source_model_id) if source_model_id else None
        if source_model is None:
            get_bearer = getattr(enhancement_source, "_get_enhancement_bearer_model", None)
            source_model = get_bearer() if callable(get_bearer) else None
        if not _model_alive(source_model):
            return None
        source_model_parent = getattr(source_model, "parent_unit", None)
        source_model_root = (
            source_model_parent.get_attached_unit_root()
            if source_model_parent is not None and hasattr(source_model_parent, "get_attached_unit_root")
            else source_model_parent
        )
        if source_model_root is not source_root:
            return None

        if is_skip_choice(request, result):
            try:
                player = getattr(source_root.get_parent_army(), "player", None)
            except Exception:
                player = None
            ability_name = str(payload.get("ability_name") or ctx.get("ability_name") or "Decoy Targets").strip() or "Decoy Targets"
            _log_action_for_players(
                game,
                player,
                f"{ability_name}: {getattr(source_model, 'name', 'Model')} selected none.",
            )
            return None

        target_model = resolve_model(game, payload.get("target_model_id") or payload.get("model_id"))
        if not _model_alive(target_model):
            return None
        target_model_id = str(get_entity_id(target_model) or getattr(target_model, "id", getattr(target_model, "_id", "")) or "")
        source_model_id_resolved = str(
            get_entity_id(source_model) or getattr(source_model, "id", getattr(source_model, "_id", "")) or ""
        )
        if target_model_id and source_model_id_resolved and target_model_id == source_model_id_resolved:
            return None
        target_parent = getattr(target_model, "parent_unit", None)
        if target_parent is None:
            return None
        target_root = target_parent.get_attached_unit_root() if hasattr(target_parent, "get_attached_unit_root") else target_parent
        if target_root is None or not _unit_on_battlefield(target_root):
            return None

        source_army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
        target_army = target_root.get_parent_army() if hasattr(target_root, "get_parent_army") else None
        if source_army is not None and target_army is not None and source_army is not target_army:
            return None

        has_infantry = False
        if hasattr(target_root, "has_any_keyword"):
            has_infantry = bool(target_root.has_any_keyword("INFANTRY"))
        elif hasattr(target_root, "has_keyword"):
            has_infantry = bool(target_root.has_keyword("INFANTRY"))
        if not has_infantry:
            return None

        from ...utility.aura_utils import model_within_engagement_range_of_unit

        game_map = getattr(game, "map", None)
        enemy_units = []
        if game_map is not None and hasattr(game_map, "get_enemy_units"):
            try:
                enemy_units = list(game_map.get_enemy_units(target_root) or [])
            except Exception:
                enemy_units = []
        for enemy in list(enemy_units or []):
            if enemy is None:
                continue
            enemy_root = enemy.get_attached_unit_root() if hasattr(enemy, "get_attached_unit_root") else enemy
            if enemy_root is None or not _unit_on_battlefield(enemy_root):
                continue
            if model_within_engagement_range_of_unit(target_model, enemy_root):
                return None

        try:
            target_pos = target_model.get_location()
        except Exception:
            return None
        find_pos = getattr(game, "_find_closest_valid_reposition_position", None)
        if callable(find_pos):
            placement = find_pos(source_root, target_pos, game_map=getattr(game, "map", None))
        else:
            placement = target_pos
        if not placement:
            return None

        remove_model = getattr(target_parent, "remove_model", None)
        if not callable(remove_model):
            return None
        remove_model(target_model, fleed=True, game_map=getattr(game, "map", None))

        try:
            facing = float(placement[3]) if len(placement) >= 4 else float(
                getattr(getattr(source_model, "model_base", None), "facing", 0.0) or 0.0
            )
        except Exception:
            facing = 0.0
        source_model.set_location(
            float(placement[0]),
            float(placement[1]),
            float(placement[2]),
            float(facing),
        )
        source_root.position = (float(placement[0]), float(placement[1]), float(placement[2]))
        if getattr(game, "map", None) is not None and hasattr(game.map, "units"):
            if source_root not in game.map.units:
                game.map.units.append(source_root)

        updated_sr = dict(enhancement_sr or {})
        updated_sr["enhancement_decoy_targets_used_count"] = int(used_count + 1)
        updated_sr["enhancement_decoy_targets_used_battle_round"] = int(current_turn)
        updated_sr["enhancement_decoy_targets_used_this_battle_round_count"] = int(used_round_count + 1)
        enhancement_source.special_rules = updated_sr

        try:
            event_system = getattr(game, "event_system", None)
            if event_system is not None:
                event_system.publish(
                    "unit_set_up",
                    unit=source_root,
                    set_up_as_reinforcements=False,
                )
        except Exception:
            pass

        try:
            player = getattr(source_root.get_parent_army(), "player", None)
        except Exception:
            player = None
        ability_name = str(payload.get("ability_name") or ctx.get("ability_name") or "Decoy Targets").strip() or "Decoy Targets"
        _log_action_for_players(
            game,
            player,
            f"{ability_name}: {getattr(target_model, 'name', 'Model')} was removed; "
            f"{getattr(source_model, 'name', 'Model')} repositioned.",
        )
        return {
            "source_unit_id": str(get_entity_id(source_root) or ""),
            "source_model_id": source_model_id_resolved,
            "target_model_id": target_model_id,
        }
    if ability == "rad_bombardment":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        source_army = _resolve_army(game, request, payload)
        if source_army is None:
            return None
        mgr = getattr(source_army, "adeptus_mechanicus_detachments", None)
        if mgr is None or not bool(getattr(mgr, "is_rad_zone_corps", lambda: False)()):
            return None

        target_unit = resolve_unit(game, payload.get("target_unit_id") or ctx.get("target_unit_id"))
        if target_unit is None:
            return None
        target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        if target_root is None:
            return None

        choice = str(payload.get("rad_bombardment_choice", "") or "").strip().lower()
        if choice not in ("stand_firm", "take_cover"):
            return None

        try:
            battle_round = int(ctx.get("battle_round", 0) or getattr(game, "turn", 0) or 0)
        except Exception:
            battle_round = int(getattr(game, "turn", 0) or 0)

        from ...utility.dice import get_roll

        roll = int(get_roll("D6") or 0)
        threshold = 3 if choice == "stand_firm" else 5
        mortal_wounds = 0
        if roll >= int(threshold):
            mortal_wounds = int(get_roll("D3") or 0)

        added_battleshock = False
        if choice == "take_cover":
            is_battle_shocked = getattr(target_root, "is_battle_shocked", None)
            currently_battle_shocked = bool(is_battle_shocked()) if callable(is_battle_shocked) else False
            if not currently_battle_shocked:
                from ...units.status_effects import BattleShockEffect

                apply_effect = getattr(target_root, "apply_status_effect", None)
                if callable(apply_effect):
                    apply_effect(BattleShockEffect(int(battle_round)))
                    added_battleshock = True
            special_rules = getattr(target_root, "special_rules", None)
            if not isinstance(special_rules, dict):
                special_rules = {}
            special_rules = dict(special_rules)
            special_rules["rad_bombardment_taking_cover_round"] = int(battle_round)
            special_rules["rad_bombardment_taking_cover_added_battleshock"] = bool(
                special_rules.get("rad_bombardment_taking_cover_added_battleshock", False) or added_battleshock
            )
            target_root.special_rules = special_rules

        if mortal_wounds > 0:
            apply_mortal_wounds = getattr(target_root, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortal_wounds):
                apply_mortal_wounds(
                    target_root,
                    int(mortal_wounds),
                    game_map=getattr(game, "map", None),
                )

        player = getattr(source_army, "player", None)
        target_name = str(getattr(target_root, "name", "Unit") or "Unit")
        if choice == "take_cover":
            if mortal_wounds > 0:
                _log_action_for_players(
                    game,
                    player,
                    f"Rad-bombardment: {target_name} took cover, is Battle-shocked until end of battle round, and suffered {int(mortal_wounds)} mortal wounds (roll {int(roll)}).",
                )
            else:
                _log_action_for_players(
                    game,
                    player,
                    f"Rad-bombardment: {target_name} took cover, is Battle-shocked until end of battle round, and suffered no mortal wounds (roll {int(roll)}).",
                )
        else:
            if mortal_wounds > 0:
                _log_action_for_players(
                    game,
                    player,
                    f"Rad-bombardment: {target_name} stood firm and suffered {int(mortal_wounds)} mortal wounds (roll {int(roll)}).",
                )
            else:
                _log_action_for_players(
                    game,
                    player,
                    f"Rad-bombardment: {target_name} stood firm and suffered no mortal wounds (roll {int(roll)}).",
                )
        return target_root
    if ability == "vanguard_of_dark_city":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return None
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None:
            return None
        mode = str(payload.get("vanguard_mode", "") or "").strip().lower()
        if mode not in ("masters_of_the_shadowed_sky", "speed_of_the_kill", "visions_of_butchery"):
            return None
        try:
            members = list(source_root.get_attached_unit_members() or [])
        except Exception:
            members = [source_root]
        if not members:
            members = [source_root]
        for member in list(members or []):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr = dict(sr)
            sr["vanguard_of_dark_city_selected_mode"] = mode
            member.special_rules = sr
        try:
            player = getattr(source_root.get_parent_army(), "player", None)
        except Exception:
            player = None
        mode_label = mode.replace("_", " ").title()
        source_name = str(getattr(source_root, "name", "Unit") or "Unit")
        ability_name = str(ctx.get("ability_name", "") or "Vanguard of the Dark City").strip() or "Vanguard of the Dark City"
        _log_action_for_players(
            game,
            player,
            f"{ability_name}: {source_name} selected {mode_label}.",
        )
        return {"mode": mode}
    if ability == "archons_will_objective":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return None
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None:
            return None
        objective_id = str(payload.get("objective_id") or ctx.get("objective_id") or "").strip()
        if not objective_id:
            return None
        objective = get_objective(game, objective_id)
        if objective is None:
            return None
        try:
            members = list(source_root.get_attached_unit_members() or [])
        except Exception:
            members = [source_root]
        if not members:
            members = [source_root]
        for member in list(members or []):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr = dict(sr)
            sr["archons_will_objective_id"] = objective_id
            member.special_rules = sr
        try:
            player = getattr(source_root.get_parent_army(), "player", None)
        except Exception:
            player = None
        source_name = str(getattr(source_root, "name", "Unit") or "Unit")
        objective_name = str(getattr(objective, "name", "") or "Objective marker")
        _log_action_for_players(
            game,
            player,
            f"Archon's Will: {source_name} selected {objective_name}.",
        )
        return objective
    if ability == "void_mine":
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return None
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None:
            return None
        if bool(getattr(source_root, "has_used_unit_once_per_battle", lambda _k: False)("void_mine")):
            return None
        ability_name = str(ctx.get("ability_name", "") or "Void Mine").strip() or "Void Mine"
        try:
            player = getattr(source_root.get_parent_army(), "player", None)
        except Exception:
            player = None
        if is_skip_choice(request, result):
            _log_action_for_players(
                game,
                player,
                f"{ability_name}: {getattr(source_root, 'name', 'Unit')} selected none.",
            )
            return None

        target_model_id = str(payload.get("target_model_id") or payload.get("model_id") or "").strip()
        target_model = resolve_model(game, target_model_id) if target_model_id else None
        if target_model is None:
            return None
        target_unit = getattr(target_model, "parent_unit", None)
        target_root = (
            target_unit.get_attached_unit_root()
            if target_unit is not None and hasattr(target_unit, "get_attached_unit_root")
            else target_unit
        )
        if target_root is None:
            return None

        from ...utility.aura_utils import model_within_range_of_unit
        from ...utility.dice import get_roll

        radius = int(get_roll("D6") or 0)
        if radius <= 0:
            return None
        game_map = getattr(game, "map", None)
        if game_map is None:
            return None

        nearby_enemy_units = []
        try:
            enemies = list(game_map.get_enemy_units(source_root) or [])
        except Exception:
            enemies = []
        seen_enemy_ids: set[str] = set()
        for enemy in list(enemies or []):
            if enemy is None:
                continue
            enemy_root = enemy.get_attached_unit_root() if hasattr(enemy, "get_attached_unit_root") else enemy
            if enemy_root is None:
                continue
            enemy_id = str(get_entity_id(enemy_root) or "")
            if not enemy_id or enemy_id in seen_enemy_ids:
                continue
            seen_enemy_ids.add(enemy_id)
            try:
                if not enemy_root.is_alive() or not bool(getattr(enemy_root, "deployed", True)):
                    continue
            except Exception:
                continue
            try:
                if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                    continue
            except Exception:
                pass
            if model_within_range_of_unit(target_model, enemy_root, float(radius)):
                nearby_enemy_units.append(enemy_root)

        summary_parts: list[str] = []
        for enemy_root in sorted(list(nearby_enemy_units or []), key=lambda u: str(get_entity_id(u) or "")):
            trigger = int(get_roll("D6") or 0)
            enemy_name = str(getattr(enemy_root, "name", "Enemy unit") or "Enemy unit")
            if trigger >= 4:
                mortals = int(get_roll("D6") or 0)
                if mortals > 0:
                    apply_mortal_wounds = getattr(enemy_root, "_apply_mortal_wounds_to_unit", None)
                    if callable(apply_mortal_wounds):
                        apply_mortal_wounds(enemy_root, int(mortals), game_map=game_map)
                summary_parts.append(f"{enemy_name}: roll {int(trigger)} -> {int(mortals)} mortal wounds")
            else:
                summary_parts.append(f"{enemy_name}: roll {int(trigger)} -> no effect")

        mark_used = getattr(source_root, "mark_unit_once_per_battle_used", None)
        if callable(mark_used):
            mark_used("void_mine", ability_name=ability_name)

        source_name = str(getattr(source_root, "name", "Unit") or "Unit")
        target_name = str(getattr(target_model, "name", "Model") or "Model")
        detail = "; ".join(summary_parts) if summary_parts else "no enemy units were within range"
        _log_action_for_players(
            game,
            player,
            f"{ability_name}: {source_name} selected {target_name}; blast radius {int(radius)}\"; {detail}.",
        )
        return {"target_model_id": target_model_id, "radius": int(radius)}
    if ability == "strategic_conqueror":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return None
        objective_id = str(payload.get("objective_id") or ctx.get("objective_id") or "").strip()
        if not objective_id:
            return None
        objective = get_objective(game, objective_id)
        if objective is None:
            return None
        sr = getattr(source_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["enhancement_strategic_conqueror"] = True
        sr["enhancement_strategic_conqueror_selected_objective_id"] = objective_id
        if "enhancement_strategic_conqueror_oc_bonus" not in sr:
            sr["enhancement_strategic_conqueror_oc_bonus"] = 1
        source_unit.special_rules = sr
        try:
            player = getattr(source_unit.get_parent_army(), "player", None)
        except Exception:
            player = None
        try:
            source_name = str(getattr(source_unit, "name", "Unit") or "Unit")
            objective_name = str(getattr(objective, "name", "") or "Objective marker")
            _log_action_for_players(
                game,
                player,
                f"Strategic Conqueror: {source_name} selected {objective_name}.",
            )
        except Exception:
            pass
        return objective
    if ability == "strike_swiftly":
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return None
        source_army = getattr(source_unit, "get_parent_army", lambda: None)()
        mgr = getattr(source_army, "tau_empire_detachments", None) if source_army is not None else None
        if mgr is None:
            return None

        source_sr = getattr(source_unit, "special_rules", None)
        if not isinstance(source_sr, dict):
            source_sr = {}
        try:
            scout_distance = float(
                source_sr.get(
                    "enhancement_strike_swiftly_scouts_distance",
                    ctx.get("scout_distance", 6),
                )
                or 6
            )
        except Exception:
            scout_distance = 6.0
        scout_distance = max(0.0, float(scout_distance))

        selected_vals = payload.get("selected_unit_ids")
        if not isinstance(selected_vals, list):
            selected_vals = []
        if not selected_vals:
            one_target = payload.get("target_unit_id") or payload.get("unit_id")
            if one_target:
                selected_vals = [one_target]
        if is_skip_choice(request, result):
            selected_vals = []

        selectable_units = list(getattr(mgr, "strike_swiftly_selectable_units")(source_unit, game=game) or [])
        selectable_by_id = {str(get_entity_id(unit) or ""): unit for unit in selectable_units}

        selected_roots = []
        seen_ids: set[str] = set()
        for unit_id in list(selected_vals or []):
            unit_id_str = str(unit_id or "").strip()
            if not unit_id_str or unit_id_str in seen_ids:
                continue
            root = selectable_by_id.get(unit_id_str)
            if root is None:
                continue
            seen_ids.add(unit_id_str)
            selected_roots.append(root)
            if len(selected_roots) >= 2:
                break

        source_unit_id = str(get_entity_id(source_unit) or "")
        selected_unit_ids = []
        for root in selected_roots:
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = []
            if not members:
                members = [root]
            for member in members:
                member_sr = getattr(member, "special_rules", None)
                if not isinstance(member_sr, dict):
                    member_sr = {}
                try:
                    current = float(member_sr.get("enhancement_scout_distance", 0) or 0)
                except Exception:
                    current = 0.0
                if scout_distance > current:
                    member_sr["enhancement_scout_distance"] = float(scout_distance)
                member_sr["enhancement_strike_swiftly_source_unit_id"] = source_unit_id
                member_sr["enhancement_strike_swiftly_scouts_distance"] = float(scout_distance)
                member.special_rules = member_sr
                invalidate_cache = getattr(member, "_invalidate_ability_cache", None)
                if callable(invalidate_cache):
                    invalidate_cache()
            selected_unit_ids.append(str(get_entity_id(root) or ""))

        source_sr["enhancement_strike_swiftly"] = True
        source_sr["enhancement_strike_swiftly_resolved"] = True
        source_sr["enhancement_strike_swiftly_selected_unit_ids"] = sorted(
            [uid for uid in selected_unit_ids if uid]
        )
        source_unit.special_rules = source_sr

        player = _resolve_player(game, request, payload)
        if player is None:
            player = getattr(source_army, "player", None) if source_army is not None else None
        source_name = str(getattr(source_unit, "name", "Unit") or "Unit")
        if selected_roots:
            names = ", ".join(str(getattr(unit_obj, "name", "Unit") or "Unit") for unit_obj in selected_roots)
            _log_action_for_players(
                game,
                player,
                f"Strike Swiftly: {source_name} selected {names}; selected units gain Scouts {int(scout_distance)}\".",
            )
        else:
            _log_action_for_players(
                game,
                player,
                f"Strike Swiftly: {source_name} selected none.",
            )
        return selected_roots
    if ability in (
        "aeldari_light_of_clarity_target",
        "aeldari_stave_of_kurnous_target",
        "aeldari_rune_of_mists_target",
    ):
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        target_unit = resolve_unit(game, payload.get("target_unit_id") or payload.get("unit_id") or ctx.get("target_unit_id"))
        if source_unit is None or target_unit is None:
            return None
        player = _resolve_player(game, request, payload)
        if player is None:
            try:
                player = getattr(source_unit.get_parent_army(), "player", None)
            except Exception:
                player = None
        ability_name = str(ctx.get("ability_name", "") or "Spirit Conclave enhancement").strip() or "Spirit Conclave enhancement"
        if ability == "aeldari_light_of_clarity_target":
            try:
                infantry_bonus = int(ctx.get("infantry_bonus", 1) or 1)
            except Exception:
                infantry_bonus = 1
            try:
                monster_bonus = int(ctx.get("monster_bonus", 3) or 3)
            except Exception:
                monster_bonus = 3
            apply_fn = getattr(game, "_apply_aeldari_light_of_clarity_effect", None)
            if callable(apply_fn):
                return apply_fn(
                    source_unit=source_unit,
                    target_unit=target_unit,
                    player=player,
                    ability_name=ability_name,
                    infantry_bonus=int(infantry_bonus),
                    monster_bonus=int(monster_bonus),
                )
            return None
        if ability == "aeldari_stave_of_kurnous_target":
            apply_fn = getattr(game, "_apply_aeldari_stave_of_kurnous_effect", None)
            if callable(apply_fn):
                return apply_fn(
                    source_unit=source_unit,
                    target_unit=target_unit,
                    player=player,
                    ability_name=ability_name,
                )
            return None
        if ability == "aeldari_rune_of_mists_target":
            try:
                threshold = int(ctx.get("min_attacker_distance_for_cover", 18) or 18)
            except Exception:
                threshold = 18
            apply_fn = getattr(game, "_apply_aeldari_rune_of_mists_effect", None)
            if callable(apply_fn):
                return apply_fn(
                    source_unit=source_unit,
                    target_unit=target_unit,
                    player=player,
                    ability_name=ability_name,
                    min_attacker_distance_for_cover=int(threshold),
                )
            return None
        return None
    if ability == "aeldari_lucid_eye_fate_die":
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return None
        source_army = getattr(source_unit, "get_parent_army", lambda: None)()
        mgr = getattr(source_army, "aeldari_detachments", None) if source_army is not None else None
        if mgr is None:
            return None
        player = _resolve_player(game, request, payload)
        if player is None:
            player = getattr(source_army, "player", None) if source_army is not None else None
        ability_name = str(ctx.get("ability_name", "") or "Lucid Eye").strip() or "Lucid Eye"
        source_name = str(getattr(source_unit, "name", "Unit") or "Unit")
        if is_skip_choice(request, result):
            _log_action_for_players(game, player, f"{ability_name}: {source_name} selected none.")
            return None
        try:
            die_index = int(payload.get("die_index"))
            delta = int(payload.get("delta"))
        except Exception:
            return None
        apply_fn = getattr(mgr, "apply_seer_council_lucid_eye_adjustment", None)
        if not callable(apply_fn):
            return None
        outcome = dict(apply_fn(die_index=int(die_index), delta=int(delta)) or {})
        if not bool(outcome.get("applied", False)):
            return None
        before = int(outcome.get("before", 0) or 0)
        after = int(outcome.get("after", 0) or 0)
        _log_action_for_players(
            game,
            player,
            f"{ability_name}: {source_name} changed Fate die {int(die_index) + 1} from {before} to {after}.",
        )
        return outcome
    if ability == "aeldari_guileful_strategist":
        skipped = is_skip_choice(request, result)
        apply_fn = getattr(game, "_apply_redeploy_choice", None)
        if callable(apply_fn):
            apply_fn(request, result, skipped=skipped)
        return None
    if ability == "aeldari_strength_from_death_lethal_reprisal":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        target_unit = resolve_unit(game, payload.get("target_unit_id") or ctx.get("target_unit_id") or payload.get("unit_id"))
        if target_unit is None:
            return None
        try:
            target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        except Exception:
            target_root = target_unit
        if target_root is None:
            return None
        ability_name = str(ctx.get("ability_name", "") or "Strength from Death (Lethal Reprisal)").strip() or "Strength from Death (Lethal Reprisal)"
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["empowered_by_death_active"] = True
        sr["empowered_by_death_expires_phase"] = "FIGHT_PHASE"
        sr["empowered_by_death_source"] = ability_name
        target_root.special_rules = sr
        player = _resolve_player(game, request, payload)
        if player is None:
            try:
                player = getattr(target_root.get_parent_army(), "player", None)
            except Exception:
                player = None
        try:
            _log_action_for_players(
                game,
                player,
                f"{ability_name}: {getattr(target_root, 'name', 'Unit')} gains Fights First until end of phase.",
            )
        except Exception:
            pass
        return target_root
    if ability == "aeldari_strength_from_death_lethal_intent":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        target_unit = resolve_unit(game, payload.get("target_unit_id") or ctx.get("target_unit_id") or payload.get("unit_id"))
        if target_unit is None:
            return None
        try:
            target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        except Exception:
            target_root = target_unit
        if target_root is None:
            return None
        try:
            from ...utility.dice import get_roll
        except Exception:
            return None
        try:
            move_distance = int(get_roll("D6") or 0) + 1
        except Exception:
            move_distance = 1
        if move_distance <= 0:
            return None
        ability_name = str(ctx.get("ability_name", "") or "Strength from Death (Lethal Intent)").strip() or "Strength from Death (Lethal Intent)"
        player = _resolve_player(game, request, payload)
        if player is None:
            try:
                player = getattr(target_root.get_parent_army(), "player", None)
            except Exception:
                player = None
        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if callable(queue_move):
            queue_move(
                player=player,
                unit=target_root,
                max_distance=int(move_distance),
                kind="aeldari_strength_from_death_lethal_intent",
                movement_type="reactive",
                source=ability_name,
            )
        try:
            _log_action_for_players(
                game,
                player,
                f"{ability_name}: {getattr(target_root, 'name', 'Unit')} can make a Normal move of up to {int(move_distance)}\".",
            )
        except Exception:
            pass
        return target_root
    if ability == "paragon_of_sanctity":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        target_unit = resolve_unit(game, payload.get("target_unit_id", payload.get("unit_id", ctx.get("target_unit_id"))))
        if source_unit is None or target_unit is None:
            return None
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        if source_root is None or target_root is None:
            return None
        ability_key = str(ctx.get("ability_key", "") or "paragon_of_sanctity").strip().lower()
        if not ability_key:
            ability_key = "paragon_of_sanctity"
        if getattr(source_root, "has_used_unit_once_per_battle", lambda _k: False)(ability_key):
            return None
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn = 0
        sr["paragon_of_sanctity_hallowed_ground_active"] = True
        sr["paragon_of_sanctity_hallowed_ground_turn"] = int(turn)
        sr["paragon_of_sanctity_hallowed_ground_phase"] = phase_name
        sr["paragon_of_sanctity_hallowed_ground_source_unit_id"] = str(get_entity_id(source_root) or "")
        sr["paragon_of_sanctity_hallowed_ground_source"] = str(ctx.get("ability_name", "") or "Paragon of Sanctity")
        target_root.special_rules = sr
        getattr(source_root, "mark_unit_once_per_battle_used", lambda _k, **_kw: None)(
            ability_key,
            ability_name=str(ctx.get("ability_name", "") or "Paragon of Sanctity"),
        )
        try:
            player = getattr(getattr(source_root, "get_parent_army", lambda: None)(), "player", None)
        except Exception:
            player = None
        try:
            _log_action_for_players(
                game,
                player,
                "Paragon of Sanctity: "
                f"{getattr(target_root, 'name', 'Unit')} counts as within Hallowed Ground until end of phase.",
            )
        except Exception:
            pass
        return None
    if ability == "blinding_spray":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        model_id = payload.get("model_id") or ctx.get("model_id")
        source_unit = resolve_unit(game, payload.get("source_unit_id") or payload.get("unit_id") or ctx.get("source_unit_id") or ctx.get("unit_id"))
        model = resolve_model(game, model_id)
        if model is None:
            return None
        if source_unit is None:
            source_unit = getattr(model, "parent_unit", None)
        if source_unit is None:
            return None
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None:
            return None
        model_root = getattr(getattr(model, "parent_unit", None), "get_attached_unit_root", None)
        if callable(model_root):
            try:
                if model_root() is not source_root:
                    return None
            except Exception:
                pass

        ability_key = str(payload.get("ability_key", "") or ctx.get("ability_key", "") or "").strip().lower()
        if not ability_key:
            ability_key = f"blinding_spray:{str(get_entity_id(model) or '')}"
        if getattr(model, "has_used_once_per_battle", lambda _k: False)(ability_key):
            return None

        try:
            player = getattr(source_root.get_parent_army(), "player", None)
        except Exception:
            player = None
        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn = 0

        ability_name = str(payload.get("ability_name", "") or ctx.get("ability_name", "") or "Blinding Spray").strip() or "Blinding Spray"
        sr = getattr(source_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["blinding_spray_fight_first_active"] = True
        sr["blinding_spray_owner"] = owner_id
        sr["blinding_spray_turn"] = int(turn)
        sr["blinding_spray_source"] = ability_name
        sr["blinding_spray_expires_phase"] = "FIGHT_PHASE"
        source_root.special_rules = sr

        try:
            getattr(model, "mark_used_once_per_battle", lambda _k, **_kw: None)(
                ability_key,
                ability_name=ability_name,
            )
        except Exception:
            pass

        try:
            sname = str(getattr(model, "name", "Model") or "Model")
            uname = str(getattr(source_root, "name", "Unit") or "Unit")
            _log_action_for_players(game, player, f"{ability_name}: {sname} ({uname}) grants Fights First until end of phase.")
        except Exception:
            pass
        return None
    if ability == "charge_end_select_one_battleshock":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, payload.get("source_unit_id") or ctx.get("source_unit_id"))
        target_unit = resolve_unit(game, payload.get("target_unit_id") or ctx.get("target_unit_id"))
        if source_unit is None or target_unit is None:
            return None
        try:
            source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        except Exception:
            source_root = source_unit
        try:
            target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        except Exception:
            target_root = target_unit
        if source_root is None or target_root is None:
            return None
        ability_name = str(ctx.get("ability_name", "") or "Charge end Battle-shock").strip() or "Charge end Battle-shock"
        try:
            test_modifier = int(ctx.get("test_modifier", 0) or 0)
        except Exception:
            test_modifier = 0
        if test_modifier:
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            current = int(sr.get("battle_shock_test_modifier", 0) or 0)
            sr["battle_shock_test_modifier"] = int(current + test_modifier)
            reasons = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
            reasons.append(ability_name)
            sr["battle_shock_test_modifier_reasons"] = reasons
            target_root.special_rules = sr
        try:
            target_root.take_battle_shock_test(int(getattr(game, "turn", 0) or 1))
        except Exception:
            pass
        try:
            player = getattr(getattr(source_root, "get_parent_army", lambda: None)(), "player", None)
        except Exception:
            player = None
        try:
            _log_action_for_players(
                game,
                player,
                f"{ability_name}: {getattr(target_root, 'name', 'Unit')} takes a Battle-shock test.",
            )
        except Exception:
            pass
        return target_root
    if ability == "unearthly_power":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return None
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None:
            return None
        choice_key = str(payload.get("choice_key", "") or "").strip().upper()
        if not choice_key:
            return None
        try:
            from ...rules.thousand_sons_crimson_king import set_active_crimson_king
        except Exception:
            return None
        try:
            start_round = int(ctx.get("battle_round", 0) or getattr(game, "turn", 0) or 0)
        except Exception:
            start_round = int(getattr(game, "turn", 0) or 0)
        try:
            expires_round = int(ctx.get("expires_round", 0) or (start_round + 1))
        except Exception:
            expires_round = int(start_round + 1)
        player_id = str(ctx.get("player_id", "") or "")
        if not player_id:
            try:
                owner = getattr(source_root.get_parent_army(), "player", None)
            except Exception:
                owner = None
            player_id = str(getattr(owner, "id", "") or "")
        set_active_crimson_king(
            source_root,
            choice_key,
            start_round=int(start_round or 0),
            expires_round=int(expires_round or 0),
            player_id=player_id,
        )
        try:
            player = getattr(getattr(source_root, "get_parent_army", lambda: None)(), "player", None)
        except Exception:
            player = None
        ability_name = str(ctx.get("ability_name", "") or "Unearthly Power").strip() or "Unearthly Power"
        choice_name = str(payload.get("choice_name", "") or payload.get("label", "") or payload.get("summary", "") or choice_key).strip() or choice_key
        try:
            _log_action_for_players(
                game,
                player,
                f"{ability_name}: {getattr(source_root, 'name', 'Unit')} selected {choice_name}.",
            )
        except Exception:
            pass
        return None
    if ability == "voice_of_triarch":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        source_unit = resolve_unit(
            game,
            payload.get("source_unit_id")
            or ctx.get("source_unit_id")
            or payload.get("unit_id")
            or ctx.get("unit_id"),
        )
        if source_unit is None:
            return None
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None or not _resurrection_orb_unit_on_battlefield(source_root):
            return None
        from ...rules.necrons_voice_of_triarch import (
            VOICE_OF_TRIARCH_BY_KEY,
            set_active_voice_of_triarch,
            unit_has_voice_of_triarch_ability,
        )

        if not bool(unit_has_voice_of_triarch_ability(source_root)):
            return None

        battle_round = int(getattr(game, "turn", 0) or 0)
        try:
            start_round = int(ctx.get("battle_round", 0) or battle_round)
        except (TypeError, ValueError):
            start_round = int(battle_round)
        if start_round > 0 and battle_round != start_round:
            return None

        choice_key = str(payload.get("choice_key", "") or "").strip().upper()
        if not choice_key:
            return None
        allowed_keys = {str(val).strip().upper() for val in list(ctx.get("allowed_choice_keys", []) or []) if str(val).strip()}
        if allowed_keys and choice_key not in allowed_keys:
            return None
        if choice_key not in VOICE_OF_TRIARCH_BY_KEY:
            return None

        try:
            expires_round = int(ctx.get("expires_round", 0) or (start_round + 1))
        except (TypeError, ValueError):
            expires_round = int(start_round + 1)
        player_id = str(ctx.get("player_id", "") or "")
        if not player_id:
            owner = getattr(source_root.get_parent_army(), "player", None) if hasattr(source_root, "get_parent_army") else None
            player_id = str(getattr(owner, "id", "") or "")

        set_active_voice_of_triarch(
            source_root,
            choice_key,
            start_round=int(start_round or 0),
            expires_round=int(expires_round or 0),
            player_id=player_id,
        )

        option = VOICE_OF_TRIARCH_BY_KEY.get(choice_key)
        choice_name = str(
            payload.get("choice_name", "")
            or payload.get("label", "")
            or (getattr(option, "name", "") if option is not None else "")
            or choice_key
        ).strip() or choice_key

        ability_name = str(ctx.get("ability_name", "") or "Voice of the Triarch").strip() or "Voice of the Triarch"
        player = getattr(source_root.get_parent_army(), "player", None) if hasattr(source_root, "get_parent_army") else None
        _log_action_for_players(
            game,
            player,
            f"{ability_name}: {getattr(source_root, 'name', 'Unit')} selected {choice_name}.",
        )
        return {
            "source_unit_id": str(get_entity_id(source_root) or ""),
            "choice_key": str(choice_key),
            "choice_name": str(choice_name),
            "battle_round": int(start_round or 0),
        }
    if ability == "possessed_blade":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, payload.get("unit_id") or ctx.get("unit_id") or ctx.get("source_unit_id"))
        if source_unit is None:
            return None
        model = resolve_model(game, payload.get("model_id") or ctx.get("model_id"))
        if model is None or not bool(getattr(model, "is_alive", True)):
            return None
        sr = getattr(source_unit, "special_rules", None)
        if not isinstance(sr, dict) or not sr.get("enhancement_possessed_blade"):
            return None
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
        model_id = str(get_entity_id(model) or "")
        if bearer_id and model_id and bearer_id != model_id:
            return None
        weapon_name = str(payload.get("weapon_name") or ctx.get("weapon_name") or "").strip()
        if not weapon_name:
            return None

        melee_weapon_names: list[str] = []
        for wargear in list(getattr(model, "wargear", []) or []):
            if wargear is None:
                continue
            if not bool(getattr(wargear, "is_melee", lambda: False)()):
                continue
            name = str(getattr(wargear, "name", "") or "").strip()
            if name and name not in melee_weapon_names:
                melee_weapon_names.append(name)
        if not melee_weapon_names:
            return None
        melee_weapon_names.sort(key=lambda name: name.lower())

        selected_weapon = ""
        if hasattr(source_unit, "_weapon_name_matches"):
            for candidate in melee_weapon_names:
                if source_unit._weapon_name_matches([candidate], weapon_name):
                    selected_weapon = candidate
                    break
        else:
            normalized = str(weapon_name).strip().lower()
            for candidate in melee_weapon_names:
                if str(candidate).strip().lower() == normalized:
                    selected_weapon = candidate
                    break
        if not selected_weapon:
            return None

        sr["enhancement_possessed_blade_weapon_name"] = selected_weapon
        for key in (
            "enhancement_possessed_blade_fight_active",
            "enhancement_possessed_blade_fight_turn",
            "enhancement_possessed_blade_fight_owner",
            "enhancement_possessed_blade_fight_phase",
            "enhancement_possessed_blade_active_weapon_name",
            "enhancement_possessed_blade_active_model_id",
            "enhancement_possessed_blade_source",
        ):
            sr.pop(key, None)
        source_unit.special_rules = sr

        try:
            player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
        except Exception:
            player = None
        try:
            ability_name = str(ctx.get("ability_name", "") or "Possessed Blade").strip() or "Possessed Blade"
            _log_action_for_players(
                game,
                player,
                f"{ability_name}: {getattr(model, 'name', 'Model')} selected {selected_weapon}.",
            )
        except Exception:
            pass
        return None
    if ability == "risen_rubricae":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, payload.get("source_unit_id") or ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return None
        try:
            source_army = source_unit.get_parent_army()
        except Exception:
            source_army = None

        selected_vals = payload.get("selected_unit_ids")
        if not isinstance(selected_vals, list):
            selected_vals = []
        if not selected_vals:
            one_target = payload.get("target_unit_id") or payload.get("unit_id")
            if one_target:
                selected_vals = [one_target]

        selected_roots = []
        seen: set[str] = set()
        for val in list(selected_vals or []):
            unit = resolve_unit(game, val)
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
            except Exception:
                root = unit
            if root is None:
                continue
            if source_army is not None:
                try:
                    if root.get_parent_army() is not source_army:
                        continue
                except Exception:
                    continue
            root_id = str(get_entity_id(root) or "")
            if not root_id or root_id in seen:
                continue
            seen.add(root_id)
            selected_roots.append(root)

        def _is_rubricae(unit_obj) -> bool:
            has_any = getattr(unit_obj, "has_any_keyword", None)
            if callable(has_any):
                try:
                    return bool(has_any("RUBRICAE"))
                except Exception:
                    return False
            return False

        def _is_battleline(unit_obj) -> bool:
            fn = getattr(unit_obj, "is_battleline", None)
            if callable(fn):
                try:
                    return bool(fn())
                except Exception:
                    return False
            has_any = getattr(unit_obj, "has_any_keyword", None)
            if callable(has_any):
                try:
                    return bool(has_any("BATTLELINE"))
                except Exception:
                    return False
            return False

        valid = False
        if len(selected_roots) == 2:
            valid = all(_is_rubricae(unit_obj) and _is_battleline(unit_obj) for unit_obj in selected_roots)
        elif len(selected_roots) == 1:
            valid = _is_rubricae(selected_roots[0]) and (not _is_battleline(selected_roots[0]))
        if not valid:
            return None

        for root in selected_roots:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["risen_rubricae_infiltrators"] = True
            sr["risen_rubricae_source_unit_id"] = str(get_entity_id(source_unit) or "")
            root.special_rules = sr
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = []
            if not members:
                members = [root]
            for member in members:
                try:
                    invalidate = getattr(member, "_invalidate_ability_cache", None)
                    if callable(invalidate):
                        invalidate()
                except Exception:
                    continue

        source_sr = getattr(source_unit, "special_rules", None)
        if not isinstance(source_sr, dict):
            source_sr = {}
        source_sr["enhancement_risen_rubricae_used"] = True
        source_unit.special_rules = source_sr
        try:
            mark_used = getattr(source_unit, "mark_unit_once_per_battle_used", None)
            if callable(mark_used):
                mark_used("risen_rubricae", ability_name=str(ctx.get("ability_name", "") or "Risen Rubricae"))
        except Exception:
            pass

        try:
            player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
        except Exception:
            player = None
        try:
            names = ", ".join(str(getattr(unit_obj, "name", "Unit") or "Unit") for unit_obj in selected_roots)
            _log_action_for_players(
                game,
                player,
                f"Risen Rubricae: {getattr(source_unit, 'name', 'Unit')} selected {names}.",
            )
        except Exception:
            pass
        return None
    if ability == "ethereal_pathway":
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, payload.get("source_unit_id") or ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return None
        source_sr = getattr(source_unit, "special_rules", None)
        if not isinstance(source_sr, dict):
            source_sr = {}
        has_enhancement = bool(source_sr.get("enhancement_ethereal_pathway"))
        if not has_enhancement:
            enhancement = getattr(source_unit, "enhancement", None)
            enh_id = str(getattr(enhancement, "id", "") or "")
            enh_name = str(getattr(enhancement, "name", "") or "").strip().lower()
            has_enhancement = enh_id == "000009911003" or enh_name == "ethereal pathway"
        if not has_enhancement:
            return None
        try:
            source_army = source_unit.get_parent_army()
        except Exception:
            source_army = None

        selected_vals = payload.get("selected_unit_ids")
        if not isinstance(selected_vals, list):
            selected_vals = []
        if not selected_vals:
            one_target = payload.get("target_unit_id") or payload.get("unit_id")
            if one_target:
                selected_vals = [one_target]

        selected_roots = []
        seen: set[str] = set()
        for val in list(selected_vals or []):
            unit = resolve_unit(game, val)
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
            except Exception:
                root = unit
            if root is None:
                continue
            if source_army is not None:
                try:
                    if root.get_parent_army() is not source_army:
                        continue
                except Exception:
                    continue
            root_id = str(get_entity_id(root) or "")
            if not root_id or root_id in seen:
                continue
            seen.add(root_id)
            selected_roots.append(root)

        def _is_guardians(unit_obj) -> bool:
            has_any = getattr(unit_obj, "has_any_keyword", None)
            if callable(has_any):
                try:
                    if bool(has_any("GUARDIANS")) or bool(has_any("GUARDIAN")):
                        return True
                except Exception:
                    pass
            name = str(getattr(unit_obj, "name", "") or "").strip().lower()
            return "guardian" in name

        skipped = is_skip_choice(request, result)
        if not skipped:
            if len(selected_roots) > 2:
                return None
            if not all(_is_guardians(unit_obj) for unit_obj in selected_roots):
                return None

        if not skipped:
            for root in selected_roots:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["ethereal_pathway_infiltrators"] = True
                sr["ethereal_pathway_source_unit_id"] = str(get_entity_id(source_unit) or "")
                root.special_rules = sr
                try:
                    members = list(root.get_attached_unit_members() or [])
                except Exception:
                    members = []
                if not members:
                    members = [root]
                for member in members:
                    try:
                        invalidate = getattr(member, "_invalidate_ability_cache", None)
                        if callable(invalidate):
                            invalidate()
                    except Exception:
                        continue

        source_sr["enhancement_ethereal_pathway_used"] = True
        source_unit.special_rules = source_sr
        try:
            mark_used = getattr(source_unit, "mark_unit_once_per_battle_used", None)
            if callable(mark_used):
                mark_used("ethereal_pathway", ability_name=str(ctx.get("ability_name", "") or "Ethereal Pathway"))
        except Exception:
            pass

        try:
            player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
        except Exception:
            player = None
        try:
            if skipped or not selected_roots:
                _log_action_for_players(
                    game,
                    player,
                    f"Ethereal Pathway: {getattr(source_unit, 'name', 'Unit')} selected none.",
                )
            else:
                names = ", ".join(str(getattr(unit_obj, "name", "Unit") or "Unit") for unit_obj in selected_roots)
                _log_action_for_players(
                    game,
                    player,
                    f"Ethereal Pathway: {getattr(source_unit, 'name', 'Unit')} selected {names}.",
                )
        except Exception:
            pass
        return None
    if ability == "cankerblight":
        payload = _option_payload(request, result)
        target_val = payload.get("target_unit_id", payload.get("unit_id", ctx.get("target_unit_id")))
        target_unit = resolve_unit(game, target_val)
        if target_unit is None:
            return None
        sr = getattr(target_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        pending = sr.get("cankerblight_pending")
        ability_name = str(ctx.get("ability_name", "") or "Cankerblight").strip() or "Cankerblight"
        if is_skip_choice(request, result):
            if isinstance(pending, dict) and pending.get("apply_terror_if_skipped"):
                try:
                    from ...rules.shadow_of_chaos import ShadowOfChaosManager
                    ShadowOfChaosManager._apply_daemonic_terror(target_unit, game=game)
                except Exception:
                    pass
            sr.pop("cankerblight_pending", None)
            target_unit.special_rules = sr
            try:
                player = getattr(getattr(target_unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            try:
                _log_action_for_players(
                    game,
                    player,
                    f"{ability_name}: skipped on {getattr(target_unit, 'name', 'Unit')}.",
                )
            except Exception:
                pass
            return None

        sr.pop("cankerblight_pending", None)
        target_unit.special_rules = sr
        try:
            models = list(target_unit.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(target_unit, "models", []) or [])
        models = [m for m in models if getattr(m, "is_alive", True)]
        try:
            models.sort(key=lambda m: str(get_entity_id(m)))
        except Exception:
            pass
        if not models:
            return None
        if len(models) == 1:
            try:
                models[0].die(game_map=getattr(game, "map", None))
            except Exception:
                pass
            try:
                player = getattr(getattr(target_unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            try:
                _log_action_for_players(
                    game,
                    player,
                    f"{ability_name}: {getattr(target_unit, 'name', 'Unit')} loses {getattr(models[0], 'name', 'a model')}.",
                )
            except Exception:
                pass
            return None

        from ...engine.decision_kinds import DECISION_SELECT_TARGET_MODEL
        from ...engine.decisions import DecisionOption, DecisionRequest

        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_SELECT_TARGET_MODEL:
                    continue
                ctx_req = dict(getattr(req, "context", {}) or {})
                if str(ctx_req.get("selection_kind", "")) == "cankerblight_destroy" and str(ctx_req.get("target_unit_id", "")) == str(get_entity_id(target_unit)):
                    return None

        options = []
        for model in models:
            label = str(getattr(model, "name", "Model") or "Model")
            options.append(DecisionOption.create(label, payload={"model_id": get_entity_id(model)}))
        if not options:
            return None
        try:
            target_player = getattr(target_unit.get_parent_army(), "player", None)
        except Exception:
            target_player = None
        ctx_request = {
            "selection_kind": "cankerblight_destroy",
            "target_unit_id": get_entity_id(target_unit),
            "source_unit_id": ctx.get("source_unit_id"),
            "ability_name": ability_name,
        }
        req = DecisionRequest.create(
            DECISION_SELECT_TARGET_MODEL,
            f"{ability_name}: select a model to destroy.",
            player_id=getattr(target_player, "id", None),
            options=options,
            context=ctx_request,
        )
        if game is not None and hasattr(game, "request_decision"):
            game.request_decision(req)
        return None
    if ability == "curse_of_walking_pox":
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return None
        try:
            root = source_unit.get_attached_unit_root()
        except Exception:
            root = source_unit
        if root is None:
            return None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        try:
            pending = int(sr.get("curse_of_walking_pox_pending_kills", 0) or 0)
        except Exception:
            pending = 0
        if pending <= 0:
            return None

        if is_skip_choice(request, result):
            sr["curse_of_walking_pox_pending_kills"] = 0
            root.special_rules = sr
            return None

        try:
            requested_returns = int(payload.get("returns", payload.get("return_models", 0)) or 0)
        except Exception:
            requested_returns = 0
        if requested_returns <= 0:
            try:
                requested_returns = int(ctx.get("max_returns", 0) or 0)
            except Exception:
                requested_returns = 0
        requested_returns = max(0, min(int(requested_returns), int(pending)))

        destroyed = list(getattr(root, "models_lost", []) or [])
        poxwalker_destroyed = []
        for model in destroyed:
            if model is None:
                continue
            is_poxwalker = False
            try:
                is_poxwalker = bool(getattr(model, "has_any_keyword", lambda *_a, **_k: False)("POXWALKER"))
            except Exception:
                is_poxwalker = False
            if not is_poxwalker:
                try:
                    is_poxwalker = bool(getattr(model, "has_keyword", lambda *_a, **_k: False)("POXWALKER"))
                except Exception:
                    is_poxwalker = False
            if not is_poxwalker:
                continue
            poxwalker_destroyed.append(model)

        available = len(poxwalker_destroyed)
        returns = max(0, min(int(requested_returns), int(available)))
        returned = 0
        if returns > 0:
            try:
                returned = int(
                    root.return_destroyed_bodyguard_models(
                        int(returns),
                        game_map=getattr(game, "map", None),
                        chosen_models=list(poxwalker_destroyed[:returns]),
                        placement_source="curse_of_walking_pox",
                    )
                    or 0
                )
            except Exception:
                returned = 0
        sr["curse_of_walking_pox_pending_kills"] = 0
        root.special_rules = sr
        try:
            player = getattr(root.get_parent_army(), "player", None)
        except Exception:
            player = None
        ability_name = str(ctx.get("ability_name", "") or "Curse of the Walking Pox").strip() or "Curse of the Walking Pox"
        try:
            _log_action_for_players(
                game,
                player,
                f"{ability_name}: returned {int(returned)} Poxwalker model(s) to {getattr(root, 'name', 'Unit')}.",
            )
        except Exception:
            pass
        return None
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    unit_val = payload.get("target_unit_id", payload.get("unit_id", payload.get("unit")))
    chosen = resolve_unit(game, unit_val)
    if str(ctx.get("ability", "") or "") == "sublime_prescience":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None or chosen is None:
            return None
        try:
            if not bool(getattr(chosen, "is_in_strategic_reserves", lambda: False)()):
                return None
        except Exception:
            return None
        source_sr = getattr(source_unit, "special_rules", None)
        if not isinstance(source_sr, dict) or not source_sr.get("enhancement_sublime_prescience"):
            return None
        player = _resolve_player(game, request, payload)
        if player is None:
            try:
                player = source_unit.get_parent_army().player
            except Exception:
                player = None
        owner_id = str(ctx.get("turn_owner", "") or getattr(player, "id", "") or "")
        try:
            turn = int(ctx.get("turn", 0) or getattr(game, "turn", 0) or 0)
        except Exception:
            turn = int(getattr(game, "turn", 0) or 0)
        try:
            used_owner = str(source_sr.get("enhancement_sublime_prescience_turn_owner", "") or "")
            used_turn = int(source_sr.get("enhancement_sublime_prescience_turn", 0) or 0)
        except Exception:
            used_owner = ""
            used_turn = 0
        if used_turn and used_turn == int(turn or 0) and (not used_owner or not owner_id or used_owner == owner_id):
            return None
        try:
            round_bonus = int(source_sr.get("enhancement_sublime_prescience_round_bonus", 1) or 1)
        except Exception:
            round_bonus = 1
        if round_bonus <= 0:
            round_bonus = 1

        target_sr = getattr(chosen, "special_rules", None)
        if not isinstance(target_sr, dict):
            target_sr = {}
        target_sr["enhancement_sublime_prescience_active"] = True
        target_sr["enhancement_sublime_prescience_turn"] = int(turn or 0)
        target_sr["enhancement_sublime_prescience_round_bonus"] = int(round_bonus)
        target_sr["enhancement_sublime_prescience_expires_phase"] = "MOVEMENT_PHASE"
        target_sr["enhancement_sublime_prescience_source"] = str(ctx.get("ability_name", "") or "Sublime Prescience")
        target_sr["enhancement_sublime_prescience_source_unit_id"] = str(get_entity_id(source_unit) or "")
        if owner_id:
            target_sr["enhancement_sublime_prescience_turn_owner"] = owner_id
        chosen.special_rules = target_sr

        source_sr["enhancement_sublime_prescience_turn"] = int(turn or 0)
        if owner_id:
            source_sr["enhancement_sublime_prescience_turn_owner"] = owner_id
        source_unit.special_rules = source_sr
        try:
            _log_action_for_players(
                game,
                player,
                "Sublime Prescience: "
                f"{getattr(chosen, 'name', 'Transport')} treats the current battle round as +{int(round_bonus)} this phase for Strategic Reserves setup.",
            )
        except Exception:
            pass
        return None
    if str(ctx.get("ability", "") or "") == "accomplished_tactician":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        transport = resolve_unit(game, payload.get("transport_unit_id") or ctx.get("transport_unit_id"))
        passenger = chosen
        if source_unit is None or transport is None or passenger is None:
            return None
        source_sr = getattr(source_unit, "special_rules", None)
        if not isinstance(source_sr, dict) or not source_sr.get("enhancement_accomplished_tactician"):
            return None
        player = _resolve_player(game, request, payload)
        if player is None:
            try:
                player = source_unit.get_parent_army().player
            except Exception:
                player = None
        owner_id = str(ctx.get("turn_owner", "") or "")
        if not owner_id:
            try:
                owner_id = str(getattr(game.get_current_player(), "id", "") or "")
            except Exception:
                owner_id = ""
        try:
            turn = int(ctx.get("turn", 0) or getattr(game, "turn", 0) or 0)
        except Exception:
            turn = int(getattr(game, "turn", 0) or 0)
        try:
            used_owner = str(source_sr.get("enhancement_accomplished_tactician_turn_owner", "") or "")
            used_turn = int(source_sr.get("enhancement_accomplished_tactician_turn", 0) or 0)
        except Exception:
            used_owner = ""
            used_turn = 0
        if used_turn and used_turn == int(turn or 0) and (not used_owner or not owner_id or used_owner == owner_id):
            return None
        try:
            embark_range = int(ctx.get("embark_range", source_sr.get("enhancement_accomplished_tactician_embark_range", 6)) or 6)
        except Exception:
            embark_range = 6
        if embark_range <= 0:
            embark_range = 6
        ability_name = str(ctx.get("ability_name", "") or "Accomplished Tactician").strip() or "Accomplished Tactician"
        resolve_fn = getattr(game, "resolve_end_of_fight_embark", None)
        if not callable(resolve_fn):
            return None
        embarked = bool(
            resolve_fn(
                transport,
                passenger,
                {
                    "source": ability_name,
                    "range": int(embark_range),
                    "allow_existing_passengers": True,
                },
            )
        )
        if not embarked:
            return None
        source_sr["enhancement_accomplished_tactician_turn"] = int(turn or 0)
        if owner_id:
            source_sr["enhancement_accomplished_tactician_turn_owner"] = owner_id
        source_unit.special_rules = source_sr
        try:
            _log_action_for_players(
                game,
                player,
                f"{ability_name}: {getattr(passenger, 'name', 'Unit')} embarked in {getattr(transport, 'name', 'Transport')}.",
            )
        except Exception:
            pass
        return None
    if str(ctx.get("ability", "") or "") == "monarch_of_the_hunt":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            ids = set()
            try:
                members = list(chosen.get_attached_unit_members() or [])
            except Exception:
                members = [chosen]
            for m in members:
                try:
                    mid = getattr(m, "_id", None)
                    if mid:
                        ids.add(mid)
                except Exception:
                    continue
            setattr(source_unit, "_monarch_of_the_hunt_quarry_ids", ids)
            try:
                setattr(source_unit, "_monarch_of_the_hunt_quarry_name", str(getattr(chosen, "name", "")))
            except Exception:
                pass
            try:
                player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            try:
                sname = str(getattr(source_unit, "name", "Model") or "Model")
                tname = str(getattr(chosen, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"Monarch of the Hunt: {sname} selected {tname} as quarry.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "methodical_destruction":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            ids = set()
            try:
                members = list(chosen.get_attached_unit_members() or [])
            except Exception:
                members = [chosen]
            for m in members:
                try:
                    mid = getattr(m, "_id", None)
                    if mid:
                        ids.add(mid)
                except Exception:
                    continue
            setattr(source_unit, "_methodical_destruction_victim_ids", ids)
            try:
                setattr(source_unit, "_methodical_destruction_victim_name", str(getattr(chosen, "name", "")))
            except Exception:
                pass
            ability_name = str(ctx.get("ability_name", "") or "Methodical Destruction").strip() or "Methodical Destruction"
            try:
                player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            try:
                sname = str(getattr(source_unit, "name", "Model") or "Model")
                tname = str(getattr(chosen, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {sname} selected {tname} as victim.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "exemplar_of_the_code":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            ids = set()
            try:
                members = list(chosen.get_attached_unit_members() or [])
            except Exception:
                members = [chosen]
            for m in members:
                try:
                    mid = getattr(m, "_id", None)
                    if mid:
                        ids.add(mid)
                except Exception:
                    continue
            setattr(source_unit, "_exemplar_of_the_code_quarry_ids", ids)
            try:
                setattr(source_unit, "_exemplar_of_the_code_quarry_name", str(getattr(chosen, "name", "")))
            except Exception:
                pass
            try:
                setattr(source_unit, "_bondsman_quarry_name", str(getattr(chosen, "name", "")))
            except Exception:
                pass
            ability_name = str(ctx.get("ability_name", "") or "Exemplar of the Code").strip() or "Exemplar of the Code"
            try:
                setattr(source_unit, "_exemplar_of_the_code_source", ability_name)
            except Exception:
                pass
            try:
                player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            try:
                sname = str(getattr(source_unit, "name", "Model") or "Model")
                tname = str(getattr(chosen, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {sname} selected {tname} as quarry.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "prey_selection":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            ids = set()
            try:
                members = list(chosen.get_attached_unit_members() or [])
            except Exception:
                members = [chosen]
            for m in members:
                try:
                    mid = getattr(m, "_id", None)
                    if mid:
                        ids.add(mid)
                except Exception:
                    continue
            setattr(source_unit, "_prey_selection_prey_ids", ids)
            try:
                setattr(source_unit, "_prey_selection_prey_name", str(getattr(chosen, "name", "")))
            except Exception:
                pass
            try:
                setattr(source_unit, "_prey_selection_reroll_hit", bool(ctx.get("prey_reroll_hit", False)))
                setattr(source_unit, "_prey_selection_reroll_wound", bool(ctx.get("prey_reroll_wound", False)))
                setattr(source_unit, "_prey_selection_melee_only", bool(ctx.get("prey_melee_only", False)))
                keyword = str(ctx.get("prey_keyword", "") or "").strip().upper()
                if keyword:
                    setattr(source_unit, "_prey_selection_keyword", keyword)
            except Exception:
                pass
            ability_name = str(ctx.get("ability_name", "") or "Prey selection").strip() or "Prey selection"
            try:
                setattr(source_unit, "_prey_selection_source", ability_name)
            except Exception:
                pass
            try:
                player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            try:
                sname = str(getattr(source_unit, "name", "Model") or "Model")
                tname = str(getattr(chosen, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {sname} selected {tname} as prey.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "movement_phase_visible_wound_bonus":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            try:
                player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            keyword = str(ctx.get("keyword", "") or "").strip()
            try:
                bonus = int(ctx.get("bonus", 0) or 0)
            except Exception:
                bonus = 0
            source = str(ctx.get("ability_name", "") or ctx.get("ability", "") or "Movement phase wound bonus").strip()
            model_id = ctx.get("model_id")
            apply_fn = getattr(chosen, "apply_movement_phase_visible_wound_bonus", None)
            if callable(apply_fn):
                apply_fn(
                    owner_id=owner_id,
                    turn=turn,
                    source=source,
                    keyword=keyword,
                    bonus=bonus,
                    source_model_id=model_id,
                )
            else:
                sr = getattr(chosen, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["movement_phase_visible_wound_bonus_active"] = True
                sr["movement_phase_visible_wound_bonus_owner"] = owner_id
                sr["movement_phase_visible_wound_bonus_turn"] = int(turn or 0)
                sr["movement_phase_visible_wound_bonus_source"] = source
                sr["movement_phase_visible_wound_bonus_keyword"] = keyword
                sr["movement_phase_visible_wound_bonus_value"] = int(bonus or 0)
                if model_id:
                    sr["movement_phase_visible_wound_bonus_model_id"] = str(model_id)
                chosen.special_rules = sr
            try:
                sname = str(getattr(source_unit, "name", "Model") or "Model")
                tname = str(getattr(chosen, "name", "Unit") or "Unit")
                _log_action_for_players(
                    game,
                    player,
                    f"{source}: {sname} selected {tname} (wound +{int(bonus)}).",
                )
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "movement_phase_visible_hit_bonus":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            try:
                player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            keyword = str(ctx.get("keyword", "") or "").strip()
            try:
                bonus = int(ctx.get("bonus", 0) or 0)
            except Exception:
                bonus = 0
            source = str(ctx.get("ability_name", "") or ctx.get("ability", "") or "Movement phase hit bonus").strip()
            model_id = ctx.get("model_id")
            apply_fn = getattr(chosen, "apply_movement_phase_visible_hit_bonus", None)
            if callable(apply_fn):
                apply_fn(
                    owner_id=owner_id,
                    turn=turn,
                    source=source,
                    keyword=keyword,
                    bonus=bonus,
                    source_model_id=model_id,
                )
            else:
                sr = getattr(chosen, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["movement_phase_visible_hit_bonus_active"] = True
                sr["movement_phase_visible_hit_bonus_owner"] = owner_id
                sr["movement_phase_visible_hit_bonus_turn"] = int(turn or 0)
                sr["movement_phase_visible_hit_bonus_source"] = source
                sr["movement_phase_visible_hit_bonus_keyword"] = keyword
                sr["movement_phase_visible_hit_bonus_value"] = int(bonus or 0)
                if model_id:
                    sr["movement_phase_visible_hit_bonus_model_id"] = str(model_id)
                chosen.special_rules = sr
            try:
                sname = str(getattr(source_unit, "name", "Model") or "Model")
                tname = str(getattr(chosen, "name", "Unit") or "Unit")
                _log_action_for_players(
                    game,
                    player,
                    f"{source}: {sname} selected {tname} (hit +{int(bonus)}).",
                )
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "fight_phase_target_attack_bonus":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            try:
                player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Fight phase target bonus").strip() or "Fight phase target bonus"
            keyword = str(ctx.get("keyword", "") or "").strip()
            attack_type = str(ctx.get("attack_type", "") or "any").strip().lower() or "any"
            try:
                s_bonus = int(ctx.get("strength_bonus", 0) or 0)
            except Exception:
                s_bonus = 0
            try:
                ap_bonus = int(ctx.get("ap_bonus", 0) or 0)
            except Exception:
                ap_bonus = 0
            try:
                d_bonus = int(ctx.get("damage_bonus", 0) or 0)
            except Exception:
                d_bonus = 0
            try:
                w_bonus = int(ctx.get("wound_bonus", 0) or 0)
            except Exception:
                w_bonus = 0
            try:
                enemy_penalty = int(ctx.get("enemy_melee_wound_penalty", 0) or 0)
            except Exception:
                enemy_penalty = 0
            model_id = ctx.get("model_id")
            apply_fn = getattr(target_root, "apply_fight_phase_target_attack_bonus", None)
            if callable(apply_fn):
                apply_fn(
                    owner_id=owner_id,
                    turn=turn,
                    source=ability_name,
                    keyword=keyword,
                    attack_type=attack_type,
                    strength_bonus=int(s_bonus),
                    ap_bonus=int(ap_bonus),
                    damage_bonus=int(d_bonus),
                    wound_bonus=int(w_bonus),
                    source_model_id=model_id,
                )
            if enemy_penalty:
                try:
                    apply_penalty = getattr(target_root, "apply_fight_phase_melee_wound_penalty", None)
                    if callable(apply_penalty):
                        apply_penalty(
                            owner_id=owner_id,
                            turn=turn,
                            source=ability_name,
                            penalty=int(enemy_penalty),
                        )
                except Exception:
                    pass
            try:
                sname = str(getattr(source_unit, "name", "Model") or "Model")
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {sname} selected {tname}.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "malign_sacrifice":
        if chosen is None:
            return None
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return None
        model_id = payload.get("model_id") or ctx.get("model_id")
        if not model_id:
            return None
        ctx_spec = dict(ctx.get("spec", {}) or {})
        try:
            player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
        except Exception:
            player = None
        ability_name = str(ctx.get("ability_name", "") or "Malign Sacrifice").strip() or "Malign Sacrifice"
        roll_spec = {
            "dice_count": 1,
            "faces": 6,
            "reason": f"{ability_name}: roll for mortal wounds",
            "roll_type": "malign_sacrifice",
            "handler_key": "malign_sacrifice",
            "source_unit_id": get_entity_id(source_unit),
            "target_unit_id": get_entity_id(chosen),
            "model_id": model_id,
            "ability_name": ability_name,
            "roll_bonus_vs_vehicle": int(ctx_spec.get("roll_bonus_vs_vehicle", 0) or 0),
            "roll_low_min": int(ctx_spec.get("roll_low_min", 2) or 2),
            "roll_low_max": int(ctx_spec.get("roll_low_max", 5) or 5),
            "roll_low_mortal": str(ctx_spec.get("roll_low_mortal", "1") or "1"),
            "roll_high_threshold": int(ctx_spec.get("roll_high_threshold", 6) or 6),
            "roll_high_mortal": str(ctx_spec.get("roll_high_mortal", "d3") or "d3"),
            "destroy_selected_model": bool(ctx_spec.get("destroy_selected_model", True)),
        }
        try:
            if hasattr(game, "request_dice_roll"):
                game.request_dice_roll(
                    player_id=getattr(player, "id", None),
                    spec=roll_spec,
                    prompt=roll_spec["reason"],
                )
        except Exception:
            pass
        try:
            sname = str(getattr(source_unit, "name", "Unit") or "Unit")
            tname = str(getattr(chosen, "name", "Unit") or "Unit")
            _log_action_for_players(game, player, f"{ability_name}: {sname} selected {tname}.")
        except Exception:
            pass
    if str(ctx.get("ability", "") or "") == "symphony_of_pain":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            try:
                player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            keywords = list(ctx.get("keywords", []) or [])
            ability_name = str(ctx.get("ability_name", "") or "Symphony of Pain").strip() or "Symphony of Pain"
            sr = getattr(chosen, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["symphony_of_pain_active"] = True
            sr["symphony_of_pain_owner"] = owner_id
            sr["symphony_of_pain_turn"] = int(turn or 0)
            sr["symphony_of_pain_source"] = ability_name
            sr["symphony_of_pain_keywords"] = list(keywords or [])
            chosen.special_rules = sr
            try:
                sname = str(getattr(source_unit, "name", "Model") or "Model")
                tname = str(getattr(chosen, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {sname} selected {tname}.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "death_hex":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        target_val = payload.get("target_unit_id") or ctx.get("target_unit_id")
        target_unit = resolve_unit(game, target_val)
        if target_unit is None:
            return None
        model_id = payload.get("model_id") or ctx.get("model_id")
        model = resolve_model(game, model_id)
        source_unit = resolve_unit(game, payload.get("source_unit_id") or ctx.get("source_unit_id"))
        if source_unit is None and model is not None:
            source_unit = getattr(model, "parent_unit", None)
        if source_unit is None:
            return None
        player = _resolve_player(game, request, payload)
        if player is None:
            try:
                player = source_unit.get_parent_army().player
            except Exception:
                player = None
        ability_name = str(ctx.get("ability_name", "") or "Death Hex").strip() or "Death Hex"
        ability_key = str(ctx.get("ability_key", "") or "DEATH_HEX").strip().upper()
        if player is not None:
            try:
                mark_fn = getattr(player, "_mark_ability_used_turn", None)
                if callable(mark_fn):
                    mark_fn(ability_key)
            except Exception:
                pass
        try:
            from ...utility.dice import get_roll
            from ...utility.event_bus import append_dice
        except Exception:
            get_roll = None
            append_dice = None
        roll = int(get_roll("D6") or 0) if callable(get_roll) else 0
        if callable(append_dice) and player is not None:
            append_dice(player, f"{ability_name} roll: {roll}")
        if roll <= 1:
            mortal = int(get_roll("D3") or 0) if callable(get_roll) else 0
            if callable(append_dice) and player is not None:
                append_dice(player, f"{ability_name} mortal wounds: {mortal}")
            if mortal > 0 and source_unit is not None:
                try:
                    source_unit._apply_mortal_wounds_to_unit(
                        source_unit,
                        int(mortal),
                        game_map=getattr(game, "map", None),
                        is_psychic_attack=True,
                    )
                except Exception:
                    pass
            try:
                sname = str(getattr(source_unit, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {sname} suffers {int(mortal)} mortal wounds.")
            except Exception:
                pass
            return target_unit
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["death_hex_active"] = True
        sr["death_hex_owner"] = str(getattr(player, "id", "") or "")
        try:
            sr["death_hex_turn"] = int(getattr(game, "turn", 0) or 0)
        except Exception:
            sr["death_hex_turn"] = 0
        sr["death_hex_source"] = ability_name
        try:
            sr["death_hex_ap_bonus"] = int(ctx.get("ap_bonus", 1) or 1)
        except Exception:
            sr["death_hex_ap_bonus"] = 1
        target_root.special_rules = sr
        try:
            tname = str(getattr(target_root, "name", "Unit") or "Unit")
            _log_action_for_players(game, player, f"{ability_name}: {tname} marked for AP -1.")
        except Exception:
            pass
    if str(ctx.get("ability", "") or "") == "spirit_thief":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        target_val = payload.get("target_unit_id") or ctx.get("target_unit_id")
        target_unit = resolve_unit(game, target_val)
        if target_unit is None:
            return None
        model_id = payload.get("model_id") or ctx.get("model_id")
        model = resolve_model(game, model_id)
        source_unit = resolve_unit(game, payload.get("source_unit_id") or ctx.get("source_unit_id"))
        if source_unit is None and model is not None:
            source_unit = getattr(model, "parent_unit", None)
        if source_unit is None:
            return None
        player = _resolve_player(game, request, payload)
        if player is None:
            try:
                player = source_unit.get_parent_army().player
            except Exception:
                player = None
        ability_name = str(ctx.get("ability_name", "") or "Spirit Thief").strip() or "Spirit Thief"
        keyword = str(ctx.get("keyword", "") or "heretic astartes").strip().lower() or "heretic astartes"
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["spirit_thief_active"] = True
        sr["spirit_thief_owner"] = str(getattr(player, "id", "") or "")
        try:
            sr["spirit_thief_turn"] = int(getattr(game, "turn", 0) or 0)
        except Exception:
            sr["spirit_thief_turn"] = 0
        sr["spirit_thief_source"] = ability_name
        sr["spirit_thief_keyword"] = keyword
        sr["spirit_thief_expires_phase"] = "SHOOTING_PHASE"
        target_root.special_rules = sr
        try:
            tname = str(getattr(target_root, "name", "Unit") or "Unit")
            _log_action_for_players(game, player, f"{ability_name}: {tname} marked for wound re-rolls of 1.")
        except Exception:
            pass
    if str(ctx.get("ability", "") or "") == "corrupt_machine_spirits":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        target_val = payload.get("target_unit_id") or ctx.get("target_unit_id")
        target_unit = resolve_unit(game, target_val)
        if target_unit is None:
            return None
        model_id = payload.get("model_id") or ctx.get("model_id")
        model = resolve_model(game, model_id)
        source_unit = resolve_unit(game, payload.get("source_unit_id") or ctx.get("source_unit_id"))
        if source_unit is None and model is not None:
            source_unit = getattr(model, "parent_unit", None)
        if source_unit is None:
            return None
        player = _resolve_player(game, request, payload)
        if player is None:
            try:
                player = source_unit.get_parent_army().player
            except Exception:
                player = None
        ability_name = str(ctx.get("ability_name", "") or "Corrupt Machine Spirits").strip() or "Corrupt Machine Spirits"
        try:
            from ...utility.dice import get_roll
            from ...utility.event_bus import append_dice
        except Exception:
            get_roll = None
            append_dice = None
        roll_mode = str(ctx.get("roll_mode", "") or "table_2_3_d3_4_5_3_6_d3plus3").strip().lower()
        roll = int(get_roll("D6") or 0) if callable(get_roll) else 0
        if callable(append_dice) and player is not None:
            append_dice(player, f"{ability_name} roll: {roll}")

        def _resolve_mortal_token(token: str) -> int:
            tok = str(token or "").strip().lower()
            if not tok:
                return 0
            if tok == "d3":
                return int(get_roll("D3") or 0) if callable(get_roll) else 0
            if tok == "d6":
                return int(get_roll("D6") or 0) if callable(get_roll) else 0
            try:
                return int(tok)
            except Exception:
                return 0

        mortal = 0
        if roll_mode == "single_threshold":
            try:
                threshold = int(ctx.get("threshold", 2) or 2)
            except Exception:
                threshold = 2
            mw_token = str(ctx.get("mortal_on_success", "") or "d3")
            if roll >= int(threshold):
                mortal = int(_resolve_mortal_token(mw_token))
        else:
            if 2 <= roll <= 3:
                mortal = int(get_roll("D3") or 0) if callable(get_roll) else 0
            elif 4 <= roll <= 5:
                mortal = 3
            elif roll >= 6:
                d3 = int(get_roll("D3") or 0) if callable(get_roll) else 0
                mortal = int(d3 + 3)
        if mortal > 0:
            try:
                source_unit._apply_mortal_wounds_to_unit(
                    target_unit,
                    int(mortal),
                    game_map=getattr(game, "map", None),
                )
            except Exception:
                pass
        if mortal > 0 and bool(ctx.get("heal_self_on_success", False)):
            heal_target = model
            if heal_target is None:
                try:
                    alive = [m for m in list(getattr(source_unit, "models", []) or []) if getattr(m, "is_alive", True)]
                except Exception:
                    alive = []
                heal_target = alive[0] if alive else None
            if heal_target is not None:
                try:
                    base_wounds = int(getattr(heal_target, "_base_wounds", getattr(heal_target, "base_wounds", 0)) or 0)
                    current_wounds = int(getattr(heal_target, "wounds", 0) or 0)
                    if base_wounds > 0 and current_wounds < base_wounds:
                        healed = min(int(mortal), int(base_wounds - current_wounds))
                        heal_target.wounds = int(current_wounds + healed)
                        if hasattr(heal_target, "_check_damaged_profile"):
                            heal_target._check_damaged_profile()
                        if callable(append_dice) and player is not None and healed > 0:
                            append_dice(player, f"{ability_name}: {getattr(heal_target, 'name', 'Model')} regains {int(healed)} wound(s).")
                except Exception:
                    pass
        try:
            tname = str(getattr(target_unit, "name", "Unit") or "Unit")
            _log_action_for_players(game, player, f"{ability_name}: {tname} suffers {int(mortal)} mortal wounds.")
        except Exception:
            pass
    if str(ctx.get("ability", "") or "") == "enrage_machine_spirits":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        target_val = payload.get("target_unit_id") or payload.get("unit_id") or ctx.get("target_unit_id")
        target_unit = resolve_unit(game, target_val)
        if target_unit is None:
            return None
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        player = _resolve_player(game, request, payload)
        if player is None and source_unit is not None:
            try:
                player = source_unit.get_parent_army().player
            except Exception:
                player = None
        ability_name = str(ctx.get("ability_name", "") or "Enrage Machine Spirits").strip() or "Enrage Machine Spirits"
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn = 0
        try:
            target_unit.take_battle_shock_test(turn)
        except Exception:
            pass
        try:
            tname = str(getattr(target_unit, "name", "Unit") or "Unit")
            _log_action_for_players(game, player, f"{ability_name}: {tname} takes a Battle-shock test.")
        except Exception:
            pass
    if str(ctx.get("ability", "") or "") == "move_over_battleshock":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        target_val = payload.get("target_unit_id") or payload.get("unit_id") or ctx.get("target_unit_id")
        target_unit = resolve_unit(game, target_val)
        if target_unit is None:
            return None
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        player = _resolve_player(game, request, payload)
        if player is None and source_unit is not None:
            try:
                player = source_unit.get_parent_army().player
            except Exception:
                player = None
        ability_name = str(ctx.get("ability_name", "") or "Move-over Battle-shock").strip() or "Move-over Battle-shock"
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn = 0
        try:
            target_unit.take_battle_shock_test(turn)
        except Exception:
            pass
        try:
            sname = str(getattr(source_unit, "name", "Model") or "Model")
            tname = str(getattr(target_unit, "name", "Unit") or "Unit")
            _log_action_for_players(game, player, f"{ability_name}: {sname} selected {tname} to take a Battle-shock test.")
        except Exception:
            pass
    if str(ctx.get("ability", "") or "") == "master_of_mechanisms":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        target_val = payload.get("target_unit_id") or payload.get("unit_id") or ctx.get("target_unit_id")
        target_unit = resolve_unit(game, target_val)
        if target_unit is None:
            return None
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return None
        player = _resolve_player(game, request, payload)
        if player is None:
            source_army = source_unit.get_parent_army()
            player = getattr(source_army, "player", None) if source_army is not None else None
        ability_name = str(ctx.get("ability_name", "") or "Master of Mechanisms").strip() or "Master of Mechanisms"
        from ...utility.dice import get_roll
        from ...utility.event_bus import append_dice
        heal_roll = str(ctx.get("heal_roll", "") or "").strip().upper()
        try:
            heal_flat = int(ctx.get("heal_flat", 0) or 0)
        except Exception:
            heal_flat = 0
        if heal_roll:
            heal = int(get_roll(heal_roll) or 0)
        else:
            heal = int(heal_flat or 0)
        if player is not None:
            append_dice(player, f"{ability_name} roll: {heal}")
        try:
            hit_bonus = int(ctx.get("hit_bonus", 1) or 1)
        except Exception:
            hit_bonus = 1
        if hit_bonus <= 0:
            hit_bonus = 1
        get_target_root = getattr(target_unit, "get_attached_unit_root", None)
        target_root = get_target_root() if callable(get_target_root) else target_unit
        get_models = getattr(target_root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(target_root, "models", []) or [])
        wounded = []
        for m in models:
            alive_attr = getattr(m, "is_alive", True)
            is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not is_alive:
                continue
            base = getattr(m, "_base_wounds", getattr(m, "wounds", 0))
            if int(getattr(m, "wounds", 0) or 0) < int(base or 0):
                wounded.append(m)
        if wounded and heal > 0:
            try:
                wounded.sort(key=lambda m: str(getattr(m, "id", getattr(m, "_id", "")) or ""))
            except Exception:
                wounded = list(wounded)
            target_model = wounded[0]
            heal_fn = getattr(target_model, "heal", None)
            if callable(heal_fn):
                heal_fn(int(heal))
        tsr = getattr(target_root, "special_rules", None)
        if not isinstance(tsr, dict):
            tsr = {}
        owner_id = str(getattr(player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        tsr["master_of_mechanisms_selected_turn_owner"] = owner_id
        tsr["master_of_mechanisms_selected_turn"] = int(turn or 0)
        tsr["master_of_mechanisms_hit_bonus_active"] = True
        tsr["master_of_mechanisms_hit_bonus"] = int(hit_bonus)
        tsr["master_of_mechanisms_hit_bonus_owner"] = owner_id
        tsr["master_of_mechanisms_source"] = ability_name
        target_root.special_rules = tsr
        tname = str(getattr(target_root, "name", "Unit") or "Unit")
        _log_action_for_players(
            game,
            player,
            f"{ability_name}: {tname} regains up to {int(heal)} wounds and gets +{int(hit_bonus)} to hit until next Command phase.",
        )
        return target_root
    if str(ctx.get("ability", "") or "") == "forgewrought_expertise":
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        target_unit = resolve_unit(game, payload.get("target_unit_id") or payload.get("unit_id") or ctx.get("target_unit_id"))
        if source_unit is None:
            return None
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None:
            return None
        player = _resolve_player(game, request, payload)
        if player is None:
            source_army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
            player = getattr(source_army, "player", None) if source_army is not None else None
        owner_id = str(getattr(player, "id", "") or str(ctx.get("turn_owner", "") or ""))
        try:
            turn = int(ctx.get("turn", 0) or getattr(game, "turn", 0) or 0)
        except Exception:
            turn = int(getattr(game, "turn", 0) or 0)
        if is_skip_choice(request, result):
            return None
        if target_unit is None:
            return None
        target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        if target_root is None:
            return None
        ability_name = str(ctx.get("ability_name", "") or "Forgewrought Expertise").strip() or "Forgewrought Expertise"
        assistant_model_name = str(ctx.get("assistant_model_name", "") or "Ironkin Assistant").strip() or "Ironkin Assistant"
        try:
            assistant_heal_flat = int(ctx.get("assistant_heal_flat", 3) or 3)
        except Exception:
            assistant_heal_flat = 3
        heal_roll = str(ctx.get("heal_roll", "") or "D3").strip().upper() or "D3"
        has_assistant = False
        try:
            source_models = (
                list(source_root.get_attached_unit_models() or [])
                if hasattr(source_root, "get_attached_unit_models")
                else list(getattr(source_root, "models", []) or [])
            )
            for model in list(source_models or []):
                alive_attr = getattr(model, "is_alive", True)
                alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                if not alive:
                    continue
                model_name = str(getattr(model, "name", "") or "").strip().lower()
                if assistant_model_name.lower() in model_name:
                    has_assistant = True
                    break
        except Exception:
            has_assistant = False

        heal = 0
        if has_assistant and assistant_heal_flat > 0:
            heal = int(assistant_heal_flat)
        else:
            try:
                from ...utility.dice import get_roll
                heal = int(get_roll(heal_roll) or 0)
            except Exception:
                heal = 0
            try:
                from ...utility.event_bus import append_dice
                if player is not None:
                    append_dice(player, f"{ability_name} roll: {int(heal)}")
            except Exception:
                pass

        tsr = getattr(target_root, "special_rules", None)
        if not isinstance(tsr, dict):
            tsr = {}
        tsr["forgewrought_expertise_repaired_turn_owner"] = owner_id
        tsr["forgewrought_expertise_repaired_turn"] = int(turn or 0)
        tsr["forgewrought_expertise_repaired_source"] = ability_name
        target_root.special_rules = tsr

        if heal > 0:
            try:
                models = (
                    list(target_root.get_attached_unit_models() or [])
                    if hasattr(target_root, "get_attached_unit_models")
                    else list(getattr(target_root, "models", []) or [])
                )
            except Exception:
                models = list(getattr(target_root, "models", []) or [])
            wounded = []
            for m in models:
                alive_attr = getattr(m, "is_alive", True)
                is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                if not is_alive:
                    continue
                base = getattr(m, "_base_wounds", getattr(m, "wounds", 0))
                if int(getattr(m, "wounds", 0) or 0) < int(base or 0):
                    wounded.append(m)
            if wounded:
                try:
                    wounded.sort(key=lambda m: str(getattr(m, "id", getattr(m, "_id", "")) or ""))
                except Exception:
                    wounded = list(wounded)
                target_model = wounded[0]
                heal_fn = getattr(target_model, "heal", None)
                if callable(heal_fn):
                    heal_fn(int(heal))
        try:
            tname = str(getattr(target_root, "name", "Unit") or "Unit")
            _log_action_for_players(
                game,
                player,
                f"{ability_name}: {tname} regains up to {int(heal)} wounds.",
            )
        except Exception:
            pass
        return target_root
    if str(ctx.get("ability", "") or "") == "computational_mastermind":
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return None
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None:
            return None
        player = _resolve_player(game, request, payload)
        if player is None:
            source_army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
            player = getattr(source_army, "player", None) if source_army is not None else None
        army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
        pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
        if pe is None:
            return None
        action = str(payload.get("action", "") or "").strip().lower()
        if action in ("none", "skip"):
            return None
        try:
            amount = int(payload.get("amount", 1) or 1)
        except Exception:
            amount = 1
        amount = max(0, amount)
        if amount <= 0:
            return None
        delta = 0
        if action == "gain":
            delta = int(getattr(pe, "add_yield_points", lambda _a, game=None: 0)(int(amount), game=game) or 0)
        elif action == "spend":
            spent = bool(getattr(pe, "spend_yield_points", lambda _a: False)(int(amount)))
            delta = -int(amount) if spent else 0
        else:
            return None
        if not delta:
            return None
        event_system = getattr(game, "event_system", None)
        if event_system is not None:
            event_system.publish(
                "prioritised_efficiency_updated",
                player=player,
                game=game,
                delta=int(delta or 0),
                mode=getattr(pe, "mode", None),
                yield_points=int(getattr(pe, "yield_points", 0) or 0),
                reason="Computational Mastermind",
            )
        try:
            objective_id = str(ctx.get("objective_id", "") or "")
            objective_label = objective_id if objective_id else f"objective {int(ctx.get('objective_index', 0) or 0) + 1}"
            if int(delta or 0) > 0:
                _log_action_for_players(game, player, f"Computational Mastermind: gained {int(delta)} YP at {objective_label}.")
            else:
                _log_action_for_players(game, player, f"Computational Mastermind: spent {int(abs(delta))} YP at {objective_label}.")
        except Exception:
            pass
        return int(delta)
    if str(ctx.get("ability", "") or "") == "resource_transmutation_gain":
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return None
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None:
            return None
        player = _resolve_player(game, request, payload)
        if player is None:
            source_army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
            player = getattr(source_army, "player", None) if source_army is not None else None
        owner_id = str(ctx.get("turn_owner", "") or getattr(player, "id", "") or "")
        try:
            turn = int(ctx.get("turn", 0) or getattr(game, "turn", 0) or 0)
        except Exception:
            turn = int(getattr(game, "turn", 0) or 0)

        sr = getattr(source_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["resource_transmutation_gain_resolved_turn_owner"] = owner_id
        sr["resource_transmutation_gain_resolved_turn"] = int(turn or 0)
        source_root.special_rules = sr

        if is_skip_choice(request, result):
            return None
        action = str(payload.get("action", "") or "").strip().lower()
        if action != "gain":
            return None
        try:
            gain_yp = int(payload.get("gain_yp", payload.get("amount", 0)) or 0)
        except Exception:
            gain_yp = 0
        gain_yp = max(0, min(2, int(gain_yp or 0)))
        if gain_yp <= 0:
            return None
        army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
        pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
        if pe is None:
            return None
        delta = int(getattr(pe, "add_yield_points", lambda _a, game=None: 0)(int(gain_yp), game=game) or 0)
        if not delta:
            return None
        event_system = getattr(game, "event_system", None)
        if event_system is not None:
            event_system.publish(
                "prioritised_efficiency_updated",
                player=player,
                game=game,
                delta=int(delta or 0),
                mode=getattr(pe, "mode", None),
                yield_points=int(getattr(pe, "yield_points", 0) or 0),
                reason="Resource Transmutation",
            )
        try:
            ability_name = str(ctx.get("ability_name", "") or "Resource Transmutation").strip() or "Resource Transmutation"
            _log_action_for_players(game, player, f"{ability_name}: gained {int(delta)} YP.")
        except Exception:
            pass
        return int(delta)
    if str(ctx.get("ability", "") or "") == "iron_ambassador":
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return None
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None:
            return None
        sr = getattr(source_root, "special_rules", None)
        if not isinstance(sr, dict) or not sr.get("enhancement_iron_ambassador"):
            return None
        used_once = getattr(source_root, "has_used_unit_once_per_battle", None)
        if callable(used_once) and bool(used_once("iron_ambassador")):
            return None
        if is_skip_choice(request, result):
            return None
        action = str(payload.get("action", "") or "").strip().lower()
        if action not in ("spend", "use"):
            return None
        try:
            spend_yp = int(payload.get("spend_yp", payload.get("amount", 0)) or 0)
        except Exception:
            spend_yp = 0
        spend_yp = max(0, min(3, int(spend_yp or 0)))
        if spend_yp <= 0:
            return None
        player = _resolve_player(game, request, payload)
        if player is None:
            source_army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
            player = getattr(source_army, "player", None) if source_army is not None else None
        if player is None:
            return None
        army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
        pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
        if pe is None:
            return None
        if not bool(getattr(pe, "spend_yield_points", lambda _a, game=None: False)(int(spend_yp), game=game)):
            return None
        owner_id = str(ctx.get("turn_owner", "") or getattr(player, "id", "") or "")
        try:
            turn = int(ctx.get("turn", 0) or getattr(game, "turn", 0) or 0)
        except Exception:
            turn = int(getattr(game, "turn", 0) or 0)
        ability_name = str(ctx.get("ability_name", "") or "Iron Ambassador").strip() or "Iron Ambassador"
        sr = dict(sr)
        sr["enhancement_iron_ambassador_active"] = True
        sr["enhancement_iron_ambassador_damage_bonus"] = int(spend_yp)
        sr["enhancement_iron_ambassador_turn_owner"] = owner_id
        sr["enhancement_iron_ambassador_turn"] = int(turn or 0)
        sr["enhancement_iron_ambassador_expires_phase"] = "SHOOTING_PHASE"
        sr["enhancement_iron_ambassador_source"] = ability_name
        source_root.special_rules = sr
        mark_used = getattr(source_root, "mark_unit_once_per_battle_used", None)
        if callable(mark_used):
            mark_used("iron_ambassador", ability_name=ability_name)
        event_system = getattr(game, "event_system", None)
        if event_system is not None:
            event_system.publish(
                "prioritised_efficiency_updated",
                player=player,
                game=game,
                delta=-int(spend_yp),
                mode=getattr(pe, "mode", None),
                yield_points=int(getattr(pe, "yield_points", 0) or 0),
                reason="Iron Ambassador",
            )
        try:
            _log_action_for_players(
                game,
                player,
                f"{ability_name}: spent {int(spend_yp)} YP (+{int(spend_yp)} Damage to bearer ranged weapons until end of phase).",
            )
        except Exception:
            pass
        return int(spend_yp)
    if str(ctx.get("ability", "") or "") == "bastion_shield":
        payload = _option_payload(request, result)
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is None:
            return None
        source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if source_root is None:
            return None
        if is_skip_choice(request, result):
            return None
        action = str(payload.get("action", "") or "").strip().lower()
        if action not in ("spend", "use"):
            return None
        try:
            spend_yp = int(payload.get("spend_yp", payload.get("amount", 0)) or 0)
        except Exception:
            spend_yp = 0
        if int(spend_yp) != 1:
            return None
        player = _resolve_player(game, request, payload)
        if player is None:
            source_army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
            player = getattr(source_army, "player", None) if source_army is not None else None
        if player is None:
            return None
        army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
        pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
        if pe is None:
            return None
        if not bool(getattr(pe, "spend_yield_points", lambda _a, game=None: False)(1, game=game)):
            return None
        owner_id = str(ctx.get("turn_owner", "") or getattr(player, "id", "") or "")
        try:
            turn = int(ctx.get("turn", 0) or getattr(game, "turn", 0) or 0)
        except Exception:
            turn = int(getattr(game, "turn", 0) or 0)
        ability_name = str(ctx.get("ability_name", "") or "Bastion Shield").strip() or "Bastion Shield"

        source_member = resolve_unit(game, ctx.get("source_member_unit_id"))
        source_member_root = None
        if source_member is not None:
            source_member_root = (
                source_member.get_attached_unit_root() if hasattr(source_member, "get_attached_unit_root") else source_member
            )
        target_holder = None
        sr = None
        if source_member is not None and source_member_root is source_root:
            member_sr = getattr(source_member, "special_rules", None)
            if isinstance(member_sr, dict) and member_sr.get("enhancement_bastion_shield"):
                target_holder = source_member
                sr = member_sr
        if target_holder is None:
            try:
                members = list(source_root.get_attached_unit_members() or [])
            except Exception:
                members = []
            if not members:
                members = [source_root]
            for member in list(members or []):
                if member is None:
                    continue
                member_sr = getattr(member, "special_rules", None)
                if isinstance(member_sr, dict) and member_sr.get("enhancement_bastion_shield"):
                    target_holder = member
                    sr = member_sr
                    break
        if target_holder is None or not isinstance(sr, dict):
            return None

        sr = dict(sr)
        sr["enhancement_bastion_shield_extended_active"] = True
        sr["enhancement_bastion_shield_extended_turn_owner"] = owner_id
        sr["enhancement_bastion_shield_extended_turn"] = int(turn or 0)
        sr["enhancement_bastion_shield_extended_expires_phase"] = "SHOOTING_PHASE"
        sr["enhancement_bastion_shield_extended_source"] = ability_name
        target_holder.special_rules = sr

        event_system = getattr(game, "event_system", None)
        if event_system is not None:
            event_system.publish(
                "prioritised_efficiency_updated",
                player=player,
                game=game,
                delta=-1,
                mode=getattr(pe, "mode", None),
                yield_points=int(getattr(pe, "yield_points", 0) or 0),
                reason=ability_name,
            )
        try:
            _log_action_for_players(
                game,
                player,
                f"{ability_name}: spent 1 YP (AP worsening extends to 18\" until end of phase).",
            )
        except Exception:
            pass
        return 1
    if str(ctx.get("ability", "") or "") == "hammer_aflame":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        target_val = payload.get("target_unit_id") or payload.get("unit_id") or ctx.get("target_unit_id")
        target_unit = resolve_unit(game, target_val)
        if target_unit is None:
            return None
        source_unit = resolve_unit(
            game,
            ctx.get("source_unit_id") or ctx.get("unit_id") or ctx.get("attacker_unit_id"),
        )
        if source_unit is None:
            return None
        player = _resolve_player(game, request, payload)
        if player is None:
            try:
                player = source_unit.get_parent_army().player
            except Exception:
                player = None
        ability_name = str(ctx.get("ability_name", "") or "Hammer Aflame (Psychic)").strip() or "Hammer Aflame (Psychic)"
        from ...utility.dice import get_roll
        from ...utility.event_bus import append_dice

        roll = int(get_roll("D6") or 0)
        if player is not None:
            append_dice(player, f"{ability_name} roll: {roll}")

        mortal = 0
        if 2 <= roll <= 3:
            mortal = 1
        elif 4 <= roll <= 5:
            mortal = int(get_roll("D3") or 0)
        elif roll >= 6:
            mortal = int(get_roll("D3") or 0) + 3
        if mortal > 0:
            try:
                source_unit._apply_mortal_wounds_to_unit(
                    target_unit,
                    int(mortal),
                    game_map=getattr(game, "map", None),
                    is_psychic_attack=True,
                )
            except Exception:
                pass
        try:
            tname = str(getattr(target_unit, "name", "Unit") or "Unit")
            if mortal > 0:
                _log_action_for_players(game, player, f"{ability_name}: {tname} suffers {int(mortal)} mortal wounds.")
            else:
                _log_action_for_players(game, player, f"{ability_name}: {tname} suffers no mortal wounds.")
        except Exception:
            pass
        return target_unit
    if str(ctx.get("ability", "") or "") == "opponent_shooting_phase_grant_stealth":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        target_val = payload.get("target_unit_id") or ctx.get("target_unit_id")
        target_unit = resolve_unit(game, target_val)
        if target_unit is None:
            return None
        player = _resolve_player(game, request, payload)
        source_unit = resolve_unit(game, payload.get("source_unit_id") or ctx.get("source_unit_id"))
        if player is None and source_unit is not None:
            try:
                player = source_unit.get_parent_army().player
            except Exception:
                player = None
        ability_name = str(ctx.get("ability_name", "") or "Hallucinogen Grenades").strip() or "Hallucinogen Grenades"
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        try:
            members = list(target_root.get_attached_unit_members() or [])
        except Exception:
            members = [target_root]
        if not members:
            members = [target_root]
        try:
            phase_owner = game.get_current_player()
        except Exception:
            phase_owner = None
        owner_id = str(getattr(phase_owner, "id", "") or "")
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn = 0
        for unit in members:
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["opponent_shooting_phase_stealth_active"] = True
            sr["opponent_shooting_phase_stealth_owner"] = owner_id
            sr["opponent_shooting_phase_stealth_turn"] = int(turn or 0)
            sr["opponent_shooting_phase_stealth_source"] = ability_name
            sr["opponent_shooting_phase_stealth_expires_phase"] = "SHOOTING_PHASE"
            unit.special_rules = sr
        try:
            tname = str(getattr(target_root, "name", "Unit") or "Unit")
            _log_action_for_players(game, player, f"{ability_name}: {tname} gains Stealth until end of phase.")
        except Exception:
            pass
        return target_unit
    if str(ctx.get("ability", "") or "") == "opponent_shooting_phase_disrupt":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        target_val = payload.get("target_unit_id") or ctx.get("target_unit_id")
        target_unit = resolve_unit(game, target_val)
        if target_unit is None:
            return None
        model_id = payload.get("model_id") or ctx.get("model_id")
        model = resolve_model(game, model_id)
        source_unit = resolve_unit(game, payload.get("source_unit_id") or ctx.get("source_unit_id"))
        if source_unit is None and model is not None:
            source_unit = getattr(model, "parent_unit", None)
        player = _resolve_player(game, request, payload)
        if player is None and source_unit is not None:
            try:
                player = source_unit.get_parent_army().player
            except Exception:
                player = None
        ability_name = str(ctx.get("ability_name", "") or "Opponent Shooting phase disruption").strip() or "Opponent Shooting phase disruption"
        ability_key = str(ctx.get("ability_key", "") or ability_name).strip().upper()
        if bool(ctx.get("limit_one_per_army")) and player is not None:
            try:
                mark_fn = getattr(player, "_mark_ability_used_turn", None)
                if callable(mark_fn):
                    mark_fn(ability_key)
            except Exception:
                pass
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        try:
            members = list(target_root.get_attached_unit_members() or [])
        except Exception:
            members = [target_root]
        if not members:
            members = [target_root]
        try:
            phase_owner = game.get_current_player()
        except Exception:
            phase_owner = None
        owner_id = str(getattr(phase_owner, "id", "") or "")
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn = 0
        if bool(ctx.get("grant_ranged_hazardous")):
            for unit in members:
                if unit is None:
                    continue
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["shooting_phase_ranged_hazardous_active"] = True
                sr["shooting_phase_ranged_hazardous_owner"] = owner_id
                sr["shooting_phase_ranged_hazardous_turn"] = int(turn or 0)
                sr["shooting_phase_ranged_hazardous_source"] = ability_name
                sr["shooting_phase_ranged_hazardous_expires_phase"] = "SHOOTING_PHASE"
                unit.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {tname} ranged weapons are Hazardous this phase.")
            except Exception:
                pass
            return target_unit
        try:
            from ...utility.dice import get_roll
            from ...utility.event_bus import append_dice
        except Exception:
            get_roll = None
            append_dice = None
        roll = int(get_roll("D6") or 0) if callable(get_roll) else 0
        if callable(append_dice) and player is not None:
            append_dice(player, f"{ability_name} roll: {roll}")
        if roll <= 1:
            if bool(ctx.get("mortal_on_one")) and source_unit is not None:
                mortal = int(get_roll("D3") or 0) if callable(get_roll) else 0
                if callable(append_dice) and player is not None:
                    append_dice(player, f"{ability_name} mortal wounds: {mortal}")
                if mortal > 0:
                    try:
                        source_unit._apply_mortal_wounds_to_unit(
                            source_unit,
                            int(mortal),
                            game_map=getattr(game, "map", None),
                            is_psychic_attack=True,
                        )
                    except Exception:
                        pass
                try:
                    sname = str(getattr(source_unit, "name", "Unit") or "Unit")
                    _log_action_for_players(game, player, f"{ability_name}: {sname} suffers {int(mortal)} mortal wounds.")
                except Exception:
                    pass
            return target_unit
        if 2 <= roll <= 5:
            for unit in members:
                if unit is None:
                    continue
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["shooting_phase_hit_penalty_active"] = True
                sr["shooting_phase_hit_penalty_owner"] = owner_id
                sr["shooting_phase_hit_penalty_turn"] = int(turn or 0)
                sr["shooting_phase_hit_penalty_source"] = ability_name
                sr["shooting_phase_hit_penalty_expires_phase"] = "SHOOTING_PHASE"
                unit.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {tname} suffers -1 to hit this phase.")
            except Exception:
                pass
        elif roll >= 6:
            for unit in members:
                if unit is None:
                    continue
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["shooting_phase_ineligible_active"] = True
                sr["shooting_phase_ineligible_owner"] = owner_id
                sr["shooting_phase_ineligible_turn"] = int(turn or 0)
                sr["shooting_phase_ineligible_source"] = ability_name
                sr["shooting_phase_ineligible_expires_phase"] = "SHOOTING_PHASE"
                unit.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {tname} cannot shoot this phase.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "maggot_maws":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if chosen is not None:
            try:
                player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Maggot Maws").strip() or "Maggot Maws"
            sr = getattr(chosen, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["maggot_maws_pending"] = {
                "owner_id": owner_id,
                "source_unit_id": ctx.get("source_unit_id") or ctx.get("unit_id"),
                "source_model_id": ctx.get("model_id"),
                "turn": int(turn or 0),
                "ability_name": ability_name,
            }
            sr["suppress_daemonic_terror_once"] = True
            sr["suppress_daemonic_terror_source"] = ability_name
            sr["battle_shock_allow_suppressed_test"] = True
            chosen.special_rules = sr
            try:
                chosen.take_battle_shock_test(int(turn or 0))
            except Exception:
                pass
            try:
                sname = str(getattr(source_unit, "name", "Model") or "Model")
                tname = str(getattr(chosen, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {sname} targeted {tname} for Battle-shock.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "grenade_pack_flyover":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            try:
                player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Grenade Pack Flyover").strip() or "Grenade Pack Flyover"
            sr = getattr(source_unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["grenade_pack_flyover_used_turn_owner"] = owner_id
            sr["grenade_pack_flyover_used_turn"] = int(turn or 0)
            sr["grenade_pack_flyover_source"] = ability_name
            sr["grenade_pack_flyover_no_grenade_turn_owner"] = owner_id
            sr["grenade_pack_flyover_no_grenade_turn"] = int(turn or 0)
            source_unit.special_rules = sr
            spec = dict(ctx.get("spec", {}) or {})
            if "source" not in spec:
                spec["source"] = ability_name
            resolve_fn = getattr(game, "resolve_grenade_pack_flyover", None)
            if callable(resolve_fn):
                resolve_fn(source_unit, chosen, spec)
            try:
                sname = str(getattr(source_unit, "name", "Unit") or "Unit")
                tname = str(getattr(chosen, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {sname} selected {tname}.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "end_of_fight_embark":
        transport = resolve_unit(game, ctx.get("transport_id") or ctx.get("unit_id"))
        if transport is not None and chosen is not None:
            spec = dict(ctx.get("spec", {}) or {})
            if "source" not in spec:
                spec["source"] = str(ctx.get("ability_name", "") or "End of fight embark").strip()
            resolve_fn = getattr(game, "resolve_end_of_fight_embark", None)
            if callable(resolve_fn):
                resolve_fn(transport, chosen, spec)
            try:
                player = getattr(getattr(transport, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            try:
                sname = str(getattr(transport, "name", "Transport") or "Transport")
                tname = str(getattr(chosen, "name", "Unit") or "Unit")
                ability_name = str(ctx.get("ability_name", "") or "End of fight embark").strip()
                _log_action_for_players(game, player, f"{ability_name}: {tname} embarked in {sname}.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "aeldari_guiding_presence":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            try:
                player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            tsr = getattr(chosen, "special_rules", None)
            if not isinstance(tsr, dict):
                tsr = {}
            ability_name = str(ctx.get("ability_name", "") or "Guiding Presence").strip()
            tsr["guiding_presence_active"] = True
            try:
                tsr["guiding_presence_bonus"] = int(ctx.get("bonus", 1) or 1)
            except Exception:
                tsr["guiding_presence_bonus"] = 1
            tsr["guiding_presence_expires_phase"] = "SHOOTING_PHASE"
            tsr["guiding_presence_source"] = ability_name
            tsr["guiding_presence_owner"] = str(getattr(player, "id", "") or "")
            chosen.special_rules = tsr
            try:
                sname = str(getattr(source_unit, "name", "Model") or "Model")
                tname = str(getattr(chosen, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {sname} selected {tname} (+1 to hit).")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "aeldari_spirit_stone_heal":
        if is_skip_choice(request, result):
            return None
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            try:
                player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            try:
                from ...utility.dice import get_roll
                from ...utility.event_bus import append_dice
            except Exception:
                get_roll = None
                append_dice = None
            ability_name = str(ctx.get("ability_name", "") or "Spirit Stone of Raelyth").strip()
            heal = int(get_roll("D3") or 0) if callable(get_roll) else 0
            if callable(append_dice) and player is not None:
                append_dice(player, f"{ability_name} roll: {heal}")
            if heal <= 0:
                return chosen
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            try:
                models = list(target_root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(target_root, "models", []) or [])
            wounded = []
            for m in models:
                try:
                    if not getattr(m, "is_alive", True):
                        continue
                except Exception:
                    continue
                base = getattr(m, "_base_wounds", getattr(m, "wounds", 0))
                if int(getattr(m, "wounds", 0) or 0) < int(base or 0):
                    wounded.append(m)
            if not wounded:
                return chosen
            try:
                wounded.sort(key=lambda m: str(getattr(m, "id", getattr(m, "_id", "")) or ""))
            except Exception:
                wounded = list(wounded)
            target_model = wounded[0]
            try:
                target_model.heal(int(heal))
            except Exception:
                pass
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {tname} regains up to {int(heal)} wounds.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") in (
        "imperial_knights_iron_chalice",
        "imperial_knights_evanescent_ion",
        "imperial_knights_judicants_helm",
        "imperial_knights_lancers_sigil",
    ):
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
            target_root = chosen.get_attached_unit_root() if hasattr(chosen, "get_attached_unit_root") else chosen
            if source_root is None or target_root is None or target_root is source_root:
                return None
            player = _resolve_player(game, request, payload)
            if player is None:
                source_army = source_root.get_parent_army() if hasattr(source_root, "get_parent_army") else None
                player = getattr(source_army, "player", None) if source_army is not None else None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_key = str(ctx.get("ability", "") or "").strip().lower()
            ability_name = str(ctx.get("ability_name", "") or "Imperial Knights enhancement").strip() or "Imperial Knights enhancement"

            if ability_key == "imperial_knights_iron_chalice":
                try:
                    from ...utility.dice import get_roll
                    from ...utility.event_bus import append_dice
                except Exception:
                    get_roll = None
                    append_dice = None
                try:
                    source_army = source_root.get_parent_army()
                except Exception:
                    source_army = None
                honoured = bool(getattr(source_army, "code_chivalric_honoured", False)) if source_army is not None else False
                mgr = getattr(source_army, "code_chivalric", None) if source_army is not None else None
                if mgr is not None and bool(getattr(mgr, "honoured", False)):
                    honoured = True
                if honoured:
                    heal = 3
                else:
                    heal = int(get_roll("D3") or 0) if callable(get_roll) else 0
                    if callable(append_dice) and player is not None:
                        append_dice(player, f"{ability_name} roll: {int(heal)}")
                if heal > 0:
                    try:
                        models = list(target_root.get_attached_unit_models() or [])
                    except Exception:
                        models = list(getattr(target_root, "models", []) or [])
                    wounded = []
                    for m in models:
                        try:
                            if not getattr(m, "is_alive", True):
                                continue
                        except Exception:
                            continue
                        base = getattr(m, "_base_wounds", getattr(m, "wounds", 0))
                        if int(getattr(m, "wounds", 0) or 0) < int(base or 0):
                            wounded.append(m)
                    if wounded:
                        try:
                            wounded.sort(key=lambda m: str(getattr(m, "id", getattr(m, "_id", "")) or ""))
                        except Exception:
                            wounded = list(wounded)
                        target_model = wounded[0]
                        heal_fn = getattr(target_model, "heal", None)
                        if callable(heal_fn):
                            heal_fn(int(heal))
                try:
                    tname = str(getattr(target_root, "name", "Unit") or "Unit")
                    _log_action_for_players(game, player, f"{ability_name}: {tname} regains up to {int(heal)} wounds.")
                except Exception:
                    pass
                return target_root

            tsr = getattr(target_root, "special_rules", None)
            if not isinstance(tsr, dict):
                tsr = {}

            if ability_key == "imperial_knights_evanescent_ion":
                tsr["imperial_knights_evanescent_ion_stealth_active"] = True
                tsr["imperial_knights_evanescent_ion_stealth_owner"] = owner_id
                tsr["imperial_knights_evanescent_ion_stealth_turn"] = int(turn)
                tsr["imperial_knights_evanescent_ion_stealth_source"] = ability_name
                target_root.special_rules = tsr
                try:
                    tname = str(getattr(target_root, "name", "Unit") or "Unit")
                    _log_action_for_players(game, player, f"{ability_name}: {tname} gains Stealth until your next Movement phase.")
                except Exception:
                    pass
                return target_root

            if ability_key == "imperial_knights_judicants_helm":
                tsr["imperial_knights_judicants_helm_ignores_cover_ranged"] = True
                tsr["imperial_knights_judicants_helm_owner"] = owner_id
                tsr["imperial_knights_judicants_helm_turn"] = int(turn)
                tsr["imperial_knights_judicants_helm_source"] = ability_name
                tsr["imperial_knights_judicants_helm_expires_phase"] = "SHOOTING_PHASE"
                target_root.special_rules = tsr
                try:
                    tname = str(getattr(target_root, "name", "Unit") or "Unit")
                    _log_action_for_players(game, player, f"{ability_name}: {tname} ranged weapons gain [IGNORES COVER] this phase.")
                except Exception:
                    pass
                return target_root

            if ability_key == "imperial_knights_lancers_sigil":
                tsr["imperial_knights_lancers_sigil_charge_reroll"] = True
                tsr["imperial_knights_lancers_sigil_owner"] = owner_id
                tsr["imperial_knights_lancers_sigil_turn"] = int(turn)
                tsr["imperial_knights_lancers_sigil_source"] = ability_name
                tsr["imperial_knights_lancers_sigil_expires_phase"] = "CHARGE_PHASE"
                target_root.special_rules = tsr
                try:
                    tname = str(getattr(target_root, "name", "Unit") or "Unit")
                    _log_action_for_players(game, player, f"{ability_name}: {tname} can re-roll Charge rolls this phase.")
                except Exception:
                    pass
                return target_root
    if str(ctx.get("ability", "") or "") == "spirit_mark_friendly":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        model = resolve_model(game, ctx.get("model_id"))
        if source_unit is not None and model is not None and chosen is not None:
            player = _resolve_player(game, request, payload)
            if player is None:
                try:
                    player = source_unit.get_parent_army().player
                except Exception:
                    player = None
            spec = {
                "keyword": str(ctx.get("keyword", "") or "").strip(),
                "sustained_hits_value": int(ctx.get("sustained_hits_value", 1) or 1),
                "source": str(ctx.get("ability_name", "") or "Spirit Mark").strip() or "Spirit Mark",
            }
            queue_fn = getattr(game, "_queue_spirit_mark_enemy_selection", None)
            if callable(queue_fn):
                queue_fn(
                    player=player,
                    source_unit=source_unit,
                    model=model,
                    friendly_unit=chosen,
                    spec=spec,
                )
    if str(ctx.get("ability", "") or "") == "spirit_mark_enemy":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        model = resolve_model(game, ctx.get("model_id"))
        friendly_unit = resolve_unit(game, ctx.get("friendly_unit_id"))
        if source_unit is not None and model is not None and friendly_unit is not None and chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            try:
                friendly_root = friendly_unit.get_attached_unit_root()
            except Exception:
                friendly_root = friendly_unit
            player = _resolve_player(game, request, payload)
            if player is None:
                try:
                    player = source_unit.get_parent_army().player
                except Exception:
                    player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Spirit Mark").strip() or "Spirit Mark"
            keyword = str(ctx.get("keyword", "") or "").strip()
            try:
                value = int(ctx.get("sustained_hits_value", 1) or 1)
            except Exception:
                value = 1
            sr = getattr(friendly_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["spirit_mark_active"] = True
            sr["spirit_mark_owner"] = owner_id
            sr["spirit_mark_turn"] = int(turn or 0)
            sr["spirit_mark_source"] = ability_name
            sr["spirit_mark_target_id"] = str(get_entity_id(target_root) or "")
            sr["spirit_mark_sustained_hits_value"] = int(value)
            sr["spirit_mark_keyword"] = keyword
            friendly_root.special_rules = sr

            sr_source = getattr(source_unit, "special_rules", None)
            if not isinstance(sr_source, dict):
                sr_source = {}
            sr_source["spirit_mark_used_turn_owner"] = owner_id
            sr_source["spirit_mark_used_turn"] = int(turn or 0)
            used_ids = {str(v) for v in list(sr_source.get("spirit_mark_used_model_ids", []) or []) if v}
            model_id = str(getattr(model, "_id", "") or "")
            if model_id:
                used_ids.add(model_id)
            sr_source["spirit_mark_used_model_ids"] = sorted(used_ids)
            source_unit.special_rules = sr_source

            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                fname = str(getattr(friendly_root, "name", "Unit") or "Unit")
                _log_action_for_players(
                    game,
                    player,
                    f"{ability_name}: {fname} marked {tname} (Sustained Hits {int(value)}).",
                )
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "tears_of_isha_target":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            player = _resolve_player(game, request, payload)
            if player is None:
                try:
                    player = source_unit.get_parent_army().player
                except Exception:
                    player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Tears of Isha").strip() or "Tears of Isha"
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["tears_of_isha_selected_turn_owner"] = owner_id
            sr["tears_of_isha_selected_turn"] = int(turn or 0)
            sr["tears_of_isha_selected_source"] = ability_name
            target_root.special_rules = sr

            destroyed = list(getattr(target_root, "models_lost", []) or [])
            if destroyed:
                queue_fn = getattr(game, "_queue_bodyguard_return_decision", None)
                if callable(queue_fn):
                    queue_fn(
                        player=player,
                        leader_unit=source_unit,
                        bodyguard_unit=target_root,
                        ability={"name": ability_name},
                        remaining=1,
                        allow_skip=True,
                    )
                return chosen

            try:
                from ...utility.dice import get_roll
                from ...utility.event_bus import append_dice
            except Exception:
                get_roll = None
                append_dice = None
            heal = int(get_roll("D3") or 0) if callable(get_roll) else 0
            if callable(append_dice) and player is not None:
                append_dice(player, f"{ability_name} roll: {heal}")
            if heal <= 0:
                return chosen
            try:
                models = list(target_root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(target_root, "models", []) or [])
            wounded = []
            for m in models:
                try:
                    if not getattr(m, "is_alive", True):
                        continue
                except Exception:
                    continue
                base = getattr(m, "_base_wounds", getattr(m, "wounds", 0))
                if int(getattr(m, "wounds", 0) or 0) < int(base or 0):
                    wounded.append(m)
            if not wounded:
                return chosen
            try:
                wounded.sort(key=lambda m: str(getattr(m, "id", getattr(m, "_id", "")) or ""))
            except Exception:
                wounded = list(wounded)
            target_model = wounded[0]
            try:
                target_model.heal(int(heal))
            except Exception:
                pass
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {tname} regains up to {int(heal)} wounds.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "post_shoot_no_cover":
        if chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["post_shoot_no_cover_active"] = True
            attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id"))
            try:
                player = getattr(attacker_unit.get_parent_army(), "player", None) if attacker_unit is not None else None
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            expires_timing = str(ctx.get("expires_timing", "") or "PHASE_END").strip().upper() or "PHASE_END"
            expires_phase = str(ctx.get("expires_phase", "") or "SHOOTING_PHASE").strip().upper() or "SHOOTING_PHASE"
            if expires_timing == "OWNER_NEXT_SHOOTING_START":
                sr.pop("post_shoot_no_cover_expires_phase", None)
                sr["post_shoot_no_cover_expires_timing"] = "OWNER_NEXT_SHOOTING_START"
            else:
                sr["post_shoot_no_cover_expires_phase"] = expires_phase
                sr.pop("post_shoot_no_cover_expires_timing", None)
            sr["post_shoot_no_cover_source"] = str(ctx.get("ability_name", "") or "No Cover").strip()
            sr["post_shoot_no_cover_owner"] = owner_id
            sr["post_shoot_no_cover_turn"] = int(turn or 0)
            target_root.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                if expires_timing == "OWNER_NEXT_SHOOTING_START":
                    _log_action_for_players(
                        game,
                        player,
                        f"{sr['post_shoot_no_cover_source']}: {tname} cannot gain Benefit of Cover until the start of your next Shooting phase.",
                    )
                else:
                    _log_action_for_players(
                        game,
                        player,
                        f"{sr['post_shoot_no_cover_source']}: {tname} cannot gain Benefit of Cover this phase.",
                    )
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "post_shoot_no_overwatch":
        if chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["post_shoot_no_overwatch_active"] = True
            attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id"))
            try:
                player = getattr(attacker_unit.get_parent_army(), "player", None) if attacker_unit is not None else None
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            sr["post_shoot_no_overwatch_source"] = str(ctx.get("ability_name", "") or "No Overwatch").strip()
            sr["post_shoot_no_overwatch_owner"] = owner_id
            sr["post_shoot_no_overwatch_turn"] = int(turn or 0)
            target_root.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(
                    game,
                    player,
                    f"{sr['post_shoot_no_overwatch_source']}: {tname} cannot be targeted with Fire Overwatch until the start of your next Shooting phase.",
                )
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "start_shooting_phase_visible_hit_bonus":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            try:
                source_root = source_unit.get_attached_unit_root()
            except Exception:
                source_root = source_unit
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            try:
                player = getattr(getattr(source_root, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            try:
                bonus = int(ctx.get("hit_bonus", 0) or 0)
            except Exception:
                bonus = 0
            if bonus <= 0:
                bonus = 1
            ability_name = str(ctx.get("ability_name", "") or "Marked by Fate").strip() or "Marked by Fate"
            sr = getattr(source_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["start_shooting_phase_visible_hit_bonus_active"] = True
            sr["start_shooting_phase_visible_hit_bonus_owner"] = owner_id
            sr["start_shooting_phase_visible_hit_bonus_turn"] = int(turn or 0)
            sr["start_shooting_phase_visible_hit_bonus_source"] = ability_name
            sr["start_shooting_phase_visible_hit_bonus_target_id"] = str(get_entity_id(target_root) or "")
            sr["start_shooting_phase_visible_hit_bonus_value"] = int(bonus)
            sr["start_shooting_phase_visible_hit_bonus_expires_phase"] = "SHOOTING_PHASE"
            source_root.special_rules = sr
            try:
                sname = str(getattr(source_root, "name", "Unit") or "Unit")
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {sname} selected {tname} (+{int(bonus)} to hit this phase).")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "blight_bombardment":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            try:
                source_root = source_unit.get_attached_unit_root()
            except Exception:
                source_root = source_unit
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            try:
                player = getattr(getattr(source_root, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Blight Bombardment").strip() or "Blight Bombardment"
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["blight_bombardment_active"] = True
            sr["blight_bombardment_owner"] = owner_id
            sr["blight_bombardment_turn"] = int(turn or 0)
            sr["blight_bombardment_source"] = ability_name
            sr["blight_bombardment_target_id"] = str(get_entity_id(target_root) or "")
            sr["blight_bombardment_expires_phase"] = "SHOOTING_PHASE"
            target_root.special_rules = sr
            try:
                sname = str(getattr(source_root, "name", "Unit") or "Unit")
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(
                    game,
                    player,
                    f"{ability_name}: {sname} marked {tname} for ranged hit re-roll support this phase.",
                )
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "eater_plague":
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        target_unit = resolve_unit(game, payload.get("target_unit_id") or ctx.get("target_unit_id"))
        model = resolve_model(game, payload.get("model_id") or ctx.get("model_id"))
        source_unit = resolve_unit(game, payload.get("source_unit_id") or ctx.get("source_unit_id"))
        if source_unit is None and model is not None:
            source_unit = getattr(model, "parent_unit", None)
        if source_unit is None or target_unit is None:
            return None
        try:
            source_root = source_unit.get_attached_unit_root()
        except Exception:
            source_root = source_unit
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        player = _resolve_player(game, request, payload)
        if player is None:
            try:
                player = source_root.get_parent_army().player
            except Exception:
                player = None
        ability_name = str(ctx.get("ability_name", "") or "Eater Plague").strip() or "Eater Plague"
        try:
            from ...utility.dice import get_roll
            from ...utility.event_bus import append_dice
        except Exception:
            get_roll = None
            append_dice = None

        def _resolve_mortal_token(token: str) -> int:
            tok = str(token or "").strip().lower()
            if not tok:
                return 0
            if tok == "d3":
                return int(get_roll("D3") or 0) if callable(get_roll) else 0
            if tok == "d6":
                return int(get_roll("D6") or 0) if callable(get_roll) else 0
            if tok in ("d3+3", "d3 3"):
                d3v = int(get_roll("D3") or 0) if callable(get_roll) else 0
                return int(d3v + 3)
            try:
                return int(tok)
            except Exception:
                return 0

        roll_mode = str(ctx.get("roll_mode", "") or "table_d6_self_1_target_2_5_6").strip().lower()
        mortal = 0
        recipient = target_root
        is_psychic = bool(roll_mode == "table_d6_self_1_target_2_5_6")

        if roll_mode == "dice_pool_threshold":
            try:
                dice_count = int(ctx.get("dice_count", 0) or 0)
            except Exception:
                dice_count = 0
            try:
                threshold = int(ctx.get("threshold", 0) or 0)
            except Exception:
                threshold = 0
            mw_token = str(ctx.get("mortal_per_success", "") or "1")
            if dice_count > 0 and threshold > 0:
                rolls = [int(get_roll("D6") or 0) if callable(get_roll) else 0 for _ in range(int(dice_count))]
                successes = sum(1 for r in rolls if int(r) >= int(threshold))
                if mw_token.strip().lower() in ("d3", "d6", "d3+3", "d3 3"):
                    mortal = sum(_resolve_mortal_token(mw_token) for _ in range(int(successes)))
                else:
                    per_success = _resolve_mortal_token(mw_token)
                    mortal = int(max(0, per_success) * int(successes))
                if callable(append_dice) and player is not None:
                    append_dice(
                        player,
                        f"{ability_name}: rolls {rolls} ({int(threshold)}+) => {int(successes)} success(es), {int(mortal)} mortal wounds.",
                    )
        else:
            roll = int(get_roll("D6") or 0) if callable(get_roll) else 0
            if callable(append_dice) and player is not None:
                append_dice(player, f"{ability_name} roll: {roll}")
            self_token = str(ctx.get("self_mortal_on_one", "") or "d3")
            mid_token = str(ctx.get("target_mortal_on_mid", "") or "d6")
            high_token = str(ctx.get("target_mortal_on_six", "") or "d3+3")
            if roll <= 1:
                mortal = int(_resolve_mortal_token(self_token))
                recipient = source_root
            elif roll <= 5:
                mortal = int(_resolve_mortal_token(mid_token))
                recipient = target_root
            else:
                mortal = int(_resolve_mortal_token(high_token))
                recipient = target_root

        if callable(append_dice) and player is not None:
            append_dice(player, f"{ability_name} mortal wounds: {int(mortal)}")
        if mortal > 0 and source_root is not None and recipient is not None:
            count_for_curse = bool(ctx.get("count_as_curse_of_walking_pox", bool(roll_mode != "dice_pool_threshold")))
            had_marker = False
            if count_for_curse:
                sr_source = getattr(source_root, "special_rules", None)
                if not isinstance(sr_source, dict):
                    sr_source = {}
                had_marker = bool(sr_source.get("curse_of_walking_pox_count_eater_plague", False))
                sr_source["curse_of_walking_pox_count_eater_plague"] = True
                source_root.special_rules = sr_source
            try:
                source_root._apply_mortal_wounds_to_unit(
                    recipient,
                    int(mortal),
                    game_map=getattr(game, "map", None),
                    is_psychic_attack=bool(is_psychic),
                )
            except Exception:
                pass
            finally:
                if count_for_curse and not had_marker:
                    sr_source = getattr(source_root, "special_rules", None)
                    if not isinstance(sr_source, dict):
                        sr_source = {}
                    sr_source.pop("curse_of_walking_pox_count_eater_plague", None)
                    source_root.special_rules = sr_source
        try:
            rname = str(getattr(recipient, "name", "Unit") or "Unit")
            if recipient is source_root:
                _log_action_for_players(game, player, f"{ability_name}: {rname} suffers {int(mortal)} mortal wounds.")
            else:
                _log_action_for_players(game, player, f"{ability_name}: {rname} suffers {int(mortal)} mortal wounds.")
        except Exception:
            pass
        return recipient
    if str(ctx.get("ability", "") or "") == "post_shoot_afflicted":
        if chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id"))
            try:
                player = getattr(attacker_unit.get_parent_army(), "player", None) if attacker_unit is not None else None
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                current_turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                current_turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Afflicted").strip() or "Afflicted"
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["post_shoot_afflicted_active"] = True
            sr["post_shoot_afflicted_owner"] = owner_id
            sr["post_shoot_afflicted_turn"] = int(current_turn or 0)
            sr["post_shoot_afflicted_source"] = ability_name
            target_root.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(
                    game,
                    player,
                    f"{ability_name}: {tname} is Afflicted until the start of your next turn.",
                )
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "post_shoot_keyword_wound_reroll":
        if chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id"))
            try:
                player = getattr(attacker_unit.get_parent_army(), "player", None) if attacker_unit is not None else None
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Post-shoot Wound reroll").strip() or "Post-shoot Wound reroll"
            phrase = str(ctx.get("keyword_phrase", "") or "").strip()
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["post_shoot_keyword_wound_reroll_active"] = True
            sr["post_shoot_keyword_wound_reroll_owner"] = owner_id
            sr["post_shoot_keyword_wound_reroll_turn"] = int(turn or 0)
            sr["post_shoot_keyword_wound_reroll_source"] = ability_name
            sr["post_shoot_keyword_wound_reroll_phrase"] = phrase
            target_root.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {tname} marked for Wound re-rolls.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "post_shoot_keyword_strength_bonus":
        if chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id"))
            try:
                player = getattr(attacker_unit.get_parent_army(), "player", None) if attacker_unit is not None else None
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Post-shoot Strength bonus").strip() or "Post-shoot Strength bonus"
            phrase = str(ctx.get("keyword_phrase", "") or "").strip()
            try:
                bonus = int(ctx.get("strength_bonus", 0) or 0)
            except Exception:
                bonus = 0
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["post_shoot_keyword_strength_bonus_active"] = True
            sr["post_shoot_keyword_strength_bonus_owner"] = owner_id
            sr["post_shoot_keyword_strength_bonus_turn"] = int(turn or 0)
            sr["post_shoot_keyword_strength_bonus_source"] = ability_name
            sr["post_shoot_keyword_strength_bonus_phrase"] = phrase
            sr["post_shoot_keyword_strength_bonus_value"] = int(bonus or 0)
            sr["post_shoot_keyword_strength_bonus_marked_state"] = "riven"
            target_root.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(
                    game,
                    player,
                    f"{ability_name}: {tname} is riven (+{int(bonus)} Strength vs target this turn).",
                )
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") in ("metalophagic_infection", "post_shoot_monster_vehicle_mortal_threshold"):
        if is_skip_choice(request, result):
            return None
        payload = _option_payload(request, result)
        target_unit = resolve_unit(game, payload.get("target_unit_id") or ctx.get("target_unit_id"))
        source_unit = resolve_unit(game, payload.get("source_unit_id") or ctx.get("source_unit_id") or ctx.get("attacker_unit_id"))
        if source_unit is None:
            model = resolve_model(game, payload.get("model_id") or ctx.get("model_id"))
            source_unit = getattr(model, "parent_unit", None) if model is not None else None
        if source_unit is None or target_unit is None:
            return None
        try:
            source_root = source_unit.get_attached_unit_root()
        except Exception:
            source_root = source_unit
        try:
            target_root = target_unit.get_attached_unit_root()
        except Exception:
            target_root = target_unit
        player = _resolve_player(game, request, payload)
        if player is None:
            try:
                player = source_root.get_parent_army().player
            except Exception:
                player = None
        ability_name = str(ctx.get("ability_name", "") or "Metalophagic Infection").strip() or "Metalophagic Infection"
        try:
            threshold = int(ctx.get("threshold", 5) or 5)
        except Exception:
            threshold = 5
        try:
            afflicted_bonus = int(ctx.get("afflicted_roll_bonus", 0) or 0)
        except Exception:
            afflicted_bonus = 0
        mw_raw = str(ctx.get("mortal_wounds", "d3") or "d3").strip().lower()
        try:
            from ...utility.dice import get_roll
            from ...utility.event_bus import append_dice
            from ...rules.nurgles_gift import NurglesGiftManager
        except Exception:
            get_roll = None
            append_dice = None
            NurglesGiftManager = None
        is_afflicted = False
        if NurglesGiftManager is not None:
            try:
                is_afflicted = bool(
                    NurglesGiftManager.get_afflicted_plague_for_unit(
                        target_root,
                        game=game,
                        game_map=getattr(game, "map", None),
                    )
                    is not None
                )
            except Exception:
                is_afflicted = False
        roll = int(get_roll("D6") or 0) if callable(get_roll) else 0
        total_roll = int(roll + (afflicted_bonus if is_afflicted else 0))
        mortal = 0
        if total_roll >= int(threshold):
            if mw_raw == "d3":
                mortal = int(get_roll("D3") or 0) if callable(get_roll) else 0
            elif mw_raw == "d6":
                mortal = int(get_roll("D6") or 0) if callable(get_roll) else 0
            else:
                try:
                    mortal = int(mw_raw)
                except Exception:
                    mortal = 0
        if mortal > 0:
            try:
                source_root._apply_mortal_wounds_to_unit(
                    target_root,
                    int(mortal),
                    game_map=getattr(game, "map", None),
                )
            except Exception:
                pass
        if callable(append_dice) and player is not None:
            append_dice(
                player,
                f"{ability_name}: roll {int(roll)}"
                + (f" (+{int(afflicted_bonus)} afflicted)" if is_afflicted and afflicted_bonus else "")
                + f" => {int(total_roll)} ({int(threshold)}+) => {int(mortal)} mortal wounds.",
            )
        try:
            tname = str(getattr(target_root, "name", "Unit") or "Unit")
            _log_action_for_players(game, player, f"{ability_name}: {tname} suffers {int(mortal)} mortal wounds.")
        except Exception:
            pass
        return target_root
    if str(ctx.get("ability", "") or "") == "post_shoot_keyword_hit_bonus":
        if chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id"))
            try:
                player = getattr(attacker_unit.get_parent_army(), "player", None) if attacker_unit is not None else None
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Post-shoot Hit bonus").strip() or "Post-shoot Hit bonus"
            phrase = str(ctx.get("keyword_phrase", "") or "").strip()
            try:
                bonus = int(ctx.get("hit_bonus", 0) or 0)
            except Exception:
                bonus = 0
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["post_shoot_keyword_hit_bonus_active"] = True
            sr["post_shoot_keyword_hit_bonus_owner"] = owner_id
            sr["post_shoot_keyword_hit_bonus_turn"] = int(turn or 0)
            sr["post_shoot_keyword_hit_bonus_source"] = ability_name
            sr["post_shoot_keyword_hit_bonus_phrase"] = phrase
            sr["post_shoot_keyword_hit_bonus_value"] = int(bonus or 0)
            sr["post_shoot_keyword_hit_bonus_expires_phase"] = "SHOOTING_PHASE"
            target_root.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {tname} marked for +{int(bonus)} to hit.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "post_shoot_ap_bonus":
        if chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id"))
            try:
                player = getattr(attacker_unit.get_parent_army(), "player", None) if attacker_unit is not None else None
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "AP Bonus").strip() or "AP Bonus"
            keyword = str(ctx.get("keyword", "") or "").strip()
            attack_type = str(ctx.get("attack_type", "") or "any").strip().lower() or "any"
            try:
                ap_bonus = int(ctx.get("ap_bonus", 0) or 0)
            except Exception:
                ap_bonus = 0
            limit_scope = str(ctx.get("limit_scope", "") or "").strip().lower()
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["post_shoot_ap_bonus_active"] = True
            sr["post_shoot_ap_bonus_expires_phase"] = "SHOOTING_PHASE"
            sr["post_shoot_ap_bonus_source"] = ability_name
            sr["post_shoot_ap_bonus_value"] = int(ap_bonus)
            sr["post_shoot_ap_bonus_keyword"] = keyword
            sr["post_shoot_ap_bonus_attack_type"] = attack_type
            sr["post_shoot_ap_bonus_owner"] = owner_id
            sr["post_shoot_ap_bonus_turn"] = int(turn or 0)
            if limit_scope in ("turn", "phase"):
                sr["post_shoot_ap_bonus_selected_owner"] = owner_id
                sr["post_shoot_ap_bonus_selected_turn"] = int(turn or 0)
                sr["post_shoot_ap_bonus_selected_scope"] = limit_scope
                if limit_scope == "phase":
                    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    if phase_name:
                        sr["post_shoot_ap_bonus_selected_phase"] = phase_name
            target_root.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                display_keyword = keyword.upper() if keyword else "friendly"
                _log_action_for_players(
                    game,
                    player,
                    f"{ability_name}: {tname} marked ({display_keyword} AP +{int(ap_bonus)} this phase).",
                )
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "post_shoot_crit_hit_threshold":
        if chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id"))
            try:
                player = getattr(attacker_unit.get_parent_army(), "player", None) if attacker_unit is not None else None
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Post-shoot crit bonus").strip() or "Post-shoot crit bonus"
            keyword = str(ctx.get("keyword", "") or "").strip()
            try:
                threshold = int(ctx.get("threshold", 6) or 6)
            except Exception:
                threshold = 6
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["post_shoot_crit_hit_threshold_active"] = True
            sr["post_shoot_crit_hit_threshold_owner"] = owner_id
            sr["post_shoot_crit_hit_threshold_turn"] = int(turn or 0)
            sr["post_shoot_crit_hit_threshold_source"] = ability_name
            sr["post_shoot_crit_hit_threshold_keyword"] = keyword
            sr["post_shoot_crit_hit_threshold_value"] = int(threshold)
            sr["post_shoot_crit_hit_threshold_expires_phase"] = "FIGHT_PHASE"
            target_root.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                display_keyword = keyword.upper() if keyword else "friendly"
                _log_action_for_players(
                    game,
                    player,
                    f"{ability_name}: {tname} marked ({display_keyword} crits on {int(threshold)}+).",
                )
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "post_shoot_disembark_wound_reroll":
        if chosen is not None:
            try:
                attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id") or ctx.get("source_unit_id"))
            except Exception:
                attacker_unit = None
            if attacker_unit is None:
                return None
            try:
                player = getattr(attacker_unit.get_parent_army(), "player", None)
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Fire Support").strip() or "Fire Support"
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            target_id = str(get_entity_id(target_root) or "")
            sr = getattr(attacker_unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["post_shoot_disembark_wound_reroll_active"] = True
            sr["post_shoot_disembark_wound_reroll_expires_phase"] = "SHOOTING_PHASE"
            sr["post_shoot_disembark_wound_reroll_source"] = ability_name
            sr["post_shoot_disembark_wound_reroll_target_id"] = target_id
            sr["post_shoot_disembark_wound_reroll_owner"] = owner_id
            sr["post_shoot_disembark_wound_reroll_turn"] = int(turn or 0)
            attacker_unit.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {tname} marked (disembarked units re-roll Wound rolls).")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "post_shoot_disembark_ap_bonus":
        if chosen is not None:
            try:
                attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id") or ctx.get("source_unit_id"))
            except Exception:
                attacker_unit = None
            if attacker_unit is None:
                return None
            try:
                player = getattr(attacker_unit.get_parent_army(), "player", None)
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Fire Focus").strip() or "Fire Focus"
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            target_id = str(get_entity_id(target_root) or "")
            try:
                ap_bonus = int(ctx.get("ap_bonus", 0) or 0)
            except Exception:
                ap_bonus = 0
            sr = getattr(attacker_unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["post_shoot_disembark_ap_bonus_active"] = True
            sr["post_shoot_disembark_ap_bonus_source"] = ability_name
            sr["post_shoot_disembark_ap_bonus_target_id"] = target_id
            sr["post_shoot_disembark_ap_bonus_owner"] = owner_id
            sr["post_shoot_disembark_ap_bonus_turn"] = int(turn or 0)
            sr["post_shoot_disembark_ap_bonus_value"] = int(ap_bonus or 0)
            attacker_unit.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(
                    game,
                    player,
                    f"{ability_name}: {tname} marked (disembarked units gain AP +{int(ap_bonus)}).",
                )
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "post_shoot_disembark_psychic_hit_wound_bonus":
        if chosen is not None:
            try:
                attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id") or ctx.get("source_unit_id"))
            except Exception:
                attacker_unit = None
            if attacker_unit is None:
                return None
            try:
                player = getattr(attacker_unit.get_parent_army(), "player", None)
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Sorcerous Support").strip() or "Sorcerous Support"
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            target_id = str(get_entity_id(target_root) or "")
            try:
                hit_bonus = int(ctx.get("hit_bonus", 0) or 0)
            except Exception:
                hit_bonus = 0
            try:
                wound_bonus = int(ctx.get("wound_bonus", 0) or 0)
            except Exception:
                wound_bonus = 0
            if hit_bonus <= 0 and wound_bonus <= 0:
                hit_bonus = 1
                wound_bonus = 1
            sr = getattr(attacker_unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["post_shoot_disembark_psychic_hit_wound_bonus_active"] = True
            sr["post_shoot_disembark_psychic_hit_wound_bonus_expires_phase"] = "SHOOTING_PHASE"
            sr["post_shoot_disembark_psychic_hit_wound_bonus_source"] = ability_name
            sr["post_shoot_disembark_psychic_hit_wound_bonus_target_id"] = target_id
            sr["post_shoot_disembark_psychic_hit_wound_bonus_owner"] = owner_id
            sr["post_shoot_disembark_psychic_hit_wound_bonus_turn"] = int(turn or 0)
            sr["post_shoot_disembark_psychic_hit_wound_bonus_hit"] = int(hit_bonus)
            sr["post_shoot_disembark_psychic_hit_wound_bonus_wound"] = int(wound_bonus)
            attacker_unit.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(
                    game,
                    player,
                    f"{ability_name}: {tname} marked (disembarked Psychic attacks +{int(hit_bonus)} hit, +{int(wound_bonus)} wound).",
                )
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "move_over_no_cover":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            try:
                player = getattr(getattr(source_unit, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Flame-wreathed").strip() or "Flame-wreathed"
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["move_over_no_cover_active"] = True
            sr["move_over_no_cover_owner"] = owner_id
            sr["move_over_no_cover_turn"] = int(turn or 0)
            sr["move_over_no_cover_source"] = ability_name
            target_root.special_rules = sr
            try:
                sname = str(getattr(source_unit, "name", "Model") or "Model")
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {sname} selected {tname}; it cannot gain Benefit of Cover this turn.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "herald_of_ynnead":
        if chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id") or ctx.get("source_unit_id"))
            try:
                player = getattr(attacker_unit.get_parent_army(), "player", None) if attacker_unit is not None else None
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Herald of Ynnead").strip() or "Herald of Ynnead"
            keyword = str(ctx.get("keyword", "") or "aeldari").strip().lower() or "aeldari"
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["herald_of_ynnead_active"] = True
            sr["herald_of_ynnead_owner"] = owner_id
            sr["herald_of_ynnead_turn"] = int(turn or 0)
            sr["herald_of_ynnead_source"] = ability_name
            sr["herald_of_ynnead_keyword"] = keyword
            sr["herald_of_ynnead_expires_phase"] = "FIGHT_PHASE"
            target_root.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {tname} marked (re-roll Wound rolls of 1).")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "inflamed_infections":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("attacker_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            try:
                source_root = source_unit.get_attached_unit_root()
            except Exception:
                source_root = source_unit
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            try:
                player = getattr(getattr(source_root, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Inflamed Infections").strip() or "Inflamed Infections"
            model_id = str(ctx.get("model_id", "") or "")
            try:
                threshold = int(ctx.get("crit_hit_threshold", 5) or 5)
            except Exception:
                threshold = 5
            try:
                threshold_below_half = int(ctx.get("crit_hit_threshold_below_half", threshold) or threshold)
            except Exception:
                threshold_below_half = threshold
            threshold = max(2, min(6, int(threshold)))
            threshold_below_half = max(2, min(6, int(threshold_below_half)))
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["inflamed_infections_active"] = True
            sr["inflamed_infections_owner"] = owner_id
            sr["inflamed_infections_turn"] = int(turn or 0)
            sr["inflamed_infections_source"] = ability_name
            sr["inflamed_infections_model_id"] = model_id
            sr["inflamed_infections_crit_hit_threshold"] = int(threshold)
            sr["inflamed_infections_crit_hit_threshold_below_half"] = int(threshold_below_half)
            sr["inflamed_infections_expires_phase"] = "FIGHT_PHASE"
            target_root.special_rules = sr
            try:
                _log_action_for_players(
                    game,
                    player,
                    f"{ability_name}: {getattr(target_root, 'name', 'Unit')} marked for critical hits on {int(threshold)}+ ({int(threshold_below_half)}+ while Below Half-strength).",
                )
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "data_spike":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("attacker_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            source_root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
            target_root = chosen.get_attached_unit_root() if hasattr(chosen, "get_attached_unit_root") else chosen
            if source_root is None or target_root is None:
                return None
            player = _resolve_player(game, request, _option_payload(request, result))
            if player is None:
                try:
                    player = source_root.get_parent_army().player
                except Exception:
                    player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Data-spike").strip() or "Data-spike"
            try:
                threshold = int(ctx.get("threshold", 4) or 4)
            except Exception:
                threshold = 4
            threshold = max(2, min(6, int(threshold)))
            try:
                ws_penalty = int(ctx.get("ws_penalty", 1) or 1)
            except Exception:
                ws_penalty = 1
            ws_penalty = max(1, int(ws_penalty))
            mw_spec = str(ctx.get("mortal_wounds", "D6") or "D6").strip().upper() or "D6"

            try:
                from ...utility.dice import get_roll
                from ...utility.event_bus import append_action, append_dice
            except Exception:
                get_roll = None
                append_action = None
                append_dice = None
            roll = int(get_roll("D6") or 0) if callable(get_roll) else 0
            if callable(append_dice) and player is not None:
                append_dice(player, f"{ability_name} roll: {int(roll)}")
            if int(roll) < int(threshold):
                if callable(append_action) and player is not None:
                    append_action(
                        player,
                        f"{ability_name}: {getattr(target_root, 'name', 'Unit')} not affected (roll {int(roll)}, need {int(threshold)}+).",
                    )
                return target_root

            total_mw = 0
            if mw_spec == "D3":
                total_mw = int(get_roll("D3") or 0) if callable(get_roll) else 0
            elif mw_spec == "D6":
                total_mw = int(get_roll("D6") or 0) if callable(get_roll) else 0
            else:
                try:
                    total_mw = int(mw_spec or 0)
                except Exception:
                    total_mw = 0
            if int(total_mw) > 0:
                source_root._apply_mortal_wounds_to_unit(
                    target_root,
                    int(total_mw),
                    game_map=getattr(game, "map", None),
                )

            tsr = getattr(target_root, "special_rules", None)
            if not isinstance(tsr, dict):
                tsr = {}
            try:
                existing_penalty = int(tsr.get("data_spike_ws_penalty", 0) or 0)
            except Exception:
                existing_penalty = 0
            tsr["data_spike_ws_penalty_active"] = True
            tsr["data_spike_ws_penalty"] = int(existing_penalty + ws_penalty)
            tsr["data_spike_ws_penalty_owner"] = owner_id
            tsr["data_spike_ws_penalty_turn"] = int(turn or 0)
            tsr["data_spike_ws_penalty_source"] = ability_name
            tsr["data_spike_ws_penalty_expires_phase"] = "FIGHT_PHASE"
            target_root.special_rules = tsr
            if callable(append_action) and player is not None:
                append_action(
                    player,
                    f"{ability_name}: {getattr(target_root, 'name', 'Unit')} suffers {int(total_mw)} mortal wounds and melee Weapon Skill is worsened by {int(ws_penalty)} until end of phase.",
                )
            return target_root
    if str(ctx.get("ability", "") or "") == "boon_of_death":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            try:
                source_root = source_unit.get_attached_unit_root()
            except Exception:
                source_root = source_unit
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            try:
                player = getattr(getattr(source_root, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Boon of Death").strip() or "Boon of Death"
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["boon_of_death_active"] = True
            sr["boon_of_death_owner"] = owner_id
            sr["boon_of_death_turn"] = int(turn or 0)
            sr["boon_of_death_source"] = ability_name
            sr["boon_of_death_threshold"] = 2
            sr["boon_of_death_expires_phase"] = "FIGHT_PHASE"
            target_root.special_rules = sr
            try:
                mark_used = getattr(source_root, "mark_lord_of_death_guard_used", None)
                if callable(mark_used):
                    mark_used(game=game, ability_name=ability_name)
            except Exception:
                pass
            try:
                _log_action_for_players(
                    game,
                    player,
                    f"{ability_name}: {getattr(target_root, 'name', 'Unit')} can fight on death on 2+ this phase.",
                )
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "inflamed_reprisal":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            try:
                source_root = source_unit.get_attached_unit_root()
            except Exception:
                source_root = source_unit
            try:
                chosen_root = chosen.get_attached_unit_root()
            except Exception:
                chosen_root = chosen
            attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id"))
            try:
                attacker_root = attacker_unit.get_attached_unit_root() if attacker_unit is not None else None
            except Exception:
                attacker_root = attacker_unit
            if attacker_root is None:
                return None
            try:
                player = getattr(getattr(source_root, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            ability_name = str(ctx.get("ability_name", "") or "Inflamed Reprisal").strip() or "Inflamed Reprisal"
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            pending = getattr(game, "_inflamed_reprisal_pending", None)
            if not isinstance(pending, list):
                pending = []
            entry = {
                "turn": int(turn or 0),
                "source_unit_id": str(get_entity_id(source_root) or ""),
                "selected_unit_id": str(get_entity_id(chosen_root) or ""),
                "attacker_unit_id": str(get_entity_id(attacker_root) or ""),
                "ability_name": ability_name,
            }
            duplicate = False
            for existing in list(pending or []):
                if not isinstance(existing, dict):
                    continue
                if str(existing.get("turn", "")) != str(entry.get("turn", "")):
                    continue
                if str(existing.get("source_unit_id", "")) != str(entry.get("source_unit_id", "")):
                    continue
                if str(existing.get("selected_unit_id", "")) != str(entry.get("selected_unit_id", "")):
                    continue
                if str(existing.get("attacker_unit_id", "")) != str(entry.get("attacker_unit_id", "")):
                    continue
                duplicate = True
                break
            if not duplicate:
                pending.append(entry)
            game._inflamed_reprisal_pending = pending
            try:
                mark_used = getattr(source_root, "mark_lord_of_death_guard_used", None)
                if callable(mark_used):
                    mark_used(game=game, ability_name=ability_name)
            except Exception:
                pass
            try:
                _log_action_for_players(
                    game,
                    player,
                    f"{ability_name}: {getattr(chosen_root, 'name', 'Unit')} will shoot after {getattr(attacker_root, 'name', 'Unit')} finishes its attacks.",
                )
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "diseased_influence":
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
        if source_unit is not None and chosen is not None:
            try:
                source_root = source_unit.get_attached_unit_root()
            except Exception:
                source_root = source_unit
            try:
                chosen_root = chosen.get_attached_unit_root()
            except Exception:
                chosen_root = chosen
            moving_unit = resolve_unit(game, ctx.get("moving_unit_id"))
            try:
                player = getattr(getattr(source_root, "get_parent_army", lambda: None)(), "player", None)
            except Exception:
                player = None
            ability_name = str(ctx.get("ability_name", "") or "Diseased Influence").strip() or "Diseased Influence"
            try:
                queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
                if callable(queue_move):
                    queue_move(
                        player=player,
                        unit=chosen_root,
                        max_distance=5,
                        kind="diseased_influence",
                        movement_type="reactive",
                        source=ability_name,
                        moving_unit=moving_unit,
                        allow_skip=True,
                    )
            except Exception:
                pass
            try:
                mark_used = getattr(source_root, "mark_lord_of_death_guard_used", None)
                if callable(mark_used):
                    mark_used(game=game, ability_name=ability_name)
            except Exception:
                pass
            try:
                _log_action_for_players(
                    game,
                    player,
                    f"{ability_name}: {getattr(chosen_root, 'name', 'Unit')} can make a Normal move of up to 5\".",
                )
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "misfortune":
        if chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("attacker_unit_id") or ctx.get("unit_id"))
            try:
                player = getattr(source_unit.get_parent_army(), "player", None) if source_unit is not None else None
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Misfortune").strip() or "Misfortune"
            try:
                penalty = int(ctx.get("penalty", -1) or -1)
            except Exception:
                penalty = -1
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["misfortune_active"] = True
            sr["misfortune_owner"] = owner_id
            sr["misfortune_turn"] = int(turn or 0)
            sr["misfortune_source"] = ability_name
            sr["misfortune_penalty"] = int(penalty or -1)
            sr["misfortune_selected_owner"] = owner_id
            sr["misfortune_selected_turn"] = int(turn or 0)
            target_root.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {tname} suffers {int(penalty)} to wound.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "nurgles_rot":
        if chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("attacker_unit_id") or ctx.get("unit_id"))
            try:
                player = getattr(source_unit.get_parent_army(), "player", None) if source_unit is not None else None
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            ability_name = str(ctx.get("ability_name", "") or "Nurgle's Rot").strip() or "Nurgle's Rot"
            try:
                penalty = int(ctx.get("penalty", -1) or -1)
            except Exception:
                penalty = -1
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["nurgles_rot_active"] = True
            sr["nurgles_rot_owner"] = owner_id
            sr["nurgles_rot_turn"] = int(turn or 0)
            sr["nurgles_rot_source"] = ability_name
            sr["nurgles_rot_penalty"] = int(penalty or -1)
            target_root.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {tname} suffers {int(penalty)} Toughness.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "piratical_raiders":
        if chosen is not None:
            source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("attacker_unit_id") or ctx.get("unit_id"))
            if source_unit is None:
                return None
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            ability_name = str(ctx.get("ability_name", "") or "Piratical Raiders").strip() or "Piratical Raiders"
            target_id = str(get_entity_id(target_root) or "")
            sr = getattr(source_unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["piratical_raiders_target_id"] = target_id
            sr["piratical_raiders_source"] = ability_name
            source_unit.special_rules = sr
            try:
                player = getattr(source_unit.get_parent_army(), "player", None)
            except Exception:
                player = None
            try:
                sname = str(getattr(source_unit, "name", "Unit") or "Unit")
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{ability_name}: {sname} selected {tname} as quarry.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "post_shoot_snare":
        if chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id"))
            try:
                player = getattr(attacker_unit.get_parent_army(), "player", None) if attacker_unit is not None else None
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            source = str(ctx.get("ability_name", "") or "Snared").strip() or "Snared"
            weapon_key = str(ctx.get("weapon_key", "") or "").strip()
            weapon_name = str(ctx.get("weapon_name", "") or "").strip()
            apply_fn = getattr(target_root, "apply_snared", None)
            if callable(apply_fn):
                apply_fn(
                    owner_id=owner_id,
                    turn=turn,
                    source=source,
                    weapon_key=weapon_key,
                    weapon_name=weapon_name,
                )
            else:
                sr = getattr(target_root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["snared_active"] = True
                sr["snared_owner"] = owner_id
                sr["snared_turn"] = int(turn or 0)
                sr["snared_source"] = source
                sr["snared_weapon_key"] = weapon_key
                sr["snared_weapon_name"] = weapon_name
                target_root.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{source}: {tname} is snared until your next turn.")
            except Exception:
                pass
    if str(ctx.get("ability", "") or "") == "post_shoot_pinned":
        if chosen is not None:
            try:
                target_root = chosen.get_attached_unit_root()
            except Exception:
                target_root = chosen
            attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id"))
            try:
                player = getattr(attacker_unit.get_parent_army(), "player", None) if attacker_unit is not None else None
            except Exception:
                player = None
            owner_id = str(getattr(player, "id", "") or "")
            try:
                turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                turn = 0
            source = str(ctx.get("ability_name", "") or "Pinned").strip() or "Pinned"
            try:
                move_penalty = int(ctx.get("move_penalty", -2) or -2)
            except Exception:
                move_penalty = -2
            try:
                charge_penalty = int(ctx.get("charge_penalty", -2) or -2)
            except Exception:
                charge_penalty = -2
            apply_fn = getattr(target_root, "apply_pinned", None)
            if callable(apply_fn):
                apply_fn(
                    owner_id=owner_id,
                    turn=turn,
                    source=source,
                    move_penalty=int(move_penalty),
                    charge_penalty=int(charge_penalty),
                )
            else:
                sr = getattr(target_root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["pinned_active"] = True
                sr["pinned_owner"] = owner_id
                sr["pinned_turn"] = int(turn or 0)
                sr["pinned_source"] = source
                sr["pinned_move_penalty"] = int(move_penalty)
                sr["pinned_charge_penalty"] = int(charge_penalty)
                target_root.special_rules = sr
            try:
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{source}: {tname} is pinned until your next turn.")
            except Exception:
                pass
    if ctx.get("necrons_command_phase_enhancement"):
        army = _resolve_army(game, request, payload)
        mgr = getattr(army, "necrons_detachments", None) if army is not None else None
        if mgr is not None and hasattr(mgr, "spec_from_context"):
            spec = mgr.spec_from_context(ctx)
            source_unit = resolve_unit(game, ctx.get("source_unit_id"))
            if source_unit is not None and chosen is not None and spec is not None:
                try:
                    mgr.apply_command_phase_bearer_effect(source_unit, chosen, spec)
                except Exception:
                    pass
    ability_key = str(ctx.get("ability", "") or "")
    if ability_key == "oath_of_moment":
        army = _resolve_army(game, request, payload)
        mgr = getattr(army, "oath_of_moment", None) if army is not None else None
        if mgr is not None and chosen is not None:
            try:
                mgr.set_target(chosen)
            except Exception:
                pass
            try:
                player = getattr(army, "player", None)
                tname = str(getattr(chosen, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"Oath of Moment: selected {tname} as target.")
            except Exception:
                pass
    if ability_key == "bondsman":
        army = _resolve_army(game, request, payload)
        mgr = getattr(army, "bondsman", None) if army is not None else None
        source_unit = resolve_unit(game, ctx.get("source_unit_id"))
        if mgr is not None and source_unit is not None and chosen is not None:
            try:
                mgr.apply_bondsman_effects(source_unit, chosen)
            except Exception:
                pass
            try:
                player = getattr(army, "player", None)
                sname = str(getattr(source_unit, "name", "Unit") or "Unit")
                tname = str(getattr(chosen, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"Bondsman: {sname} -> {tname}")
            except Exception:
                pass
    return chosen


def _validate_post_shoot_battleshock_target(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    target_val = payload.get("unit_id") or payload.get("target_unit_id")
    if not target_val:
        return ("Post-shoot Battle-shock requires target unit.",)
    if resolve_unit(game, target_val) is None:
        return ("Post-shoot Battle-shock target not found.",)
    return ()


def _apply_post_shoot_battleshock_target(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    target_unit = resolve_unit(game, payload.get("unit_id") or payload.get("target_unit_id"))
    if target_unit is None:
        raise RuntimeError("Post-shoot Battle-shock target not found.")
    ctx = dict(getattr(request, "context", {}) or {})
    ability_name = str(ctx.get("ability_name", "") or payload.get("ability_name", "") or "Post-shoot Battle-shock").strip()
    modifier = None
    try:
        modifier = payload.get("battle_shock_test_modifier", ctx.get("battle_shock_test_modifier"))
        if modifier is not None:
            modifier = int(modifier)
    except Exception:
        modifier = None
    if modifier:
        sr = getattr(target_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current = int(sr.get("battle_shock_test_modifier", 0) or 0)
        sr["battle_shock_test_modifier"] = current + int(modifier)
        if ability_name:
            reasons = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
            reasons.append(ability_name)
            sr["battle_shock_test_modifier_reasons"] = reasons
        target_unit.special_rules = sr
    turn = int(getattr(game, "turn", 0) or 0)
    try:
        target_unit.take_battle_shock_test(turn)
    except Exception:
        pass
    attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id") or payload.get("attacker_unit_id"))
    model = resolve_model(game, ctx.get("model_id") or payload.get("model_id"))
    model_name = str(getattr(model, "name", "") or "") if model is not None else ""
    if not model_name and attacker_unit is not None:
        model_name = str(getattr(attacker_unit, "name", "") or "")
    if not model_name:
        model_name = "Model"
    player = _resolve_player(game, request, payload)
    if player is None and attacker_unit is not None:
        try:
            player = attacker_unit.get_parent_army().player
        except Exception:
            player = None
    try:
        from ...utility.event_bus import append_action
        if player is not None:
            append_action(player, f"{model_name} used {ability_name} on {target_unit.name}")
    except Exception:
        pass
    return target_unit


def _validate_start_shooting_battleshock_target(
    game: object, request: DecisionRequest, result: DecisionResult
) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    target_val = payload.get("unit_id") or payload.get("target_unit_id")
    if not target_val:
        return ("Start of Shooting phase Battle-shock requires target unit.",)
    if resolve_unit(game, target_val) is None:
        return ("Start of Shooting phase Battle-shock target not found.",)
    return ()


def _apply_start_shooting_battleshock_target(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    target_unit = resolve_unit(game, payload.get("unit_id") or payload.get("target_unit_id"))
    if target_unit is None:
        raise RuntimeError("Start of Shooting phase Battle-shock target not found.")
    ctx = dict(getattr(request, "context", {}) or {})
    ability_name = str(
        ctx.get("ability_name", "") or payload.get("ability_name", "") or "Start of Shooting phase Battle-shock"
    ).strip()
    turn = int(getattr(game, "turn", 0) or 0)
    use_leadership_test = bool(ctx.get("use_leadership_test", payload.get("use_leadership_test", False)))
    leadership_test_passed = None
    mortal_applied = 0
    if use_leadership_test:
        source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id") or payload.get("source_unit_id"))
        try:
            fail_mortal_wounds = int(ctx.get("fail_mortal_wounds", payload.get("fail_mortal_wounds", 0)) or 0)
        except Exception:
            fail_mortal_wounds = 0
        try:
            test_modifier = int(
                ctx.get(
                    "leadership_test_modifier_if_battle_shocked",
                    payload.get("leadership_test_modifier_if_battle_shocked", 0),
                )
                or 0
            )
        except Exception:
            test_modifier = 0
        try:
            target_is_battle_shocked = bool(target_unit.is_battle_shocked())
        except Exception:
            target_is_battle_shocked = False

        temp_keys = (
            "post_shoot_leadership_debuff_active",
            "post_shoot_leadership_debuff_owner",
            "post_shoot_leadership_debuff_turn",
            "post_shoot_leadership_debuff_value",
            "post_shoot_leadership_debuff_source",
        )
        previous_temp: dict[str, object] = {}
        sr = getattr(target_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        inject_temp_modifier = bool(target_is_battle_shocked and test_modifier)
        if inject_temp_modifier:
            for key in temp_keys:
                if key in sr:
                    previous_temp[key] = sr.get(key)
            sr["post_shoot_leadership_debuff_active"] = True
            sr["post_shoot_leadership_debuff_owner"] = ""
            sr["post_shoot_leadership_debuff_turn"] = int(turn or 0)
            sr["post_shoot_leadership_debuff_value"] = int(test_modifier)
            sr["post_shoot_leadership_debuff_source"] = ability_name
            target_unit.special_rules = sr

        try:
            pass_check = getattr(target_unit, "pass_leadership_check", None)
            if callable(pass_check):
                leadership_test_passed = bool(pass_check())
            else:
                from ...utility.dice import get_roll

                roll = int(get_roll("2D6") or 0)
                leadership = int(getattr(target_unit, "leadership", 0) or 0)
                modified_roll = int(roll + (int(test_modifier) if target_is_battle_shocked else 0))
                leadership_test_passed = bool(modified_roll <= leadership)
        finally:
            if inject_temp_modifier:
                sr_restore = getattr(target_unit, "special_rules", None)
                if not isinstance(sr_restore, dict):
                    sr_restore = {}
                for key in temp_keys:
                    if key in previous_temp:
                        sr_restore[key] = previous_temp[key]
                    else:
                        sr_restore.pop(key, None)
                target_unit.special_rules = sr_restore

        if leadership_test_passed is False and int(fail_mortal_wounds or 0) > 0:
            if source_unit is not None:
                apply_mortals = getattr(source_unit, "_apply_mortal_wounds_to_unit", None)
                if callable(apply_mortals):
                    apply_mortals(target_unit, int(fail_mortal_wounds), game_map=getattr(game, "map", None))
                    mortal_applied = int(fail_mortal_wounds)
    else:
        try:
            target_unit.take_battle_shock_test(turn)
        except Exception:
            pass
    model = resolve_model(game, ctx.get("model_id") or payload.get("model_id"))
    model_name = str(getattr(model, "name", "") or "") if model is not None else ""
    if not model_name:
        model_name = "Model"
    player = _resolve_player(game, request, payload)
    try:
        from ...utility.event_bus import append_action

        if player is not None:
            if use_leadership_test:
                outcome = "passed" if leadership_test_passed else "failed"
                if mortal_applied > 0:
                    append_action(
                        player,
                        f"{model_name} used {ability_name} on {target_unit.name} (Leadership test {outcome}; {int(mortal_applied)} mortal wounds).",
                    )
                else:
                    append_action(
                        player,
                        f"{model_name} used {ability_name} on {target_unit.name} (Leadership test {outcome}).",
                    )
            else:
                append_action(player, f"{model_name} used {ability_name} on {target_unit.name}")
    except Exception:
        pass
    return target_unit


def _validate_battleshock_clear_target(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    target_val = payload.get("unit_id") or payload.get("target_unit_id")
    if not target_val:
        return ("Battle-shock clear requires target unit.",)
    if resolve_unit(game, target_val) is None:
        return ("Battle-shock clear target not found.",)
    return ()


def _apply_battleshock_clear_target(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    target_unit = resolve_unit(game, payload.get("unit_id") or payload.get("target_unit_id"))
    if target_unit is None:
        raise RuntimeError("Battle-shock clear target not found.")
    ctx = dict(getattr(request, "context", {}) or {})
    source_unit = resolve_unit(game, ctx.get("source_unit_id") or ctx.get("unit_id"))
    ability_name = str(ctx.get("ability_name", "") or payload.get("ability_name", "") or "Battle-shock clear").strip()
    ability_key = str(ctx.get("ability_key", "") or "start_any_phase_clear_battleshock").strip().lower()
    cleared = False
    try:
        if target_unit.is_battle_shocked():
            target_unit.clear_battle_shock()
            cleared = True
    except Exception:
        cleared = False
    if cleared and source_unit is not None:
        try:
            source_unit.mark_unit_once_per_battle_used(ability_key, ability_name=ability_name)
        except Exception:
            pass
    try:
        from ...utility.event_bus import append_action
        player = _resolve_player(game, request, payload)
        if player is None and source_unit is not None:
            player = getattr(source_unit.get_parent_army(), "player", None)
        if player is not None:
            label = "cleared Battle-shock" if cleared else "could not clear Battle-shock"
            append_action(player, f"{ability_name}: {getattr(target_unit, 'name', 'Unit')} {label}.")
    except Exception:
        pass
    return target_unit


def _validate_post_shoot_mortal_wounds_target(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    target_val = payload.get("unit_id") or payload.get("target_unit_id")
    if not target_val:
        return ("Post-shoot mortal wounds requires target unit.",)
    if resolve_unit(game, target_val) is None:
        return ("Post-shoot mortal wounds target not found.",)
    return ()


def _apply_post_shoot_mortal_wounds_target(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    target_unit = resolve_unit(game, payload.get("unit_id") or payload.get("target_unit_id"))
    if target_unit is None:
        raise RuntimeError("Post-shoot mortal wounds target not found.")
    ctx = dict(getattr(request, "context", {}) or {})
    ability_name = str(ctx.get("ability_name", "") or payload.get("ability_name", "") or "Post-shoot Mortals").strip()
    dice_count = int(ctx.get("dice", 3) or 3)
    threshold = int(ctx.get("threshold", 4) or 4)
    mortal_per = int(ctx.get("mortal_per_success", 1) or 1)
    if dice_count <= 0 or threshold <= 0 or mortal_per <= 0:
        return target_unit

    from ...utility.dice import get_roll

    rolls = []
    successes = 0
    for _ in range(dice_count):
        r = int(get_roll("D6") or 0)
        rolls.append(r)
        if r >= threshold:
            successes += 1
    total_mw = int(successes * mortal_per)

    attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id") or payload.get("attacker_unit_id"))
    if total_mw > 0 and attacker_unit is not None:
        try:
            attacker_unit._apply_mortal_wounds_to_unit(target_unit, total_mw, game_map=getattr(game, "map", None))
        except Exception:
            pass
        try:
            if hasattr(target_unit, "is_alive") and not target_unit.is_alive():
                return target_unit
        except Exception:
            pass
        try:
            target_unit.take_battle_shock_test(int(getattr(game, "turn", 0) or 0))
        except Exception:
            pass

    player = _resolve_player(game, request, payload)
    if player is None and attacker_unit is not None:
        try:
            player = attacker_unit.get_parent_army().player
        except Exception:
            player = None
    model = resolve_model(game, ctx.get("model_id") or payload.get("model_id"))
    model_name = str(getattr(model, "name", "") or "") if model is not None else ""
    if not model_name and attacker_unit is not None:
        model_name = str(getattr(attacker_unit, "name", "") or "")
    if not model_name:
        model_name = "Model"
    try:
        from ...utility.event_bus import append_action, append_dice
        if player is not None:
            append_dice(
                player,
                f"{ability_name}: rolls {rolls} => {int(total_mw)} mortal wounds to {getattr(target_unit, 'name', 'Target')}.",
            )
            append_action(
                player,
                f"{ability_name}: {model_name} dealt {int(total_mw)} mortal wounds to {getattr(target_unit, 'name', 'Target')}.",
            )
    except Exception:
        pass

    return target_unit


def _validate_post_shoot_wracked_agonies_target(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    target_val = payload.get("unit_id") or payload.get("target_unit_id")
    if not target_val:
        return ("Wracking Agonies requires target unit.",)
    if resolve_unit(game, target_val) is None:
        return ("Wracking Agonies target not found.",)
    return ()


def _apply_post_shoot_wracked_agonies_target(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    target_unit = resolve_unit(game, payload.get("unit_id") or payload.get("target_unit_id"))
    if target_unit is None:
        raise RuntimeError("Wracking Agonies target not found.")
    ctx = dict(getattr(request, "context", {}) or {})
    ability_name = str(ctx.get("ability_name", "") or payload.get("ability_name", "") or "Wracking Agonies").strip()
    try:
        move_penalty = int(ctx.get("move_penalty", -2) or -2)
    except Exception:
        move_penalty = -2
    try:
        charge_penalty = int(ctx.get("charge_penalty", -2) or -2)
    except Exception:
        charge_penalty = -2
    turn = int(getattr(game, "turn", 0) or 0)

    attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id") or payload.get("attacker_unit_id"))
    player = _resolve_player(game, request, payload)
    if player is None and attacker_unit is not None:
        try:
            player = attacker_unit.get_parent_army().player
        except Exception:
            player = None
    owner_id = str(getattr(player, "id", "") or "")

    apply_fn = getattr(target_unit, "apply_wracked_with_agonies", None)
    if callable(apply_fn):
        apply_fn(
            owner_id=owner_id,
            turn=turn,
            source=ability_name,
            move_penalty=move_penalty,
            charge_penalty=charge_penalty,
        )
    else:
        sr = getattr(target_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["wracked_with_agonies_active"] = True
        sr["wracked_with_agonies_owner"] = owner_id
        sr["wracked_with_agonies_turn"] = int(turn or 0)
        sr["wracked_with_agonies_source"] = ability_name
        sr["wracked_with_agonies_move_penalty"] = int(move_penalty or 0)
        sr["wracked_with_agonies_charge_penalty"] = int(charge_penalty or 0)
        if hasattr(target_unit, "add_characteristic_modifier"):
            from ...utility.modifiers import Modifier, ModifierOp
            target_unit.add_characteristic_modifier(
                "movement",
                Modifier(ModifierOp.ADD, int(move_penalty or 0), source="ability:wracked_with_agonies"),
            )
        mods = list(sr.get("charge_roll_modifiers", []) or [])
        mods.append(
            {
                "value": int(charge_penalty or 0),
                "source": ability_name,
                "tag": "ability:wracked_with_agonies",
            }
        )
        sr["charge_roll_modifiers"] = mods
        target_unit.special_rules = sr

    if player is not None:
        from ...utility.event_bus import append_action
        append_action(player, f"{ability_name}: {getattr(target_unit, 'name', 'Unit')} is wracked with agonies.")
    return target_unit


def _validate_post_shoot_aflame_target(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    target_val = payload.get("unit_id") or payload.get("target_unit_id")
    if not target_val:
        return ("Post-shoot aflame requires target unit.",)
    if resolve_unit(game, target_val) is None:
        return ("Post-shoot aflame target not found.",)
    return ()


def _apply_post_shoot_aflame_target(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    target_unit = resolve_unit(game, payload.get("unit_id") or payload.get("target_unit_id"))
    if target_unit is None:
        raise RuntimeError("Post-shoot aflame target not found.")
    ctx = dict(getattr(request, "context", {}) or {})
    ability_name = str(ctx.get("ability_name", "") or payload.get("ability_name", "") or "Aflame").strip()
    def _int_or(value, default: int) -> int:
        if value is None:
            return int(default)
        try:
            return int(value)
        except Exception:
            return int(default)

    move_penalty = _int_or(ctx.get("move_penalty", -2), -2)
    advance_penalty = _int_or(ctx.get("advance_penalty", -2), -2)
    charge_penalty = _int_or(ctx.get("charge_penalty", advance_penalty), int(advance_penalty))
    threshold = _int_or(ctx.get("roll_threshold", 4), 4)

    attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id") or payload.get("attacker_unit_id"))
    model = resolve_model(game, ctx.get("model_id") or payload.get("model_id"))
    model_name = str(getattr(model, "name", "") or "") if model is not None else ""
    if not model_name and attacker_unit is not None:
        model_name = str(getattr(attacker_unit, "name", "") or "")
    if not model_name:
        model_name = "Model"

    player = _resolve_player(game, request, payload)
    if player is None and attacker_unit is not None:
        try:
            player = attacker_unit.get_parent_army().player
        except Exception:
            player = None
    owner_id = str(getattr(player, "id", "") or "")
    turn = int(getattr(game, "turn", 0) or 0)

    battleshock_on_fail = bool(
        ctx.get("battleshock_on_fail")
        or ctx.get("battle_shock_on_fail")
        or payload.get("battleshock_on_fail")
        or payload.get("battle_shock_on_fail")
    )
    if battleshock_on_fail:
        root = target_unit
        try:
            root = target_unit.get_attached_unit_root()
        except Exception:
            root = target_unit
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["aflame_on_battleshock_pending"] = True
        sr["aflame_on_battleshock_owner"] = owner_id
        sr["aflame_on_battleshock_turn"] = int(turn or 0)
        sr["aflame_on_battleshock_source"] = ability_name
        sr["aflame_on_battleshock_move_penalty"] = int(move_penalty or 0)
        sr["aflame_on_battleshock_advance_penalty"] = int(advance_penalty or 0)
        sr["aflame_on_battleshock_charge_penalty"] = int(charge_penalty or 0)
        root.special_rules = sr
        try:
            target_unit.take_battle_shock_test(turn)
        except Exception:
            pass
        try:
            from ...utility.event_bus import append_action
            if player is not None:
                append_action(player, f"{ability_name}: {getattr(target_unit, 'name', 'Unit')} takes a Battle-shock test.")
        except Exception:
            pass
        return target_unit

    from ...utility.dice import get_roll
    roll = int(get_roll("D6") or 0)
    success = bool(roll >= int(threshold))

    try:
        from ...utility.event_bus import append_action, append_dice
        if player is not None:
            append_dice(
                player,
                f"{ability_name}: rolled {roll} (needs {int(threshold)}+).",
            )
    except Exception:
        append_action = None

    if not success:
        if player is not None and append_action is not None:
            append_action(player, f"{ability_name}: {getattr(target_unit, 'name', 'Unit')} is not aflame.")
        return target_unit

    root = target_unit
    try:
        root = target_unit.get_attached_unit_root()
    except Exception:
        root = target_unit

    apply_fn = getattr(root, "apply_aflame", None)
    if callable(apply_fn):
        apply_fn(
            owner_id=owner_id,
            turn=turn,
            source=ability_name,
            move_penalty=move_penalty,
            advance_penalty=advance_penalty,
            charge_penalty=charge_penalty,
        )
    else:
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["aflame_active"] = True
        sr["aflame_owner"] = owner_id
        sr["aflame_turn"] = int(turn or 0)
        sr["aflame_source"] = ability_name
        sr["aflame_move_penalty"] = int(move_penalty or 0)
        sr["aflame_advance_penalty"] = int(advance_penalty or 0)
        sr["aflame_charge_penalty"] = int(charge_penalty or 0)
        if hasattr(root, "add_characteristic_modifier"):
            from ...utility.modifiers import Modifier, ModifierOp
            root.add_characteristic_modifier(
                "movement",
                Modifier(ModifierOp.ADD, int(move_penalty or 0), source="ability:aflame"),
            )
        adv_mods = list(sr.get("advance_roll_modifiers", []) or [])
        adv_mods.append(
            {
                "value": int(advance_penalty or 0),
                "source": ability_name,
                "tag": "ability:aflame",
            }
        )
        sr["advance_roll_modifiers"] = adv_mods
        charge_mods = list(sr.get("charge_roll_modifiers", []) or [])
        charge_mods.append(
            {
                "value": int(charge_penalty or 0),
                "source": ability_name,
                "tag": "ability:aflame",
            }
        )
        sr["charge_roll_modifiers"] = charge_mods
        root.special_rules = sr

    if player is not None and append_action is not None:
        append_action(
            player,
            f"{ability_name}: {getattr(root, 'name', 'Unit')} is aflame until end of your opponent's next turn.",
        )
    return target_unit


def _validate_post_shoot_suppression_target(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    target_val = payload.get("unit_id") or payload.get("target_unit_id")
    if not target_val:
        return ("Post-shoot suppression requires target unit.",)
    if resolve_unit(game, target_val) is None:
        return ("Post-shoot suppression target not found.",)
    return ()


def _validate_post_shoot_leadership_debuff_target(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    target_val = payload.get("unit_id") or payload.get("target_unit_id")
    if not target_val:
        return ("Post-shoot Leadership debuff requires target unit.",)
    if resolve_unit(game, target_val) is None:
        return ("Post-shoot Leadership debuff target not found.",)
    return ()


def _apply_post_shoot_suppression_target(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    target_unit = resolve_unit(game, payload.get("unit_id") or payload.get("target_unit_id"))
    if target_unit is None:
        raise RuntimeError("Post-shoot suppression target not found.")
    ctx = dict(getattr(request, "context", {}) or {})
    ability_name = str(ctx.get("ability_name", "") or payload.get("ability_name", "") or "Suppressed").strip()
    attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id") or payload.get("attacker_unit_id"))
    model = resolve_model(game, ctx.get("model_id") or payload.get("model_id"))
    model_name = str(getattr(model, "name", "") or "") if model is not None else ""
    if not model_name and attacker_unit is not None:
        model_name = str(getattr(attacker_unit, "name", "") or "")
    if not model_name:
        model_name = "Model"
    player = _resolve_player(game, request, payload)
    if player is None and attacker_unit is not None:
        try:
            player = attacker_unit.get_parent_army().player
        except Exception:
            player = None
    owner_id = str(getattr(player, "id", "") or "")
    current_turn = int(getattr(game, "turn", 0) or 0)

    root = target_unit
    try:
        root = target_unit.get_attached_unit_root()
    except Exception:
        root = target_unit
    try:
        members = list(root.get_attached_unit_members() or [])
    except Exception:
        members = []
    if not members:
        members = [root]

    for unit in members:
        if unit is None:
            continue
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["post_shoot_suppressed_active"] = True
        sr["post_shoot_suppressed_owner"] = owner_id
        sr["post_shoot_suppressed_turn"] = int(current_turn)
        unit.special_rules = sr

    try:
        from ...utility.event_bus import append_action
        if player is not None:
            append_action(player, f"{model_name} suppressed {target_unit.name} ({ability_name})")
    except Exception:
        pass
    return target_unit


def _validate_choose_unleash_hell_vehicle(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    target_val = payload.get("unit_id") or payload.get("target_unit_id")
    if not target_val:
        return ("Unleash Hell requires a target unit.",)
    target_unit = resolve_unit(game, target_val)
    if target_unit is None:
        return ("Unleash Hell target not found.",)
    if not getattr(target_unit, "is_alive", lambda: True)():
        return ("Unleash Hell target must be alive.",)
    if not (getattr(target_unit, "is_vehicle", False) or getattr(target_unit, "is_transport", False)):
        return ("Unleash Hell target must be a Vehicle or Transport.",)

    ctx = dict(getattr(request, "context", {}) or {})
    allowed_ids = ctx.get("allowed_unit_ids")
    if isinstance(allowed_ids, (list, tuple, set)):
        allowed = {str(x or "") for x in allowed_ids if str(x or "")}
        if allowed and str(target_val) not in allowed:
            return ("Unleash Hell target is not eligible.",)

    transport_id = str(ctx.get("transport_id", "") or "")
    if transport_id:
        if str(target_val) != transport_id:
            return ("Unleash Hell target must be the bearer transport.",)
        return ()

    bearer_id = str(ctx.get("bearer_model_id", "") or "")
    if bearer_id:
        bearer_model = resolve_model(game, bearer_id)
        if bearer_model is None:
            return ("Unleash Hell bearer model not found.",)
        try:
            range_in = float(ctx.get("range", 0) or 0)
        except Exception:
            range_in = 0.0
        if range_in <= 0:
            range_in = 6.0
        try:
            models = list(target_unit.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(target_unit, "models", []) or [])
        in_range = False
        from ...utility.aura_utils import distance_between_models_bases_3d
        for model in list(models or []):
            try:
                if not getattr(model, "is_alive", False):
                    continue
            except Exception:
                continue
            if distance_between_models_bases_3d(bearer_model, model) <= range_in + 1e-6:
                in_range = True
                break
        if not in_range:
            return ("Unleash Hell target is out of range.",)
    return ()


def _apply_choose_unleash_hell_vehicle(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    target_unit = resolve_unit(game, payload.get("unit_id") or payload.get("target_unit_id"))
    if target_unit is None:
        raise RuntimeError("Unleash Hell requires a target unit.")
    ctx = dict(getattr(request, "context", {}) or {})
    ability_name = str(ctx.get("ability_name", "") or "Unleash Hell").strip() or "Unleash Hell"
    source_unit_id = ctx.get("source_unit_id")
    source_unit = resolve_unit(game, source_unit_id)
    player = _resolve_player(game, request, payload)
    if player is None and source_unit is not None:
        try:
            player = source_unit.get_parent_army().player
        except Exception:
            player = None
    owner_id = str(getattr(player, "id", "") or "")
    try:
        current_turn = int(getattr(game, "turn", 0) or 0)
    except Exception:
        current_turn = 0
    if not (getattr(target_unit, "is_vehicle", False) or getattr(target_unit, "is_transport", False)):
        raise RuntimeError("Unleash Hell target must be a Vehicle or Transport.")
    sr = getattr(target_unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    sr["unleash_hell_active"] = True
    sr["unleash_hell_owner"] = owner_id
    sr["unleash_hell_turn"] = int(current_turn)
    sr["unleash_hell_source"] = ability_name
    if source_unit_id:
        sr["unleash_hell_source_unit_id"] = str(source_unit_id)
    sr["unleash_hell_expires_phase"] = "SHOOTING_PHASE"
    sr["unleash_hell_consumed"] = False
    sr["unleash_hell_exclude_monster_vehicle"] = bool(ctx.get("exclude_monster_vehicle", False))
    target_unit.special_rules = sr
    try:
        if player is not None:
            sname = str(getattr(source_unit, "name", "Unit") or "Unit")
            tname = str(getattr(target_unit, "name", "Unit") or "Unit")
            _log_action_for_players(game, player, f"Unleash Hell: {sname} empowered {tname}.")
    except Exception:
        pass
    return target_unit


def _apply_post_shoot_leadership_debuff_target(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    target_unit = resolve_unit(game, payload.get("unit_id") or payload.get("target_unit_id"))
    if target_unit is None:
        raise RuntimeError("Post-shoot Leadership debuff target not found.")
    ctx = dict(getattr(request, "context", {}) or {})
    ability_name = (
        str(ctx.get("ability_name", "") or payload.get("ability_name", "") or "Post-shoot Leadership debuff").strip()
    )
    attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id") or payload.get("attacker_unit_id"))
    player = _resolve_player(game, request, payload)
    if player is None and attacker_unit is not None:
        try:
            player = attacker_unit.get_parent_army().player
        except Exception:
            player = None
    owner_id = str(getattr(player, "id", "") or "")
    current_turn = int(getattr(game, "turn", 0) or 0)

    root = target_unit
    try:
        root = target_unit.get_attached_unit_root()
    except Exception:
        root = target_unit
    try:
        members = list(root.get_attached_unit_members() or [])
    except Exception:
        members = []
    if not members:
        members = [root]

    for unit in members:
        if unit is None:
            continue
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current_val = 0
        if bool(sr.get("post_shoot_leadership_debuff_active")):
            current_owner = str(sr.get("post_shoot_leadership_debuff_owner", "") or "")
            if not current_owner or not owner_id or current_owner == owner_id:
                try:
                    current_val = int(sr.get("post_shoot_leadership_debuff_value", 0) or 0)
                except Exception:
                    current_val = 0
        sr["post_shoot_leadership_debuff_active"] = True
        sr["post_shoot_leadership_debuff_owner"] = owner_id
        sr["post_shoot_leadership_debuff_turn"] = int(current_turn)
        sr["post_shoot_leadership_debuff_value"] = int(current_val) - 1
        sr["post_shoot_leadership_debuff_source"] = ability_name
        unit.special_rules = sr

    try:
        from ...utility.event_bus import append_action
        if player is not None:
            append_action(player, f"{getattr(attacker_unit, 'name', 'Unit')} applied {ability_name} to {target_unit.name}")
    except Exception:
        pass
    return target_unit


def _validate_daemonic_poisons_target(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    payload = _option_payload(request, result)
    target_val = payload.get("unit_id") or payload.get("target_unit_id")
    if not target_val:
        return ("Daemonic Poisons requires target unit.",)
    if resolve_unit(game, target_val) is None:
        return ("Daemonic Poisons target not found.",)
    return ()


def _apply_daemonic_poisons_target(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    target_unit = resolve_unit(game, payload.get("unit_id") or payload.get("target_unit_id"))
    if target_unit is None:
        raise RuntimeError("Daemonic Poisons target not found.")
    ctx = dict(getattr(request, "context", {}) or {})
    ability_name = str(ctx.get("ability_name", "") or payload.get("ability_name", "") or "Daemonic Poisons").strip()
    attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id") or payload.get("attacker_unit_id"))
    model = resolve_model(game, ctx.get("model_id") or payload.get("model_id"))
    player = _resolve_player(game, request, payload)
    if player is None and attacker_unit is not None:
        try:
            player = attacker_unit.get_parent_army().player
        except Exception:
            player = None

    from ...rules.daemonic_poisons import apply_daemonic_poisons

    apply_daemonic_poisons(
        target_unit,
        source_unit=attacker_unit,
        ability_name=ability_name,
        game=game,
        player=player,
    )

    model_name = str(getattr(model, "name", "") or "") if model is not None else ""
    if not model_name and attacker_unit is not None:
        model_name = str(getattr(attacker_unit, "name", "") or "")
    if not model_name:
        model_name = "Model"
    _log_action_for_players(game, player, f"{model_name} poisoned {target_unit.name} ({ability_name}).")
    return target_unit


def _validate_discard_secondary(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    return validate_option_choice(request, result)


def _apply_discard_secondary(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    card = payload.get("card", payload.get("secondary"))
    if card is not None:
        return card
    name = payload.get("card_name") or payload.get("name")
    if not name:
        return None
    player = _resolve_player(game, request, payload)
    if player is None:
        return None
    cards = list(getattr(player, "active_secondaries", []) or [])
    for card_obj in cards:
        if str(getattr(card_obj, "name", "") or "") == str(name):
            return card_obj
    return None


def _validate_choose_shadow_form(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id") or payload.get("unit")
    choice = payload.get("choice_key") or payload.get("key")
    if unit_val is None or choice is None:
        return ("Shadow Form requires unit_id and key.",)
    if resolve_unit(game, unit_val) is None:
        return ("Shadow Form unit not found.",)
    return ()


def _apply_choose_shadow_form(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    from ...rules.shadow_form import set_active_shadow_form

    payload = _option_payload(request, result)
    unit = resolve_unit(game, payload.get("unit_id") or payload.get("unit"))
    if unit is None:
        raise RuntimeError("Shadow Form unit not found.")
    choice = payload.get("choice_key") or payload.get("key")
    battle_round = request.context.get("battle_round")
    if battle_round is None and game is not None:
        battle_round = getattr(game, "turn", 0)
    set_active_shadow_form(unit, str(choice), battle_round=int(battle_round or 0))
    try:
        player = getattr(getattr(unit, "get_parent_army", lambda: None)(), "player", None)
    except Exception:
        player = None
    try:
        label = _option_label(request, result) or str(choice)
        uname = str(getattr(unit, "name", "Unit") or "Unit")
        if label:
            _log_action_for_players(game, player, f"Shadow Form: {uname} selected {label} (Battle Round {battle_round})")
    except Exception:
        pass
    return str(choice)


def _validate_choose_vow(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    choice = payload.get("choice_key") or payload.get("key")
    if choice is None:
        return ("Templar Vow requires key.",)
    army = _resolve_army(game, request, payload)
    if army is None or getattr(army, "templar_vows", None) is None:
        return ("Templar Vows manager not found.",)
    return ()


def _apply_choose_vow(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Templar Vows army not found.")
    mgr = getattr(army, "templar_vows", None)
    if mgr is None:
        raise RuntimeError("Templar Vows manager not found.")
    choice = payload.get("choice_key") or payload.get("key")
    mgr.active_vow_key = str(choice).strip().upper()
    try:
        player = getattr(army, "player", None)
        label = _option_label(request, result) or str(choice)
        if label:
            _log_action_for_players(game, player, f"Templar Vows: {label}")
    except Exception:
        pass
    return mgr.active_vow_key


def _validate_issue_order(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    payload = _option_payload(request, result)
    if is_skip_choice(request, result):
        return ()
    officer_val = payload.get("officer_unit_id") or payload.get("officer_unit") or request.context.get("officer_unit_id")
    target_val = result.payload.get("target_unit_id") or payload.get("target_unit_id") or payload.get("target_unit")
    order_key = payload.get("order_key") or payload.get("key") or result.payload.get("order_key")
    if officer_val is None or target_val is None or order_key is None:
        return ("Voice of Command requires officer_unit_id, target_unit_id, and order_key.",)
    if resolve_unit(game, officer_val) is None or resolve_unit(game, target_val) is None:
        return ("Voice of Command units not found.",)
    army = _resolve_army(game, request, payload)
    if army is None or getattr(army, "voice_of_command", None) is None:
        return ("Voice of Command manager not found.",)
    return ()


def _apply_issue_order(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    if is_skip_choice(request, result):
        return None
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Voice of Command army not found.")
    mgr = getattr(army, "voice_of_command", None)
    if mgr is None:
        raise RuntimeError("Voice of Command manager not found.")
    officer = resolve_unit(game, payload.get("officer_unit_id") or payload.get("officer_unit") or request.context.get("officer_unit_id"))
    target = resolve_unit(game, result.payload.get("target_unit_id") or payload.get("target_unit_id") or payload.get("target_unit"))
    order_key = payload.get("order_key") or payload.get("key") or result.payload.get("order_key")
    phase_name = str(payload.get("phase_name", "") or request.context.get("phase_name", "") or "")
    return bool(mgr.issue_order(game, officer, target, str(order_key), phase_name=phase_name))


def _validate_choose_wrathful(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id") or payload.get("unit")
    choice = payload.get("choice_key") or payload.get("key")
    if unit_val is None or choice is None:
        return ("Wrathful Presence requires unit_id and key.",)
    if resolve_unit(game, unit_val) is None:
        return ("Wrathful Presence unit not found.",)
    return ()


def _apply_choose_wrathful(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    from ...rules.wrathful_presence import set_active_wrathful_presence

    payload = _option_payload(request, result)
    unit = resolve_unit(game, payload.get("unit_id") or payload.get("unit"))
    if unit is None:
        raise RuntimeError("Wrathful Presence unit not found.")
    choice = payload.get("choice_key") or payload.get("key")
    battle_round = request.context.get("battle_round")
    if battle_round is None and game is not None:
        battle_round = getattr(game, "turn", 0)
    set_active_wrathful_presence(unit, str(choice), battle_round=int(battle_round or 0))
    try:
        player = getattr(getattr(unit, "get_parent_army", lambda: None)(), "player", None)
    except Exception:
        player = None
    try:
        label = _option_label(request, result) or str(choice)
        uname = str(getattr(unit, "name", "Unit") or "Unit")
        if label:
            _log_action_for_players(game, player, f"Wrathful Presence: {uname} selected {label} (Battle Round {battle_round})")
    except Exception:
        pass
    return str(choice)


def _validate_choose_daemon_primarch_slaanesh(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id") or payload.get("unit")
    choice = payload.get("choice_key") or payload.get("key")
    if unit_val is None or choice is None:
        return ("Daemon Primarch of Slaanesh requires unit_id and key.",)
    if resolve_unit(game, unit_val) is None:
        return ("Daemon Primarch unit not found.",)
    return ()


def _apply_choose_daemon_primarch_slaanesh(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    from ...rules.daemon_primarch_slaanesh import set_active_daemon_primarch_slaanesh

    payload = _option_payload(request, result)
    unit = resolve_unit(game, payload.get("unit_id") or payload.get("unit"))
    if unit is None:
        raise RuntimeError("Daemon Primarch unit not found.")
    choice = payload.get("choice_key") or payload.get("key")
    start_round = request.context.get("battle_round")
    if start_round is None and game is not None:
        start_round = getattr(game, "turn", 0)
    expires_round = request.context.get("expires_round")
    if expires_round is None:
        try:
            expires_round = int(start_round or 0) + 1
        except Exception:
            expires_round = 0
    opponent_player_id = request.context.get("opponent_player_id")
    set_active_daemon_primarch_slaanesh(
        unit,
        str(choice),
        start_round=int(start_round or 0),
        expires_round=int(expires_round or 0),
        opponent_player_id=opponent_player_id,
    )
    try:
        player = getattr(getattr(unit, "get_parent_army", lambda: None)(), "player", None)
    except Exception:
        player = None
    try:
        label = _option_label(request, result) or str(choice)
        uname = str(getattr(unit, "name", "Unit") or "Unit")
        until_txt = f"until opponent Command phase (BR {expires_round})" if expires_round else "until opponent Command phase"
        if label:
            _log_action_for_players(game, player, f"Daemon Primarch of Slaanesh: {uname} selected {label} ({until_txt})")
    except Exception:
        pass
    return str(choice)


def _validate_choose_warmaster_ability(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id") or payload.get("unit")
    choice = payload.get("choice_key") or payload.get("key")
    if unit_val is None or choice is None:
        return ("Warmaster selection requires unit_id and key.",)
    if resolve_unit(game, unit_val) is None:
        return ("Warmaster unit not found.",)
    return ()


def _apply_choose_warmaster_ability(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    from ...rules.csm_warmaster import set_active_warmaster

    payload = _option_payload(request, result)
    unit = resolve_unit(game, payload.get("unit_id") or payload.get("unit"))
    if unit is None:
        raise RuntimeError("Warmaster unit not found.")
    choice = payload.get("choice_key") or payload.get("key")
    start_round = request.context.get("battle_round")
    if start_round is None and game is not None:
        start_round = getattr(game, "turn", 0)
    expires_round = request.context.get("expires_round")
    if expires_round is None:
        try:
            expires_round = int(start_round or 0) + 1
        except Exception:
            expires_round = 0
    player_id = request.context.get("player_id")
    set_active_warmaster(
        unit,
        str(choice),
        start_round=int(start_round or 0),
        expires_round=int(expires_round or 0),
        player_id=str(player_id or ""),
    )
    try:
        player = getattr(getattr(unit, "get_parent_army", lambda: None)(), "player", None)
    except Exception:
        player = None
    try:
        label = _option_label(request, result) or str(choice)
        uname = str(getattr(unit, "name", "Unit") or "Unit")
        until_txt = f"until next Command phase (BR {expires_round})" if expires_round else "until next Command phase"
        if label:
            _log_action_for_players(game, player, f"The Warmaster: {uname} selected {label} ({until_txt})")
    except Exception:
        pass
    return str(choice)


def _validate_choose_aspect(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    if is_skip_choice(request, result):
        return ()
    return validate_option_choice(request, result)


def _apply_choose_aspect(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    return payload.get("choice")


def _validate_use_leading_unmodified_six(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    ability_key = payload.get("ability_key") or request.context.get("ability_key")
    if not ability_key:
        return ("Leading unmodified-six choice requires ability_key.",)
    return ()


def _apply_use_leading_unmodified_six(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    return payload


def _validate_use_model_unmodified_six(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    return _validate_use_leading_unmodified_six(game, request, result)


def _apply_use_model_unmodified_six(game: object, request: DecisionRequest, result: DecisionResult):
    return _apply_use_leading_unmodified_six(game, request, result)


def _validate_choose_battle_focus_maneuver(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id") or request.context.get("unit_id")
    choice = payload.get("choice_key") or payload.get("choice")
    if unit_val is None or choice is None:
        return ("Battle Focus maneuver requires unit_id and choice.",)
    if resolve_unit(game, unit_val) is None:
        return ("Battle Focus unit not found.",)
    return ()


def _apply_choose_battle_focus_maneuver(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    unit = resolve_unit(game, payload.get("unit_id") or request.context.get("unit_id"))
    if unit is None:
        raise RuntimeError("Battle Focus unit not found.")
    army = getattr(unit, "get_parent_army", lambda: None)()
    mgr = getattr(army, "battle_focus", None) if army is not None else None
    if mgr is None:
        raise RuntimeError("Battle Focus manager not found.")
    choice = payload.get("choice_key") or payload.get("choice")
    applied = bool(mgr.apply_maneuver(unit, str(choice), game))
    try:
        player = getattr(army, "player", None)
        label = _option_label(request, result) or str(choice)
        if label:
            uname = str(getattr(unit, "name", "Unit") or "Unit")
            _log_action_for_players(game, player, f"Battle Focus: {uname} used {label}.")
    except Exception:
        pass
    return applied


def _validate_choose_power_from_pain_option(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id") or request.context.get("unit_id")
    choice_kind = payload.get("choice_kind") or request.context.get("choice_kind")
    choice = payload.get("choice_key") or payload.get("choice")
    if unit_val is None or choice_kind is None or choice is None:
        return ("Power from Pain choice requires unit_id, choice_kind, and choice.",)
    if resolve_unit(game, unit_val) is None:
        return ("Power from Pain unit not found.",)
    return ()


def _apply_choose_power_from_pain_option(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    unit = resolve_unit(game, payload.get("unit_id") or request.context.get("unit_id"))
    if unit is None:
        raise RuntimeError("Power from Pain unit not found.")
    army = getattr(unit, "get_parent_army", lambda: None)()
    mgr = getattr(army, "power_from_pain", None) if army is not None else None
    if mgr is None:
        raise RuntimeError("Power from Pain manager not found.")
    choice_kind = payload.get("choice_kind") or request.context.get("choice_kind")
    choice = payload.get("choice_key") or payload.get("choice")
    pending_key = request.context.get("pending_key") or payload.get("pending_key")
    if pending_key:
        try:
            mgr.record_empowerment_choice(pending_key=str(pending_key), choice_kind=str(choice_kind), choice=str(choice), game=game)
        except Exception:
            pass
    return str(choice)


def _validate_choose_malefic_surge_unit(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id") or request.context.get("unit_id")
    if unit_val is None:
        return ("Malefic Surge choice requires unit_id.",)
    unit = resolve_unit(game, unit_val)
    if unit is None:
        return ("Malefic Surge unit not found.",)
    army = getattr(unit, "get_parent_army", lambda: None)()
    mgr = getattr(army, "chaos_knights_detachments", None) if army is not None else None
    if mgr is None or not getattr(mgr, "is_infernal_lance", lambda: False)():
        return ("Malefic Surge requires Infernal Lance detachment.",)
    if not getattr(mgr, "can_unit_malefic_surge", lambda *_a, **_k: False)(unit, game=game):
        return ("Unit is not eligible to make a Malefic Surge.",)
    return ()


def _apply_choose_malefic_surge_unit(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    unit = resolve_unit(game, payload.get("unit_id") or request.context.get("unit_id"))
    player = resolve_player(game, getattr(request, "player_id", None))
    army = getattr(unit, "get_parent_army", lambda: None)() if unit is not None else None
    mgr = getattr(army, "chaos_knights_detachments", None) if army is not None else None
    if mgr is None:
        raise RuntimeError("Malefic Surge manager not found.")
    if is_skip_choice(request, result):
        mgr.record_declined(player=player, game=game)
        return None
    if unit is None:
        raise RuntimeError("Malefic Surge unit not found.")
    mgr.apply_malefic_surge(unit, game=game)
    if player is None:
        player = getattr(army, "player", None)
    try:
        mgr.prompt_malefic_surge_selection(game=game, player=player)
    except Exception:
        pass
    return get_entity_id(unit)


def _validate_choose_malefic_surge_ability(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id") or request.context.get("unit_id")
    choice = payload.get("choice") or payload.get("choice_key") or payload.get("key")
    trigger = request.context.get("trigger") or payload.get("trigger")
    if unit_val is None or not choice or not trigger:
        return ("Malefic Surge ability choice requires unit_id, choice, and trigger.",)
    unit = resolve_unit(game, unit_val)
    if unit is None:
        return ("Malefic Surge unit not found.",)
    army = getattr(unit, "get_parent_army", lambda: None)()
    mgr = getattr(army, "chaos_knights_detachments", None) if army is not None else None
    if mgr is None or not getattr(mgr, "is_infernal_lance", lambda: False)():
        return ("Malefic Surge requires Infernal Lance detachment.",)
    if not getattr(mgr, "is_unit_empowered", lambda *_a, **_k: False)(unit, game=game):
        return ("Unit is not Empowered for Malefic Surge.",)
    trigger_key = str(trigger or "").strip().lower()
    choice_key = str(choice or "").strip().upper()
    if trigger_key == "movement" and choice_key != "UNHOLY_HUNGER":
        return ("Movement trigger requires Unholy Hunger choice.",)
    if trigger_key in ("shooting", "fight") and choice_key not in ("LETHAL_HITS", "SUSTAINED_HITS_1"):
        return ("Diabolic Power choice must be Lethal Hits or Sustained Hits 1.",)
    if trigger_key in ("targeted_shooting", "targeted_fight") and choice_key not in ("INVULN_5", "FNP_6"):
        return ("Unnatural Fortitude choice must be invulnerable save or Feel No Pain.",)
    return ()


def _apply_choose_malefic_surge_ability(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    unit = resolve_unit(game, payload.get("unit_id") or request.context.get("unit_id"))
    if unit is None:
        raise RuntimeError("Malefic Surge unit not found.")
    army = getattr(unit, "get_parent_army", lambda: None)()
    mgr = getattr(army, "chaos_knights_detachments", None) if army is not None else None
    if mgr is None:
        raise RuntimeError("Malefic Surge manager not found.")
    if is_skip_choice(request, result):
        try:
            mgr.clear_pending_choice(unit)
        except Exception:
            pass
        return None
    choice = payload.get("choice") or payload.get("choice_key") or payload.get("key")
    trigger = request.context.get("trigger") or payload.get("trigger")
    if not getattr(mgr, "apply_malefic_surge_choice", None):
        raise RuntimeError("Malefic Surge apply hook missing.")
    applied = bool(mgr.apply_malefic_surge_choice(unit, trigger=str(trigger), choice=str(choice), game=game))
    try:
        mgr.clear_pending_choice(unit)
    except Exception:
        pass
    return applied


def _validate_select_setup_reactive_target(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    target_val = payload.get("unit_id") or payload.get("target_unit_id")
    if target_val is None:
        return ("Setup reactive target requires unit_id.",)
    if resolve_unit(game, target_val) is None:
        return ("Setup reactive target unit not found.",)
    return ()


def _apply_select_setup_reactive_target(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    return resolve_unit(game, payload.get("unit_id") or payload.get("target_unit_id"))


def _validate_choose_setup_reactive_action(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    action = str(payload.get("action", "") or payload.get("choice", "") or payload.get("value", ""))
    if action not in ("shoot", "charge"):
        return ("Setup reactive action requires 'shoot' or 'charge'.",)
    return ()


def _apply_choose_setup_reactive_action(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    return str(payload.get("action", "") or payload.get("choice", "") or payload.get("value", ""))


def _validate_select_rise_to_challenge(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id") or payload.get("unit")
    if unit_val is None:
        return ("Rise to the Challenge selection requires unit_id.",)
    if resolve_unit(game, unit_val) is None:
        return ("Rise to the Challenge unit not found.",)
    return ()


def _apply_select_rise_to_challenge(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    return resolve_unit(game, payload.get("unit_id") or payload.get("unit"))


def _validate_select_reverberating_summons_unit(
    game: object,
    request: DecisionRequest,
    result: DecisionResult,
) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    unit_val = payload.get("unit_id") or payload.get("unit")
    if unit_val is None:
        return ("Reverberating Summons selection requires unit_id.",)
    if resolve_unit(game, unit_val) is None:
        return ("Reverberating Summons unit not found.",)
    return ()


def _apply_select_reverberating_summons_unit(
    game: object,
    request: DecisionRequest,
    result: DecisionResult,
):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    return resolve_unit(game, payload.get("unit_id") or payload.get("unit"))


def _validate_choose_hit_modifier_ignores(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    ctx = dict(getattr(request, "context", {}) or {})
    seq_id = ctx.get("sequence_id")
    attack_index = ctx.get("attack_index")
    if seq_id is None or attack_index is None:
        return ()
    mgr = getattr(game, "attack_manager", None)
    if mgr is None:
        return ("Attack manager not found.",)
    try:
        seq = mgr.sequences.get(int(seq_id))
    except Exception:
        seq = None
    if seq is None:
        return ("Attack sequence not found.",)
    try:
        idx = int(attack_index)
    except Exception:
        return ("Attack index must be an integer.",)
    modifier_kind = str(ctx.get("modifier_kind", "") or "").strip().lower()
    if modifier_kind == "wound_roll":
        instances = list(getattr(seq, "hit_instances", []) or [])
    else:
        instances = list(getattr(seq, "attack_instances", []) or [])
    if idx < 0 or idx >= len(instances):
        return ("Attack index out of range.",)
    return ()


def _apply_choose_hit_modifier_ignores(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    choice = payload.get("choice")
    if choice is None:
        choice = result.payload.get("choice")
    if choice is None:
        choice = _option_label(request, result) or "keep_all"
    ctx = dict(getattr(request, "context", {}) or {})
    seq_id = ctx.get("sequence_id")
    attack_index = ctx.get("attack_index")
    modifier_kind = str(ctx.get("modifier_kind", "") or "").strip().lower()
    if seq_id is not None and attack_index is not None:
        mgr = getattr(game, "attack_manager", None)
        if mgr is not None:
            try:
                seq = mgr.sequences.get(int(seq_id))
            except Exception:
                seq = None
            if seq is not None:
                try:
                    idx = int(attack_index)
                except Exception:
                    idx = None
                if idx is not None:
                    if modifier_kind == "wound_roll":
                        instances = list(getattr(seq, "hit_instances", []) or [])
                    else:
                        instances = list(getattr(seq, "attack_instances", []) or [])
                    if 0 <= idx < len(instances):
                        try:
                            if modifier_kind == "wound_roll":
                                instances[idx]["wound_modifier_choice"] = choice
                            else:
                                instances[idx]["hit_modifier_choice"] = choice
                        except Exception:
                            pass
                        try:
                            if modifier_kind == "wound_roll":
                                resume = getattr(mgr, "resume_after_wound_modifier_choice", None)
                            else:
                                resume = getattr(mgr, "resume_after_hit_modifier_choice", None)
                            if callable(resume):
                                resume(game, seq)
                        except Exception:
                            pass
    return choice


def _validate_choose_skill_modifier_ignores(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    return _validate_choose_hit_modifier_ignores(game, request, result)


def _apply_choose_skill_modifier_ignores(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    choice = payload.get("choice")
    if choice is None:
        choice = result.payload.get("choice")
    if choice is None:
        choice = _option_label(request, result) or "keep_all"
    ctx = dict(getattr(request, "context", {}) or {})
    seq_id = ctx.get("sequence_id")
    attack_index = ctx.get("attack_index")
    if seq_id is not None and attack_index is not None:
        mgr = getattr(game, "attack_manager", None)
        if mgr is not None:
            try:
                seq = mgr.sequences.get(int(seq_id))
            except Exception:
                seq = None
            if seq is not None:
                try:
                    idx = int(attack_index)
                except Exception:
                    idx = None
                if idx is not None:
                    instances = list(getattr(seq, "attack_instances", []) or [])
                    if 0 <= idx < len(instances):
                        try:
                            instances[idx]["skill_modifier_choice"] = choice
                        except Exception:
                            pass
                        try:
                            resume = getattr(mgr, "resume_after_skill_modifier_choice", None)
                            if callable(resume):
                                resume(game, seq)
                        except Exception:
                            pass
    return choice


def _validate_choose_move_modifier_ignores(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    ctx = dict(getattr(request, "context", {}) or {})
    unit_id = ctx.get("unit_id") or _option_payload(request, result).get("unit_id")
    if not unit_id:
        return ("Move modifier choice requires unit_id.",)
    if resolve_unit(game, unit_id) is None:
        return ("Move modifier unit not found.",)
    return ()


def _apply_choose_move_modifier_ignores(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    choice = payload.get("choice")
    if choice is None:
        choice = result.payload.get("choice")
    if choice is None:
        choice = _option_label(request, result) or "keep_all"
    ctx = dict(getattr(request, "context", {}) or {})
    unit_id = ctx.get("unit_id") or payload.get("unit_id")
    unit = resolve_unit(game, unit_id)
    if unit is None:
        return choice
    try:
        unit.round_state.move_modifier_choice = choice
        unit.round_state.move_modifier_choice_pending = False
    except Exception:
        pass
    return choice


def _validate_choose_advance_modifier_ignores(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    ctx = dict(getattr(request, "context", {}) or {})
    unit_id = ctx.get("unit_id") or _option_payload(request, result).get("unit_id")
    if not unit_id:
        return ("Advance modifier choice requires unit_id.",)
    if resolve_unit(game, unit_id) is None:
        return ("Advance modifier unit not found.",)
    return ()


def _apply_choose_advance_modifier_ignores(game: object, request: DecisionRequest, result: DecisionResult):
    from ...utility.modifier_choice import filter_signed_modifiers

    payload = _option_payload(request, result)
    choice = payload.get("choice")
    if choice is None:
        choice = result.payload.get("choice")
    if choice is None:
        choice = _option_label(request, result) or "keep_all"
    ctx = dict(getattr(request, "context", {}) or {})
    unit_id = ctx.get("unit_id") or payload.get("unit_id")
    unit = resolve_unit(game, unit_id)
    if unit is None:
        return choice
    try:
        unit.round_state.advance_modifier_choice = choice
    except Exception:
        pass
    base_roll = None
    try:
        base_roll = int(getattr(unit.round_state, "advance_roll_unmodified", 0) or 0)
    except Exception:
        base_roll = None
    if base_roll is None or base_roll <= 0:
        try:
            base_roll = int(getattr(unit.round_state, "advance_roll", 0) or 0)
        except Exception:
            base_roll = 0
    mods = []
    try:
        mods = list(unit._collect_advance_roll_modifiers() or [])
    except Exception:
        mods = []
    try:
        filt = getattr(unit, "_filter_internal_rivalries_roll_modifiers", None)
        if callable(filt):
            mods = filt(mods, kind="advance")
    except Exception:
        pass
    try:
        filt = getattr(unit, "_filter_bestial_aspect_roll_modifiers", None)
        if callable(filt):
            mods = filt(mods, kind="advance")
    except Exception:
        pass
    kept_mods, _ignored = filter_signed_modifiers(mods, str(choice or "keep_all"))
    total = int(base_roll or 0)
    for val, _source in kept_mods:
        try:
            total += int(val)
        except Exception:
            continue
    try:
        unit.round_state.advance_roll = int(total)
        unit.round_state.advance_modifier_choice = choice
        unit.round_state.advance_modifier_choice_pending = False
        unit.round_state.advance_roll_unmodified = None
    except Exception:
        pass
    try:
        player = unit.get_parent_army().player
    except Exception:
        player = None
    try:
        event_system = getattr(game, "event_system", None)
        if event_system is not None:
            event_system.publish(
                "roll_made",
                player=player,
                unit=unit,
                roll_type="advance",
                value=int(total),
                reroll=None,
                dice=None,
            )
    except Exception:
        pass
    return choice


def _validate_choose_charge_modifier_ignores(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    ctx = dict(getattr(request, "context", {}) or {})
    unit_id = ctx.get("unit_id") or _option_payload(request, result).get("unit_id")
    if not unit_id:
        return ("Charge modifier choice requires unit_id.",)
    if resolve_unit(game, unit_id) is None:
        return ("Charge modifier unit not found.",)
    return ()


def _apply_choose_charge_modifier_ignores(game: object, request: DecisionRequest, result: DecisionResult):
    payload = _option_payload(request, result)
    choice = payload.get("choice")
    if choice is None:
        choice = result.payload.get("choice")
    if choice is None:
        choice = _option_label(request, result) or "keep_all"
    ctx = dict(getattr(request, "context", {}) or {})
    unit_id = ctx.get("unit_id") or payload.get("unit_id")
    unit = resolve_unit(game, unit_id)
    if unit is None:
        return choice
    try:
        unit.round_state.charge_modifier_choice = choice
        unit.round_state.charge_modifier_choice_pending = False
    except Exception:
        pass
    target_unit_ids = list(ctx.get("target_unit_ids", []) or [])
    try:
        if not target_unit_ids:
            target_unit_ids = list(getattr(unit.round_state, "charge_modifier_choice_targets", []) or [])
    except Exception:
        pass
    try:
        player = unit.get_parent_army().player
    except Exception:
        player = None
    try:
        event_system = getattr(game, "event_system", None)
        if event_system is not None:
            event_system.publish(
                "roll_made",
                player=player,
                unit=unit,
                roll_type="charge",
                value=int(getattr(unit.round_state, "charge_roll", 0) or 0),
                reroll=None,
                dice=None,
                target_unit_ids=target_unit_ids,
            )
    except Exception:
        pass
    return choice


register_decision_handler(DECISION_CHOOSE_BLESSINGS, validate=_validate_choose_blessings, apply=_apply_choose_blessings)
register_decision_handler(DECISION_CHOOSE_BLOOD_TITHE, validate=_validate_choose_blood_tithe, apply=_apply_choose_blood_tithe)
register_decision_handler(DECISION_CHOOSE_IDOL_OF_KHORNE, validate=_validate_choose_idol_of_khorne, apply=_apply_choose_idol_of_khorne)
register_decision_handler(
    DECISION_SELECT_VESSEL_OF_WRATH_MODELS,
    validate=_validate_select_vessel_of_wrath_models,
    apply=_apply_select_vessel_of_wrath_models,
)
register_decision_handler(
    DECISION_SELECT_REALM_OF_CHAOS_UNITS,
    validate=_validate_select_realm_of_chaos_units,
    apply=_apply_select_realm_of_chaos_units,
)
register_decision_handler(
    DECISION_CHOOSE_VESSEL_OF_WRATH_BLESSING,
    validate=_validate_choose_vessel_of_wrath_blessing,
    apply=_apply_choose_vessel_of_wrath_blessing,
)
register_decision_handler(DECISION_CHOOSE_RITUALS, validate=_validate_choose_ritual, apply=_apply_choose_ritual)
register_decision_handler(DECISION_CHOOSE_CHIVALRIC_OATH, validate=_validate_choose_chivalric, apply=_apply_choose_chivalric)
register_decision_handler(
    DECISION_CHOOSE_DAEMONIC_ALLEGIANCE,
    validate=_validate_choose_daemonic_allegiance,
    apply=_apply_choose_daemonic_allegiance,
)
register_decision_handler(DECISION_CHOOSE_DARK_PACT, validate=_validate_choose_dark_pact, apply=_apply_choose_dark_pact)
register_decision_handler(DECISION_CHOOSE_DOCTRINA, validate=_validate_choose_doctrina, apply=_apply_choose_doctrina)
register_decision_handler(
    DECISION_CHOOSE_COMBAT_DOCTRINE,
    validate=_validate_choose_combat_doctrine,
    apply=_apply_choose_combat_doctrine,
)
register_decision_handler(
    DECISION_CHOOSE_GRAND_COVEN,
    validate=_validate_choose_grand_coven,
    apply=_apply_choose_grand_coven,
)
register_decision_handler(
    DECISION_CHOOSE_COMBAT_DRUGS,
    validate=_validate_choose_combat_drugs,
    apply=_apply_choose_combat_drugs,
)
register_decision_handler(
    DECISION_CHOOSE_HYPER_ADAPTATION,
    validate=_validate_choose_hyper_adaptation,
    apply=_apply_choose_hyper_adaptation,
)
register_decision_handler(DECISION_CHOOSE_FRENZY_TARGET, validate=_validate_choose_frenzy, apply=_apply_choose_frenzy)
register_decision_handler(DECISION_CHOOSE_HARBINGER, validate=_validate_choose_harbinger, apply=_apply_choose_harbinger)
register_decision_handler(DECISION_CHOOSE_MARTIAL_KATAH, validate=_validate_choose_martial_katah, apply=_apply_choose_martial_katah)
register_decision_handler(DECISION_CHOOSE_MOMENT_SHACKLE, validate=_validate_choose_moment_shackle, apply=_apply_choose_moment_shackle)
register_decision_handler(DECISION_CHOOSE_PATH_OF_WARRIOR, validate=_validate_choose_path_of_warrior, apply=_apply_choose_path_of_warrior)
register_decision_handler(DECISION_CHOOSE_CRUEL_AMUSEMENT, validate=_validate_choose_cruel_amusement, apply=_apply_choose_cruel_amusement)
register_decision_handler(DECISION_CHOOSE_MASTER_OF_MAGICKS, validate=_validate_choose_master_of_magicks, apply=_apply_choose_master_of_magicks)
register_decision_handler(DECISION_CHOOSE_HARBINGER_OF_DEATH, validate=_validate_choose_harbinger_of_death, apply=_apply_choose_harbinger_of_death)
register_decision_handler(DECISION_CHOOSE_DANCE_OF_DEATH, validate=_validate_choose_dance_of_death, apply=_apply_choose_dance_of_death)
register_decision_handler(DECISION_CHOOSE_LIMB_FROM_LIMB, validate=_validate_choose_limb_from_limb, apply=_apply_choose_limb_from_limb)
register_decision_handler(DECISION_CHOOSE_RED_WRATH, validate=_validate_choose_red_wrath, apply=_apply_choose_red_wrath)
register_decision_handler(DECISION_USE_MIRACLE_DIE, validate=_validate_use_miracle_die, apply=_apply_use_miracle_die)
register_decision_handler(DECISION_CHOOSE_PLAGUE, validate=_validate_choose_plague, apply=_apply_choose_plague)
register_decision_handler(
    DECISION_CHOOSE_START_OF_BATTLE_KEYWORD,
    validate=_validate_choose_start_of_battle_keyword,
    apply=_apply_choose_start_of_battle_keyword,
)
register_decision_handler(DECISION_CHOOSE_PLEDGE, validate=_validate_choose_pledge, apply=_apply_choose_pledge)
register_decision_handler(DECISION_CHOOSE_QUARRY, validate=_validate_choose_quarry, apply=_apply_choose_quarry)
register_decision_handler(
    DECISION_CHOOSE_HYSTERICAL_FRENZY_PSYKER,
    validate=_validate_choose_hysterical_frenzy,
    apply=_apply_choose_hysterical_frenzy,
)
register_decision_handler(
    DECISION_CHOOSE_GIFT_OF_CHAOS_TARGET,
    validate=_validate_choose_gift_of_chaos_target,
    apply=_apply_choose_gift_of_chaos_target,
)
register_decision_handler(
    DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
    validate=_validate_post_shoot_battleshock_target,
    apply=_apply_post_shoot_battleshock_target,
)
register_decision_handler(
    DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET,
    validate=_validate_start_shooting_battleshock_target,
    apply=_apply_start_shooting_battleshock_target,
)
register_decision_handler(
    DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET,
    validate=_validate_battleshock_clear_target,
    apply=_apply_battleshock_clear_target,
)
register_decision_handler(
    DECISION_CHOOSE_POST_SHOOT_MORTAL_WOUNDS_TARGET,
    validate=_validate_post_shoot_mortal_wounds_target,
    apply=_apply_post_shoot_mortal_wounds_target,
)
register_decision_handler(
    DECISION_CHOOSE_POST_SHOOT_WRACKED_AGONIES_TARGET,
    validate=_validate_post_shoot_wracked_agonies_target,
    apply=_apply_post_shoot_wracked_agonies_target,
)
register_decision_handler(
    DECISION_CHOOSE_POST_SHOOT_AFLAME_TARGET,
    validate=_validate_post_shoot_aflame_target,
    apply=_apply_post_shoot_aflame_target,
)
register_decision_handler(
    DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET,
    validate=_validate_post_shoot_suppression_target,
    apply=_apply_post_shoot_suppression_target,
)
register_decision_handler(
    DECISION_SELECT_UNLEASH_HELL_VEHICLE,
    validate=_validate_choose_unleash_hell_vehicle,
    apply=_apply_choose_unleash_hell_vehicle,
)
register_decision_handler(
    DECISION_CHOOSE_POST_SHOOT_LEADERSHIP_DEBUFF_TARGET,
    validate=_validate_post_shoot_leadership_debuff_target,
    apply=_apply_post_shoot_leadership_debuff_target,
)
register_decision_handler(
    DECISION_CHOOSE_DAEMONIC_POISONS_TARGET,
    validate=_validate_daemonic_poisons_target,
    apply=_apply_daemonic_poisons_target,
)
register_decision_handler(DECISION_DISCARD_SECONDARY, validate=_validate_discard_secondary, apply=_apply_discard_secondary)
register_decision_handler(DECISION_CHOOSE_SHADOW_FORM, validate=_validate_choose_shadow_form, apply=_apply_choose_shadow_form)
register_decision_handler(DECISION_CHOOSE_VOW, validate=_validate_choose_vow, apply=_apply_choose_vow)
register_decision_handler(DECISION_ISSUE_ORDER, validate=_validate_issue_order, apply=_apply_issue_order)
register_decision_handler(
    DECISION_CHOOSE_WRATHFUL_PRESENCE,
    validate=_validate_choose_wrathful,
    apply=_apply_choose_wrathful,
)
register_decision_handler(
    DECISION_CHOOSE_DAEMON_PRIMARCH_SLAANESH,
    validate=_validate_choose_daemon_primarch_slaanesh,
    apply=_apply_choose_daemon_primarch_slaanesh,
)
register_decision_handler(
    DECISION_CHOOSE_WARMASTER_ABILITY,
    validate=_validate_choose_warmaster_ability,
    apply=_apply_choose_warmaster_ability,
)
register_decision_handler(DECISION_CHOOSE_ASPECT, validate=_validate_choose_aspect, apply=_apply_choose_aspect)
register_decision_handler(
    DECISION_USE_LEADING_UNMODIFIED_SIX,
    validate=_validate_use_leading_unmodified_six,
    apply=_apply_use_leading_unmodified_six,
)
register_decision_handler(
    DECISION_USE_MODEL_UNMODIFIED_SIX,
    validate=_validate_use_model_unmodified_six,
    apply=_apply_use_model_unmodified_six,
)
register_decision_handler(
    DECISION_CHOOSE_BATTLE_FOCUS_MANEUVER,
    validate=_validate_choose_battle_focus_maneuver,
    apply=_apply_choose_battle_focus_maneuver,
)
register_decision_handler(
    DECISION_CHOOSE_POWER_FROM_PAIN_OPTION,
    validate=_validate_choose_power_from_pain_option,
    apply=_apply_choose_power_from_pain_option,
)
register_decision_handler(
    DECISION_CHOOSE_MALEFIC_SURGE_UNIT,
    validate=_validate_choose_malefic_surge_unit,
    apply=_apply_choose_malefic_surge_unit,
)
register_decision_handler(
    DECISION_CHOOSE_MALEFIC_SURGE_ABILITY,
    validate=_validate_choose_malefic_surge_ability,
    apply=_apply_choose_malefic_surge_ability,
)
register_decision_handler(
    DECISION_SELECT_SETUP_REACTIVE_TARGET,
    validate=_validate_select_setup_reactive_target,
    apply=_apply_select_setup_reactive_target,
)
register_decision_handler(
    DECISION_CHOOSE_SETUP_REACTIVE_ACTION,
    validate=_validate_choose_setup_reactive_action,
    apply=_apply_choose_setup_reactive_action,
)
register_decision_handler(
    DECISION_SELECT_RISE_TO_CHALLENGE,
    validate=_validate_select_rise_to_challenge,
    apply=_apply_select_rise_to_challenge,
)
register_decision_handler(
    DECISION_SELECT_REVERBERATING_SUMMONS_UNIT,
    validate=_validate_select_reverberating_summons_unit,
    apply=_apply_select_reverberating_summons_unit,
)
register_decision_handler(
    DECISION_CHOOSE_HIT_MODIFIER_IGNORES,
    validate=_validate_choose_hit_modifier_ignores,
    apply=_apply_choose_hit_modifier_ignores,
)
register_decision_handler(
    DECISION_CHOOSE_SKILL_MODIFIER_IGNORES,
    validate=_validate_choose_skill_modifier_ignores,
    apply=_apply_choose_skill_modifier_ignores,
)
register_decision_handler(
    DECISION_CHOOSE_MOVE_MODIFIER_IGNORES,
    validate=_validate_choose_move_modifier_ignores,
    apply=_apply_choose_move_modifier_ignores,
)
register_decision_handler(
    DECISION_CHOOSE_ADVANCE_MODIFIER_IGNORES,
    validate=_validate_choose_advance_modifier_ignores,
    apply=_apply_choose_advance_modifier_ignores,
)
register_decision_handler(
    DECISION_CHOOSE_CHARGE_MODIFIER_IGNORES,
    validate=_validate_choose_charge_modifier_ignores,
    apply=_apply_choose_charge_modifier_ignores,
)
