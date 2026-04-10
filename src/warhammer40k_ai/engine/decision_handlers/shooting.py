from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import register_decision_handler
from ..decision_kinds import (
    DECISION_DECLARE_FIRING_DECK,
    DECISION_DECLARE_SHOTS,
    DECISION_DEATHSTRIKE_ACTION,
    DECISION_REROLL_ROLL,
    DECISION_SELECT_OVERWATCH_SHOOTER,
    DECISION_SELECT_WEAPON,
)
from ..decisions import DecisionRequest, DecisionResult
from ._helpers import find_option, get_model, get_unit, get_wargear, validate_option_choice
import logging
logger = logging.getLogger(__name__)


def _validate_select_weapon(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or "")
    wargear_id = str(payload.get("wargear_id", "") or "")
    profile_name = str(payload.get("profile_name", "") or "")
    if not unit_id or not wargear_id or not profile_name:
        return ("Weapon selection requires unit_id, wargear_id, and profile_name.",)
    unit = get_unit(game, unit_id)
    wargear = get_wargear(game, wargear_id)
    if unit is None or wargear is None:
        return ("Weapon selection units not found.",)
    profiles = getattr(wargear, "profiles", {}) or {}
    if profile_name not in profiles:
        return ("Weapon profile not found.",)
    return ()


def _apply_select_weapon(game: object, request: DecisionRequest, result: DecisionResult):
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    return {
        "unit_id": str(payload.get("unit_id", "") or ""),
        "wargear_id": str(payload.get("wargear_id", "") or ""),
        "profile_name": str(payload.get("profile_name", "") or ""),
    }


