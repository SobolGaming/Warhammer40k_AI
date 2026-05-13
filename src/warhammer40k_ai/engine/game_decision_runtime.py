from __future__ import annotations

from .candidate_semantics import ensure_candidate_semantic_metadata
from .decision_kinds import (
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_DECLARE_RESERVES,
    DECISION_MOVE_UNIT,
    DECISION_REQUEST_DICE_ROLL,
    DECISION_REROLL_ROLL,
    DECISION_SCOUT_MOVE,
    DECISION_SELECT_DICE_REROLL,
    DECISION_SELECT_MOVEMENT_ACTION,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
)
from .deployment_intent import DeploymentIntent
from .deployment_solver import generate_deployment_candidates
from .descriptor_compiler import compile_descriptor_bundle
from .dice_rolls import DiceRollState
from .limited_use_context import normalize_optional_ability_limited_use_context
from .movement_intent import MovementIntent
from .movement_solver import generate_move_unit_candidates, generate_select_movement_action_candidates
from .path_witness import PathWitnessStore
from .time_manager import TimeManager
from .version_adapter import ensure_version_adapter_boundary
from .decisions import CandidateAction


def _normalize_candidate_bundle(candidates, mask, solver_ms: int, fallback_mode: bool) -> tuple[list[CandidateAction], list[bool], list[str | None]]:
    normalized_candidates: list[CandidateAction] = []
    for candidate in list(candidates or []):
        metadata = dict(candidate.metadata or {})
        metadata["solver_ms"] = int(max(0, solver_ms))
        metadata["fallback_mode"] = bool(fallback_mode or metadata.get("fallback_mode", False))
        normalized_candidates.append(
            CandidateAction(
                action_id=str(candidate.action_id),
                params=dict(candidate.params or {}),
                metadata=metadata,
            )
        )
    normalized_mask = [bool(value) for value in list(mask or [])]
    if len(normalized_mask) != len(normalized_candidates):
        normalized_mask = [True] * len(normalized_candidates)
    mask_reasons = [None if value else "masked_as_illegal" for value in normalized_mask]
    return normalized_candidates, normalized_mask, mask_reasons


