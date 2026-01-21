from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import register_decision_handler
from ..decision_kinds import (
    DECISION_CHOOSE_BLESSINGS,
    DECISION_CHOOSE_BLOOD_TITHE,
    DECISION_CHOOSE_RITUALS,
    DECISION_CHOOSE_CHIVALRIC_OATH,
    DECISION_CHOOSE_DAEMONIC_ALLEGIANCE,
    DECISION_CHOOSE_DARK_PACT,
    DECISION_CHOOSE_DOCTRINA,
    DECISION_CHOOSE_FRENZY_TARGET,
    DECISION_CHOOSE_HARBINGER,
    DECISION_CHOOSE_MARTIAL_KATAH,
    DECISION_USE_MIRACLE_DIE,
    DECISION_CHOOSE_PLAGUE,
    DECISION_CHOOSE_PLEDGE,
    DECISION_CHOOSE_QUARRY,
    DECISION_DISCARD_SECONDARY,
    DECISION_CHOOSE_SHADOW_FORM,
    DECISION_CHOOSE_VOW,
    DECISION_ISSUE_ORDER,
    DECISION_CHOOSE_WRATHFUL_PRESENCE,
    DECISION_CHOOSE_ASPECT,
    DECISION_SELECT_SETUP_REACTIVE_TARGET,
    DECISION_CHOOSE_SETUP_REACTIVE_ACTION,
)
from ..decisions import DecisionRequest, DecisionResult
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
    ctx_data = dict(request.context.get("ctx") or request.context.get("roll_context") or {})
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
    return mgr.apply_choice(ctx, selected_blessing_keys=list(selected), use_reborn_in_blood=use_reborn)


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
    return bool(mgr.select_imperative(choice, battle_round=battle_round))


def _validate_choose_frenzy(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    if is_skip_choice(request, result):
        return ()
    return validate_option_choice(request, result)


def _apply_choose_frenzy(game: object, request: DecisionRequest, result: DecisionResult):
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
    if bool(payload.get("random", False)) or str(choice or "").strip().upper() == "ROLL":
        return mgr.roll_dread_abilities(battle_round=battle_round)
    return bool(mgr.select_dread_ability(choice, battle_round=battle_round))


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
    if resolve_unit(game, unit_val) is None:
        return ("Martial Ka'tah unit not found.",)
    return ()


def _apply_choose_martial_katah(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    unit = resolve_unit(game, payload.get("unit_id") or payload.get("unit"))
    if unit is None:
        raise RuntimeError("Martial Ka'tah unit not found.")
    choice = payload.get("choice_key") or payload.get("key")
    selection_kind = str(request.context.get("selection_kind", "") or payload.get("selection_kind", "") or "")
    if selection_kind == "exquisite_swordsmanship":
        unit.set_exquisite_swordsmanship_choice(str(choice))
    else:
        unit.set_martial_katah_choice(str(choice))
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
    if army is None or getattr(army, "detachment_manager", None) is None:
        return ("Emperor's Children manager not found.",)
    return ()


def _apply_choose_pledge(game: object, request: DecisionRequest, result: DecisionResult):
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    army = _resolve_army(game, request, payload)
    if army is None:
        raise RuntimeError("Emperor's Children army not found.")
    mgr = getattr(army, "detachment_manager", None)
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
    if is_skip_choice(request, result):
        return None
    payload = _option_payload(request, result)
    unit_val = payload.get("target_unit_id", payload.get("unit_id", payload.get("unit")))
    return resolve_unit(game, unit_val)


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


register_decision_handler(DECISION_CHOOSE_BLESSINGS, validate=_validate_choose_blessings, apply=_apply_choose_blessings)
register_decision_handler(DECISION_CHOOSE_BLOOD_TITHE, validate=_validate_choose_blood_tithe, apply=_apply_choose_blood_tithe)
register_decision_handler(DECISION_CHOOSE_RITUALS, validate=_validate_choose_ritual, apply=_apply_choose_ritual)
register_decision_handler(DECISION_CHOOSE_CHIVALRIC_OATH, validate=_validate_choose_chivalric, apply=_apply_choose_chivalric)
register_decision_handler(
    DECISION_CHOOSE_DAEMONIC_ALLEGIANCE,
    validate=_validate_choose_daemonic_allegiance,
    apply=_apply_choose_daemonic_allegiance,
)
register_decision_handler(DECISION_CHOOSE_DARK_PACT, validate=_validate_choose_dark_pact, apply=_apply_choose_dark_pact)
register_decision_handler(DECISION_CHOOSE_DOCTRINA, validate=_validate_choose_doctrina, apply=_apply_choose_doctrina)
register_decision_handler(DECISION_CHOOSE_FRENZY_TARGET, validate=_validate_choose_frenzy, apply=_apply_choose_frenzy)
register_decision_handler(DECISION_CHOOSE_HARBINGER, validate=_validate_choose_harbinger, apply=_apply_choose_harbinger)
register_decision_handler(DECISION_CHOOSE_MARTIAL_KATAH, validate=_validate_choose_martial_katah, apply=_apply_choose_martial_katah)
register_decision_handler(DECISION_USE_MIRACLE_DIE, validate=_validate_use_miracle_die, apply=_apply_use_miracle_die)
register_decision_handler(DECISION_CHOOSE_PLAGUE, validate=_validate_choose_plague, apply=_apply_choose_plague)
register_decision_handler(DECISION_CHOOSE_PLEDGE, validate=_validate_choose_pledge, apply=_apply_choose_pledge)
register_decision_handler(DECISION_CHOOSE_QUARRY, validate=_validate_choose_quarry, apply=_apply_choose_quarry)
register_decision_handler(DECISION_DISCARD_SECONDARY, validate=_validate_discard_secondary, apply=_apply_discard_secondary)
register_decision_handler(DECISION_CHOOSE_SHADOW_FORM, validate=_validate_choose_shadow_form, apply=_apply_choose_shadow_form)
register_decision_handler(DECISION_CHOOSE_VOW, validate=_validate_choose_vow, apply=_apply_choose_vow)
register_decision_handler(DECISION_ISSUE_ORDER, validate=_validate_issue_order, apply=_apply_issue_order)
register_decision_handler(
    DECISION_CHOOSE_WRATHFUL_PRESENCE,
    validate=_validate_choose_wrathful,
    apply=_apply_choose_wrathful,
)
register_decision_handler(DECISION_CHOOSE_ASPECT, validate=_validate_choose_aspect, apply=_apply_choose_aspect)
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
