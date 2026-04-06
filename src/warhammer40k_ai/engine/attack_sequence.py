from __future__ import annotations

from typing import Any, Optional

from ..utility.entity_ids import get_entity_id, maybe_entity_id


def _resolve_unit(manager, game: object, unit_id: str):
    registry = getattr(game, "entity_registry", None)
    if registry is None:
        return None
    return registry.get(str(unit_id), kind="unit")


def _resolve_model(manager, game: object, model_id: str):
    registry = getattr(game, "entity_registry", None)
    if registry is None:
        return None
    return registry.get(str(model_id), kind="model")


def _resolve_wargear(manager, game: object, wargear_id: str):
    registry = getattr(game, "entity_registry", None)
    if registry is None:
        return None
    return registry.get(str(wargear_id), kind="wargear")


def _resolve_profile(manager, game: object, wargear_id: str, profile_name: str):
    wargear = manager._resolve_wargear(game, wargear_id)
    if wargear is None:
        return None
    profiles = getattr(wargear, "profiles", {}) or {}
    return profiles.get(str(profile_name))


def _weapon_display_name(manager, profile) -> str:
    if profile is None:
        return "Weapon"
    name = getattr(profile, "name", "Weapon")
    parent = getattr(profile, "parent_wargear", None)
    if parent is not None:
        parent_name = getattr(parent, "name", "Weapon")
        if name == "default":
            return parent_name
        return f"{parent_name} - {name}"
    return str(name or "Weapon")


def _sorted_models(manager, models: list) -> list:
    ordered = [model for model in list(models or []) if model is not None]
    ordered.sort(key=lambda model: str(maybe_entity_id(model) or ""))
    return ordered


def _build_sequence(manager, game: object, decl: dict, *, out_of_phase: bool):
    from .attack_resolution import AttackSequence

    weapon_profile = decl.get("weapon_profile")
    target_unit = decl.get("target_unit")
    models = list(decl.get("models") or [])
    attacks_override = decl.get("attacks_override")
    attacks_override_modifiers = decl.get("attacks_override_modifiers")
    attacks_override_note = decl.get("attacks_override_note")
    if weapon_profile is None or target_unit is None or not models:
        return None
    parent_wargear = getattr(weapon_profile, "parent_wargear", None)
    if parent_wargear is None:
        return None
    wargear_id = get_entity_id(parent_wargear)
    profile_name = getattr(weapon_profile, "name", "default")
    attacker_unit = getattr(models[0], "parent_unit", None)
    if attacker_unit is None:
        return None
    seq_id = int(manager.next_sequence_id)
    manager.next_sequence_id += 1
    seq = AttackSequence(
        sequence_id=seq_id,
        attacker_unit_id=get_entity_id(attacker_unit),
        target_unit_id=get_entity_id(target_unit),
        wargear_id=wargear_id,
        profile_name=str(profile_name or "default"),
        model_ids=[get_entity_id(model) for model in models],
        out_of_phase=bool(out_of_phase),
        step="hits",
        attack_context={},
        context={},
    )
    seq.attack_context = {"pending_mortal_wounds": {}}
    seq.context = manager._build_attack_context(game, weapon_profile, attacker_unit, target_unit)
    if attacks_override is not None:
        try:
            seq.context["attacks_override"] = int(attacks_override)
        except (TypeError, ValueError):
            seq.context["attacks_override"] = attacks_override
    if attacks_override_modifiers is not None:
        seq.context["attacks_override_modifiers"] = list(attacks_override_modifiers or [])
    if attacks_override_note is not None:
        seq.context["attacks_override_note"] = str(attacks_override_note or "")
    is_torrent = getattr(weapon_profile, "is_torrent", None)
    if seq.context.get("indirect_fire_no_visible") and callable(is_torrent) and is_torrent():
        seq.attack_instances = []
        return seq
    attack_count_spec = None
    alive_models = [model for model in list(models or []) if getattr(model, "is_alive", False)]
    try:
        from ..utility.count import Count, CountType

        attacks = getattr(weapon_profile, "attacks", None)
        if attacks_override is None and isinstance(attacks, Count) and attacks.ctype is CountType.DICE:
            dice = attacks.value
            attack_count_spec = {
                "dice_per_model": int(getattr(dice, "number", 1) or 1),
                "faces": int(getattr(dice, "die_faces", 6) or 6),
                "modifier": int(getattr(dice, "modifier", 0) or 0),
            }
    except (AttributeError, TypeError, ValueError):
        attack_count_spec = None
    if attack_count_spec and alive_models:
        seq.context["attack_count_spec"] = attack_count_spec
        seq.context["attack_count_model_ids"] = [get_entity_id(model) for model in alive_models]
        seq.attack_instances = []
        seq.step = "attack_count"
    else:
        seq.attack_instances = manager._build_attack_instances(
            game,
            weapon_profile,
            attacker_unit,
            target_unit,
            models,
            seq.context,
            attacks_override=attacks_override,
            attacks_override_modifiers=attacks_override_modifiers,
            attacks_override_note=attacks_override_note,
        )
    return seq


