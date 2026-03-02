from __future__ import annotations

import time
from typing import Any

from .decisions import CandidateAction, DecisionRequest
from .movement_intent import MovementIntent
from .path_witness import build_model_path_witness_for_unit, current_model_positions


def _resolve_unit(game: object, unit_id: str):
    resolver = getattr(game, "_resolve_unit_by_id", None)
    if callable(resolver):
        unit = resolver(unit_id)
        if unit is not None:
            return unit
    for player in list(getattr(game, "players", []) or []):
        army = getattr(player, "army", None)
        for unit in list(getattr(army, "units", []) or []):
            uid = str(getattr(unit, "id", "") or getattr(unit, "_id", "") or "")
            if uid == str(unit_id or ""):
                return unit
    return None


def _fallback_candidates(request: DecisionRequest) -> tuple[list[CandidateAction], list[bool]]:
    fallback: list[CandidateAction] = []
    for candidate in list(request.candidates or []):
        metadata = dict(candidate.metadata or {})
        metadata["fallback_mode"] = True
        fallback.append(
            CandidateAction(
                action_id=str(candidate.action_id),
                params=dict(candidate.params or {}),
                metadata=metadata,
            )
        )
    mask = [bool(v) for v in list(request.mask or [])]
    if len(mask) != len(fallback):
        mask = [True] * len(fallback)
    return fallback, mask


def _solver_candidates(game: object, request: DecisionRequest, intent: MovementIntent) -> tuple[list[CandidateAction], list[bool]]:
    ctx = dict(getattr(request, "context", {}) or {})
    movement_type = str(ctx.get("movement_type", "move") or "move")
    unit_id = str(ctx.get("unit_id", "") or "")
    unit = _resolve_unit(game, unit_id)
    skip_option = None
    confirm_option = None
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        action = str(payload.get("action", "") or "").lower()
        if action == "skip":
            skip_option = option
        else:
            confirm_option = option

    candidates: list[CandidateAction] = []
    if skip_option is not None:
        skip_action_id = request.action_id_for_option_id(getattr(skip_option, "option_id", None))
        skip_payload = dict(getattr(skip_option, "payload", {}) or {})
        skip_payload.pop("action_id", None)
        candidates.append(
            CandidateAction(
                action_id=str(skip_action_id),
                params=skip_payload,
                metadata={
                    "candidate_kind": "noop",
                    "solver_ms": 0,
                    "fallback_mode": False,
                    "intent_hash": intent.stable_hash(),
                },
            )
        )

    if confirm_option is not None and unit is not None:
        confirm_action_id = request.action_id_for_option_id(getattr(confirm_option, "option_id", None))
        confirm_payload = dict(getattr(confirm_option, "payload", {}) or {})
        confirm_payload.pop("action_id", None)
        model_positions = current_model_positions(unit)
        confirm_payload["model_positions"] = model_positions
        witness = build_model_path_witness_for_unit(
            unit=unit,
            model_positions=model_positions,
            movement_type=movement_type,
        )
        store = getattr(game, "path_witness_store", None)
        if store is None:
            raise RuntimeError("Game is missing path_witness_store.")
        path_witness_ref = store.put(witness)
        weights = dict(intent.weights or {})
        score_weight = float(weights.get("score", 0.0))
        deny_weight = float(weights.get("deny", 0.0))
        safety_weight = float(weights.get("safety", 0.0))
        coherency_weight = float(weights.get("coherency", 0.0))
        action_enable_weight = float(weights.get("action_enable", 0.0))
        trade_weight = float(weights.get("trade", 0.0))
        rules_bundle_id = str(ctx.get("rules_bundle_id", "") or "")
        rules_provenance_refs = [rules_bundle_id] if rules_bundle_id else []
        candidates.append(
            CandidateAction(
                action_id=str(confirm_action_id),
                params=confirm_payload,
                metadata={
                    "candidate_kind": "move",
                    "solver_ms": 0,
                    "fallback_mode": False,
                    "intent_hash": intent.stable_hash(),
                    "path_witness_ref": path_witness_ref,
                    "screen_coverage_score": float(deny_weight + action_enable_weight),
                    "coherency_score": coherency_weight,
                    "threat_score": float(max(0.0, 1.0 - safety_weight)),
                    "projected_score_delta_next_window": score_weight * 2.0,
                    "projected_score_delta_round": score_weight * 3.0,
                    "projected_deny_delta_next_window": deny_weight * 2.0,
                    "projected_control_delta": (score_weight + deny_weight) * 1.5,
                    "projected_action_enablement_delta": action_enable_weight * 2.0,
                    "projected_exposure_delta": -safety_weight,
                    "projected_trade_ev": trade_weight - (1.0 - safety_weight) * 0.25,
                    "cover_delta": safety_weight * 0.5,
                    "los_delta": score_weight * 0.25 - safety_weight * 0.15,
                    "resource_delta": -max(0.0, action_enable_weight * 0.1),
                    "rules_provenance_refs": rules_provenance_refs,
                },
            )
        )

    candidates.sort(key=lambda candidate: str(candidate.action_id))
    top_k = int(ctx.get("movement_top_k", 2) or 2)
    if top_k > 0:
        candidates = candidates[:top_k]
    mask = [True] * len(candidates)
    return candidates, mask


def generate_move_unit_candidates(game: object, request: DecisionRequest, intent: MovementIntent) -> tuple[list[CandidateAction], list[bool], int, bool]:
    ctx = dict(getattr(request, "context", {}) or {})
    budget_ms = int(ctx.get("time_budget_ms", 0) or 0)
    time_manager = getattr(game, "time_manager", None)
    if time_manager is None or budget_ms <= 0:
        start = time.perf_counter()
        candidates, mask = _solver_candidates(game, request, intent)
        wall_clock_ms = int(round((time.perf_counter() - start) * 1000.0))
        return candidates, mask, wall_clock_ms, False

    def _action(_deadline: float):
        return _solver_candidates(game, request, intent)

    def _fallback():
        return _fallback_candidates(request)

    (candidates, mask), fallback_mode, wall_clock_ms = time_manager.run_with_time_budget(
        budget_ms=budget_ms,
        action=_action,
        fallback=_fallback,
    )
    return candidates, mask, int(wall_clock_ms), bool(fallback_mode)