def _validate_select_overwatch(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    if bool(result.payload.get("skipped", False)) or str(payload.get("action", "") or "") == "skip":
        return ()
    unit_id = str(payload.get("unit_id", "") or "")
    if not unit_id:
        return ("Overwatch selection requires unit_id.",)
    if get_unit(game, unit_id) is None:
        return ("Overwatch unit not found.",)
    return ()


def _apply_select_overwatch(game: object, request: DecisionRequest, result: DecisionResult):
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    if bool(result.payload.get("skipped", False)) or str(payload.get("action", "") or "") == "skip":
        return None
    return get_unit(game, str(payload.get("unit_id", "") or ""))


def _validate_declare_shots(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or request.context.get("unit_id", "") or "")
    if not unit_id:
        return ("Shooting declaration requires unit_id.",)
    unit = get_unit(game, unit_id)
    if unit is None:
        return ("Shooting unit not found.",)
    try:
        if hasattr(unit, "_formless_horror_has_pending_gate") and unit._formless_horror_has_pending_gate():
            return ("Formless Horror: Battle-shock test pending.",)
    except Exception:
        pass
    try:
        if hasattr(unit, "is_shooting_phase_ineligible") and unit.is_shooting_phase_ineligible(game):
            return ("Unit is not eligible to shoot this phase.",)
    except Exception:
        pass
    if bool(result.payload.get("skipped", False)) or str(payload.get("action", "") or "") == "skip":
        return ()
    declarations = result.payload.get("declarations")
    if not isinstance(declarations, list) or not declarations:
        return ("Shooting declaration requires declarations list.",)
    allowed_model_ids = {
        str(value or "").strip()
        for value in list(request.context.get("allowed_model_ids", []) or [])
        if str(value or "").strip()
    }
    allowed_wargear_ids = {
        str(value or "").strip()
        for value in list(request.context.get("allowed_wargear_ids", []) or [])
        if str(value or "").strip()
    }
    try:
        max_declarations = int(request.context.get("max_declarations", 0) or 0)
    except Exception:
        max_declarations = 0
    if max_declarations > 0 and len(declarations) > max_declarations:
        return (f"Shooting declaration allows at most {int(max_declarations)} declaration(s).",)
    ctan_profiles = []
    force_target_id = str(request.context.get("force_target_unit_id", "") or "")
    if not force_target_id:
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("persecution_prospect_guerrilla_active")):
            target_id = str(sr.get("persecution_prospect_guerrilla_target_unit_id", "") or "")
            owner_id = str(sr.get("persecution_prospect_guerrilla_turn_owner", "") or "")
            try:
                marked_turn = int(sr.get("persecution_prospect_guerrilla_turn", 0) or 0)
            except Exception:
                marked_turn = 0
            try:
                current_turn = int(getattr(game, "turn", 0) or 0)
            except Exception:
                current_turn = 0
            current_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            current_owner = ""
            current_player = getattr(game, "get_current_player", lambda: None)()
            if current_player is not None:
                current_owner = str(getattr(current_player, "id", "") or "")
            if (
                target_id
                and current_phase == "SHOOTING_PHASE"
                and (not owner_id or owner_id == current_owner)
                and (marked_turn <= 0 or current_turn <= 0 or marked_turn == current_turn)
            ):
                force_target_id = target_id
    out_of_phase = bool(request.context.get("out_of_phase", False))
    for decl in declarations:
        if not isinstance(decl, dict):
            return ("Declaration entry must be a dict.",)
        wargear_id = str(decl.get("wargear_id", "") or "")
        profile_name = str(decl.get("profile_name", "") or "")
        model_ids = decl.get("model_ids")
        if not wargear_id or not profile_name:
            return ("Declaration missing wargear_id/profile_name.",)
        if allowed_wargear_ids and wargear_id not in allowed_wargear_ids:
            return ("Declaration uses a weapon that is not allowed for this shooting decision.",)
        wargear = get_wargear(game, wargear_id)
        if wargear is None:
            return ("Declaration wargear not found.",)
        profiles = getattr(wargear, "profiles", {}) or {}
        if profile_name not in profiles:
            return ("Declaration weapon profile not found.",)
        profile = profiles.get(profile_name)
        is_ctan_power = bool(getattr(unit, "_is_ctan_power_profile", lambda _p: False)(profile))
        if is_ctan_power:
            ctan_profiles.append(profile)
        is_plasma_warhead = bool(getattr(profile, "is_plasma_warhead", lambda: False)())
        target_id = str(decl.get("target_unit_id", "") or "")
        if not is_plasma_warhead:
            if not target_id:
                return ("Declaration missing target_unit_id.",)
            if force_target_id and target_id != force_target_id:
                return ("Declaration target must match forced target unit.",)
            target_unit = get_unit(game, target_id)
            if target_unit is None:
                return ("Declaration target unit not found.",)
            if unit is not None:
                reason_fn = getattr(unit, "_space_marines_bastion_heresy_undone_target_restriction_reason", None)
                if callable(reason_fn):
                    reason = str(reason_fn(target_unit, game=game) or "").strip()
                    if reason:
                        return (reason,)
            if unit is not None:
                reason_fn = getattr(unit, "_adeptus_mechanicus_auto_divinatory_target_restriction_reason", None)
                if callable(reason_fn):
                    reason = str(reason_fn(target_unit, game=game) or "").strip()
                    if reason:
                        return (reason,)
            if unit is not None:
                try:
                    allowed, reason = unit._formless_horror_gate(
                        target_unit,
                        game=game,
                        allow_trigger=True,
                    )
                except Exception:
                    allowed, reason = True, None
                if not allowed:
                    return (str(reason or "Formless Horror: target not allowed."),)
        else:
            if force_target_id:
                return ("Plasma Warhead cannot be used with a forced target unit.",)
        if not isinstance(model_ids, list) or not model_ids:
            return ("Declaration requires model_ids list.",)
        models = []
        for model_id in model_ids:
            model_id = str(model_id or "")
            if allowed_model_ids and model_id not in allowed_model_ids:
                return ("Declaration uses a model that is not allowed for this shooting decision.",)
            model = get_model(game, str(model_id or ""))
            if model is None:
                return ("Declaration model not found.",)
            models.append(model)

        if is_plasma_warhead and profile is not None:
            can_shoot_fn = getattr(profile, "can_shoot_plasma_warhead", None)
            if callable(can_shoot_fn):
                can_shoot, reason = can_shoot_fn(models[0], out_of_phase=out_of_phase)
                if not can_shoot:
                    return (str(reason or "Plasma Warhead cannot be fired."),)

        # Validate Linked Fire / Infernal Puppeteer origin unit if present
        linked_fire_origin_id = decl.get("linked_fire_origin_unit_id")
        linked_fire_mode = str(decl.get("linked_fire_mode", "") or "").strip().lower()
        if linked_fire_origin_id is not None:
            if not linked_fire_mode:
                return ("Linked Fire origin requires linked_fire_mode.",)
            if linked_fire_mode not in ("linked_fire", "infernal_puppeteer"):
                return ("Linked Fire origin has invalid mode.",)
            origin_unit = get_unit(game, str(linked_fire_origin_id or ""))
            if origin_unit is None:
                return ("Linked Fire origin unit not found.",)

            # Get the shooting unit
            unit_id = str(payload.get("unit_id", "") or request.context.get("unit_id", "") or "")
            shooting_unit = get_unit(game, unit_id)
            if shooting_unit is None:
                return ("Shooting unit not found for Linked Fire validation.",)

            # Validate origin unit is not the bearer
            from ...utility.entity_ids import maybe_entity_id
            origin_entity_id = maybe_entity_id(origin_unit)
            shooting_entity_id = maybe_entity_id(shooting_unit)
            if origin_entity_id and shooting_entity_id:
                if origin_entity_id == shooting_entity_id:
                    return ("Linked Fire origin cannot be the bearer unit.",)
            elif origin_unit is shooting_unit:
                return ("Linked Fire origin cannot be the bearer unit.",)

            # Validate origin unit is friendly
            shooter_army = getattr(shooting_unit, "parent_army", None)
            if shooter_army is None and hasattr(shooting_unit, "get_parent_army"):
                shooter_army = shooting_unit.get_parent_army()
            origin_army = getattr(origin_unit, "parent_army", None)
            if origin_army is None and hasattr(origin_unit, "get_parent_army"):
                origin_army = origin_unit.get_parent_army()
            if shooter_army is None or origin_army is None or shooter_army is not origin_army:
                return ("Linked Fire origin must be friendly.",)

            if linked_fire_mode == "infernal_puppeteer":
                sr = getattr(shooting_unit, "special_rules", None)
                if not isinstance(sr, dict) or not sr.get("enhancement_infernal_puppeteer"):
                    return ("Infernal Puppeteer origin requires the enhancement.",)
                bearer = None
                try:
                    get_bearer = getattr(shooting_unit, "_get_enhancement_bearer_model", None)
                    if callable(get_bearer):
                        bearer = get_bearer()
                except Exception:
                    bearer = None
                if bearer is None:
                    return ("Infernal Puppeteer bearer must be on the battlefield.",)
                from ...rules.enhancement_descriptors import get_enhancement_tool_descriptor
                desc = get_enhancement_tool_descriptor(enhancement_id="000009810003", name="Infernal Puppeteer")
                try:
                    rng = float(getattr(desc, "range_in", 9.0) or 9.0)
                except Exception:
                    rng = 9.0
                # Validate origin unit is alive/deployed and within range of bearer
                try:
                    if hasattr(origin_unit, "is_active_for_rules"):
                        if not origin_unit.is_active_for_rules():
                            return ("Infernal Puppeteer origin must be on the battlefield.",)
                    else:
                        if not getattr(origin_unit, "is_alive", lambda: False)():
                            return ("Infernal Puppeteer origin must be alive.",)
                        if not getattr(origin_unit, "deployed", False):
                            return ("Infernal Puppeteer origin must be deployed.",)
                except Exception:
                    return ("Infernal Puppeteer origin must be on the battlefield.",)
                try:
                    if not (origin_unit.has_any_keyword("LEGIONES DAEMONICA") and origin_unit.has_any_keyword("TZEENTCH")):
                        return ("Infernal Puppeteer origin must be a LEGIONES DAEMONICA TZEENTCH unit.",)
                except Exception:
                    return ("Infernal Puppeteer origin must be a LEGIONES DAEMONICA TZEENTCH unit.",)
                from ...utility.aura_utils import model_within_range_of_unit, linked_fire_origin_is_visible
                if not model_within_range_of_unit(bearer, origin_unit, rng, use_attached_aggregate=True):
                    return ("Infernal Puppeteer origin must be within range of the bearer.",)
                game_map = getattr(game, "map", None)
                if not linked_fire_origin_is_visible(shooting_unit, origin_unit, game_map=game_map):
                    return ("Infernal Puppeteer origin must be visible to the bearer unit.",)
            else:
                from ...utility.aura_utils import unit_has_fire_prism_keyword, linked_fire_origin_is_visible

                # Validate origin unit has FIRE PRISM keyword
                if not unit_has_fire_prism_keyword(origin_unit):
                    return ("Linked Fire origin must have FIRE PRISM keyword.",)

                # Validate origin unit is alive and deployed
                try:
                    if not getattr(origin_unit, "is_alive", lambda: False)():
                        return ("Linked Fire origin must be alive.",)
                    if not getattr(origin_unit, "deployed", False):
                        return ("Linked Fire origin must be deployed.",)
                except Exception:
                    return ("Linked Fire origin must be alive and deployed.",)

                # Validate origin unit is visible to bearer (visibility is required)
                game_map = getattr(game, "map", None)
                if not linked_fire_origin_is_visible(shooting_unit, origin_unit, game_map=game_map):
                    return ("Linked Fire origin must be visible to the bearer unit.",)

    validate_ctan = getattr(unit, "validate_ctan_power_selection", None)
    if callable(validate_ctan):
        ok, reason = validate_ctan([{"weapon_profile": profile} for profile in ctan_profiles])
        if not ok:
            return (str(reason or "Invalid C'tan Power selection."),)

    return ()