def _build_attack_context(manager, game: object, weapon_profile, attacker_unit, target_unit) -> dict:
    ctx: dict[str, Any] = {}
    closest_dist = 0.0
    try:
        _closest, closest_dist = attacker_unit.return_closest_model_in_unit(target_unit)
    except (AttributeError, TypeError, ValueError):
        closest_dist = 0.0
    ctx["closest_dist"] = float(closest_dist)
    try:
        if hasattr(weapon_profile, "range"):
            ctx["half_range"] = float(getattr(weapon_profile.range, "max", 0.0) or 0.0) / 2.0
        else:
            ctx["half_range"] = 0.0
    except (AttributeError, TypeError, ValueError):
        ctx["half_range"] = 0.0
    ctx["indirect_fire_no_visible"] = False
    try:
        if weapon_profile.is_indirect_fire() and getattr(game, "map", None) is not None:
            if hasattr(attacker_unit, "_attacking_unit_has_any_los_to_target_unit"):
                ctx["indirect_fire_no_visible"] = not attacker_unit._attacking_unit_has_any_los_to_target_unit(
                    target_unit,
                    game.map,
                )
    except (AttributeError, TypeError, ValueError):
        ctx["indirect_fire_no_visible"] = False
    ctx["conversion_active"] = False
    ctx["conversion_distance_threshold"] = 0.0
    try:
        if weapon_profile.is_conversion():
            threshold = float(weapon_profile.get_conversion_distance(attacker_unit))
            ctx["conversion_distance_threshold"] = threshold
            ctx["conversion_active"] = float(closest_dist) > float(threshold)
    except (AttributeError, TypeError, ValueError):
        pass
    ctx["kill_team_toughness"] = None
    try:
        root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        if bool(getattr(root, "attached_unit_has_kill_team", lambda: False)()) and hasattr(root, "get_kill_team_majority_toughness"):
            kill_team_toughness = root.get_kill_team_majority_toughness()
            if kill_team_toughness is not None:
                ctx["kill_team_toughness"] = int(kill_team_toughness)
    except (AttributeError, TypeError, ValueError):
        ctx["kill_team_toughness"] = None
    ctx["furious_onslaught_applies"] = False
    try:
        is_ranged = bool(getattr(getattr(weapon_profile, "parent_wargear", None), "is_ranged", lambda: False)())
        if is_ranged and hasattr(attacker_unit, "has_furious_onslaught"):
            if attacker_unit.has_furious_onslaught(attacker_unit):
                game_map = getattr(game, "map", None)
                if game_map is not None and getattr(attacker_unit, "is_target_closest_eligible", None):
                    ctx["furious_onslaught_applies"] = bool(
                        attacker_unit.is_target_closest_eligible(attacker_unit, weapon_profile, target_unit, game_map, max_distance=18.0)
                    )
    except (AttributeError, TypeError, ValueError):
        ctx["furious_onslaught_applies"] = False
    ctx["closest_enemy_hit_reroll_rule"] = None
    ctx["closest_monster_vehicle_reroll_rule"] = None
    try:
        rules = getattr(attacker_unit, "model_closest_enemy_reroll_rules", lambda *_args, **_kwargs: [])(
            attacker_unit,
            weapon_profile,
            target_unit,
            game_map=getattr(game, "map", None),
        )
    except (AttributeError, TypeError, ValueError):
        rules = []
    if rules:
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            if rule.get("reroll_hit"):
                ctx["closest_enemy_hit_reroll_rule"] = rule
            if rule.get("reroll_hit_monster_vehicle"):
                ctx["closest_monster_vehicle_reroll_rule"] = rule
    ctx["attacker_key"] = None
    try:
        root = attacker_unit.get_attached_unit_root() if hasattr(attacker_unit, "get_attached_unit_root") else attacker_unit
        ctx["attacker_key"] = get_entity_id(root)
    except (AttributeError, TypeError, ValueError):
        ctx["attacker_key"] = None
    return ctx


