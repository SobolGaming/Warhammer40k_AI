from __future__ import annotations

from typing import TYPE_CHECKING

from .decision_kinds import (
    DECISION_CHOOSE_HIT_MODIFIER_IGNORES,
    DECISION_CHOOSE_SKILL_MODIFIER_IGNORES,
)
from .decisions import DecisionOption, DecisionRequest

if TYPE_CHECKING:
    from .attack_resolution import AttackSequence


def _ensure_hit_modifier_choices(manager, game: object, seq: AttackSequence) -> bool:
    """
    Ensure per-attack modifier ignore choices are resolved before grouping hit rolls.
    Returns True if a decision was requested (pause), False otherwise.
    """
    if not bool(getattr(game, "is_authoritative", True)):
        return False
    target = manager._resolve_unit(game, seq.target_unit_id)
    profile = manager._resolve_profile(game, seq.wargear_id, seq.profile_name)
    if target is None or profile is None:
        return False
    from ..utility.modifier_choice import (
        CHOICE_KEEP_ALL,
        CHOICE_LABELS,
        options_for_signed_pairs,
    )

    for idx, attack_instance in enumerate(list(seq.attack_instances or [])):
        if not isinstance(attack_instance, dict):
            continue
        hit_choice_set = attack_instance.get("hit_modifier_choice") is not None
        skill_choice_set = attack_instance.get("skill_modifier_choice") is not None
        attacker = manager._resolve_model(game, attack_instance.get("attacker_model_id"))
        if attacker is None:
            continue
        try:
            ignore_rule = profile._ignore_hit_modifier_rule(attacker, target_unit=target)
        except (AttributeError, TypeError, ValueError):
            ignore_rule = None
        attacker_unit = getattr(attacker, "parent_unit", None)
        parent_wargear = getattr(profile, "parent_wargear", None)
        is_melee = bool(
            parent_wargear is not None
            and callable(getattr(parent_wargear, "is_melee", None))
            and parent_wargear.is_melee()
        )
        is_ranged = bool(
            parent_wargear is not None
            and callable(getattr(parent_wargear, "is_ranged", None))
            and parent_wargear.is_ranged()
        )
        if ignore_rule:
            rule_attack_type = str(ignore_rule.get("attack_type") or "any").strip().lower()
            if rule_attack_type == "ranged" and not is_ranged:
                ignore_rule = None
            elif rule_attack_type == "melee" and not is_melee:
                ignore_rule = None
        driven_by_ultimate_rage = False
        driven_rule_name = ""
        if is_melee and attacker_unit is not None:
            try:
                from ..rules.wrathful_presence import (
                    DRIVEN_BY_ULTIMATE_RAGE_NAME,
                    driven_by_ultimate_rage_applies,
                )

                driven_by_ultimate_rage = driven_by_ultimate_rage_applies(
                    attacker_unit,
                    game_map=getattr(game, "map", None),
                )
                if driven_by_ultimate_rage:
                    driven_rule_name = DRIVEN_BY_ULTIMATE_RAGE_NAME
            except (ImportError, AttributeError, TypeError, ValueError):
                driven_by_ultimate_rage = False
                driven_rule_name = ""
        if not ignore_rule and not driven_by_ultimate_rage:
            continue
        if ignore_rule and hit_choice_set and skill_choice_set and not driven_by_ultimate_rage:
            continue
        if driven_by_ultimate_rage and hit_choice_set and skill_choice_set and not ignore_rule:
            continue

        preview = profile._hit_target_with_tracking(
            target,
            attacker,
            attack_instance,
            roll_value=1,
            allow_rerolls=False,
            log_roll=False,
            preview_modifiers=True,
        )
        skill_mods = list(preview.get("skill_mods", []) or [])
        hit_mods = list(preview.get("hit_mods", []) or [])

        player = getattr(
            getattr(getattr(attacker, "parent_unit", None), "get_parent_army", lambda: None)(),
            "player",
            None,
        )
        game_map = getattr(game, "map", None)
        provider = getattr(game_map, "hit_modifier_choice_provider", None) if game_map is not None else None

        if ignore_rule:
            rule_name = str(ignore_rule.get("name") or "Ignore modifiers").strip()
            skill_kinds = set(ignore_rule.get("skill_kinds") or ())
            allow_skill = False
            skill_label = "Skill"
            if is_melee:
                allow_skill = "weapon" in skill_kinds
                skill_label = "Weapon Skill"
            elif is_ranged:
                allow_skill = "ballistic" in skill_kinds
                skill_label = "Ballistic Skill"
            else:
                allow_skill = bool(skill_kinds)
                if "weapon" in skill_kinds:
                    skill_label = "Weapon Skill"
                elif "ballistic" in skill_kinds:
                    skill_label = "Ballistic Skill"
            allow_hit = bool(ignore_rule.get("allow_hit", True))

            if allow_skill and attack_instance.get("skill_modifier_choice") is None:
                skill_opts = options_for_signed_pairs(skill_mods)
                if not skill_opts:
                    attack_instance["skill_modifier_choice"] = CHOICE_KEEP_ALL
                else:
                    skill_provider = (
                        getattr(game_map, "skill_modifier_choice_provider", None)
                        if game_map is not None
                        else None
                    )
                    if not callable(skill_provider):
                        skill_provider = provider
                    if callable(skill_provider) and player is not None and bool(
                        getattr(player, "has_control", lambda: False)()
                    ):
                        try:
                            choice = skill_provider(
                                player=player,
                                attacker=attacker,
                                target=target,
                                weapon_profile=profile,
                                ability_name=f"{rule_name} ({skill_label})",
                                choices=skill_opts,
                            )
                        except (AttributeError, TypeError, ValueError):
                            choice = None
                        if choice not in skill_opts:
                            choice = CHOICE_KEEP_ALL
                        attack_instance["skill_modifier_choice"] = choice
                if attack_instance.get("skill_modifier_choice") is None and skill_opts:
                    prompt = "Choose which modifiers to ignore."
                    req_options = [
                        DecisionOption.create(CHOICE_LABELS.get(opt, str(opt)), payload={"choice": opt})
                        for opt in skill_opts
                    ]
                    ctx = {
                        "sequence_id": int(seq.sequence_id),
                        "attack_index": int(idx),
                        "attacker_model_id": attack_instance.get("attacker_model_id"),
                        "target_unit_id": seq.target_unit_id,
                        "wargear_id": seq.wargear_id,
                        "profile_name": seq.profile_name,
                        "ability_name": f"{rule_name} ({skill_label})",
                        "modifier_kind": "weapon_skill" if is_melee else "ballistic_skill",
                    }
                    request = DecisionRequest.create(
                        DECISION_CHOOSE_SKILL_MODIFIER_IGNORES,
                        prompt,
                        player_id=getattr(player, "id", None) if player is not None else None,
                        options=req_options,
                        context=ctx,
                    )
                    seq.step = "skill_modifier_choice"
                    if hasattr(game, "request_decision"):
                        game.request_decision(request)
                    return True

            if allow_hit and attack_instance.get("hit_modifier_choice") is None:
                hit_opts = options_for_signed_pairs(hit_mods)
                if not hit_opts:
                    attack_instance["hit_modifier_choice"] = CHOICE_KEEP_ALL
                else:
                    if callable(provider) and player is not None and bool(getattr(player, "has_control", lambda: False)()):
                        try:
                            choice = provider(
                                player=player,
                                attacker=attacker,
                                target=target,
                                weapon_profile=profile,
                                ability_name=f"{rule_name} (Hit roll)",
                                choices=hit_opts,
                            )
                        except (AttributeError, TypeError, ValueError):
                            choice = None
                        if choice not in hit_opts:
                            choice = CHOICE_KEEP_ALL
                        attack_instance["hit_modifier_choice"] = choice
                if attack_instance.get("hit_modifier_choice") is None and hit_opts:
                    prompt = "Choose which modifiers to ignore."
                    req_options = [
                        DecisionOption.create(CHOICE_LABELS.get(opt, str(opt)), payload={"choice": opt})
                        for opt in hit_opts
                    ]
                    ctx = {
                        "sequence_id": int(seq.sequence_id),
                        "attack_index": int(idx),
                        "attacker_model_id": attack_instance.get("attacker_model_id"),
                        "target_unit_id": seq.target_unit_id,
                        "wargear_id": seq.wargear_id,
                        "profile_name": seq.profile_name,
                        "ability_name": f"{rule_name} (Hit roll)",
                        "modifier_kind": "hit_roll",
                    }
                    request = DecisionRequest.create(
                        DECISION_CHOOSE_HIT_MODIFIER_IGNORES,
                        prompt,
                        player_id=getattr(player, "id", None) if player is not None else None,
                        options=req_options,
                        context=ctx,
                    )
                    seq.step = "hit_modifier_choice"
                    if hasattr(game, "request_decision"):
                        game.request_decision(request)
                    return True

        if driven_by_ultimate_rage:
            if attack_instance.get("skill_modifier_choice") is None:
                skill_opts = options_for_signed_pairs(skill_mods)
                if not skill_opts:
                    attack_instance["skill_modifier_choice"] = CHOICE_KEEP_ALL
                else:
                    skill_provider = (
                        getattr(game_map, "skill_modifier_choice_provider", None)
                        if game_map is not None
                        else None
                    )
                    if not callable(skill_provider):
                        skill_provider = provider
                    if callable(skill_provider) and player is not None and bool(
                        getattr(player, "has_control", lambda: False)()
                    ):
                        try:
                            choice = skill_provider(
                                player=player,
                                attacker=attacker,
                                target=target,
                                weapon_profile=profile,
                                ability_name=f"{driven_rule_name} (Weapon Skill)",
                                choices=skill_opts,
                            )
                        except (AttributeError, TypeError, ValueError):
                            choice = None
                        if choice not in skill_opts:
                            choice = CHOICE_KEEP_ALL
                        attack_instance["skill_modifier_choice"] = choice
                if attack_instance.get("skill_modifier_choice") is None and skill_opts:
                    prompt = "Choose which modifiers to ignore."
                    req_options = [
                        DecisionOption.create(CHOICE_LABELS.get(opt, str(opt)), payload={"choice": opt})
                        for opt in skill_opts
                    ]
                    ctx = {
                        "sequence_id": int(seq.sequence_id),
                        "attack_index": int(idx),
                        "attacker_model_id": attack_instance.get("attacker_model_id"),
                        "target_unit_id": seq.target_unit_id,
                        "wargear_id": seq.wargear_id,
                        "profile_name": seq.profile_name,
                        "ability_name": f"{driven_rule_name} (Weapon Skill)",
                        "modifier_kind": "weapon_skill",
                    }
                    request = DecisionRequest.create(
                        DECISION_CHOOSE_SKILL_MODIFIER_IGNORES,
                        prompt,
                        player_id=getattr(player, "id", None) if player is not None else None,
                        options=req_options,
                        context=ctx,
                    )
                    seq.step = "skill_modifier_choice"
                    if hasattr(game, "request_decision"):
                        game.request_decision(request)
                    return True

            if attack_instance.get("hit_modifier_choice") is None:
                hit_opts = options_for_signed_pairs(hit_mods)
                if not hit_opts:
                    attack_instance["hit_modifier_choice"] = CHOICE_KEEP_ALL
                else:
                    if callable(provider) and player is not None and bool(getattr(player, "has_control", lambda: False)()):
                        try:
                            choice = provider(
                                player=player,
                                attacker=attacker,
                                target=target,
                                weapon_profile=profile,
                                ability_name=f"{driven_rule_name} (Hit roll)",
                                choices=hit_opts,
                            )
                        except (AttributeError, TypeError, ValueError):
                            choice = None
                        if choice not in hit_opts:
                            choice = CHOICE_KEEP_ALL
                        attack_instance["hit_modifier_choice"] = choice
                if attack_instance.get("hit_modifier_choice") is None and hit_opts:
                    prompt = "Choose which modifiers to ignore."
                    req_options = [
                        DecisionOption.create(CHOICE_LABELS.get(opt, str(opt)), payload={"choice": opt})
                        for opt in hit_opts
                    ]
                    ctx = {
                        "sequence_id": int(seq.sequence_id),
                        "attack_index": int(idx),
                        "attacker_model_id": attack_instance.get("attacker_model_id"),
                        "target_unit_id": seq.target_unit_id,
                        "wargear_id": seq.wargear_id,
                        "profile_name": seq.profile_name,
                        "ability_name": f"{driven_rule_name} (Hit roll)",
                        "modifier_kind": "hit_roll",
                    }
                    request = DecisionRequest.create(
                        DECISION_CHOOSE_HIT_MODIFIER_IGNORES,
                        prompt,
                        player_id=getattr(player, "id", None) if player is not None else None,
                        options=req_options,
                        context=ctx,
                    )
                    seq.step = "hit_modifier_choice"
                    if hasattr(game, "request_decision"):
                        game.request_decision(request)
                    return True

    return False