def _apply_declare_shots(game: object, request: DecisionRequest, result: DecisionResult):
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    unit_id = str(payload.get("unit_id", "") or request.context.get("unit_id", "") or "")
    unit = get_unit(game, unit_id)
    if unit is None:
        raise RuntimeError("Shooting unit missing.")
    if bool(result.payload.get("skipped", False)) or str(payload.get("action", "") or "") == "skip":
        return False
    game_map = getattr(game, "map", None)
    out_of_phase = bool(request.context.get("out_of_phase", False))
    declarations = []
    for decl in list(result.payload.get("declarations") or []):
        wargear = get_wargear(game, str(decl.get("wargear_id", "") or ""))
        if wargear is None:
            continue
        profile_name = str(decl.get("profile_name", "") or "")
        profile = getattr(wargear, "profiles", {}).get(profile_name)
        if profile is None:
            continue
        is_plasma_warhead = bool(getattr(profile, "is_plasma_warhead", lambda: False)())
        target_unit = None
        if not is_plasma_warhead:
            target_unit = get_unit(game, str(decl.get("target_unit_id", "") or ""))
            if target_unit is None:
                continue
        models = []
        for model_id in list(decl.get("model_ids") or []):
            model = get_model(game, str(model_id or ""))
            if model is not None:
                models.append(model)
        if not models:
            continue

        entry = {"weapon_profile": profile, "target_unit": target_unit, "models": models}
        # Linked Fire: add origin unit if present
        linked_fire_origin_id = decl.get("linked_fire_origin_unit_id")
        linked_fire_mode = str(decl.get("linked_fire_mode", "") or "").strip().lower()
        if linked_fire_origin_id is not None:
            origin_unit = get_unit(game, str(linked_fire_origin_id or ""))
            if origin_unit is not None:
                entry["linked_fire_origin_unit"] = origin_unit
                entry["linked_fire_mode"] = linked_fire_mode
        fd_ids = decl.get("firing_deck_source_model_ids")
        if isinstance(fd_ids, list) and fd_ids:
            fd_models = [m for m in (get_model(game, str(mid or "")) for mid in fd_ids) if m is not None]
            if fd_models:
                entry["firing_deck_source_models"] = fd_models
        declarations.append(entry)
    if not declarations:
        return False
    hypersensory_flow = bool(request.context.get("hypersensory_abilities_flow", False))
    if hypersensory_flow:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["hypersensory_abilities_pending_move"] = True
        sr["hypersensory_abilities_pending_move_source"] = (
            str(request.context.get("hypersensory_abilities_source", "") or "Hypersensory Abilities").strip()
            or "Hypersensory Abilities"
        )
        sr["hypersensory_abilities_pending_enemy_unit_id"] = str(
            request.context.get("hypersensory_abilities_enemy_unit_id", "") or ""
        )
        unit.special_rules = sr
    success = bool(unit.execute_shooting_declarations(declarations, game_map, out_of_phase=out_of_phase))
    if not success and hypersensory_flow:
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict):
            sr.pop("hypersensory_abilities_pending_move", None)
            sr.pop("hypersensory_abilities_pending_move_source", None)
            sr.pop("hypersensory_abilities_pending_enemy_unit_id", None)
            unit.special_rules = sr
    if success and bool(request.context.get("guns_blazing_flow", False)):
        mark_used = getattr(unit, "mark_guns_blazing_used", None)
        if callable(mark_used):
            mark_used(game)
    if success and bool(request.context.get("storm_of_vengeance_flow", False)):
        mark_used = getattr(unit, "mark_storm_of_vengeance_used", None)
        if callable(mark_used):
            mark_used(game)
    if success and hypersensory_flow:
        mark_used = getattr(unit, "mark_hypersensory_abilities_used", None)
        if callable(mark_used):
            mark_used(game)
    try:
        if hasattr(unit, "_clear_formless_horror_allowed"):
            unit._clear_formless_horror_allowed()
    except Exception:
        pass
    return bool(success)


