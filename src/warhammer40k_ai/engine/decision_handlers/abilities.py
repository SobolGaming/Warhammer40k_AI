from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import register_decision_handler
from ..decision_kinds import (
    DECISION_CHOOSE_BLESSINGS,
    DECISION_CHOOSE_BLOOD_TITHE,
    DECISION_CHOOSE_IDOL_OF_KHORNE,
    DECISION_SELECT_VESSEL_OF_WRATH_MODELS,
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
    DECISION_CHOOSE_DANCE_OF_DEATH,
    DECISION_CHOOSE_LIMB_FROM_LIMB,
    DECISION_CHOOSE_RED_WRATH,
    DECISION_USE_MIRACLE_DIE,
    DECISION_CHOOSE_PLAGUE,
    DECISION_CHOOSE_PLEDGE,
    DECISION_CHOOSE_QUARRY,
    DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
    DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET,
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
    find_option,
    is_skip_choice,
    resolve_army,
    resolve_model,
    resolve_player,
    resolve_unit,
    validate_option_choice,
)


def _option_payload(request: DecisionRequest, result: DecisionResult) -> dict:
    opt = find_option(request, result.option_id)
    return dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}


def _option_label(request: DecisionRequest, result: DecisionResult) -> str:
    opt = find_option(request, result.option_id)
    if opt is None:
        return ""
    return str(getattr(opt, "label", "") or "")


def _log_action_for_players(game: object, player: object, text: str) -> None:
    if not text:
        return
    try:
        from ...utility.event_bus import append_action
    except Exception:
        return
    try:
        if player is not None:
            append_action(player, text)
    except Exception:
        pass
    if game is None:
        return
    try:
        for opp in list(getattr(game, "players", []) or []):
            if opp is None or opp is player:
                continue
            append_action(opp, text)
    except Exception:
        pass


def _resolve_player(game: object, request: DecisionRequest, payload: dict):
    player_val = payload.get("player_id", None)
    if player_val is None:
        player_val = request.player_id
    if player_val is None:
        player_val = payload.get("player", None)
    return resolve_player(game, player_val)


def _resolve_army(game: object, request: DecisionRequest, payload: dict):
    army_val = payload.get("army_id", None)
    if army_val is None:
        army_val = request.context.get("army_id")
    army = resolve_army(game, army_val)
    if army is not None:
        return army
    player = _resolve_player(game, request, payload)
    if player is None:
        return None
    try:
        return player.get_army()
    except Exception:
        return getattr(player, "army", None)


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
    if resolve_unit(game, unit_val) is None:
        return ("Dark Pact unit not found.",)
    return ()


