from __future__ import annotations

from typing import Sequence

from ..decision_dispatcher import _validate_choice_from_options, register_decision_handler
from ..decision_kinds import DECISION_CONFIRM_EXAMPLE, DECISION_CONFIRM_YES_NO
from ..decisions import DecisionRequest, DecisionResult


def _validate_confirm(game: object, request: DecisionRequest, result: DecisionResult) -> Sequence[str]:
    return _validate_choice_from_options(request, result)


def _apply_confirm(game: object, request: DecisionRequest, result: DecisionResult):
    ctx = dict(getattr(request, "context", {}) or {})
    ability = str(ctx.get("ability", "") or "").strip().lower()
    def _is_alive(entity: object) -> bool:
        alive_attr = getattr(entity, "is_alive", False)
        return bool(alive_attr() if callable(alive_attr) else alive_attr)

    unit_id = str(ctx.get("unit_id", "") or "")
    choice = None
    selected_option = None
    selected_payload = {}
    for opt in list(getattr(request, "options", []) or []):
        if getattr(opt, "option_id", None) == getattr(result, "option_id", None):
            selected_option = opt
            break
    if selected_option is not None:
        selected_payload = dict(getattr(selected_option, "payload", {}) or {})
        if "choice" in selected_payload:
            choice = bool(selected_payload.get("choice"))
        if not unit_id:
            unit_id = str(selected_payload.get("unit_id", "") or "")
        if ability == "pyrogenesis_flux":
            ctx.setdefault("strength_bonus", selected_payload.get("strength_bonus"))
            ctx.setdefault("ap_bonus", selected_payload.get("ap_bonus"))
            ctx.setdefault("base_strength_bonus", selected_payload.get("base_strength_bonus"))
            ctx.setdefault("flux_strength_bonus", selected_payload.get("flux_strength_bonus"))
            ctx.setdefault("flux_ap_bonus", selected_payload.get("flux_ap_bonus"))
    if choice is None:
        if "choice" in result.payload:
            choice = bool(result.payload.get("choice"))
    resolved_payload = dict(selected_payload or {})
    resolved_payload.update(dict(getattr(result, "payload", {}) or {}))
    if choice is not None:
        resolved_payload["choice"] = bool(choice)

    if ability not in (
        "hover_mode",
        "patrol_squad",
        "combat_squads",
        "fight_within_3",
        "flickering_reality_reroll",
        "pyrogenesis_flux",
        "extremis_level_threat",
        "oath_of_rynn",
        "orks_speedwaaagh_turbo_boostas",
    ):
        return resolved_payload if choice is not None else None

    if ability == "extremis_level_threat":
        army_id = str(
            ctx.get("army_id", "")
            or selected_payload.get("army_id", "")
            or result.payload.get("army_id", "")
            or ""
        )
        if choice is None:
            return None
        army = None
        resolver = getattr(game, "_resolve_army_by_id", None)
        if callable(resolver) and army_id:
            army = resolver(army_id)
        if army is None:
            for player in list(getattr(game, "players", []) or []):
                if player is None:
                    continue
                get_army = getattr(player, "get_army", None)
                candidate = get_army() if callable(get_army) else getattr(player, "army", None)
                if candidate is None:
                    continue
                candidate_id = str(getattr(candidate, "_id", "") or getattr(candidate, "id", "") or "")
                if army_id and candidate_id != army_id:
                    continue
                army = candidate
                break
        if army is None:
            return None
        mgr = getattr(army, "oath_of_moment", None)
        if choice and mgr is not None and hasattr(mgr, "activate_extremis_level_threat"):
            player = getattr(army, "player", None)
            mgr.activate_extremis_level_threat(game=game, player=player)
        return None

    if ability == "oath_of_rynn":
        model_id = str(
            ctx.get("model_id", "")
            or selected_payload.get("model_id", "")
            or result.payload.get("model_id", "")
            or ""
        )
        if not unit_id or not model_id or choice is None:
            return None
        unit = None
        resolver = getattr(game, "_resolve_unit_by_id", None)
        if callable(resolver):
            unit = resolver(unit_id)
        if unit is None:
            return None
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None or not _is_alive(root):
            return None
        if not bool(choice):
            return None
        model = None
        model_resolver = getattr(game, "_resolve_model_by_id", None)
        if callable(model_resolver):
            model = model_resolver(model_id)
        if model is None:
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            for candidate in list(models or []):
                if str(getattr(candidate, "_id", "") or "") == model_id:
                    model = candidate
                    break
        if model is None or not _is_alive(model):
            return None
        ability_key = str(
            ctx.get("ability_key", "")
            or selected_payload.get("ability_key", "")
            or result.payload.get("ability_key", "")
            or "oath_of_rynn"
        ).strip().lower() or "oath_of_rynn"
        if getattr(model, "has_used_once_per_battle", lambda _k: False)(ability_key):
            return None
        try:
            attacks_bonus = int(
                ctx.get("attacks_bonus", 0)
                or selected_payload.get("attacks_bonus", 0)
                or result.payload.get("attacks_bonus", 0)
                or 0
            )
        except Exception:
            attacks_bonus = 0
        if attacks_bonus <= 0:
            return None
        expires_phase = str(
            ctx.get("expires_phase", "")
            or selected_payload.get("expires_phase", "")
            or result.payload.get("expires_phase", "")
            or "FIGHT_PHASE"
        ).strip().upper() or "FIGHT_PHASE"
        ability_name = str(ctx.get("ability_name", "") or "Oath of Rynn").strip() or "Oath of Rynn"
        try:
            models = list(root.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(root, "models", []) or [])
        for target_model in list(models or []):
            if target_model is None or not _is_alive(target_model):
                continue
            for weapon_index, wargear in enumerate(list(getattr(target_model, "wargear", []) or [])):
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name or not hasattr(target_model, "set_temporary_weapon_bonus"):
                    continue
                target_model.set_temporary_weapon_bonus(
                    key=f"oath_of_rynn:{ability_key}:{getattr(target_model, '_id', '')}:{weapon_index}",
                    weapon_name=weapon_name,
                    attacks_bonus=int(attacks_bonus),
                    source=ability_name,
                    expires_phase=expires_phase,
                )
        mark_used = getattr(model, "mark_used_once_per_battle", None)
        if callable(mark_used):
            mark_used(ability_key, ability_name=ability_name, source="datasheet")
        return None

    if not unit_id:
        return None

    unit = None
    resolver = getattr(game, "_resolve_unit_by_id", None)
    if callable(resolver):
        unit = resolver(unit_id)
    if unit is None:
        for player in list(getattr(game, "players", []) or []):
            if player is None:
                continue
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None:
                continue
            for candidate in list(getattr(army, "units", []) or []):
                if candidate is None:
                    continue
                if str(getattr(candidate, "_id", "")) == unit_id or str(getattr(candidate, "id", "")) == unit_id:
                    unit = candidate
                    break
            if unit is not None:
                break

    if unit is None or choice is None:
        return None

    if ability == "orks_speedwaaagh_turbo_boostas":
        try:
            army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else getattr(unit, "parent_army", None)
        except AttributeError:
            army = getattr(unit, "parent_army", None)
        mgr = getattr(army, "orks_detachments", None) if army is not None else None
        apply_choice = getattr(mgr, "apply_speedwaaagh_turbo_boostas_choice", None) if mgr is not None else None
        if callable(apply_choice):
            apply_choice(unit, use_turbo=bool(choice), game=game, player=getattr(army, "player", None))
        prepare_advance = getattr(unit, "prepare_advance", None)
        if callable(prepare_advance):
            prepare_advance()
        return resolved_payload

    if ability == "fight_within_3":
        root = unit
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return None
        clear_active = getattr(root, "clear_fight_within_3_active", None)
        if callable(clear_active):
            clear_active()
        else:
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict):
                sr.pop("fight_within_3_active", None)
                sr.pop("fight_within_3_active_source", None)
        if bool(choice):
            ability_name = str(ctx.get("ability_name", "") or 'Fight Within 3"').strip() or 'Fight Within 3"'
            set_active = getattr(root, "set_fight_within_3_active", None)
            if callable(set_active):
                set_active(True, source=ability_name)
            else:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["fight_within_3_active"] = True
                sr["fight_within_3_active_source"] = ability_name
                root.special_rules = sr
        return resolved_payload

    if ability in ("patrol_squad", "combat_squads"):
        declared_flag = str(ctx.get("declared_flag", "") or "").strip()
        if not declared_flag:
            declared_flag = "patrol_squad_declared" if ability == "patrol_squad" else "combat_squads_declared"
        if not bool(choice):
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr[declared_flag] = True
            unit.special_rules = sr
            return None
        if ability == "patrol_squad":
            from ...utility.unit_split import split_unit_into_patrol_squad_units

            split_units = split_unit_into_patrol_squad_units(
                unit,
                game=game,
                game_map=getattr(game, "map", None),
            )
        else:
            from ...utility.unit_split import split_unit_into_combat_squad_units

            split_units = split_unit_into_combat_squad_units(
                unit,
                game=game,
                game_map=getattr(game, "map", None),
            )
        if len(list(split_units or [])) != 2:
            raise RuntimeError(f"{str(ctx.get('ability_name', '') or ability).strip() or ability} split failed.")
        return None

    if ability == "hover_mode":
        setter = getattr(unit, "set_hover_mode", None)
        if callable(setter):
            setter(bool(choice))
        else:
            unit.hover_mode = bool(choice)
        unit.hover_declared = True
        return None

    if ability == "flickering_reality_reroll":
        try:
            from ...utility.dice import get_roll
        except Exception:
            get_roll = None
        try:
            from ...utility.event_bus import append_dice
        except Exception:
            append_dice = None
        try:
            from ...utility.stratagem_effects import apply_flickering_reality_effect
        except Exception:
            apply_flickering_reality_effect = None
        root = unit
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        base_roll = None
        try:
            base_roll = int(ctx.get("base_roll", 0) or 0)
        except Exception:
            base_roll = None
        if base_roll is None or base_roll <= 0:
            return None
        roll = base_roll
        player = None
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        mgr = getattr(game, "fates_in_flux", None)
        if choice and mgr is not None and player is not None:
            if mgr.spend_tokens(player, 1, reason="Flickering Reality re-roll"):
                roll = get_roll("D6")
                if append_dice is not None and player is not None:
                    append_dice(player, f"Flickering Reality re-roll: {roll}")
            else:
                choice = False
        if append_dice is not None and player is not None:
            append_dice(player, f"Flickering Reality roll: {roll}")
        if callable(apply_flickering_reality_effect):
            apply_flickering_reality_effect(
                root,
                roll,
                game=game,
                player=player,
                source=str(ctx.get("ability_name", "") or "Flickering Reality").strip() or "Flickering Reality",
            )
        return None

    if ability == "pyrogenesis_flux":
        try:
            from ...utility.stratagem_effects import apply_pyrogenesis_effect
        except Exception:
            apply_pyrogenesis_effect = None
        root = unit
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        player = None
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        strength_bonus = None
        ap_bonus = None
        try:
            strength_bonus = int(ctx.get("base_strength_bonus", 2) or 2)
        except Exception:
            strength_bonus = 2
        try:
            ap_bonus = int(ctx.get("base_ap_bonus", 0) or 0)
        except Exception:
            ap_bonus = 0
        flux_strength_bonus = int(ctx.get("flux_strength_bonus", 3) or 3)
        flux_ap_bonus = int(ctx.get("flux_ap_bonus", 1) or 1)
        mgr = getattr(game, "fates_in_flux", None)
        if choice and mgr is not None and player is not None:
            if mgr.spend_tokens(player, 1, reason="Pyrogenesis empowered"):
                strength_bonus = flux_strength_bonus
                ap_bonus = flux_ap_bonus
            else:
                choice = False
        phase_name = str(ctx.get("phase_name", "") or "")
        phase_key = phase_name.strip().upper()
        if not phase_key:
            try:
                phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            except Exception:
                phase_key = ""
        if phase_key not in ("SHOOTING_PHASE", "FIGHT_PHASE"):
            phase_key = "SHOOTING_PHASE"
        if callable(apply_pyrogenesis_effect):
            apply_pyrogenesis_effect(
                root,
                int(strength_bonus or 0),
                int(ap_bonus or 0),
                phase_key=phase_key,
                game=game,
                player=player,
                source=str(ctx.get("ability_name", "") or "Pyrogenesis").strip() or "Pyrogenesis",
            )
    return None


register_decision_handler(DECISION_CONFIRM_YES_NO, validate=_validate_confirm, apply=_apply_confirm)
register_decision_handler(DECISION_CONFIRM_EXAMPLE, validate=_validate_confirm, apply=_apply_confirm)