def request_decision(game, request) -> None:
    """Queue a decision request (interrupt window)."""
    if request is None:
        return
    request.finalize_candidates()
    ctx = dict(getattr(request, "context", {}) or {})
    ctx = normalize_optional_ability_limited_use_context(
        ctx,
        ability_key=str(
            ctx.get("ability", "")
            or ctx.get("ability_key", "")
            or ctx.get("once_per_battle_key", "")
            or ctx.get("once_key", "")
            or request.decision_type
        ),
        ability_name=str(ctx.get("ability_name", "") or request.prompt),
        message=str(ctx.get("message", "") or request.prompt),
    )
    if request.decision_type in (DECISION_REQUEST_DICE_ROLL, DECISION_REROLL_ROLL, DECISION_SELECT_DICE_REROLL):
        roll_id = ctx.get("roll_id")
        if roll_id is not None and game.roll_manager is not None:
            roll_state = game.roll_manager.get_roll(int(roll_id))
            if roll_state is None:
                spec = dict(ctx.get("roll_spec", {}) or {})
                roll_state = DiceRollState(
                    roll_id=int(roll_id),
                    player_id=request.player_id,
                    spec=spec,
                    status="pending",
                )
                game.roll_manager.rolls[int(roll_id)] = roll_state
            if request.decision_type in (DECISION_REROLL_ROLL, DECISION_SELECT_DICE_REROLL):
                if "roll_spec" not in ctx:
                    ctx["roll_spec"] = dict(getattr(roll_state, "spec", {}) or {})
                if "roll_state" not in ctx:
                    ctx["roll_state"] = roll_state.to_dict()

    ruleset_ctx = game.get_ruleset_context()
    if "rules_bundle" not in ctx:
        ctx["rules_bundle"] = dict(ruleset_ctx or {})
    elif dict(ctx.get("rules_bundle", {}) or {}) != dict(ruleset_ctx or {}):
        raise ValueError("Decision context rules_bundle mismatch with game rules bundle.")
    for key, value in ruleset_ctx.items():
        if key not in ctx:
            ctx[key] = value
        elif ctx.get(key) != value:
            raise ValueError(f"Decision context ruleset mismatch for {key}: {ctx.get(key)} != {value}")
    rules_bundle = getattr(game, "ruleset_bundle", None)
    rules_bundle_id = str(getattr(rules_bundle, "rules_bundle_id", "") or "")
    if rules_bundle_id and "rules_bundle_id" not in ctx:
        ctx["rules_bundle_id"] = rules_bundle_id

    descriptor_bundle = compile_descriptor_bundle(game)
    if "descriptor_ids" not in ctx or not isinstance(ctx.get("descriptor_ids"), dict):
        ctx["descriptor_ids"] = descriptor_bundle.descriptor_ids()
    else:
        descriptor_ids = dict(ctx.get("descriptor_ids", {}) or {})
        expected_descriptor_ids = descriptor_bundle.descriptor_ids()
        for key, value in expected_descriptor_ids.items():
            existing_value = descriptor_ids.get(key)
            if existing_value in (None, "", []):
                descriptor_ids[key] = value
        ctx["descriptor_ids"] = descriptor_ids
    if "descriptor_bundle_id" not in ctx:
        ctx["descriptor_bundle_id"] = str(descriptor_bundle.bundle_id)
    ctx = ensure_version_adapter_boundary(ctx)

    plan_player_id = str(getattr(request, "player_id", "") or "")
    if not plan_player_id:
        current_player = game.get_current_player() if game.players else None
        plan_player_id = str(getattr(current_player, "id", "") or "")
    if plan_player_id:
        plan = game.get_or_create_tier1_plan(plan_player_id)
        tier2_bundle = game.get_or_create_tier2_task_bundle(plan_player_id)
        if "plan_id" not in ctx:
            ctx["plan_id"] = plan.plan_id
        if "turn_plan" not in ctx:
            ctx["turn_plan"] = plan.to_dict()
        if "score_window_state" not in ctx:
            ctx["score_window_state"] = {
                "windows": [window.to_dict() for window in list(plan.scoring_windows or [])],
                "battle_round": int(getattr(plan, "battle_round", 0) or 0),
            }
        if "opportunity_catalog" not in ctx:
            ctx["opportunity_catalog"] = {
                "priority": [opp.to_dict() for opp in list(plan.priority_opportunities or [])],
                "denial": [opp.to_dict() for opp in list(plan.denial_opportunities or [])],
            }
        if "mission_state" not in ctx:
            ctx["mission_state"] = {
                "selected_mission_info": dict(getattr(game, "selected_mission_info", {}) or {}),
                "secondary_mission_mode": str(getattr(game, "secondary_mission_mode", "") or ""),
            }
        if "terrain_state_summary" not in ctx:
            map_obj = getattr(game, "map", None)
            terrain_features = list(getattr(map_obj, "terrain_features", []) or [])
            terrain_ids = sorted(str(getattr(feature, "id", "") or "") for feature in terrain_features)
            ctx["terrain_state_summary"] = {
                "terrain_count": int(len(terrain_features)),
                "terrain_ids": terrain_ids,
            }
        if "cp_reserve_policy" not in ctx:
            ctx["cp_reserve_policy"] = dict(tier2_bundle.cp_reserve_policy or {})
        unit_id = str(ctx.get("unit_id", "") or "")
        task = tier2_bundle.tasks_by_unit_id.get(unit_id) if unit_id else None
        if task is not None:
            if "tier2_task" not in ctx:
                ctx["tier2_task"] = task.to_dict()
            if "movement_intent" not in ctx:
                ctx["movement_intent"] = task.movement_intent.to_dict()
            if "compute_tier" not in ctx:
                ctx["compute_tier"] = str(task.compute_tier)
        if "compute_tier" not in ctx:
            ctx["compute_tier"] = "P1"

    time_manager = getattr(game, "time_manager", None)
    if time_manager is None:
        time_manager = TimeManager()
        game.time_manager = time_manager
    ctx = time_manager.decorate_context(request.decision_type, ctx)

    if request.decision_type in (
        DECISION_CHOOSE_DEPLOYMENT_ZONE,
        DECISION_SELECT_NEXT_DEPLOY_UNIT,
        DECISION_DECLARE_RESERVES,
        DECISION_SCOUT_MOVE,
    ):
        deployment_intent = DeploymentIntent.from_context(ctx)
        ctx["deployment_intent"] = deployment_intent.to_dict()
        request.context = ctx
        deployment_candidates, deployment_mask, solver_ms, fallback_mode = generate_deployment_candidates(
            game,
            request,
            deployment_intent,
        )
        if deployment_candidates:
            request.candidates, request.mask, request.mask_reasons = _normalize_candidate_bundle(
                deployment_candidates,
                deployment_mask,
                solver_ms,
                fallback_mode,
            )
    if request.decision_type == DECISION_MOVE_UNIT:
        placement_kind = str(ctx.get("placement_kind", "") or "").strip().lower()
        if placement_kind == "deployment":
            deployment_intent = DeploymentIntent.from_context(ctx)
            ctx["deployment_intent"] = deployment_intent.to_dict()
            request.context = ctx
            deployment_candidates, deployment_mask, solver_ms, fallback_mode = generate_deployment_candidates(
                game,
                request,
                deployment_intent,
            )
            if deployment_candidates:
                request.candidates, request.mask, request.mask_reasons = _normalize_candidate_bundle(
                    deployment_candidates,
                    deployment_mask,
                    solver_ms,
                    fallback_mode,
                )
        elif placement_kind not in ("advance_redeploy_9h", "normal_move_redeploy_9h"):
            if getattr(game, "path_witness_store", None) is None:
                game.path_witness_store = PathWitnessStore()
            intent = MovementIntent.from_context(ctx)
            ctx["movement_intent"] = intent.to_dict()
            request.context = ctx
            move_candidates, move_mask, solver_ms, fallback_mode = generate_move_unit_candidates(game, request, intent)
            if move_candidates:
                request.candidates, request.mask, request.mask_reasons = _normalize_candidate_bundle(
                    move_candidates,
                    move_mask,
                    solver_ms,
                    fallback_mode,
                )
    if request.decision_type == DECISION_SELECT_MOVEMENT_ACTION:
        phase_name = str(ctx.get("phase_name", "") or "").strip().upper()
        phase_step = str(ctx.get("phase_step", "") or "").strip().upper()
        if phase_name == "MOVEMENT_PHASE" and phase_step == "MOVE_UNITS":
            intent = MovementIntent.from_context(ctx)
            ctx["movement_intent"] = intent.to_dict()
            request.context = ctx
            action_candidates, action_mask, action_mask_reasons = generate_select_movement_action_candidates(
                game,
                request,
                intent,
            )
            if action_candidates:
                request.candidates, request.mask, _default_reasons = _normalize_candidate_bundle(
                    action_candidates,
                    action_mask,
                    solver_ms=0,
                    fallback_mode=False,
                )
                if len(action_mask_reasons) == len(request.candidates):
                    request.mask_reasons = list(action_mask_reasons)

    request.context = ctx
    semantic_rules_bundle_id = str(ctx.get("rules_bundle_id", "") or "")
    ensure_candidate_semantic_metadata(
        request,
        rules_bundle_id=semantic_rules_bundle_id,
    )
    game.decision_queue.add(request)
    game.event_system.publish("decision_requested", request=request, game=game)
