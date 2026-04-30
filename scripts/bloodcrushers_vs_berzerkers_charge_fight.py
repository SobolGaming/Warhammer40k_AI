#!/usr/bin/env python3
"""Headless Bloodcrushers into Khorne Berzerkers charge/fight scenario.

This is a focused smoke script for real datasheet units. It uses Waha datasheets,
engine decision requests, the movement solver for the charge move, and the
FightPhaseManager flow for melee weapon declarations and attack resolution.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
from pathlib import Path
from typing import Any

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_ALLOCATE_DAMAGE,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_CHARGE,
    DECISION_DECLARE_MELEE_WEAPONS,
    DECISION_MOVE_UNIT,
    DECISION_RESOLVE_COHERENCY,
    DECISION_SELECT_FIGHT_TARGETS,
    DECISION_SELECT_UNIT,
)
from warhammer40k_ai.engine.decisions import DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.movement_intent import MovementIntent
from warhammer40k_ai.engine.movement_solver import generate_move_unit_candidates
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.game_context import game_context
from warhammer40k_ai.utility import dice as dice_module
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper

ROOT = Path(__file__).resolve().parents[1]
WAHAPEDIA_DATA = ROOT / "wahapedia_data"


def _normalized_name(value: object) -> str:
    return str(value or "").strip().lower().replace("’", "'")


class _FixedPrefixRandomSource:
    def __init__(self, *, seed: int, randint_prefix: list[int]) -> None:
        self._rng = random.Random(seed)
        self._randint_prefix = list(randint_prefix)

    def seed(self, seed: int | None) -> None:
        self._rng.seed(seed)

    def random(self) -> float:
        return self._rng.random()

    def randint(self, a: int, b: int) -> int:
        if self._randint_prefix and int(a) == 1 and int(b) == 6:
            self._rng.randint(a, b)
            return int(self._randint_prefix.pop(0))
        return int(self._rng.randint(a, b))

    def randrange(self, *args: int) -> int:
        return int(self._rng.randrange(*args))

    def uniform(self, a: float, b: float) -> float:
        return float(self._rng.uniform(a, b))

    def choice(self, seq):
        return self._rng.choice(seq)

    def sample(self, population, k: int):
        return self._rng.sample(population, k)

    def shuffle(self, values) -> None:
        self._rng.shuffle(values)

    def getstate(self):
        return self._rng.getstate(), tuple(self._randint_prefix)

    def setstate(self, state) -> None:
        rng_state, prefix = state
        self._rng.setstate(rng_state)
        self._randint_prefix = list(prefix)


def _stable_id_part(value: object) -> str:
    raw = str(value or "").strip().lower()
    cleaned = [character if character.isalnum() else "-" for character in raw]
    compact = "-".join(part for part in "".join(cleaned).split("-") if part)
    return compact or "item"


def _assign_stable_unit_ids(unit: Unit, slug: str) -> None:
    unit._id = f"unit:{slug}"
    for index, model in enumerate(unit.models):
        model._id = f"model:{slug}:{index:02d}"
    seen_wargear: set[int] = set()
    for index, wargear in enumerate(list(getattr(unit, "possible_wargear", []) or [])):
        marker = id(wargear)
        if marker in seen_wargear:
            continue
        seen_wargear.add(marker)
        wargear_slug = _stable_id_part(getattr(wargear, "name", f"wargear-{index}"))
        wargear._id = f"wargear:{slug}:{index:02d}:{wargear_slug}"
        for profile_name, profile in sorted((getattr(wargear, "profiles", {}) or {}).items()):
            profile._id = f"profile:{slug}:{index:02d}:{_stable_id_part(profile_name)}"


def _wargear_by_name(unit: Unit, name: str):
    target = _normalized_name(name)
    for wargear in list(getattr(unit, "possible_wargear", []) or []):
        if _normalized_name(getattr(wargear, "name", "")) == target:
            return wargear
    raise RuntimeError(f"{unit.name}: missing wargear {name!r}")


def _replace_wargear(model: object, old_name: str, new_wargear: object) -> None:
    target = _normalized_name(old_name)
    for index, wargear in enumerate(list(getattr(model, "wargear", []) or [])):
        if _normalized_name(getattr(wargear, "name", "")) == target:
            model.wargear[index] = new_wargear
            return
    raise RuntimeError(f"{getattr(model, 'name', 'Model')}: missing wargear {old_name!r}")


def _refresh_rule_caches(unit: Unit) -> None:
    for method_name in (
        "_invalidate_ability_cache",
        "_refresh_charge_end_mortal_wounds_flags",
        "_refresh_fight_within_3_flags",
        "_refresh_bearer_unit_common_modifiers",
    ):
        method = getattr(unit, method_name, None)
        if callable(method):
            method()


def _build_bloodcrushers(waha: WahaHelper) -> Unit:
    datasheet = waha.get_datasheet("Bloodcrushers", datasheet_id="000001115", faction_id="CD")
    unit = Unit(datasheet, quantity=6)
    unit.apply_wargear_options_strict("instrument of Chaos")
    unit.apply_wargear_options_strict("daemonic icon")
    _refresh_rule_caches(unit)
    return unit


def _build_berzerkers(waha: WahaHelper) -> Unit:
    datasheet = waha.get_datasheet("Khorne Berzerkers", datasheet_id="000002627", faction_id="WE")
    unit = Unit(datasheet, quantity=10)
    plasma_pistol = _wargear_by_name(unit, "Plasma pistol")
    eviscerator = _wargear_by_name(unit, "Khornate eviscerator")

    _replace_wargear(unit.models[0], "Bolt pistol", plasma_pistol)
    for model_index in (1, 2):
        _replace_wargear(unit.models[model_index], "Bolt pistol", plasma_pistol)
        _replace_wargear(unit.models[model_index], "Chainblade", eviscerator)
    unit.models[3].optional_wargear.append("icon of khorne")

    _refresh_rule_caches(unit)
    return unit


def _count_wargear(unit: Unit, name: str, *, model_name: str | None = None) -> int:
    target = _normalized_name(name)
    count = 0
    for model in unit.models:
        if model_name is not None and _normalized_name(model.name) != _normalized_name(model_name):
            continue
        count += sum(1 for wargear in model.wargear if _normalized_name(wargear.name) == target)
    return count


def _count_optional(unit: Unit, name: str) -> int:
    target = _normalized_name(name)
    return sum(
        1
        for model in unit.models
        for item in list(getattr(model, "optional_wargear", []) or [])
        if _normalized_name(item) == target
    )


def _assert_requested_loadouts(bloodcrushers: Unit, berzerkers: Unit) -> None:
    if len(bloodcrushers.models) != 6:
        raise RuntimeError("Bloodcrushers unit is not 6 models.")
    if _count_optional(bloodcrushers, "instrument of chaos") != 1:
        raise RuntimeError("Bloodcrushers loadout does not include exactly 1 Instrument of Chaos.")
    if _count_optional(bloodcrushers, "daemonic icon") != 1:
        raise RuntimeError("Bloodcrushers loadout does not include exactly 1 Daemonic Icon.")

    if len(berzerkers.models) != 10:
        raise RuntimeError("Khorne Berzerkers unit is not 10 models.")
    if _count_wargear(berzerkers, "Plasma pistol", model_name="Khorne Berzerker Champion") != 1:
        raise RuntimeError("Khorne Berzerker Champion does not have exactly 1 plasma pistol.")
    if _count_wargear(berzerkers, "Plasma pistol", model_name="Khorne Berzerker") != 2:
        raise RuntimeError("Khorne Berzerkers do not have exactly 2 squad plasma pistols.")
    if _count_wargear(berzerkers, "Khornate eviscerator", model_name="Khorne Berzerker") != 2:
        raise RuntimeError("Khorne Berzerkers do not have exactly 2 Khornate eviscerators.")
    if _count_optional(berzerkers, "icon of khorne") != 1:
        raise RuntimeError("Khorne Berzerkers loadout does not include exactly 1 Icon of Khorne.")


def _deploy_units(game: Game, bloodcrushers: Unit, berzerkers: Unit) -> None:
    for unit in (bloodcrushers, berzerkers):
        unit.deployed = True
        unit.reserve_status = "deployed"

    bloodcrusher_positions = [
        (18.0, 22.0),
        (14.0, 16.0),
        (14.0, 21.0),
        (14.0, 26.0),
        (10.0, 18.5),
        (10.0, 23.5),
    ]
    for model, (x, y) in zip(bloodcrushers.models, bloodcrusher_positions):
        model.set_location(x, y, 0.0, 0.0)

    berzerker_positions = [
        (23.0, 22.0),
        (25.0, 17.5),
        (25.0, 19.1),
        (25.0, 20.7),
        (25.0, 22.3),
        (25.0, 23.9),
        (25.0, 25.5),
        (27.0, 19.1),
        (27.0, 22.3),
        (27.0, 25.5),
    ]
    for model, (x, y) in zip(berzerkers.models, berzerker_positions):
        model.set_location(x, y, 0.0, math.pi)

    if not game.map.place_unit(bloodcrushers):
        raise RuntimeError("Failed to place Bloodcrushers on the battlefield.")
    if not game.map.place_unit(berzerkers):
        raise RuntimeError("Failed to place Khorne Berzerkers on the battlefield.")
    game.rebuild_entity_registry()


def _option_for_action_id(request: DecisionRequest, action_id: str):
    for option in request.options:
        if request.action_id_for_option_id(option.option_id) == action_id:
            return option
    raise RuntimeError(f"{request.decision_type}: no option for action_id {action_id!r}")


def _option_by_payload(request: DecisionRequest, key: str, value: object):
    target = str(value or "")
    for option in request.options:
        if str(option.payload.get(key, "") or "") == target:
            return option
    return None


def _non_skip_option(request: DecisionRequest):
    for option in request.options:
        action = str(option.payload.get("action", "") or "").strip().lower()
        if action not in {"skip", "pass"}:
            return option
    return None


def _skip_option(request: DecisionRequest):
    for option in request.options:
        action = str(option.payload.get("action", "") or "").strip().lower()
        if action in {"skip", "pass"}:
            return option
    return None


def _resolve_decision(game: Game, request: DecisionRequest, option: object, payload: dict[str, Any] | None = None) -> None:
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=request.player_id,
        option_id=option.option_id,
        payload=dict(option.payload if payload is None else payload),
    )
    apply_result = game.resolve_decision(result)
    if not bool(getattr(apply_result, "ok", False)):
        errors = ", ".join(str(error) for error in list(getattr(apply_result, "errors", ()) or ()))
        raise RuntimeError(f"{request.decision_type} rejected: {errors}")


def _unit_from_request(game: Game, request: DecisionRequest) -> Unit | None:
    unit_id = str(request.context.get("unit_id", "") or "")
    if not unit_id:
        for option in request.options:
            candidate = str(option.payload.get("unit_id", "") or "")
            if candidate:
                unit_id = candidate
                break
    if not unit_id:
        return None
    return game.entity_registry.get(unit_id, kind="unit")


def _model_from_option(game: Game, option: object):
    model_id = str(option.payload.get("model_id", option.payload.get("model", "")) or "")
    if not model_id:
        return None
    return game.entity_registry.get(model_id, kind="model")


def _engaged_enemy_targets(game: Game, unit: Unit) -> list[Unit]:
    return [
        enemy
        for enemy in game.map.get_enemy_units(unit)
        if enemy.is_alive() and game.map.is_within_engagement_range(unit, enemy)
    ]


def _append_fight_flow_step(trace: dict[str, Any], step: str, unit: Unit | None, **extra: Any) -> None:
    steps = trace.setdefault("fight_flow_steps", [])
    steps.append(
        {
            "index": len(steps),
            "step": step,
            "unit_id": str(get_entity_id(unit) or "") if unit is not None else "",
            "unit_name": str(getattr(unit, "name", "") or ""),
            **extra,
        }
    )


def _record_fight_move(
    game: Game,
    request: DecisionRequest,
    trace: dict[str, Any],
    *,
    movement_type: str,
    skipped: bool,
    candidate: object | None = None,
) -> None:
    if str(request.context.get("phase_name", "") or "").upper() != "FIGHT_PHASE":
        return
    unit = _unit_from_request(game, request)
    _append_fight_flow_step(
        trace,
        f"{movement_type}_move",
        unit,
        phase_step=str(request.context.get("phase_step", "") or ""),
        skipped=bool(skipped),
    )
    trace.setdefault("fight_movement_steps", []).append(
        {
            "unit_id": str(get_entity_id(unit) or "") if unit is not None else "",
            "unit_name": str(getattr(unit, "name", "") or ""),
            "movement_type": movement_type,
            "phase_step": str(request.context.get("phase_step", "") or ""),
            "fight_sequence_step": str(request.context.get("fight_sequence_step", "") or ""),
            "skipped": bool(skipped),
            "candidate_kind": str(getattr(candidate, "metadata", {}).get("candidate_kind", "") or "") if candidate is not None else "",
            "movement_distance_inches": getattr(candidate, "metadata", {}).get("movement_distance_inches") if candidate is not None else None,
            "path_witness_ref": getattr(candidate, "metadata", {}).get("path_witness_ref") if candidate is not None else None,
        }
    )


def _resolve_move_request(game: Game, request: DecisionRequest, trace: dict[str, Any]) -> None:
    movement_type = str(request.context.get("movement_type", "") or "").strip().lower()
    if movement_type == "charge":
        intent = MovementIntent.from_context(request.context)
        candidates, mask, _wall_clock_ms, fallback_mode = generate_move_unit_candidates(game, request, intent)
        candidate = next(
            (
                item
                for item, legal in zip(candidates, mask)
                if legal and item.metadata.get("candidate_kind") == "charge"
            ),
            None,
        )
        if candidate is None:
            raise RuntimeError("No legal charge movement candidate generated.")
        option = _option_for_action_id(request, candidate.action_id)
        trace["charge_move_candidate"] = {
            "action_id": candidate.action_id,
            "candidate_source": candidate.metadata.get("candidate_source"),
            "movement_distance_inches": candidate.metadata.get("movement_distance_inches"),
            "fallback_mode": fallback_mode,
            "path_witness_ref": candidate.metadata.get("path_witness_ref"),
        }
        _resolve_decision(game, request, option, candidate.params)
        attacker = _unit_from_request(game, request)
        target_ids = [str(value or "") for value in list(request.context.get("target_unit_ids", []) or [])]
        target = game.entity_registry.get(target_ids[0], kind="unit") if target_ids else None
        if attacker is not None and target is not None:
            trace["charge_move_distance_before_damage_allocations"] = round(
                game.map.get_distance_between_units(attacker, target),
                4,
            )
            trace["charge_move_engaged_before_damage_allocations"] = bool(
                game.map.is_within_engagement_range(attacker, target)
            )
        return

    if movement_type in {"pile_in", "consolidate"}:
        intent = MovementIntent.from_context(request.context)
        candidates, mask, _wall_clock_ms, _fallback_mode = generate_move_unit_candidates(game, request, intent)
        candidate = next(
            (
                item
                for item, legal in zip(candidates, mask)
                if legal and item.metadata.get("candidate_kind") == movement_type
            ),
            None,
        )
        if candidate is not None:
            option = _option_for_action_id(request, candidate.action_id)
            _record_fight_move(
                game,
                request,
                trace,
                movement_type=movement_type,
                skipped=False,
                candidate=candidate,
            )
            _resolve_decision(game, request, option, candidate.params)
            return

    option = _skip_option(request)
    if option is not None:
        _record_fight_move(game, request, trace, movement_type=movement_type, skipped=True)
        _resolve_decision(game, request, option, option.payload)
        return

    intent = MovementIntent.from_context(request.context)
    candidates, mask, _wall_clock_ms, _fallback_mode = generate_move_unit_candidates(game, request, intent)
    candidate = next((item for item, legal in zip(candidates, mask) if legal), None)
    if candidate is None:
        raise RuntimeError(f"No legal {movement_type} movement candidate generated.")
    option = _option_for_action_id(request, candidate.action_id)
    _record_fight_move(
        game,
        request,
        trace,
        movement_type=movement_type,
        skipped=False,
        candidate=candidate,
    )
    _resolve_decision(game, request, option, candidate.params)


def _resolve_damage_allocation_request(
    game: Game,
    request: DecisionRequest,
    *,
    bloodcrushers: Unit,
    berzerkers: Unit,
    damage_allocation_mode: str,
    trace: dict[str, Any],
) -> None:
    target_unit = _unit_from_request(game, request)
    option = None
    if target_unit is berzerkers:
        candidate_options = [
            candidate_option
            for candidate_option in request.options
            if _model_from_option(game, candidate_option) is not None
        ]
        if candidate_options:
            chooser = min if damage_allocation_mode == "break_engagement" else max
            option = chooser(
                candidate_options,
                key=lambda candidate_option: (
                    _model_center_distance_to_unit(
                        _model_from_option(game, candidate_option),
                        bloodcrushers,
                    ),
                    str(candidate_option.option_id),
                ),
            )
    option = option or _non_skip_option(request) or _skip_option(request) or request.options[0]
    selected_model = _model_from_option(game, option)
    trace.setdefault("damage_allocation_steps", []).append(
        {
            "target_unit_id": str(get_entity_id(target_unit) or "") if target_unit is not None else "",
            "target_unit_name": str(getattr(target_unit, "name", "") or ""),
            "model_id": str(get_entity_id(selected_model) or "") if selected_model is not None else "",
            "model_name": str(getattr(selected_model, "name", "") or ""),
            "reason": str(request.context.get("reason", "") or request.prompt),
            "selection_kind": str(request.context.get("selection_kind", "") or ""),
        }
    )
    _resolve_decision(game, request, option, option.payload)


def _pump_headless_decisions(
    game: Game,
    *,
    preferred_charge_unit: Unit,
    bloodcrushers: Unit,
    berzerkers: Unit,
    damage_allocation_mode: str,
    trace: dict[str, Any],
    max_steps: int = 160,
) -> list[str]:
    resolved: list[str] = []
    for _step in range(max_steps):
        request = game.decision_queue.peek()
        if request is None:
            return resolved
        decision_type = request.decision_type
        resolved.append(decision_type)

        if decision_type in {DECISION_ALLOCATE_DAMAGE, DECISION_RESOLVE_COHERENCY}:
            if decision_type == DECISION_ALLOCATE_DAMAGE:
                _resolve_damage_allocation_request(
                    game,
                    request,
                    bloodcrushers=bloodcrushers,
                    berzerkers=berzerkers,
                    damage_allocation_mode=damage_allocation_mode,
                    trace=trace,
                )
                continue
            option = _non_skip_option(request) or _skip_option(request) or request.options[0]
            _resolve_decision(game, request, option, option.payload)
            continue

        if decision_type == DECISION_SELECT_UNIT:
            phase_name = str(
                request.context.get("phase_name", "") or getattr(game.phase, "name", "")
            ).upper()
            option = None
            if "CHARGE" in phase_name:
                option = _option_by_payload(request, "unit_id", get_entity_id(preferred_charge_unit))
            option = option or _non_skip_option(request) or _skip_option(request)
            if option is None:
                raise RuntimeError("SELECT_UNIT request has no usable option.")
            selected_unit_id = str(option.payload.get("unit_id", "") or "")
            selected_unit = game.entity_registry.get(selected_unit_id, kind="unit") if selected_unit_id else None
            if "FIGHT" in phase_name:
                _append_fight_flow_step(
                    trace,
                    "select_unit",
                    selected_unit,
                    phase_step=str(request.context.get("phase_step", "") or ""),
                    player_id=str(request.player_id or ""),
                )
                trace.setdefault("fight_unit_selections", []).append(
                    {
                        "unit_id": selected_unit_id,
                        "unit_name": str(getattr(selected_unit, "name", "") or ""),
                        "player_id": str(request.player_id or ""),
                        "phase_step": str(request.context.get("phase_step", "") or ""),
                    }
                )
            _resolve_decision(game, request, option, option.payload)
            continue

        if decision_type == DECISION_DECLARE_CHARGE:
            attacker = _unit_from_request(game, request)
            if attacker is None:
                raise RuntimeError("DECLARE_CHARGE request is missing attacker unit.")
            target = next(enemy for enemy in game.map.get_enemy_units(attacker) if enemy.is_alive())
            option = _option_by_payload(request, "target_unit_id", get_entity_id(target)) or _non_skip_option(request)
            if option is None:
                raise RuntimeError("DECLARE_CHARGE request has no target option.")
            _resolve_decision(game, request, option, {"target_unit_ids": [str(get_entity_id(target))]})
            continue

        if decision_type == DECISION_MOVE_UNIT:
            _resolve_move_request(game, request, trace)
            continue

        if decision_type == DECISION_SELECT_FIGHT_TARGETS:
            fighting_unit = _unit_from_request(game, request)
            if fighting_unit is None:
                raise RuntimeError("SELECT_FIGHT_TARGETS request is missing fighting unit.")
            targets = _engaged_enemy_targets(game, fighting_unit)
            if not targets:
                option = _skip_option(request) or _non_skip_option(request)
                if option is None:
                    raise RuntimeError("SELECT_FIGHT_TARGETS request has no usable option.")
                _resolve_decision(game, request, option, option.payload)
                continue
            target = targets[0]
            option = _option_by_payload(request, "target_unit_id", get_entity_id(target)) or _non_skip_option(request)
            if option is None:
                raise RuntimeError("SELECT_FIGHT_TARGETS request has no target option.")
            _append_fight_flow_step(
                trace,
                "select_targets",
                fighting_unit,
                phase_step=str(request.context.get("phase_step", "") or ""),
                target_unit_id=str(get_entity_id(target) or ""),
            )
            trace.setdefault("fight_target_selections", []).append(
                {
                    "unit_id": str(get_entity_id(fighting_unit) or ""),
                    "unit_name": str(getattr(fighting_unit, "name", "") or ""),
                    "target_unit_id": str(get_entity_id(target) or ""),
                    "target_unit_name": str(getattr(target, "name", "") or ""),
                    "phase_step": str(request.context.get("phase_step", "") or ""),
                }
            )
            _resolve_decision(game, request, option, {"target_unit_ids": [str(get_entity_id(target))]})
            continue

        if decision_type == DECISION_DECLARE_MELEE_WEAPONS:
            option = _non_skip_option(request)
            if option is None:
                raise RuntimeError("DECLARE_MELEE_WEAPONS request has no confirm option.")
            weapon_bundles = list(option.payload.get("weapon_bundles", []) or [])
            trace["melee_weapon_bundle_count"] = trace.get("melee_weapon_bundle_count", 0) + len(weapon_bundles)
            fighting_unit = _unit_from_request(game, request)
            _append_fight_flow_step(
                trace,
                "declare_melee_weapons",
                fighting_unit,
                phase_step=str(request.context.get("phase_step", "") or ""),
                weapon_bundle_count=len(weapon_bundles),
            )
            trace.setdefault("melee_weapon_declarations", []).append(
                {
                    "unit_id": str(get_entity_id(fighting_unit) or "") if fighting_unit is not None else "",
                    "unit_name": str(getattr(fighting_unit, "name", "") or ""),
                    "phase_step": str(request.context.get("phase_step", "") or ""),
                    "fight_sequence_step": str(request.context.get("fight_sequence_step", "") or ""),
                    "weapon_bundle_count": len(weapon_bundles),
                    "target_unit_ids": [
                        str(value or "")
                        for value in list(request.context.get("target_unit_ids", []) or [])
                    ],
                }
            )
            _resolve_decision(game, request, option, option.payload)
            continue

        if decision_type == DECISION_CONFIRM_YES_NO:
            option = _skip_option(request) or request.options[-1]
            _resolve_decision(game, request, option, option.payload)
            continue

        raise RuntimeError(f"Unhandled decision request: {decision_type} ({request.prompt})")

    raise RuntimeError("Decision pump exceeded max_steps.")


def _alive_model_count(unit: Unit) -> int:
    return sum(1 for model in unit.models if model.is_alive)


def _remaining_wounds(unit: Unit) -> int:
    return sum(max(0, int(getattr(model, "wounds", 0) or 0)) for model in unit.models)


def _model_center_distance_to_unit(model: object, unit: Unit) -> float:
    model_base = getattr(model, "model_base", None)
    if model_base is None:
        return 0.0
    model_x = float(getattr(model_base, "x", 0.0) or 0.0)
    model_y = float(getattr(model_base, "y", 0.0) or 0.0)
    distances: list[float] = []
    for other_model in list(getattr(unit, "models", []) or []):
        if not getattr(other_model, "is_alive", False):
            continue
        other_base = getattr(other_model, "model_base", None)
        if other_base is None:
            continue
        other_x = float(getattr(other_base, "x", 0.0) or 0.0)
        other_y = float(getattr(other_base, "y", 0.0) or 0.0)
        distances.append(math.hypot(model_x - other_x, model_y - other_y))
    return max(distances) if distances else 0.0


def _fight_flow_steps_for_unit(trace: dict[str, Any], unit: Unit) -> list[dict[str, Any]]:
    unit_id = str(get_entity_id(unit) or "")
    return [
        dict(step)
        for step in list(trace.get("fight_flow_steps", []) or [])
        if str(step.get("unit_id", "") or "") == unit_id
    ]


def _assert_fight_activation_flow(trace: dict[str, Any], unit: Unit, *, expected_phase_step: str) -> None:
    unit_name = str(getattr(unit, "name", "") or "Unit")
    steps = _fight_flow_steps_for_unit(trace, unit)
    by_name: dict[str, list[dict[str, Any]]] = {}
    for step in steps:
        by_name.setdefault(str(step.get("step", "") or ""), []).append(step)

    required_steps = [
        "select_unit",
        "select_targets",
        "pile_in_move",
        "declare_melee_weapons",
        "melee_attacks_resolved",
        "consolidate_move",
        "fight_sequence_complete",
    ]
    missing = [step_name for step_name in required_steps if step_name not in by_name]
    if missing:
        raise RuntimeError(f"{unit_name} fight activation missing step(s): {', '.join(missing)}.")

    ordered_indices = [
        min(int(step.get("index", 0) or 0) for step in by_name[step_name])
        for step_name in required_steps
    ]
    if ordered_indices != sorted(ordered_indices):
        flow = ", ".join(
            f"{step.get('index')}:{step.get('step')}:{step.get('phase_step')}"
            for step in steps
        )
        raise RuntimeError(f"{unit_name} fight activation did not run Pile-In -> melee -> Consolidate in order: {flow}.")

    selected_steps = by_name["select_unit"]
    if not any(str(step.get("phase_step", "") or "") == expected_phase_step for step in selected_steps):
        raise RuntimeError(f"{unit_name} was not selected in expected fight step {expected_phase_step}.")


def _assert_berzerkers_fought_after_fight_first_completion(
    trace: dict[str, Any],
    bloodcrushers: Unit,
    berzerkers: Unit,
) -> None:
    bloodcrusher_steps = _fight_flow_steps_for_unit(trace, bloodcrushers)
    berzerker_steps = _fight_flow_steps_for_unit(trace, berzerkers)
    bloodcrusher_completion_indices = [
        int(step.get("index", 0) or 0)
        for step in bloodcrusher_steps
        if str(step.get("step", "") or "") == "fight_sequence_complete"
        and str(step.get("phase_step", "") or "") == "FIGHT_FIRST"
    ]
    berzerker_selection_indices = [
        int(step.get("index", 0) or 0)
        for step in berzerker_steps
        if str(step.get("step", "") or "") == "select_unit"
        and str(step.get("phase_step", "") or "") == "REMAINING_COMBATANTS"
    ]
    if not bloodcrusher_completion_indices:
        raise RuntimeError("Bloodcrushers did not complete a Fights First activation.")
    if not berzerker_selection_indices:
        raise RuntimeError("Khorne Berzerkers were not selected in Remaining Combatants.")
    if min(berzerker_selection_indices) <= max(bloodcrusher_completion_indices):
        raise RuntimeError("Khorne Berzerkers were selected before Bloodcrushers completed Fights First.")


def _parse_charge_dice(value: str) -> list[int]:
    parts = [part.strip() for part in str(value or "").split(",") if part.strip()]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("--charge-dice must contain exactly two comma-separated D6 values.")
    dice_values = [int(part) for part in parts]
    if any(die < 1 or die > 6 for die in dice_values):
        raise argparse.ArgumentTypeError("--charge-dice values must be between 1 and 6.")
    return dice_values


def _make_game(seed: int, charge_dice: list[int]) -> tuple[Game, Unit, Unit]:
    waha = WahaHelper(data_dir=str(WAHAPEDIA_DATA))
    bloodcrushers = _build_bloodcrushers(waha)
    berzerkers = _build_berzerkers(waha)
    _assert_requested_loadouts(bloodcrushers, berzerkers)
    _assign_stable_unit_ids(bloodcrushers, "chaos-daemons-bloodcrushers")
    _assign_stable_unit_ids(berzerkers, "world-eaters-khorne-berzerkers")

    daemon_army = Army.with_detachment("Chaos Daemons", "Daemonic Incursion")
    world_eaters_army = Army.with_detachment("World Eaters", "Berzerker Warband")
    daemon_army._id = "army:chaos-daemons"
    world_eaters_army._id = "army:world-eaters"
    daemon_army.add_unit(bloodcrushers)
    world_eaters_army.add_unit(berzerkers)

    players = [
        Player("Chaos Daemons", PlayerControl.REMOTE, army=daemon_army),
        Player("World Eaters", PlayerControl.REMOTE, army=world_eaters_army),
    ]
    players[0]._id = "player:chaos-daemons"
    players[1]._id = "player:world-eaters"
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=players)
    game.random_source = _FixedPrefixRandomSource(seed=seed, randint_prefix=charge_dice)
    dice_module.RNG = random.Random(seed)
    game.setup_complete = True
    game.current_player_index = 0
    game.first_turn_player_index = 1
    # Treat the Daemons as the bottom player so Fight -> Command advances the battle round.
    game.battle_round_starting_player_index = 1
    game.phase = BattleRoundPhases.CHARGE_PHASE
    _deploy_units(game, bloodcrushers, berzerkers)
    return game, bloodcrushers, berzerkers


def run_scenario(
    seed: int,
    forced_charge_dice: list[int],
    *,
    damage_allocation_mode: str = "preserve_engagement",
    expect_berzerkers_fight_back: bool = True,
) -> dict[str, Any]:
    if damage_allocation_mode not in {"preserve_engagement", "break_engagement"}:
        raise ValueError("damage_allocation_mode must be 'preserve_engagement' or 'break_engagement'.")
    game, bloodcrushers, berzerkers = _make_game(seed, forced_charge_dice)
    trace: dict[str, Any] = {}

    brass_stampede_specs = [
        dict(spec)
        for spec in list(getattr(bloodcrushers, "special_rules", {}).get("charge_end_mortal_wounds", []) or [])
        if _normalized_name(spec.get("name", "")) == "brass stampede"
    ]
    if not brass_stampede_specs:
        raise RuntimeError("Bloodcrushers datasheet did not parse a Brass Stampede charge-end mortal wound spec.")

    original_charge_end_mortals = game.resolve_charge_end_mortal_wounds

    def _record_charge_end_mortals(unit, target_unit, spec) -> None:
        before_models = _alive_model_count(target_unit)
        before_wounds = _remaining_wounds(target_unit)
        original_charge_end_mortals(unit, target_unit, spec)
        after_models = _alive_model_count(target_unit)
        after_wounds = _remaining_wounds(target_unit)
        if unit is bloodcrushers and target_unit is berzerkers and _normalized_name(spec.get("name", "")) == "brass stampede":
            trace.setdefault("brass_stampede_resolutions", []).append(
                {
                    "source_unit_id": str(get_entity_id(unit) or ""),
                    "target_unit_id": str(get_entity_id(target_unit) or ""),
                    "kind": str(spec.get("kind", "") or ""),
                    "target_models_before": before_models,
                    "target_models_after": after_models,
                    "target_wounds_before": before_wounds,
                    "target_wounds_after": after_wounds,
                    "mortal_wounds_applied_immediate": max(0, before_wounds - after_wounds),
                    "models_destroyed": max(0, before_models - after_models),
                }
            )

    game.resolve_charge_end_mortal_wounds = _record_charge_end_mortals

    def _record_fight_attacks_resolved(**kwargs) -> None:
        attacking_unit = kwargs.get("unit")
        target_unit = kwargs.get("target_unit")
        if attacking_unit is not bloodcrushers and attacking_unit is not berzerkers:
            return
        if target_unit is None:
            return
        if target_unit is not bloodcrushers and target_unit is not berzerkers:
            return
        summary = {
            "unit_id": str(get_entity_id(attacking_unit) or ""),
            "unit_name": str(getattr(attacking_unit, "name", "") or ""),
            "target_unit_id": str(get_entity_id(target_unit) or "") if target_unit is not None else None,
            "target_unit_name": str(getattr(target_unit, "name", "") or "") if target_unit is not None else None,
            "successful_attacks": int(kwargs.get("successful_attacks", 0) or 0),
            "declaration_count": int(kwargs.get("declaration_count", 0) or 0),
            "executed_declarations": len(list(kwargs.get("executed_declarations") or [])),
            "skipped_declarations": len(list(kwargs.get("skipped_declarations") or [])),
        }
        _append_fight_flow_step(
            trace,
            "melee_attacks_resolved",
            attacking_unit,
            target_unit_id=summary["target_unit_id"] or "",
            declaration_count=summary["declaration_count"],
            successful_attacks=summary["successful_attacks"],
        )
        trace.setdefault("fight_attack_summaries", []).append(summary)
        if attacking_unit is bloodcrushers:
            trace.setdefault("bloodcrusher_fight_attack_summaries", []).append(summary)
        if attacking_unit is berzerkers:
            trace.setdefault("berzerker_fight_attack_summaries", []).append(summary)

    def _record_fight_sequence_complete(**kwargs) -> None:
        unit = kwargs.get("unit")
        stage = kwargs.get("stage")
        if unit is bloodcrushers and str(getattr(stage, "name", stage) or "") == "FIGHT_FIRST":
            trace["after_bloodcrushers_fights_first"] = {
                "distance_to_berzerkers": round(
                    game.map.get_distance_between_units(bloodcrushers, berzerkers),
                    4,
                ),
                "bloodcrushers_engaged_with_berzerkers": bool(
                    game.map.is_within_engagement_range(bloodcrushers, berzerkers)
                ),
                "berzerkers_eligible_to_fight": bool(berzerkers.is_eligible_to_fight(game.map)),
                "berzerkers_should_fight_first": bool(berzerkers.should_fight_first()),
            }
        _append_fight_flow_step(
            trace,
            "fight_sequence_complete",
            unit,
            phase_step=str(getattr(stage, "name", stage) or ""),
            stage_value=str(getattr(stage, "value", stage) or ""),
        )
        trace.setdefault("fight_sequence_completions", []).append(
            {
                "unit_id": str(get_entity_id(unit) or "") if unit is not None else "",
                "unit_name": str(getattr(unit, "name", "") or ""),
                "stage": str(getattr(stage, "name", stage) or ""),
                "stage_value": str(getattr(stage, "value", stage) or ""),
            }
        )

    game.event_system.subscribe("fight_attacks_resolved", _record_fight_attacks_resolved)
    game.event_system.subscribe("fight_sequence_complete", _record_fight_sequence_complete)

    with game_context(game):
        start_distance = game.map.get_distance_between_units(bloodcrushers, berzerkers)
        if game.map.is_within_engagement_range(bloodcrushers, berzerkers):
            raise RuntimeError("Scenario starts with units already in Engagement Range.")

        game.event_system.publish("phase_start", player=game.get_current_player(), phase=game.phase)
        game._queue_charge_phase_selection(player=game.get_current_player())
        charge_decisions = _pump_headless_decisions(
            game,
            preferred_charge_unit=bloodcrushers,
            bloodcrushers=bloodcrushers,
            berzerkers=berzerkers,
            damage_allocation_mode=damage_allocation_mode,
            trace=trace,
        )

        charge_base_roll = int(getattr(bloodcrushers.round_state, "charge_roll", 0) or 0)
        rolled_charge_dice = list(getattr(bloodcrushers.round_state, "charge_dice", []) or [])
        if rolled_charge_dice != list(forced_charge_dice):
            raise RuntimeError(
                f"Expected forced charge dice {forced_charge_dice}, got {rolled_charge_dice}."
            )
        charge_modified_roll = game._apply_charge_modifiers(
            bloodcrushers,
            charge_base_roll,
            target_unit=berzerkers,
        )
        if not bool(trace.get("charge_move_engaged_before_damage_allocations", False)):
            raise RuntimeError("Bloodcrushers did not complete their Charge move in Engagement Range.")
        after_charge_distance = game.map.get_distance_between_units(bloodcrushers, berzerkers)
        if expect_berzerkers_fight_back and not game.map.is_within_engagement_range(bloodcrushers, berzerkers):
            raise RuntimeError("Bloodcrushers were not in Engagement Range after charge damage allocations.")
        brass_stampede_resolutions = list(trace.get("brass_stampede_resolutions", []) or [])
        if not brass_stampede_resolutions:
            raise RuntimeError("Brass Stampede did not trigger during the charge move.")
        brass_stampede_target_wounds_before = max(
            int(entry.get("target_wounds_before", 0) or 0)
            for entry in brass_stampede_resolutions
        )
        brass_stampede_target_models_before = max(
            int(entry.get("target_models_before", 0) or 0)
            for entry in brass_stampede_resolutions
        )
        brass_stampede_mortal_wounds = max(
            0,
            brass_stampede_target_wounds_before - _remaining_wounds(berzerkers),
        )
        brass_stampede_models_destroyed = max(
            0,
            brass_stampede_target_models_before - _alive_model_count(berzerkers),
        )
        for entry in brass_stampede_resolutions:
            entry["target_wounds_after_allocations"] = _remaining_wounds(berzerkers)
            entry["target_models_after_allocations"] = _alive_model_count(berzerkers)
            entry["mortal_wounds_applied"] = brass_stampede_mortal_wounds
            entry["models_destroyed"] = brass_stampede_models_destroyed
        if brass_stampede_mortal_wounds <= 0:
            raise RuntimeError("Brass Stampede triggered but did not apply any mortal wounds in this scenario.")

        berzerker_models_alive_before_fight = _alive_model_count(berzerkers)
        game.next_phase()
        if game.phase != BattleRoundPhases.FIGHT_PHASE:
            raise RuntimeError(f"Expected Fight phase, got {game.phase}.")
        daemon_player = bloodcrushers.get_parent_army().player
        world_eaters_player = berzerkers.get_parent_army().player
        bloodcrushers_charged_this_round = bool(getattr(bloodcrushers.round_state, "charged_this_round", False))
        bloodcrushers_should_fight_first = bool(bloodcrushers.should_fight_first())
        bloodcrushers_in_fight_first_units = bloodcrushers in list(game.get_fight_first_units(daemon_player) or [])
        berzerkers_in_remaining_units_at_fight_start = berzerkers in list(
            game.get_remaining_combatant_units(world_eaters_player) or []
        )
        if not bloodcrushers_charged_this_round:
            raise RuntimeError("Bloodcrushers did not retain charged_this_round at Fight phase start.")
        if not bloodcrushers_should_fight_first or not bloodcrushers_in_fight_first_units:
            raise RuntimeError("Bloodcrushers did not have charge-granted Fights First at Fight phase start.")
        fight_decisions = _pump_headless_decisions(
            game,
            preferred_charge_unit=bloodcrushers,
            bloodcrushers=bloodcrushers,
            berzerkers=berzerkers,
            damage_allocation_mode=damage_allocation_mode,
            trace=trace,
        )
        fight_manager = getattr(game, "fight_phase_manager", None)
        if fight_manager is None or not fight_manager.is_complete():
            raise RuntimeError("Fight phase manager did not complete the queued fight sequence.")
        bloodcrushers_fought = bool(getattr(bloodcrushers.round_state, "fought_this_phase", False))
        if not bloodcrushers_fought:
            raise RuntimeError("Bloodcrushers did not mark fought_this_phase during the Fight phase.")
        bloodcrusher_attack_summaries = [
            summary
            for summary in list(trace.get("bloodcrusher_fight_attack_summaries", []) or [])
            if summary.get("target_unit_id") == str(getattr(berzerkers, "id", "") or "")
        ]
        bloodcrusher_melee_declaration_count = sum(
            int(summary.get("declaration_count", 0) or 0)
            for summary in bloodcrusher_attack_summaries
        )
        bloodcrusher_melee_successful_attacks = sum(
            int(summary.get("successful_attacks", 0) or 0)
            for summary in bloodcrusher_attack_summaries
        )
        if bloodcrusher_melee_declaration_count <= 0 or bloodcrusher_melee_successful_attacks <= 0:
            raise RuntimeError("Bloodcrushers did not resolve any melee attacks into Khorne Berzerkers.")
        berzerkers_fought = bool(getattr(berzerkers.round_state, "fought_this_phase", False))
        if expect_berzerkers_fight_back and not berzerkers_fought:
            raise RuntimeError("Khorne Berzerkers did not fight back after the Fights First stage completed.")
        berzerker_attack_summaries = [
            summary
            for summary in list(trace.get("berzerker_fight_attack_summaries", []) or [])
            if summary.get("target_unit_id") == str(get_entity_id(bloodcrushers) or "")
        ]
        berzerker_melee_declaration_count = sum(
            int(summary.get("declaration_count", 0) or 0)
            for summary in berzerker_attack_summaries
        )
        berzerker_melee_successful_attacks = sum(
            int(summary.get("successful_attacks", 0) or 0)
            for summary in berzerker_attack_summaries
        )
        if expect_berzerkers_fight_back and (
            berzerker_melee_declaration_count <= 0 or berzerker_melee_successful_attacks <= 0
        ):
            raise RuntimeError("Khorne Berzerkers did not resolve melee attacks back into Bloodcrushers.")
        _assert_fight_activation_flow(trace, bloodcrushers, expected_phase_step="FIGHT_FIRST")
        if expect_berzerkers_fight_back:
            _assert_fight_activation_flow(trace, berzerkers, expected_phase_step="REMAINING_COMBATANTS")
            _assert_berzerkers_fought_after_fight_first_completion(trace, bloodcrushers, berzerkers)
        else:
            after_fights_first = dict(trace.get("after_bloodcrushers_fights_first", {}) or {})
            if bool(after_fights_first.get("bloodcrushers_engaged_with_berzerkers", True)):
                raise RuntimeError("No-fightback regression did not leave Berzerkers outside Engagement Range.")
            if bool(after_fights_first.get("berzerkers_eligible_to_fight", True)):
                raise RuntimeError("No-fightback regression left Berzerkers eligible to fight.")
            if berzerkers_fought or berzerker_melee_declaration_count > 0 or berzerker_melee_successful_attacks > 0:
                raise RuntimeError("Khorne Berzerkers fought despite being expected to be ineligible.")
            if _fight_flow_steps_for_unit(trace, berzerkers):
                raise RuntimeError("Khorne Berzerkers received a fight activation despite being expected ineligible.")
        bloodcrusher_models_alive = _alive_model_count(bloodcrushers)
        berzerker_models_alive = _alive_model_count(berzerkers)

        game.next_phase()
        if game.turn != 2 or game.phase != BattleRoundPhases.COMMAND_PHASE:
            raise RuntimeError("End-of-round transition did not advance to battle round 2 Command phase.")

    pending_next_round = [
        {"decision_type": request.decision_type, "prompt": request.prompt}
        for request in list(game.decision_queue.list() or [])
    ]
    return {
        "seed": seed,
        "bloodcrushers_datasheet_id": "000001115",
        "berzerkers_datasheet_id": "000002627",
        "forced_charge_dice": list(forced_charge_dice),
        "damage_allocation_mode": damage_allocation_mode,
        "expect_berzerkers_fight_back": bool(expect_berzerkers_fight_back),
        "start_distance_inches": round(start_distance, 4),
        "charge_dice": rolled_charge_dice,
        "charge_base_roll": charge_base_roll,
        "charge_modified_roll": charge_modified_roll,
        "charge_move_distance_before_damage_allocations": trace.get("charge_move_distance_before_damage_allocations"),
        "charge_move_engaged_before_damage_allocations": bool(
            trace.get("charge_move_engaged_before_damage_allocations", False)
        ),
        "after_charge_distance_inches": round(after_charge_distance, 4),
        "engaged_after_charge_damage_allocations": bool(
            game.map.is_within_engagement_range(bloodcrushers, berzerkers)
        ),
        "bloodcrusher_models_alive": bloodcrusher_models_alive,
        "berzerker_models_alive": berzerker_models_alive,
        "berzerker_models_alive_before_fight": berzerker_models_alive_before_fight,
        "bloodcrushers_fought_this_phase": bloodcrushers_fought,
        "berzerkers_fought_this_phase": berzerkers_fought,
        "bloodcrushers_charged_this_round_at_fight_start": bloodcrushers_charged_this_round,
        "bloodcrushers_should_fight_first_at_fight_start": bloodcrushers_should_fight_first,
        "bloodcrushers_in_fight_first_units_at_fight_start": bloodcrushers_in_fight_first_units,
        "berzerkers_in_remaining_units_at_fight_start": berzerkers_in_remaining_units_at_fight_start,
        "bloodcrushers_has_inherent_fights_first": bool(bloodcrushers.has_fight_first()),
        "brass_stampede_specs": brass_stampede_specs,
        "brass_stampede_resolutions": brass_stampede_resolutions,
        "brass_stampede_mortal_wounds": brass_stampede_mortal_wounds,
        "bloodcrusher_melee_declaration_count": bloodcrusher_melee_declaration_count,
        "bloodcrusher_melee_successful_attacks": bloodcrusher_melee_successful_attacks,
        "bloodcrusher_fight_attack_summaries": bloodcrusher_attack_summaries,
        "berzerker_melee_declaration_count": berzerker_melee_declaration_count,
        "berzerker_melee_successful_attacks": berzerker_melee_successful_attacks,
        "berzerker_fight_attack_summaries": berzerker_attack_summaries,
        "charge_decisions": charge_decisions,
        "fight_decisions": fight_decisions,
        "fight_unit_selections": list(trace.get("fight_unit_selections", []) or []),
        "fight_movement_steps": list(trace.get("fight_movement_steps", []) or []),
        "fight_flow_steps": list(trace.get("fight_flow_steps", []) or []),
        "fight_sequence_completions": list(trace.get("fight_sequence_completions", []) or []),
        "after_bloodcrushers_fights_first": dict(trace.get("after_bloodcrushers_fights_first", {}) or {}),
        "melee_weapon_declarations": list(trace.get("melee_weapon_declarations", []) or []),
        "damage_allocation_steps": list(trace.get("damage_allocation_steps", []) or []),
        "melee_weapon_bundle_count": trace.get("melee_weapon_bundle_count", 0),
        "charge_move_candidate": trace.get("charge_move_candidate", {}),
        "final_turn": game.turn,
        "final_phase": game.phase.name,
        "final_current_player": game.get_current_player().name,
        "pending_next_round_decisions": pending_next_round,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=40, help="Seed for deterministic headless dice.")
    parser.add_argument(
        "--charge-dice",
        type=_parse_charge_dice,
        default=[6, 6],
        help="Forced 2D6 charge roll values, comma-separated. Default: 6,6.",
    )
    parser.add_argument(
        "--damage-allocation-mode",
        choices=["preserve_engagement", "break_engagement"],
        default="preserve_engagement",
        help="Choose Berzerker casualty allocation behavior for regression scenarios.",
    )
    parser.add_argument(
        "--expect-no-berzerker-fightback",
        action="store_true",
        help="Assert that Berzerkers do not receive a return fight activation.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON summary.")
    parser.add_argument("--verbose", action="store_true", help="Enable engine INFO logging.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.CRITICAL,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )

    summary = run_scenario(
        seed=args.seed,
        forced_charge_dice=list(args.charge_dice),
        damage_allocation_mode=args.damage_allocation_mode,
        expect_berzerkers_fight_back=not bool(args.expect_no_berzerker_fightback),
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    print("Bloodcrushers vs Khorne Berzerkers headless scenario completed.")
    print(f"Seed: {summary['seed']}")
    print(f"Forced charge dice: {summary['forced_charge_dice']}")
    print(f"Damage allocation mode: {summary['damage_allocation_mode']}")
    print(f"Start distance: {summary['start_distance_inches']}\"")
    print(
        "Charge roll: "
        f"{summary['charge_dice']} base {summary['charge_base_roll']}, "
        f"modified {summary['charge_modified_roll']}"
    )
    print(f"After charge distance: {summary['after_charge_distance_inches']}\"")
    print(
        "Charge move engagement before damage allocations: "
        f"{summary['charge_move_engaged_before_damage_allocations']} "
        f"({summary['charge_move_distance_before_damage_allocations']}\")"
    )
    print(
        "Brass Stampede: "
        f"{summary['brass_stampede_mortal_wounds']} mortal wounds, "
        f"{summary['brass_stampede_resolutions'][0]['models_destroyed']} models destroyed"
    )
    print(
        "Bloodcrushers Fights First from charge: "
        f"{summary['bloodcrushers_should_fight_first_at_fight_start']} "
        f"(charged flag {summary['bloodcrushers_charged_this_round_at_fight_start']})"
    )
    print(f"Charge decisions: {', '.join(summary['charge_decisions'])}")
    print(f"Fight decisions: {', '.join(summary['fight_decisions'])}")
    print(f"Melee weapon bundles declared: {summary['melee_weapon_bundle_count']}")
    print(
        "Bloodcrusher melee attacks resolved: "
        f"{summary['bloodcrusher_melee_successful_attacks']} attacks from "
        f"{summary['bloodcrusher_melee_declaration_count']} declarations"
    )
    print(
        "Berzerker melee attacks resolved: "
        f"{summary['berzerker_melee_successful_attacks']} attacks from "
        f"{summary['berzerker_melee_declaration_count']} declarations"
    )
    flow = " -> ".join(
        f"{step['unit_name']}:{step['step']}"
        for step in summary["fight_flow_steps"]
        if step["step"] in {
            "select_unit",
            "pile_in_move",
            "declare_melee_weapons",
            "melee_attacks_resolved",
            "consolidate_move",
            "fight_sequence_complete",
        }
    )
    print(f"Fight flow: {flow}")
    movement_steps = ", ".join(
        f"{step['unit_name']} {step['movement_type']} "
        f"({step['phase_step']}, {'skip' if step['skipped'] else 'move'})"
        for step in summary["fight_movement_steps"]
    )
    print(f"Fight movement steps: {movement_steps}")
    print(
        "Models alive after fight: "
        f"Bloodcrushers {summary['bloodcrusher_models_alive']}, "
        f"Khorne Berzerkers {summary['berzerker_models_alive']}"
    )
    print(
        "End state: "
        f"battle round {summary['final_turn']} {summary['final_phase']}, "
        f"current player {summary['final_current_player']}"
    )
    if summary["pending_next_round_decisions"]:
        prompts = ", ".join(item["decision_type"] for item in summary["pending_next_round_decisions"])
        print(f"Pending next-round command decisions: {prompts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