def _validate_firing_deck(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    opt_payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    transport_id = str(opt_payload.get("transport_id", "") or request.context.get("transport_id", "") or "")
    if not transport_id:
        return ("Firing deck requires transport_id.",)
    transport = get_unit(game, transport_id)
    if transport is None:
        return ("Firing deck transport not found.",)
    try:
        has_fd, fd_x = transport.has_firing_deck()
    except Exception:
        has_fd, fd_x = (False, 0)
    if not has_fd or int(fd_x or 0) <= 0:
        return ("Firing deck transport is missing Firing Deck X.",)

    payload = dict(result.payload or {})
    selections = payload.get("selected_entries")
    if selections is None:
        return ("Firing deck requires selected_entries.",)
    if not isinstance(selections, list):
        return ("selected_entries must be a list.",)
    selected_model_ids: set[str] = set()
    total_slots = 0
    for entry in selections:
        if not isinstance(entry, dict):
            return ("selected_entries must contain dicts.",)
        wargear_id = str(entry.get("wargear_id", "") or "")
        profile_name = str(entry.get("profile_name", "") or "")
        model_id = str(entry.get("model_id", "") or "")
        if not wargear_id or not profile_name or not model_id:
            return ("Firing deck entry missing wargear_id/profile_name/model_id.",)
        wargear = get_wargear(game, wargear_id)
        if wargear is None:
            return ("Firing deck wargear not found.",)
        model = get_model(game, model_id)
        if model is None:
            return ("Firing deck model not found.",)
        if profile_name not in (getattr(wargear, "profiles", {}) or {}):
            return ("Firing deck profile not found on wargear.",)
        if model_id in selected_model_ids:
            return ("Firing deck can select at most one weapon per embarked model.",)
        selected_model_ids.add(model_id)
        source_unit = getattr(model, "parent_unit", None)
        if source_unit is None:
            return ("Firing deck model has no source unit.",)
        try:
            source_root = source_unit.get_attached_unit_root()
        except Exception:
            source_root = source_unit
        if (
            source_root is None
            or (
                getattr(source_root, "embarked_in", None) is not transport
                and source_root not in list(getattr(transport, "transport_passengers", []) or [])
            )
        ):
            return ("Firing deck model is not embarked in this transport.",)
        try:
            total_slots += max(1, int(transport.get_firing_deck_selection_cost(model) or 1))
        except Exception:
            total_slots += 1
    if total_slots > int(fd_x or 0):
        return (f"Firing deck selections exceed Firing Deck {int(fd_x or 0)}.",)
    return ()


def _apply_firing_deck(game: object, request: DecisionRequest, result: DecisionResult) -> None:
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    transport = get_unit(game, str(payload.get("transport_id", "") or request.context.get("transport_id", "") or ""))
    if transport is None:
        raise RuntimeError("Firing deck transport missing.")
    selections = []
    for entry in list(result.payload.get("selected_entries") or []):
        wargear = get_wargear(game, str(entry.get("wargear_id", "") or ""))
        model = get_model(game, str(entry.get("model_id", "") or ""))
        if wargear is None or model is None:
            continue
        profile_name = str(entry.get("profile_name", "") or "")
        profile = getattr(wargear, "profiles", {}).get(profile_name)
        if profile is None:
            continue
        selections.append(
            {
                "model": model,
                "wargear": wargear,
                "profile": profile,
                "profile_name": profile_name,
            }
        )
    transport.apply_firing_deck_virtual_wargear(selections)
    return None


def _validate_reroll(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    return validate_option_choice(request, result)


def _apply_reroll(game: object, request: DecisionRequest, result: DecisionResult):
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    return bool(payload.get("reroll", False))


def _validate_deathstrike_action(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    errors = list(validate_option_choice(request, result))
    if errors:
        return errors
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    action = str(payload.get("action", "") or "")
    if action not in ("designate", "adjust", "none"):
        return ("Invalid Deathstrike action. Must be 'designate', 'adjust', or 'none'.",)

    unit_id = str(request.context.get("unit_id", "") or "")
    if not unit_id:
        return ("Deathstrike action requires unit_id in context.",)

    unit = get_unit(game, unit_id)
    if unit is None:
        return ("Unit not found.",)
    if not bool(getattr(unit, "has_plasma_warhead_weapon", lambda: False)()):
        return ("Deathstrike action requires a Plasma Warhead weapon.",)
    if not bool(getattr(unit, "_is_controlling_players_shooting_phase", lambda: False)()):
        return ("Deathstrike action must be used in your Shooting phase.",)

    army = unit.get_parent_army()
    deathstrike_mgr = getattr(army, "deathstrike", None)
    if deathstrike_mgr is None:
        return ("Deathstrike manager not found for army.",)
    if action == "designate":
        can_designate, reason = deathstrike_mgr.can_designate_target(unit_id)
        if not can_designate:
            return (str(reason or "Cannot Designate Target."),)
    if action == "adjust":
        can_adjust, reason = deathstrike_mgr.can_adjust_target(unit_id)
        if not can_adjust:
            return (str(reason or "Cannot Adjust Target."),)

    # Validate position if designate or adjust
    if action in ("designate", "adjust"):
        position = result.payload.get("position")
        if not isinstance(position, (list, tuple)) or len(position) != 2:
            return ("Deathstrike action requires position as [x, y].",)
        try:
            x = float(position[0])
            y = float(position[1])
        except (TypeError, ValueError):
            return ("Position coordinates must be numeric.",)
        game_map = getattr(game, "map", None)
        if game_map is None:
            return ("Deathstrike action requires a battlefield map.",)
        width = getattr(game_map, "width", None)
        height = getattr(game_map, "height", None)
        if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
            return ("Deathstrike action requires battlefield bounds.",)
        if x < 0 or y < 0 or x > float(width) or y > float(height):
            return ("Position must be on the battlefield.",)

    return ()


def _apply_deathstrike_action(game: object, request: DecisionRequest, result: DecisionResult):
    opt = find_option(request, result.option_id)
    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
    action = str(payload.get("action", "") or "")
    unit_id = str(request.context.get("unit_id", "") or "")
    unit = get_unit(game, unit_id)
    if unit is None:
        raise RuntimeError("Unit not found for Deathstrike action.")

    army = unit.get_parent_army()
    deathstrike_mgr = getattr(army, "deathstrike", None)
    if deathstrike_mgr is None:
        raise RuntimeError("Deathstrike manager not found for army.")

    if action == "none":
        return None

    position = result.payload.get("position")
    if not position:
        raise RuntimeError("Position required for Deathstrike action.")

    position = (float(position[0]), float(position[1]))

    if action == "designate":
        deathstrike_mgr.place_marker(unit_id, position)
        logger.info(f"INFO: Deathstrike marker placed at ({position[0]:.1f}, {position[1]:.1f})")
    elif action == "adjust":
        deathstrike_mgr.move_marker(unit_id, position)
        logger.info(f"INFO: Deathstrike marker moved to ({position[0]:.1f}, {position[1]:.1f})")

    return None


register_decision_handler(DECISION_SELECT_WEAPON, validate=_validate_select_weapon, apply=_apply_select_weapon)
register_decision_handler(DECISION_DECLARE_SHOTS, validate=_validate_declare_shots, apply=_apply_declare_shots)
register_decision_handler(DECISION_DECLARE_FIRING_DECK, validate=_validate_firing_deck, apply=_apply_firing_deck)
register_decision_handler(DECISION_SELECT_OVERWATCH_SHOOTER, validate=_validate_select_overwatch, apply=_apply_select_overwatch)
register_decision_handler(DECISION_REROLL_ROLL, validate=_validate_reroll, apply=_apply_reroll)
register_decision_handler(DECISION_DEATHSTRIKE_ACTION, validate=_validate_deathstrike_action, apply=_apply_deathstrike_action)