def _ensure_wound_modifier_choices(manager, game: object, seq: AttackSequence) -> bool:
    """
    Ensure per-attack Wound modifier ignore choices are resolved before grouping wound rolls.
    Returns True if a decision was requested (pause), False otherwise.
    """
    if not bool(getattr(game, "is_authoritative", True)):
        return False
    target = manager._resolve_unit(game, seq.target_unit_id)
    profile = manager._resolve_profile(game, seq.wargear_id, seq.profile_name)
    if target is None or profile is None:
        return False
    from ..utility.modifier_choice import (
        CHOICE_KEEP_ALL,
        CHOICE_LABELS,
        options_for_signed_pairs,
    )

    for idx, attack_instance in enumerate(list(seq.hit_instances or [])):
        if not isinstance(attack_instance, dict):
            continue
        if attack_instance.get("lethal_hit"):
            continue
        if attack_instance.get("wound_modifier_choice") is not None:
            continue
        attacker = manager._resolve_model(game, attack_instance.get("attacker_model_id"))
        if attacker is None:
            continue
        try:
            ignore_rule = profile._ignore_wound_modifier_rule(attacker)
        except (AttributeError, TypeError, ValueError):
            ignore_rule = None
        if not ignore_rule:
            continue

        parent_wargear = getattr(profile, "parent_wargear", None)
        is_melee = bool(
            parent_wargear is not None
            and callable(getattr(parent_wargear, "is_melee", None))
            and parent_wargear.is_melee()
        )
        is_ranged = bool(
            parent_wargear is not None
            and callable(getattr(parent_wargear, "is_ranged", None))
            and parent_wargear.is_ranged()
        )
        rule_attack_type = str(ignore_rule.get("attack_type") or "any").strip().lower()
        if rule_attack_type == "ranged" and not is_ranged:
            continue
        if rule_attack_type == "melee" and not is_melee:
            continue

        preview = profile._wound_target_with_tracking(
            target,
            attacker,
            attack_instance,
            roll_value=1,
            allow_rerolls=False,
            log_roll=False,
        )
        wound_mods = list(preview.get("wound_mods", []) or [])
        options = options_for_signed_pairs(wound_mods)
        if not options:
            attack_instance["wound_modifier_choice"] = CHOICE_KEEP_ALL
            continue

        player = getattr(
            getattr(getattr(attacker, "parent_unit", None), "get_parent_army", lambda: None)(),
            "player",
            None,
        )
        game_map = getattr(game, "map", None)
        provider = getattr(game_map, "hit_modifier_choice_provider", None) if game_map is not None else None
        rule_name = str(ignore_rule.get("name") or "Ignore modifiers").strip() or "Ignore modifiers"
        if callable(provider) and player is not None and bool(getattr(player, "has_control", lambda: False)()):
            try:
                choice = provider(
                    player=player,
                    attacker=attacker,
                    target=target,
                    weapon_profile=profile,
                    ability_name=f"{rule_name} (Wound roll)",
                    choices=options,
                )
            except (AttributeError, TypeError, ValueError):
                choice = None
            if choice not in options:
                choice = CHOICE_KEEP_ALL
            attack_instance["wound_modifier_choice"] = choice

        if attack_instance.get("wound_modifier_choice") is not None:
            continue

        prompt = "Choose which modifiers to ignore."
        req_options = [
            DecisionOption.create(CHOICE_LABELS.get(opt, str(opt)), payload={"choice": opt})
            for opt in options
        ]
        ctx = {
            "sequence_id": int(seq.sequence_id),
            "attack_index": int(idx),
            "attacker_model_id": attack_instance.get("attacker_model_id"),
            "target_unit_id": seq.target_unit_id,
            "wargear_id": seq.wargear_id,
            "profile_name": seq.profile_name,
            "ability_name": f"{rule_name} (Wound roll)",
            "modifier_kind": "wound_roll",
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_HIT_MODIFIER_IGNORES,
            prompt,
            player_id=getattr(player, "id", None) if player is not None else None,
            options=req_options,
            context=ctx,
        )
        seq.step = "wound_modifier_choice"
        if hasattr(game, "request_decision"):
            game.request_decision(request)
        return True

    return False


def resume_after_hit_modifier_choice(manager, game: object, seq: AttackSequence) -> None:
    if seq is None:
        return
    if str(getattr(seq, "step", "")) != "hit_modifier_choice":
        return
    manager._begin_hits(game, seq)


def resume_after_wound_modifier_choice(manager, game: object, seq: AttackSequence) -> None:
    if seq is None:
        return
    if str(getattr(seq, "step", "")) != "wound_modifier_choice":
        return
    manager._begin_wounds(game, seq)


def resume_after_skill_modifier_choice(manager, game: object, seq: AttackSequence) -> None:
    if seq is None:
        return
    if str(getattr(seq, "step", "")) != "skill_modifier_choice":
        return
    manager._begin_hits(game, seq)