def _apply_choose_dark_pact(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    unit = resolve_unit(game, payload.get("unit_id") or payload.get("unit"))
    if unit is None:
        raise RuntimeError("Dark Pact unit not found.")
    choice = payload.get("choice") or payload.get("choice_key") or payload.get("key")
    phase_name = str(payload.get("phase_name", "") or request.context.get("phase_name", "") or "")
    trigger = str(payload.get("trigger", "") or request.context.get("trigger", "") or "")
    apply_fn = getattr(unit, "apply_dark_pacts_choice", None)
    if not callable(apply_fn):
        raise RuntimeError("Dark Pact apply hook missing.")
    return bool(apply_fn(game, choice=str(choice), phase_name=phase_name, trigger=trigger))


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


def _validate_choose_cruel_amusement(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    if is_skip_choice(request, result):
        return ()
    payload = _option_payload(request, result)
    model_val = payload.get("model_id") or payload.get("model") or request.context.get("model_id")
    choice = payload.get("choice") or payload.get("choice_key") or payload.get("key")
    if model_val is None or not choice:
        return ("Cruel Amusement requires model_id and choice.",)
    model = resolve_model(game, model_val)
    if model is None:
        return ("Cruel Amusement model not found.",)
    choice_key = str(choice or "").strip().upper()
    if choice_key not in ("IGNORES_COVER", "PRECISION", "SUSTAINED_HITS_3"):
        return ("Cruel Amusement choice must be Ignores Cover, Precision, or Sustained Hits 3.",)
    return ()


def _apply_choose_cruel_amusement(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    model = resolve_model(game, payload.get("model_id") or payload.get("model") or request.context.get("model_id"))
    if model is None:
        raise RuntimeError("Cruel Amusement model not found.")
    choice = payload.get("choice") or payload.get("choice_key") or payload.get("key")
    choice_key = str(choice or "").strip().upper()
    keyword_map = {
        "IGNORES_COVER": ["IGNORES COVER"],
        "PRECISION": ["PRECISION"],
        "SUSTAINED_HITS_3": ["SUSTAINED HITS 3"],
    }
    keywords = keyword_map.get(choice_key)
    if not keywords:
        raise RuntimeError("Cruel Amusement choice invalid.")
    weapon_name = str(payload.get("weapon_name") or request.context.get("weapon_name") or "shrieker cannon").strip()
    ability_name = str(payload.get("ability_name") or request.context.get("ability_name") or "Cruel Amusement").strip()
    model_id = getattr(model, "id", None) or getattr(model, "_id", None)
    key = f"cruel_amusement:{model_id or ''}"
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
            "PRECISION": "Precision",
            "SUSTAINED_HITS_3": "Sustained Hits 3",
        }.get(choice_key, choice_key.title())
        _log_action_for_players(
            game,
            player,
            f"{ability_name}: {getattr(model, 'name', 'Model')} grants {label} to {weapon_name}.",
        )
    except Exception:
        pass
    return str(choice_key)


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
    if bool(payload.get("random", False)) or str(choice or "").strip().upper() == "ROLL":
        applied = mgr.roll_combat_drugs(battle_round=battle_round)
    else:
        applied = bool(mgr.select_combat_drug(choice, battle_round=battle_round))
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


def _validate_choose_quarry(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    if is_skip_choice(request, result):
        return ()
    return validate_option_choice(request, result)


def _apply_choose_quarry(game: object, request: DecisionRequest, result: DecisionResult):
    ctx = dict(getattr(request, "context", {}) or {})
    if str(ctx.get("ability", "") or "") == "aeldari_guileful_strategist":
        skipped = is_skip_choice(request, result)
        apply_fn = getattr(game, "_apply_redeploy_choice", None)
        if callable(apply_fn):
            apply_fn(request, result, skipped=skipped)
        return None
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    unit_val = payload.get("target_unit_id", payload.get("unit_id", payload.get("unit")))
    chosen = resolve_unit(game, unit_val)
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
            sr["post_shoot_no_cover_expires_phase"] = "SHOOTING_PHASE"
            sr["post_shoot_no_cover_source"] = str(ctx.get("ability_name", "") or "No Cover").strip()
            target_root.special_rules = sr
            try:
                player = None
                attacker_unit = resolve_unit(game, ctx.get("attacker_unit_id"))
                if attacker_unit is not None:
                    player = getattr(attacker_unit.get_parent_army(), "player", None)
                tname = str(getattr(target_root, "name", "Unit") or "Unit")
                _log_action_for_players(game, player, f"{sr['post_shoot_no_cover_source']}: {tname} cannot gain Benefit of Cover this phase.")
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
            append_action(player, f"{model_name} used {ability_name} on {target_unit.name}")
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
    try:
        move_penalty = int(ctx.get("move_penalty", -2) or -2)
    except Exception:
        move_penalty = -2
    try:
        advance_penalty = int(ctx.get("advance_penalty", -2) or -2)
    except Exception:
        advance_penalty = -2
    try:
        charge_penalty = int(ctx.get("charge_penalty", advance_penalty) or advance_penalty)
    except Exception:
        charge_penalty = int(advance_penalty)
    try:
        threshold = int(ctx.get("roll_threshold", 4) or 4)
    except Exception:
        threshold = 4

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
        sr["post_shoot_leadership_debuff_active"] = True
        sr["post_shoot_leadership_debuff_owner"] = owner_id
        sr["post_shoot_leadership_debuff_turn"] = int(current_turn)
        sr["post_shoot_leadership_debuff_value"] = -1
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
    if idx < 0 or idx >= len(getattr(seq, "attack_instances", []) or []):
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
                            instances[idx]["hit_modifier_choice"] = choice
                        except Exception:
                            pass
                        try:
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