def _init_attack_result(manager, weapon_profile, attacker, target_unit):
    from ..units.wargear import AttackResult

    weapon_display_name = weapon_profile.name
    if weapon_profile.parent_wargear:
        if weapon_profile.name == "default":
            weapon_display_name = weapon_profile.parent_wargear.name
        else:
            weapon_display_name = f"{weapon_profile.parent_wargear.name} - {weapon_profile.name}"
    return AttackResult(
        weapon_name=weapon_display_name,
        attacker_name=getattr(attacker, "name", "Attacker"),
        target_unit_name=getattr(target_unit, "name", "Target"),
        attacks_rolled=0,
        attacks_dice_expression=str(weapon_profile.attacks),
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


def _build_attack_instance(manager, ctx: dict, model, *, weapon_profile=None, target_unit=None) -> dict:
    within_half_range = bool(ctx.get("closest_dist", 0.0) <= (ctx.get("half_range", 0.0) or 0.0))
    unit = getattr(model, "parent_unit", None)
    if (not within_half_range) and unit is not None and weapon_profile is not None and target_unit is not None:
        resolver = getattr(unit, "weapon_target_counts_as_half_range", None)
        if callable(resolver):
            try:
                within_half_range = bool(
                    resolver(model=model, target=target_unit, weapon_profile=weapon_profile)
                )
            except (AttributeError, TypeError, ValueError):
                within_half_range = False
    attack_instance = {
        "crit_hit": False,
        "crit_wound": False,
        "mortal_wound": False,
        "below_half_distance": bool(within_half_range),
        "damage": 0,
        "target_toughness_override": ctx.get("kill_team_toughness"),
        "conversion_active": bool(ctx.get("conversion_active", False)),
        "distance_to_target": float(ctx.get("closest_dist", 0.0) or 0.0),
        "attacker_model_id": get_entity_id(model),
    }
    if ctx.get("attacker_key"):
        attack_instance["attacker_key"] = ctx.get("attacker_key")
    if ctx.get("furious_onslaught_applies"):
        attack_instance["furious_onslaught_applies"] = True
    if ctx.get("closest_enemy_hit_reroll_rule"):
        attack_instance["closest_enemy_hit_reroll_rule"] = ctx.get("closest_enemy_hit_reroll_rule")
    if ctx.get("closest_monster_vehicle_reroll_rule"):
        attack_instance["closest_monster_vehicle_reroll_rule"] = ctx.get("closest_monster_vehicle_reroll_rule")
    if ctx.get("indirect_fire_no_visible"):
        attack_instance["indirect_fire_no_visible"] = True
    return attack_instance


def _build_attack_instances(
    manager,
    game: object,
    weapon_profile,
    attacker_unit,
    target_unit,
    models: list,
    ctx: dict,
    *,
    attacks_override: Optional[int] = None,
    attacks_override_modifiers: Optional[list[str]] = None,
    attacks_override_note: Optional[str] = None,
) -> list[dict]:
    instances: list[dict] = []
    for model in list(models or []):
        if not getattr(model, "is_alive", False):
            continue
        attack_result = manager._init_attack_result(weapon_profile, model, target_unit)
        try:
            count_info = weapon_profile._resolve_attack_count(
                target_unit,
                model,
                attack_result,
                game_map=getattr(game, "map", None),
                closest_dist=float(ctx.get("closest_dist", 0.0) or 0.0),
                attacks_override=attacks_override,
                attacks_override_modifiers=attacks_override_modifiers,
                attacks_override_note=attacks_override_note,
                publish_roll_event=False,
            )
            num_attacks = int(getattr(count_info, "num_attacks", 0) or 0)
        except (AttributeError, TypeError, ValueError):
            num_attacks = int(getattr(weapon_profile, "attacks", 0) or 0)
        if num_attacks <= 0:
            continue
        for _ in range(int(num_attacks)):
            instances.append(
                manager._build_attack_instance(ctx, model, weapon_profile=weapon_profile, target_unit=target_unit)
            )
    return instances
