#!/usr/bin/env python3

from __future__ import annotations

import argparse
import cProfile
from collections import Counter
from contextlib import contextmanager
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import pstats
import sys
import time
from typing import Any, Callable, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_headless_self_play as self_play
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.general_plan import (
    GeneralPlan,
    GeneralResourceLedger,
    GeneralRoundDirective,
)
from warhammer40k_ai.utility.entity_ids import get_entity_id


ROOT = SCRIPT_DIR.parents[0]
DEFAULT_PROFILES_PATH = ROOT / "data" / "general_profiles" / "we_vs_aeldari_general_profiles.json"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "general_profile_eval" / "current"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(inner) for key, inner in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(inner) for inner in value]
    if isinstance(value, set):
        return [_json_safe(inner) for inner in sorted(value, key=lambda item: str(item))]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _json_safe(to_dict())
    return str(value)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_label(value: str) -> str:
    text = str(value or "profile").strip() or "profile"
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    return cleaned.strip("._") or "profile"


def _load_profile_document(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected profile document object at {path}.")
    profiles = payload.get("profiles", [])
    if not isinstance(profiles, list):
        raise ValueError(f"Expected profiles array at {path}.")
    return dict(payload)


def _profile_catalog(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for profile in list(document.get("profiles", []) or []):
        if not isinstance(profile, dict):
            continue
        profile_id = str(profile.get("id", "") or "").strip()
        if not profile_id:
            continue
        catalog[profile_id] = dict(profile)
    return dict(sorted(catalog.items(), key=lambda item: (int(item[1].get("index", 0) or 0), str(item[0]))))


def _selected_profiles(document: dict[str, Any], profile_ids: Iterable[str] | None) -> list[dict[str, Any]]:
    wanted = {str(profile_id).strip() for profile_id in list(profile_ids or []) if str(profile_id).strip()}
    catalog = _profile_catalog(document)
    profiles = list(catalog.values())
    if not wanted:
        return sorted(profiles, key=lambda profile: (int(profile.get("index", 0) or 0), str(profile.get("id", ""))))
    selected = [catalog[profile_id] for profile_id in wanted if profile_id in catalog]
    missing = sorted(wanted.difference(set(catalog)))
    if missing:
        raise ValueError(f"Unknown profile id(s): {', '.join(missing)}")
    return sorted(selected, key=lambda profile: (int(profile.get("index", 0) or 0), str(profile.get("id", ""))))


def _profiles_by_id(document: dict[str, Any], profile_ids: Iterable[str]) -> list[dict[str, Any]]:
    profile_ids = [str(profile_id).strip() for profile_id in list(profile_ids or []) if str(profile_id).strip()]
    if not profile_ids:
        return []
    return _selected_profiles(document, profile_ids)


def _profile_pair_label(player1_profile: dict[str, Any], player2_profile: dict[str, Any]) -> str:
    p1_index = int(player1_profile.get("index", 0) or 0)
    p2_index = int(player2_profile.get("index", 0) or 0)
    p1_id = _safe_label(str(player1_profile.get("id", "") or "player1"))
    p2_id = _safe_label(str(player2_profile.get("id", "") or "player2"))
    return f"p1_{p1_index:02d}_{p1_id}_vs_p2_{p2_index:02d}_{p2_id}"


def _profile_pairings(
    *,
    player1_profiles: list[dict[str, Any]],
    player2_profiles: list[dict[str, Any]],
    pairing_mode: str,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    mode = str(pairing_mode or "cartesian").strip().lower()
    if not player1_profiles or not player2_profiles:
        return []
    if mode == "mirror":
        p2_by_id = {str(profile.get("id", "") or ""): profile for profile in player2_profiles}
        pairs = [
            (profile, p2_by_id[str(profile.get("id", "") or "")])
            for profile in player1_profiles
            if str(profile.get("id", "") or "") in p2_by_id
        ]
        if pairs:
            return pairs
        return list(zip(player1_profiles, player2_profiles))
    if mode == "zip":
        if len(player1_profiles) != len(player2_profiles):
            raise ValueError("--pairing-mode zip requires equal player1/player2 profile counts.")
        return list(zip(player1_profiles, player2_profiles))
    if mode != "cartesian":
        raise ValueError(f"Unknown pairing mode: {pairing_mode}")
    return [(p1, p2) for p1 in player1_profiles for p2 in player2_profiles]


def _floatish(value: Any, default: float = 0.0) -> float:
    stat_average = getattr(value, "stat_average", None)
    if callable(stat_average):
        try:
            return float(stat_average())
        except (TypeError, ValueError):
            return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _entity_id(entity: object) -> str:
    return str(get_entity_id(entity) or getattr(entity, "id", "") or getattr(entity, "_id", "") or "")


def _army_units(player: object) -> list[object]:
    get_army = getattr(player, "get_army", None)
    army = get_army() if callable(get_army) else getattr(player, "army", None)
    return sorted(
        [unit for unit in list(getattr(army, "units", []) or []) if _entity_id(unit)],
        key=lambda unit: _entity_id(unit),
    )


def _player_for_id(game: object, player_id: str) -> object | None:
    for player in list(getattr(game, "players", []) or []):
        if str(getattr(player, "id", "") or "") == str(player_id or ""):
            return player
    return None


def _opponent_player(game: object, player_id: str) -> object | None:
    for player in list(getattr(game, "players", []) or []):
        if str(getattr(player, "id", "") or "") != str(player_id or ""):
            return player
    return None


def _is_alive(entity: object) -> bool:
    value = getattr(entity, "is_alive", True)
    return bool(value() if callable(value) else value)


def _unit_keywords(unit: object) -> set[str]:
    keywords: list[object] = []
    keywords.extend(list(getattr(unit, "keywords", []) or []))
    keywords.extend(list(getattr(unit, "faction_keywords", []) or []))
    for model in list(getattr(unit, "models", []) or []):
        keywords.extend(list(getattr(model, "keywords", []) or []))
        keywords.extend(list(getattr(model, "faction_keywords", []) or []))
    if bool(getattr(unit, "is_vehicle", False)):
        keywords.append("VEHICLE")
    if bool(getattr(unit, "is_monster", False)):
        keywords.append("MONSTER")
    return {str(keyword).strip().upper() for keyword in keywords if str(keyword).strip()}


def _unit_wounds(unit: object) -> float:
    total = 0.0
    for model in list(getattr(unit, "models", []) or []):
        if not _is_alive(model):
            continue
        wounds = getattr(model, "wounds", None)
        if wounds is None:
            wounds = getattr(model, "max_wounds", None)
        total += max(0.0, _floatish(wounds, 1.0))
    if total <= 0.0:
        total = _floatish(getattr(unit, "wounds", 1.0), 1.0)
    return max(1.0, float(total))


def _unit_objective_control(unit: object) -> float:
    total = 0.0
    for model in list(getattr(unit, "models", []) or []):
        if _is_alive(model):
            total += max(0.0, _floatish(getattr(model, "objective_control", 0.0), 0.0))
    if total <= 0.0:
        total = _floatish(getattr(unit, "objective_control", 0.0), 0.0)
    return max(0.0, float(total))


def _unit_movement(unit: object) -> float:
    values: list[float] = []
    for model in list(getattr(unit, "models", []) or []):
        values.append(_floatish(getattr(model, "movement", None), 0.0))
    if values:
        return max(values)
    return _floatish(getattr(unit, "movement", None), 0.0)


def _unit_wargear_counts(unit: object) -> tuple[int, int]:
    melee = 0
    ranged = 0
    for model in list(getattr(unit, "models", []) or []):
        for wargear in list(getattr(model, "wargear", []) or []):
            is_melee = getattr(wargear, "is_melee", None)
            is_ranged = getattr(wargear, "is_ranged", None)
            if callable(is_melee) and bool(is_melee()):
                melee += 1
                continue
            if callable(is_ranged) and bool(is_ranged()):
                ranged += 1
                continue
            name = str(getattr(wargear, "name", "") or getattr(wargear, "id", "") or "").lower()
            if any(token in name for token in ("axe", "blade", "chain", "claw", "fist", "sword", "talon")):
                melee += 1
            elif name:
                ranged += 1
    return melee, ranged


def _is_transport(unit: object) -> bool:
    capacity = _floatish(getattr(unit, "transport_capacity", 0), 0.0)
    return bool(getattr(unit, "is_transport", False)) or "TRANSPORT" in _unit_keywords(unit) or capacity > 0.0


def _rank_enemy_targets(game: object, player_id: str, mode: str) -> list[str]:
    opponent = _opponent_player(game, player_id)
    units = _army_units(opponent) if opponent is not None else []
    target_mode = str(mode or "threat").strip().lower()

    def score(unit: object) -> tuple[float, str]:
        keywords = _unit_keywords(unit)
        wounds = _unit_wounds(unit)
        oc = _unit_objective_control(unit)
        if target_mode in {"objective_denial", "denial"}:
            value = 4.0 * oc + 0.6 * wounds
            if keywords.intersection({"BATTLELINE", "INFANTRY"}):
                value += 4.0
        else:
            value = wounds + 2.5 * oc
            if keywords.intersection({"CHARACTER", "MONSTER", "VEHICLE", "PSYKER"}):
                value += 4.0
            if keywords.intersection({"BATTLELINE", "INFANTRY"}):
                value += 1.5
        return (-float(value), _entity_id(unit))

    return [_entity_id(unit) for unit in sorted(units, key=score)]


def _rank_friendly_commit_units(game: object, player_id: str) -> list[str]:
    player = _player_for_id(game, player_id)
    units = [unit for unit in _army_units(player) if not _is_transport(unit)]

    def score(unit: object) -> tuple[float, str]:
        melee, ranged = _unit_wargear_counts(unit)
        value = 2.0 * melee + 0.8 * ranged + 0.4 * _unit_movement(unit) + 0.15 * _unit_wounds(unit)
        return (-float(value), _entity_id(unit))

    return [_entity_id(unit) for unit in sorted(units, key=score)]


def _rank_friendly_preserve_units(game: object, player_id: str) -> list[str]:
    player = _player_for_id(game, player_id)
    units = [unit for unit in _army_units(player) if not _is_transport(unit)]

    def score(unit: object) -> tuple[float, str]:
        _melee, ranged = _unit_wargear_counts(unit)
        value = _unit_wounds(unit) + 0.5 * _unit_movement(unit) + 2.0 * ranged
        return (-float(value), _entity_id(unit))

    return [_entity_id(unit) for unit in sorted(units, key=score)]


def _round_directives_from_profile(profile: dict[str, Any], preserve_rank: list[str]) -> dict[int, GeneralRoundDirective]:
    directives: dict[int, GeneralRoundDirective] = {}
    profile_id = str(profile.get("id", "") or "")
    for raw in list(profile.get("round_directives", []) or []):
        if not isinstance(raw, dict):
            continue
        battle_round = int(raw.get("battle_round", 0) or 0)
        if battle_round <= 0:
            continue
        preserve_count = max(0, int(raw.get("preserve_unit_count", 0) or 0))
        directives[battle_round] = GeneralRoundDirective(
            battle_round=battle_round,
            posture=str(raw.get("posture", "") or "stage"),
            push_priority=_floatish(raw.get("push_priority", 0.0), 0.0),
            stage_priority=_floatish(raw.get("stage_priority", 0.0), 0.0),
            preserve_priority=_floatish(raw.get("preserve_priority", 0.0), 0.0),
            scoring_preservation_priority=_floatish(raw.get("scoring_preservation_priority", 0.0), 0.0),
            cp_reserve_target=_floatish(raw.get("cp_reserve_target", 0.0), 0.0),
            preserve_unit_ids=preserve_rank[:preserve_count],
            metadata={
                "source": "general_profile_eval",
                "eval_profile_id": profile_id,
                "profile_mode": str(profile.get("mode", "") or ""),
            },
        )
    return directives


def _target_order_overrides(profile: dict[str, Any], ranked_targets: list[str]) -> dict[str, dict[str, Any]]:
    settings = dict(profile.get("target_order", {}) or {})
    count = max(0, int(settings.get("count", 0) or 0))
    base = _floatish(settings.get("base_priority", 0.98), 0.98)
    decay = _floatish(settings.get("priority_decay", 0.08), 0.08)
    minimum = _floatish(settings.get("min_priority", 0.55), 0.55)
    first_count = max(0, int(settings.get("intent_first_count", 1) or 1))
    desired_first = _floatish(settings.get("desired_kill_probability_first", 0.88), 0.88)
    desired_rest = _floatish(settings.get("desired_kill_probability_rest", 0.75), 0.75)
    overrides: dict[str, dict[str, Any]] = {}
    for index, target_id in enumerate(ranked_targets[:count]):
        priority = max(minimum, base - decay * index)
        overrides[str(target_id)] = {
            "intent": "kill" if index < first_count else "soften",
            "priority": priority,
            "desired_kill_probability": desired_first if index == 0 else desired_rest,
            "max_overkill_wounds": _floatish(settings.get("max_overkill_wounds", 1.5), 1.5),
            "preferred_phase": str(settings.get("preferred_phase", "shooting") or "shooting"),
            "allowed_resource_kinds": list(settings.get("allowed_resource_kinds", []) or []),
            "metadata": {
                "source": "general_profile_eval",
                "eval_profile_id": str(profile.get("id", "") or ""),
                "target_rank_index": int(index),
            },
        }
    return overrides


def _unit_order_overrides(
    profile: dict[str, Any],
    commit_unit_ids: list[str],
    preserve_unit_ids: list[str],
    ranked_targets: list[str],
) -> dict[str, dict[str, Any]]:
    primary_target = ranked_targets[0] if ranked_targets else ""
    backup_targets = ranked_targets[1:4]
    settings = dict(profile.get("unit_order", {}) or {})
    profile_id = str(profile.get("id", "") or "")
    orders: dict[str, dict[str, Any]] = {}
    for unit_id in commit_unit_ids:
        shooting_intent = str(settings.get("shooting_intent", "opportunistic") or "opportunistic")
        charge_intent = str(settings.get("charge_intent", "opportunistic") or "opportunistic")
        fight_intent = str(settings.get("fight_intent", "opportunistic") or "opportunistic")
        intentionally_skip = bool(settings.get("intentionally_skip_shooting", False))
        accept_ineligible = bool(settings.get("intentionally_accept_shooting_ineligible", False))
        orders[str(unit_id)] = {
            "role": str(settings.get("role", "melee_first") or "melee_first"),
            "primary_target_unit_id": primary_target,
            "backup_target_unit_ids": backup_targets,
            "constraint_mode": str(settings.get("constraint_mode", "constrain") or "constrain"),
            "order_strength": _floatish(settings.get("order_strength", 0.75), 0.75),
            "shooting_intent": shooting_intent,
            "charge_intent": charge_intent,
            "fight_intent": fight_intent,
            "movement_intent": str(settings.get("movement_intent", "execute_profile_plan") or "execute_profile_plan"),
            "movement_order": {
                "intent": str(settings.get("movement_intent", "execute_profile_plan") or "execute_profile_plan"),
                "desired_action": str(settings.get("desired_action", "") or ""),
                "charge_staging_target_unit_id": primary_target,
                "avoid_becoming_shooting_ineligible": not accept_ineligible,
                "intentionally_accept_shooting_ineligible": accept_ineligible,
            },
            "shooting_order": {
                "intent": shooting_intent,
                "primary_target_unit_id": "" if intentionally_skip else primary_target,
                "backup_target_unit_ids": backup_targets,
                "requires_los": False,
                "requires_half_range": False,
                "requires_stationary": False,
            },
            "charge_order": {
                "intent": charge_intent,
                "primary_target_unit_id": primary_target,
                "backup_target_unit_ids": backup_targets,
                "intentionally_skip_shooting": intentionally_skip,
            },
            "fight_order": {
                "intent": fight_intent,
                "primary_target_unit_id": primary_target,
                "backup_target_unit_ids": backup_targets,
            },
            "metadata": {
                "source": "general_profile_eval",
                "eval_profile_id": profile_id,
                "source_intent_kinds": ["explicit_general_unit_order", "general_profile_eval"],
            },
        }
    for unit_id in preserve_unit_ids:
        orders.setdefault(
            str(unit_id),
            {
                "role": "preserve",
                "preserve": True,
                "constraint_mode": "constrain",
                "order_strength": 0.8,
                "movement_order": {
                    "intent": "preserve_hidden",
                    "desired_action": "normal_move",
                    "avoid_becoming_shooting_ineligible": True,
                    "intentionally_accept_shooting_ineligible": False,
                },
                "shooting_order": {"intent": "opportunistic"},
                "charge_order": {"intent": "hold", "intentionally_skip_shooting": False},
                "fight_order": {"intent": "hold"},
                "metadata": {
                    "source": "general_profile_eval",
                    "eval_profile_id": profile_id,
                    "source_intent_kinds": ["general_preserve_directive", "general_profile_eval"],
                },
            },
        )
    return orders


def _updated_resource_policies(
    plan: GeneralPlan,
    profile: dict[str, Any],
    primary_target_id: str,
) -> dict[str, Any]:
    resource_settings = dict(profile.get("resource_policy", {}) or {})
    target_kinds = {str(kind) for kind in list(resource_settings.get("target_kinds", []) or [])}
    target_bound_kinds = {str(kind) for kind in list(resource_settings.get("target_bound_kinds", []) or [])}
    if not target_kinds:
        return dict(plan.limited_resource_policy)
    updated: dict[str, Any] = {}
    for resource_id, policy in dict(plan.limited_resource_policy).items():
        kind = str(getattr(policy, "resource_kind", "") or "")
        if kind not in target_kinds:
            updated[str(resource_id)] = policy
            continue
        updated[str(resource_id)] = replace(
            policy,
            status=str(resource_settings.get("status", getattr(policy, "status", "reserved")) or "reserved"),
            reserved_for_round=(
                int(resource_settings["reserved_for_round"])
                if "reserved_for_round" in resource_settings and resource_settings.get("reserved_for_round") is not None
                else getattr(policy, "reserved_for_round", None)
            ),
            reserved_for_target_unit_id=primary_target_id if kind in target_bound_kinds and primary_target_id else None,
            authorization_threshold=_floatish(
                resource_settings.get("authorization_threshold", getattr(policy, "authorization_threshold", 0.0)),
                0.0,
            ),
            fallback_policy=str(
                resource_settings.get("fallback_policy", getattr(policy, "fallback_policy", "local_fallback"))
                or "local_fallback"
            ),
            metadata={
                **dict(getattr(policy, "metadata", {}) or {}),
                "source": "general_profile_eval",
                "eval_profile_id": str(profile.get("id", "") or ""),
                "profile_mode": str(profile.get("mode", "") or ""),
            },
        )
    return updated


def _updated_transport_policy(plan: GeneralPlan, profile: dict[str, Any]) -> dict[str, Any]:
    overrides = dict(profile.get("transport_policy_overrides", {}) or {})
    if not overrides:
        return dict(plan.transport_policy)
    updated: dict[str, Any] = {}
    for unit_id, doctrine in dict(plan.transport_policy).items():
        updated[str(unit_id)] = replace(
            doctrine,
            desired_round=(
                int(overrides["desired_round"])
                if "desired_round" in overrides and overrides.get("desired_round") is not None
                else getattr(doctrine, "desired_round", None)
            ),
            protected_until_round=(
                int(overrides["protected_until_round"])
                if "protected_until_round" in overrides and overrides.get("protected_until_round") is not None
                else getattr(doctrine, "protected_until_round", None)
            ),
            preserve_passengers=bool(overrides.get("preserve_passengers", getattr(doctrine, "preserve_passengers", True))),
            priority=_floatish(overrides.get("priority", getattr(doctrine, "priority", 0.0)), 0.0),
            metadata={
                **dict(getattr(doctrine, "metadata", {}) or {}),
                "source": "general_profile_eval",
                "eval_profile_id": str(profile.get("id", "") or ""),
            },
        )
    return updated


def _clear_plan_dependents(game: object, player_id: str) -> None:
    pid = str(player_id or "")
    for attr in ("_deployment_order_bundles", "_prebattle_order_bundles", "_deployment_plans"):
        cache = getattr(game, attr, None)
        if isinstance(cache, dict):
            cache.pop(pid, None)
    battle_plans = getattr(game, "_battle_round_plans", None)
    if isinstance(battle_plans, dict):
        for key in [key for key in battle_plans if isinstance(key, tuple) and len(key) >= 2 and str(key[1]) == pid]:
            battle_plans.pop(key, None)


def _apply_profile_to_plan(game: object, plan: GeneralPlan, profile: dict[str, Any]) -> tuple[GeneralPlan, dict[str, Any]]:
    profile_id = str(profile.get("id", "") or "")
    if str(profile.get("mode", "") or "") == "default":
        return plan, {}
    player_id = str(plan.player_id)
    target_settings = dict(profile.get("target_order", {}) or {})
    ranked_targets = _rank_enemy_targets(
        game,
        player_id,
        str(target_settings.get("target_priority_mode", profile.get("target_mode", "threat")) or "threat"),
    )
    primary_target = ranked_targets[0] if ranked_targets else ""
    preserve_rank = _rank_friendly_preserve_units(game, player_id)
    preserve_count = max(0, int(profile.get("preserve_unit_count", 0) or 0))
    preserve_ids = preserve_rank[:preserve_count]
    commit_rank = [unit_id for unit_id in _rank_friendly_commit_units(game, player_id) if unit_id not in set(preserve_ids)]
    commit_count = max(0, int(profile.get("commit_unit_count", 0) or 0))
    commit_ids = commit_rank[:commit_count]

    directives = dict(plan.battle_round_directives)
    directives.update(_round_directives_from_profile(profile, preserve_rank))
    resource_policies = _updated_resource_policies(plan, profile, primary_target)
    transport_policy = _updated_transport_policy(plan, profile)
    target_orders = _target_order_overrides(profile, ranked_targets)
    unit_orders = _unit_order_overrides(profile, commit_ids, preserve_ids, ranked_targets)
    cp_policy = {
        **dict(plan.cp_policy or {}),
        **dict(profile.get("cp_policy_overrides", {}) or {}),
        "eval_profile_id": profile_id,
    }
    target_priority_doctrine = {
        **dict(plan.target_priority_doctrine or {}),
        "target_orders": target_orders,
        "unit_order_overrides": unit_orders,
        "eval_profile_id": profile_id,
        "eval_profile_mode": str(profile.get("mode", "") or ""),
        "eval_profile_description": str(profile.get("description", "") or ""),
    }
    metadata = {
        **dict(plan.metadata or {}),
        "eval_profile_id": profile_id,
        "eval_profile_description": str(profile.get("description", "") or ""),
        "eval_profile_mode": str(profile.get("mode", "") or ""),
    }
    updated = replace(
        plan,
        strategic_posture=str(profile.get("strategic_posture", plan.strategic_posture) or plan.strategic_posture),
        battle_round_directives=directives,
        limited_resource_policy=resource_policies,
        resource_ledger=GeneralResourceLedger(
            resources=resource_policies,
            metadata={
                **dict(getattr(plan.resource_ledger, "metadata", {}) or {}),
                "source": "general_profile_eval",
                "eval_profile_id": profile_id,
            },
        ),
        transport_policy=transport_policy,
        target_priority_doctrine=target_priority_doctrine,
        cp_policy=cp_policy,
        metadata=metadata,
    )
    event = {
        "profile_id": profile_id,
        "primary_target_unit_id": primary_target,
        "backup_target_unit_ids": ranked_targets[1:4],
        "target_override_count": int(len(target_orders)),
        "unit_order_override_count": int(len(unit_orders)),
        "preserve_unit_count": int(len(preserve_ids)),
        "cp_policy": cp_policy,
        "resource_policy_status_counts": dict(Counter(str(getattr(policy, "status", "")) for policy in resource_policies.values())),
    }
    return updated, event


@contextmanager
def _general_profile_context(
    profiles_by_player_slot: dict[int, dict[str, Any]],
    events_by_player_slot: dict[int, list[dict[str, Any]]],
):
    original_callable: Callable[..., Any] = getattr(Game, "get_or_create_general_plan")
    had_class_attr = "get_or_create_general_plan" in Game.__dict__
    original_class_attr = Game.__dict__.get("get_or_create_general_plan")

    def _wrapped_get_or_create_general_plan(game: Game, player_id: str):
        plan = original_callable(game, player_id)
        players = list(getattr(game, "players", []) or [])
        player_slot = -1
        for index, player in enumerate(players):
            if str(getattr(player, "id", "") or "") == str(player_id or ""):
                player_slot = int(index)
                break
        if player_slot < 0:
            return plan
        profile = profiles_by_player_slot.get(player_slot)
        if profile is None:
            return plan
        if str(dict(getattr(plan, "metadata", {}) or {}).get("eval_profile_id", "") or "") == str(profile.get("id", "") or ""):
            return plan
        updated, event = _apply_profile_to_plan(game, plan, profile)
        if event:
            event = {
                **event,
                "player_slot": f"player{player_slot + 1}",
                "player_id": str(player_id),
            }
            key = game._general_plan_key(str(player_id))
            game._general_plans[key] = updated
            _clear_plan_dependents(game, str(player_id))
            events_by_player_slot.setdefault(player_slot, []).append(event)
            record_event = getattr(game, "record_orchestration_audit_event", None)
            if callable(record_event):
                record_event(
                    "general_profile_applied",
                    player_id=str(player_id),
                    plan_id=str(updated.plan_id),
                    metadata=event,
                )
            return updated
        return plan

    Game.get_or_create_general_plan = _wrapped_get_or_create_general_plan
    try:
        yield
    finally:
        if had_class_attr:
            Game.get_or_create_general_plan = original_class_attr
        else:
            delattr(Game, "get_or_create_general_plan")


def _run_profile_game(
    *,
    run_index: int,
    player1_profile: dict[str, Any],
    player2_profile: dict[str, Any],
    player1_army: str,
    player2_army: str,
    seed: int,
    max_phase_steps: int,
    output_dir: Path,
    profile_enabled: bool,
    profile_lines: int,
    replay_dir: str,
    write_records: bool,
) -> dict[str, Any]:
    player1_profile_id = str(player1_profile.get("id", "") or "player1_profile")
    player2_profile_id = str(player2_profile.get("id", "") or "player2_profile")
    label = _profile_pair_label(player1_profile, player2_profile)
    events_by_slot: dict[int, list[dict[str, Any]]] = {0: [], 1: []}
    profiler = cProfile.Profile() if profile_enabled else None

    def _execute() -> dict[str, Any]:
        with _general_profile_context(
            {
                0: player1_profile,
                1: player2_profile,
            },
            events_by_slot,
        ):
            with self_play._deterministic_uuid4_context(int(seed)):
                return self_play._run_single_game(
                    game_id=f"general_profile_eval:{int(run_index):06d}:seed:{int(seed)}",
                    player1_army_file=str(player1_army),
                    player2_army_file=str(player2_army),
                    max_phase_steps=int(max_phase_steps),
                    game_seed=int(seed),
                    replay_dir=str(replay_dir or ""),
                    export_records=bool(write_records),
                )

    started = time.perf_counter()
    if profiler is not None:
        result = profiler.runcall(_execute)
    else:
        result = _execute()
    elapsed = float(time.perf_counter() - started)

    profile_artifacts: dict[str, str] = {}
    if profiler is not None:
        profile_dir = output_dir / "profiles"
        profile_dir.mkdir(parents=True, exist_ok=True)
        prof_path = profile_dir / f"{label}.prof"
        txt_path = profile_dir / f"{label}.txt"
        profiler.dump_stats(str(prof_path))
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("tottime")
        stats.print_stats(max(1, int(profile_lines)))
        txt_path.write_text(stream.getvalue(), encoding="utf-8")
        profile_artifacts = {
            "profile_binary": str(prof_path.resolve()),
            "profile_text": str(txt_path.resolve()),
        }

    records = list(result.pop("records", []) or [])
    if write_records:
        _write_json(output_dir / f"{label}_records.json", records)

    summary = {
        "run_index": int(run_index),
        "profile_pair_id": label,
        "player1_profile_id": player1_profile_id,
        "player1_profile_index": int(player1_profile.get("index", 0) or 0),
        "player1_profile_description": str(player1_profile.get("description", "") or ""),
        "player2_profile_id": player2_profile_id,
        "player2_profile_index": int(player2_profile.get("index", 0) or 0),
        "player2_profile_description": str(player2_profile.get("description", "") or ""),
        "seed": int(seed),
        "elapsed_seconds": round(elapsed, 6),
        "decision_record_count": int(len(records)),
        "applied_general_profile_events": {
            "player1": list(events_by_slot.get(0, []) or []),
            "player2": list(events_by_slot.get(1, []) or []),
        },
        "winner_army_label": str(result.get("winner_army_label", "") or ""),
        "winner_score_line": str(result.get("winner_score_line", "") or ""),
        "phase_steps": int(result.get("phase_steps", 0) or 0),
        "scoreboard": dict(result.get("scoreboard", {}) or {}),
        "profile_artifacts": profile_artifacts,
        "game_result": result,
    }
    _write_json(output_dir / f"{label}_summary.json", summary)
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate reusable GeneralPlan profiles in deterministic WE vs Aeldari headless games.",
    )
    parser.add_argument("--profiles", default=str(DEFAULT_PROFILES_PATH), help="General profile JSON document.")
    parser.add_argument(
        "--profile-id",
        action="append",
        default=[],
        help="Profile id to run for both players. Repeat to select many.",
    )
    parser.add_argument(
        "--player1-profile-id",
        action="append",
        default=[],
        help="Profile id for Player 1. Repeat to select many.",
    )
    parser.add_argument(
        "--player2-profile-id",
        action="append",
        default=[],
        help="Profile id for Player 2. Repeat to select many.",
    )
    parser.add_argument(
        "--pairing-mode",
        choices=("cartesian", "mirror", "zip"),
        default="cartesian",
        help="How to pair selected Player 1 and Player 2 profiles.",
    )
    parser.add_argument("--list-profiles", action="store_true", help="List configured profiles and exit.")
    parser.add_argument("--json", action="store_true", help="With --list-profiles, print the full profile JSON.")
    parser.add_argument("--player1-army", default="", help="Player 1 army list path. Defaults to profile document value.")
    parser.add_argument("--player2-army", default="", help="Player 2 army list path. Defaults to profile document value.")
    parser.add_argument("--seed", type=int, default=0, help="Deterministic seed. Defaults to profile document value.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for summaries and profiles.")
    parser.add_argument("--max-phase-steps", type=int, default=50, help="Battle phase safety cap per game.")
    parser.add_argument("--decision-record-max", type=int, default=4096, help="WH40K_DECISION_RECORD_MAX for each run.")
    parser.add_argument("--no-profile", action="store_true", help="Disable cProfile artifacts.")
    parser.add_argument("--profile-lines", type=int, default=80, help="Readable cProfile line count.")
    parser.add_argument("--replay-dir", default="", help="Optional replay output directory.")
    parser.add_argument("--write-records", action="store_true", help="Write per-profile DecisionRecord JSON files.")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    profiles_path = Path(str(args.profiles)).expanduser()
    if not profiles_path.is_absolute():
        profiles_path = ROOT / profiles_path
    document = _load_profile_document(profiles_path)
    catalog = _profile_catalog(document)
    generic_profiles = _profiles_by_id(document, args.profile_id)
    player1_profiles = _profiles_by_id(document, args.player1_profile_id) or generic_profiles or list(catalog.values())
    player2_profiles = _profiles_by_id(document, args.player2_profile_id) or generic_profiles or list(catalog.values())
    profile_pairs = _profile_pairings(
        player1_profiles=player1_profiles,
        player2_profiles=player2_profiles,
        pairing_mode=str(args.pairing_mode),
    )
    if bool(args.list_profiles):
        if bool(args.json):
            print(json.dumps(_json_safe({"profiles": list(catalog.values())}), indent=2, sort_keys=True))
            return
        for profile in list(catalog.values()):
            print(f"{int(profile.get('index', 0) or 0):02d} {profile.get('id', '')}: {profile.get('description', '')}")
        return

    os.environ["WH40K_DECISION_RECORD_MAX"] = str(max(1, int(args.decision_record_max or 4096)))
    player1_army = str(args.player1_army or document.get("default_player1_army", "") or "")
    player2_army = str(args.player2_army or document.get("default_player2_army", "") or "")
    if not player1_army or not player2_army:
        raise ValueError("Both player army paths are required.")
    seed = int(args.seed or document.get("default_seed", 2026052000) or 2026052000)
    output_dir = Path(str(args.output_dir)).expanduser()
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, Any]] = []
    for run_index, (player1_profile, player2_profile) in enumerate(profile_pairs):
        summary = _run_profile_game(
            run_index=run_index,
            player1_profile=player1_profile,
            player2_profile=player2_profile,
            player1_army=player1_army,
            player2_army=player2_army,
            seed=seed,
            max_phase_steps=max(1, int(args.max_phase_steps or 50)),
            output_dir=output_dir,
            profile_enabled=not bool(args.no_profile),
            profile_lines=max(1, int(args.profile_lines or 80)),
            replay_dir=str(args.replay_dir or ""),
            write_records=bool(args.write_records),
        )
        summaries.append(summary)
        print(
            f"{summary['player1_profile_index']:02d} {summary['player1_profile_id']} vs "
            f"{summary['player2_profile_index']:02d} {summary['player2_profile_id']}: "
            f"{summary['winner_score_line']} in {summary['elapsed_seconds']:.2f}s"
        )
    _write_json(
        output_dir / "summary.json",
        {
            "profiles_path": str(profiles_path.resolve()),
            "player1_army": player1_army,
            "player2_army": player2_army,
            "seed": seed,
            "decision_record_max": int(os.environ["WH40K_DECISION_RECORD_MAX"]),
            "pairing_mode": str(args.pairing_mode),
            "profile_pair_count": int(len(profile_pairs)),
            "profile_privacy": {
                "opponent_profile_hidden_from_general_plan": True,
                "pair_ids_are_report_only": True,
            },
            "summaries": summaries,
        },
    )


if __name__ == "__main__":
    main()
