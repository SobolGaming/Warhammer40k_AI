from __future__ import annotations

import hashlib
import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Iterable

from .combat_timing import geometry_profile_for_game
from .ai_controller_router import AIControllerRouter
from .decision_controller import DecisionController
from .decision_kinds import (
    DECISION_ATTACH_LEADER,
    DECISION_ASSIGN_TRANSPORT,
    DECISION_ATTACH_SUPPORT_ARTILLERY,
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_CHOOSE_MISSION,
    DECISION_DECLARE_RESERVES,
    DECISION_DECLARE_SHOTS,
    DECISION_MOVE_UNIT,
    DECISION_REQUEST_DICE_ROLL,
    DECISION_RESOLVE_COHERENCY,
    DECISION_SELECT_DICE_REROLL,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
    DECISION_SELECT_UNIT,
)
from .decision_handlers.movement import validate_move_unit_payload
from .decisions import CandidateAction, DecisionRequest
from .placement_zone_heuristics import (
    exhaustive_lattice_candidate_positions as _exhaustive_lattice_candidate_positions_shared,
    gap_anchor_candidates as _gap_anchor_candidates_shared,
    lattice_candidate_positions as _lattice_candidate_positions_shared,
    packing_row_anchor_candidates as _packing_row_anchor_candidates_shared,
)
from .reserve_entry_geometry import build_model_positions_from_anchor as _build_reserves_model_positions_from_anchor
from .reserve_entry_geometry import (
    is_valid_strategic_reserves_edge as _is_valid_strategic_reserves_edge,
    strategic_reserves_edges as _strategic_reserves_edges,
)
from .reserve_entry_rules import masters_of_void_enemy_dz_override_active
from ..utility.call_utils import call_with_supported_kwargs
from ..utility.decision_utils import resolve_decision_command
from ..utility.entity_ids import get_entity_id, maybe_entity_id
from ..utility.placement_search import (
    build_placement_search_context,
    deployed_unit_bounds,
    estimate_unit_pack_footprint,
)

_DEFAULT_SKIPPED_DECISION_TYPES = {
    DECISION_REQUEST_DICE_ROLL,
    DECISION_SELECT_DICE_REROLL,
}

_DRIVER_MANAGED_DECISION_TYPES = {
    DECISION_CHOOSE_MISSION,
}

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SemanticScoreWeights:
    score_next_window: float = 2.0
    score_round: float = 1.0
    deny_next_window: float = 1.5
    control_delta: float = 1.0
    action_enablement_delta: float = 0.5
    trade_ev: float = 0.5
    exposure_delta: float = -0.75
    cover_delta: float = 0.3
    los_delta: float = 0.2
    resource_delta: float = 0.25


class HeadlessPolicyDecisionController(DecisionController):
    """
    Deterministic headless controller that selects only legal (masked) candidates.

    Intended use:
    - non-UI/headless execution
    - baseline data generation before ML policy onboarding
    """

    def __init__(
        self,
        game: object | None = None,
        *,
        player_id: str | None = None,
        skip_decision_types: Iterable[str] | None = None,
        semantic_score_weights: SemanticScoreWeights | None = None,
        exploration_epsilon: float = 0.0,
        tie_break_salt: str = "headless_policy_v1",
        max_reserves_anchor_points: int = 4096,
        max_reserves_arrival_seconds: float = 10.0,
        reserve_policy: str = "forced_only",
        require_authoritative: bool = True,
        ai_router: AIControllerRouter | None = None,
        auto_attach: bool = True,
    ) -> None:
        super().__init__(player_id=player_id)
        self._game = game
        skipped = set(_DEFAULT_SKIPPED_DECISION_TYPES)
        for value in list(skip_decision_types or []):
            text = str(value or "").strip()
            if text:
                skipped.add(text)
        self._skip_decision_types = skipped
        self._weights = semantic_score_weights or SemanticScoreWeights()
        self._exploration_epsilon = float(max(0.0, min(1.0, exploration_epsilon)))
        self._tie_break_salt = str(tie_break_salt or "headless_policy_v1")
        self._max_reserves_anchor_points = int(max(64, int(max_reserves_anchor_points or 0)))
        self._reserves_exhaustive_anchor_limit = int(max(32, min(self._max_reserves_anchor_points, 512)))
        self._max_reserves_arrival_seconds = float(max(0.1, float(max_reserves_arrival_seconds or 0.1)))
        self._reserve_policy = self._normalize_reserve_policy(reserve_policy)
        self._require_authoritative = bool(require_authoritative)
        self._ai_router = ai_router
        self._attached = False
        self._reserves_arrival_search_metrics: list[dict[str, object]] = []
        if auto_attach and self._game is not None:
            self.attach()

    def attach(self) -> None:
        if self._attached or self._game is None:
            return
        add_controller = getattr(self._game, "add_decision_controller", None)
        if not callable(add_controller):
            return
        add_controller(self)
        self._attached = True

    def supports_generic_tool_decisions(self) -> bool:
        return True

    def on_decision_requested(self, game: object, request: DecisionRequest) -> None:
        if request is None:
            return
        observed_game = game if game is not None else self._game
        if observed_game is None:
            return
        resolution_game = self._game if self._game is not None else observed_game
        if self._require_authoritative and not bool(getattr(observed_game, "is_authoritative", True)):
            return
        if self._should_skip_request(request):
            return
        if str(getattr(request, "decision_type", "") or "") in self._skip_decision_types:
            return

        ranked = self._rank_legal_candidates(request)
        if self._ai_router is not None:
            ranked = self._ai_router.rank_legal_candidates(request, fallback_order=ranked)
        if self._is_reserves_arrival_request(request):
            ranked_move = [candidate for candidate in ranked if not self._candidate_requests_skip(candidate)]
            ranked_skip = [candidate for candidate in ranked if self._candidate_requests_skip(candidate)]
            for candidate in ranked_move:
                if self._try_resolve_candidate(resolution_game, request, candidate):
                    return
            if self._try_resolve_reserves_arrival_bruteforce(resolution_game, request):
                return
            for candidate in ranked_skip:
                if self._try_resolve_candidate(resolution_game, request, candidate):
                    return
            self._resolve_first_legal_option(resolution_game, request)
            return

        if not ranked:
            self._resolve_first_legal_option(resolution_game, request)
            return

        for candidate in ranked:
            if self._try_resolve_candidate(resolution_game, request, candidate):
                return
        if self._try_resolve_reserves_arrival_bruteforce(resolution_game, request):
            return
        self._resolve_first_legal_option(resolution_game, request)

    def _resolve_first_legal_option(self, game: object, request: DecisionRequest) -> None:
        for option in list(getattr(request, "options", []) or []):
            option_id = str(getattr(option, "option_id", "") or "")
            if not option_id:
                continue
            action_id = request.action_id_for_option_id(option_id)
            masked = request.candidate_mask_for_action_id(action_id)
            if masked is False:
                continue
            option_payload = dict(getattr(option, "payload", {}) or {})
            candidate = self._candidate_for_action_id(request, action_id)
            if candidate is None:
                candidate = self._candidate_from_option_payload(action_id, option_payload)
            if not self._candidate_is_structurally_resolvable(request, candidate):
                continue
            result_payload = self._normalized_result_payload(request, option_payload, game=game)
            if bool(option_payload.get("skip", False)):
                result_payload["skipped"] = True
            if str(option_payload.get("action", "") or "").strip().lower() == "skip":
                result_payload["skipped"] = True
            if not self._result_payload_is_structurally_resolvable(request, result_payload):
                continue
            if not self._candidate_passes_current_game_precheck(game, request, option_id):
                continue
            apply_result = self._safe_resolve_decision_command(
                game,
                request,
                option_id,
                result_payload=result_payload,
                player_id=getattr(request, "player_id", None),
                metadata=self._command_metadata_for_candidate(candidate, strategy="first_legal_option"),
            )
            if apply_result is not None and bool(getattr(apply_result, "ok", False)):
                return

    def _try_resolve_candidate(self, game: object, request: DecisionRequest, candidate: CandidateAction) -> bool:
        option_id = self._option_id_for_action_id(request, str(candidate.action_id or ""))
        if not option_id:
            return False
        payload = self._normalized_result_payload(request, dict(getattr(candidate, "params", {}) or {}), game=game)
        if bool(payload.get("skip", False)):
            payload["skipped"] = True
        if str(payload.get("action", "") or "").strip().lower() == "skip":
            payload["skipped"] = True
        if not self._result_payload_is_structurally_resolvable(request, payload):
            return False
        if not self._candidate_passes_current_game_precheck(game, request, option_id):
            return False
        if self._is_reserves_arrival_request(request):
            validation_errors = validate_move_unit_payload(
                game,
                request,
                option_payload=self._option_payload(request, option_id),
                result_payload=payload,
            )
            if validation_errors:
                return False
        apply_result = self._safe_resolve_decision_command(
            game,
            request,
            option_id,
            result_payload=payload,
            player_id=getattr(request, "player_id", None),
            metadata=self._command_metadata_for_candidate(candidate, strategy="ranked_candidate"),
        )
        return bool(apply_result is not None and getattr(apply_result, "ok", False))

    def _safe_resolve_decision_command(
        self,
        game: object,
        request: DecisionRequest,
        option_id: str,
        *,
        result_payload: dict[str, Any],
        player_id: str | None,
        metadata: dict[str, Any] | None = None,
    ):
        try:
            return resolve_decision_command(
                game,
                request,
                option_id,
                result_payload=result_payload,
                player_id=player_id,
                metadata=metadata,
            )
        except (RuntimeError, ValueError) as exc:
            logger.debug(
                "Headless controller rejected candidate for %s (%s): %s",
                str(getattr(request, "decision_type", "") or ""),
                str(option_id or ""),
                str(exc),
            )
            return None

    def _normalized_result_payload(
        self,
        request: DecisionRequest,
        payload: dict[str, Any],
        *,
        game: object | None = None,
    ) -> dict[str, Any]:
        normalized = dict(payload or {})
        if str(getattr(request, "decision_type", "") or "") == DECISION_RESOLVE_COHERENCY:
            model_ids = [str(value or "") for value in list(normalized.get("model_ids", []) or []) if str(value or "")]
            if not model_ids:
                model_id = str(normalized.get("model_id", "") or "").strip()
                if model_id:
                    model_ids = [model_id]
            if model_ids:
                normalized["model_ids"] = model_ids
        if str(getattr(request, "decision_type", "") or "") == DECISION_DECLARE_SHOTS:
            action = str(normalized.get("action", "") or "").strip().lower()
            if action not in {"skip", "pass"} and not bool(normalized.get("skipped", False)):
                declarations = normalized.get("declarations")
                if not isinstance(declarations, list) or not declarations:
                    default_declarations = self._default_shooting_declarations(game, request, normalized)
                    if default_declarations:
                        normalized["declarations"] = default_declarations
        if str(getattr(request, "decision_type", "") or "") == DECISION_MOVE_UNIT:
            action = str(normalized.get("action", "") or "").strip().lower()
            if action not in {"skip", "pass"} and not bool(normalized.get("skipped", False)):
                model_positions = normalized.get("model_positions")
                if not isinstance(model_positions, list) or not model_positions:
                    synthesized_positions = self._synthesized_move_model_positions(game, request, normalized)
                    if synthesized_positions:
                        normalized["model_positions"] = synthesized_positions
        return normalized

    @staticmethod
    def _move_request_can_synthesize_positions(request: DecisionRequest, payload: dict[str, Any]) -> bool:
        if str(getattr(request, "decision_type", "") or "") != DECISION_MOVE_UNIT:
            return False
        params = dict(payload or {})
        action = str(params.get("action", "") or "").strip().lower()
        if action in {"skip", "pass"} or bool(params.get("skip", False)) or bool(params.get("skipped", False)):
            return False
        ctx = dict(getattr(request, "context", {}) or {})
        movement_type = str(params.get("movement_type", "") or ctx.get("movement_type", "") or "").strip().lower()
        if movement_type != "deploy":
            return False
        placement_kind = str(ctx.get("placement_kind", "") or "").strip().lower()
        if not placement_kind:
            return False
        if placement_kind in {
            "deployment",
            "reserves_arrival",
            "hyperphasic_recall",
            "subterranean_tunnel_network",
            "aeldari_unshrouded_truth",
            "advance_redeploy_9h",
            "normal_move_redeploy_9h",
        }:
            return False
        allowed_model_ids = [
            str(value or "").strip()
            for value in list(ctx.get("allowed_model_ids", []) or [])
            if str(value or "").strip()
        ]
        return bool(allowed_model_ids)

    @staticmethod
    def _model_location(model: object) -> tuple[float, float, float, float] | None:
        get_location = getattr(model, "get_location", None)
        if callable(get_location):
            try:
                location = get_location()
            except (AttributeError, RuntimeError, TypeError, ValueError):
                location = None
            if isinstance(location, (tuple, list)) and len(location) >= 2:
                base = getattr(model, "model_base", None)
                z = float(location[2]) if len(location) >= 3 else float(getattr(base, "z", 0.0) or 0.0)
                facing = float(location[3]) if len(location) >= 4 else float(getattr(base, "facing", 0.0) or 0.0)
                return (float(location[0]), float(location[1]), z, facing)
        base = getattr(model, "model_base", None)
        if base is None:
            return None
        return (
            float(getattr(base, "x", 0.0) or 0.0),
            float(getattr(base, "y", 0.0) or 0.0),
            float(getattr(base, "z", 0.0) or 0.0),
            float(getattr(base, "facing", 0.0) or 0.0),
        )

    @staticmethod
    def _set_model_location(
        model: object,
        *,
        x: float,
        y: float,
        z: float,
        facing: float,
    ) -> bool:
        set_location = getattr(model, "set_location", None)
        if callable(set_location):
            try:
                set_location(float(x), float(y), float(z), float(facing))
                return True
            except (AttributeError, RuntimeError, TypeError, ValueError):
                return False
        base = getattr(model, "model_base", None)
        if base is None:
            return False
        base.x = float(x)
        base.y = float(y)
        base.z = float(z)
        base.facing = float(facing)
        return True

    @staticmethod
    def _serialize_model_position(
        model: object,
        *,
        x: float,
        y: float,
        z: float,
        facing: float,
    ) -> dict[str, object]:
        return {
            "model_id": str(maybe_entity_id(model) or ""),
            "position": [float(x), float(y), float(z)],
            "facing": float(facing),
        }

    @classmethod
    def _unit_positions_for_coherency(
        cls,
        unit: object,
    ) -> list[tuple[float, float, float]]:
        positions: list[tuple[float, float, float]] = []
        for model in list(getattr(unit, "models", []) or []):
            location = cls._model_location(model)
            if location is None:
                positions.append((0.0, 0.0, 0.0))
                continue
            positions.append((float(location[0]), float(location[1]), float(location[2])))
        return positions

    @classmethod
    def _placement_keeps_unit_coherent(
        cls,
        unit: object,
        *,
        pending_models: list[object],
    ) -> bool:
        unit_models = list(getattr(unit, "models", []) or [])
        if not unit_models:
            return True
        pending_ids = {
            str(maybe_entity_id(model) or "").strip()
            for model in list(pending_models or [])
            if model is not None and str(maybe_entity_id(model) or "").strip()
        }
        if not pending_ids:
            return True
        unit_model_ids = {
            str(maybe_entity_id(model) or "").strip()
            for model in unit_models
            if model is not None and str(maybe_entity_id(model) or "").strip()
        }
        if not pending_ids.issubset(unit_model_ids):
            return True
        try:
            from ..utility.calcs import validate_unit_coherency_after_movement
        except ImportError:
            return True
        try:
            coherent, _non_coherent = validate_unit_coherency_after_movement(
                unit,
                cls._unit_positions_for_coherency(unit),
                ignore_pending=False,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return True
        return bool(coherent)

    @classmethod
    def _reanimation_candidate_positions(
        cls,
        root: object,
        model: object,
        *,
        search_models: list[object],
        game_map: object | None,
        required_neighbors: int,
        limit: int = 128,
    ) -> list[tuple[float, float, float, float]]:
        candidates: list[tuple[float, float, float, float]] = []
        seen: set[tuple[float, float, float, float]] = set()

        def _add_candidate(candidate: object) -> None:
            if not isinstance(candidate, (tuple, list)) or len(candidate) < 4:
                return
            key = (
                round(float(candidate[0]), 6),
                round(float(candidate[1]), 6),
                round(float(candidate[2]), 6),
                round(float(candidate[3]), 6),
            )
            if key in seen:
                return
            seen.add(key)
            candidates.append((float(candidate[0]), float(candidate[1]), float(candidate[2]), float(candidate[3])))

        find_position = getattr(root, "_find_reanimation_position", None)
        if callable(find_position):
            primary = call_with_supported_kwargs(
                find_position,
                model,
                list(search_models),
                game_map=game_map,
                required_neighbors=required_neighbors,
            )
            _add_candidate(primary)
            if len(candidates) >= int(max(1, limit)):
                return candidates

        validate_position = getattr(root, "_reanimation_position_valid", None)
        if not callable(validate_position):
            return candidates

        try:
            model_radius = float(getattr(model.model_base, "get_longest_radius")())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            try:
                model_radius = float(getattr(model.model_base, "get_radius")())
            except (AttributeError, RuntimeError, TypeError, ValueError):
                return candidates

        for anchor in list(search_models or []):
            location = cls._model_location(anchor)
            if location is None:
                continue
            try:
                anchor_radius = float(getattr(anchor.model_base, "get_longest_radius")())
            except (AttributeError, RuntimeError, TypeError, ValueError):
                try:
                    anchor_radius = float(getattr(anchor.model_base, "get_radius")())
                except (AttributeError, RuntimeError, TypeError, ValueError):
                    continue
            min_center = anchor_radius + model_radius + 0.05
            max_center = min_center + 2.0 + 1e-6
            ring = 0.0
            while ring <= max(0.01, max_center - min_center) + 0.001:
                radius = float(min_center + ring)
                if radius > max_center + 1e-6:
                    break
                for deg in range(0, 360, 15):
                    angle = math.radians(deg)
                    candidate = (
                        float(location[0]) + math.cos(angle) * radius,
                        float(location[1]) + math.sin(angle) * radius,
                        float(location[2]),
                        float(location[3]),
                    )
                    try:
                        valid = bool(
                            validate_position(
                                candidate[0],
                                candidate[1],
                                candidate[2],
                                candidate[3],
                                model,
                                list(search_models),
                                game_map,
                                required_neighbors,
                            )
                        )
                    except (AttributeError, RuntimeError, TypeError, ValueError):
                        valid = False
                    if not valid:
                        continue
                    _add_candidate(candidate)
                    if len(candidates) >= int(max(1, limit)):
                        return candidates
                ring += 0.5
        return candidates

    @classmethod
    def _reanimation_backtracking_positions(
        cls,
        root: object,
        *,
        pending_models: list[object],
        anchored_models: list[object],
        game_map: object | None,
        required_neighbors: int,
        original_locations: dict[str, tuple[float, float, float, float]],
        candidate_limit: int = 128,
        max_nodes: int = 4096,
    ) -> list[dict[str, object]] | None:
        if not pending_models:
            return None

        nodes_visited = 0

        def _restore_model_location(model: object) -> None:
            model_id = str(maybe_entity_id(model) or "").strip()
            location = original_locations.get(model_id)
            if location is None:
                return
            cls._set_model_location(
                model,
                x=location[0],
                y=location[1],
                z=location[2],
                facing=location[3],
            )

        def _search(index: int, search_models: list[object]) -> list[dict[str, object]] | None:
            nonlocal nodes_visited
            if nodes_visited >= int(max(1, max_nodes)):
                return None
            if index >= len(pending_models):
                if not cls._placement_keeps_unit_coherent(root, pending_models=pending_models):
                    return None
                serialized: list[dict[str, object]] = []
                for pending_model in pending_models:
                    location = cls._model_location(pending_model)
                    if location is None:
                        return None
                    serialized.append(
                        cls._serialize_model_position(
                            pending_model,
                            x=location[0],
                            y=location[1],
                            z=location[2],
                            facing=location[3],
                        )
                    )
                return serialized

            model = pending_models[index]
            for candidate in cls._reanimation_candidate_positions(
                root,
                model,
                search_models=list(search_models),
                game_map=game_map,
                required_neighbors=required_neighbors,
                limit=int(max(1, candidate_limit)),
            ):
                nodes_visited += 1
                if not cls._set_model_location(
                    model,
                    x=candidate[0],
                    y=candidate[1],
                    z=candidate[2],
                    facing=candidate[3],
                ):
                    continue
                resolved = _search(index + 1, list(search_models) + [model])
                if resolved is not None:
                    return resolved
            _restore_model_location(model)
            return None

        try:
            return _search(0, list(anchored_models))
        finally:
            for model in pending_models:
                _restore_model_location(model)

    @classmethod
    def _synthesized_move_model_positions(
        cls,
        game: object | None,
        request: DecisionRequest,
        payload: dict[str, Any],
    ) -> list[dict[str, object]] | None:
        if game is None or not cls._move_request_can_synthesize_positions(request, payload):
            return None

        ctx = dict(getattr(request, "context", {}) or {})
        unit_id = str(payload.get("unit_id", "") or ctx.get("unit_id", "") or "").strip()
        if not unit_id:
            return None
        unit = cls._resolve_unit(game, unit_id)
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit

        find_position = getattr(root, "_find_reanimation_position", None)
        validate_position = getattr(root, "_reanimation_position_valid", None)
        if not callable(find_position) and not callable(validate_position):
            return None

        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        attached_models: list[object] = []
        for member in list(members or []):
            if member is None:
                continue
            attached_models.extend(list(getattr(member, "models", []) or []))
        if not attached_models:
            get_models = getattr(root, "get_attached_unit_models", None)
            attached_models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        identified_models = [
            model
            for model in attached_models
            if model is not None and str(maybe_entity_id(model) or "").strip()
        ]
        if not identified_models:
            return None

        models_by_id = {
            str(maybe_entity_id(model) or "").strip(): model
            for model in identified_models
        }
        allowed_model_ids = [
            str(value or "").strip()
            for value in list(ctx.get("allowed_model_ids", []) or [])
            if str(value or "").strip()
        ]
        pending_models: list[object] = []
        for model_id in allowed_model_ids:
            model = models_by_id.get(model_id)
            if model is None:
                return None
            pending_models.append(model)
        if not pending_models:
            return None

        allowed_set = set(allowed_model_ids)
        anchored_models = [
            model
            for model in sorted(identified_models, key=cls._entity_sort_key)
            if str(maybe_entity_id(model) or "").strip() not in allowed_set and cls._alive(model)
        ]
        final_alive_count = len(anchored_models) + len(pending_models)
        required_neighbors = 0 if final_alive_count <= 1 else (2 if final_alive_count >= 7 else 1)
        game_map = getattr(game, "map", None)

        original_locations: dict[str, tuple[float, float, float, float]] = {}
        placed_positions: list[dict[str, object]] = []
        search_models = list(anchored_models)
        for model in pending_models:
            model_id = str(maybe_entity_id(model) or "").strip()
            if not model_id:
                return None
            location = cls._model_location(model)
            if location is None:
                return None
            original_locations[model_id] = location

        try:
            if callable(find_position):
                for model in pending_models:
                    candidate = call_with_supported_kwargs(
                        find_position,
                        model,
                        list(search_models),
                        game_map=game_map,
                        required_neighbors=required_neighbors,
                    )
                    if not isinstance(candidate, (tuple, list)) or len(candidate) < 4:
                        placed_positions = []
                        break
                    x = float(candidate[0])
                    y = float(candidate[1])
                    z = float(candidate[2])
                    facing = float(candidate[3])
                    if not cls._set_model_location(model, x=x, y=y, z=z, facing=facing):
                        placed_positions = []
                        break
                    search_models.append(model)
                    placed_positions.append(
                        cls._serialize_model_position(model, x=x, y=y, z=z, facing=facing)
                    )
            if placed_positions and cls._placement_keeps_unit_coherent(root, pending_models=pending_models):
                return list(placed_positions)
            coherent_positions = cls._reanimation_backtracking_positions(
                root,
                pending_models=pending_models,
                anchored_models=anchored_models,
                game_map=game_map,
                required_neighbors=required_neighbors,
                original_locations=original_locations,
            )
            if coherent_positions:
                return coherent_positions
        finally:
            for model in pending_models:
                model_id = str(maybe_entity_id(model) or "").strip()
                location = original_locations.get(model_id)
                if location is None:
                    continue
                cls._set_model_location(
                    model,
                    x=location[0],
                    y=location[1],
                    z=location[2],
                    facing=location[3],
                )

        return placed_positions or None

    @staticmethod
    def _alive(value: object) -> bool:
        alive = getattr(value, "is_alive", True)
        if callable(alive):
            try:
                return bool(alive())
            except (AttributeError, RuntimeError, TypeError, ValueError):
                return False
        return bool(alive)

    @staticmethod
    def _entity_sort_key(value: object) -> str:
        return str(maybe_entity_id(value) or getattr(value, "name", "") or "")

    @classmethod
    def _attached_alive_models(cls, unit: object) -> list[object]:
        get_models = getattr(unit, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(unit, "models", []) or [])
        return sorted(
            [model for model in models if model is not None and cls._alive(model)],
            key=cls._entity_sort_key,
        )

    @staticmethod
    def _resolve_unit(game: object | None, unit_id: str) -> object | None:
        if game is None or not unit_id:
            return None
        resolver = getattr(game, "_resolve_unit_by_id", None)
        if callable(resolver):
            unit = resolver(unit_id)
            if unit is not None:
                return unit
        registry = getattr(game, "entity_registry", None)
        get_entity = getattr(registry, "get", None) if registry is not None else None
        if callable(get_entity):
            unit = get_entity(unit_id, kind="unit")
            if unit is not None:
                return unit
        for player in list(getattr(game, "players", []) or []):
            army = getattr(player, "army", None)
            for unit in list(getattr(army, "units", []) or []):
                if str(maybe_entity_id(unit) or "") == str(unit_id):
                    return unit
        return None

    @classmethod
    def _enemy_units_for_shooting(cls, game: object | None, unit: object) -> list[object]:
        if game is None or unit is None:
            return []
        game_map = getattr(game, "map", None)
        get_enemy_units = getattr(game_map, "get_enemy_units", None) if game_map is not None else None
        if callable(get_enemy_units):
            try:
                enemies = list(get_enemy_units(unit) or [])
            except (AttributeError, RuntimeError, TypeError, ValueError):
                enemies = []
        else:
            enemies = []
        if not enemies:
            get_army = getattr(unit, "get_parent_army", None)
            try:
                army = get_army() if callable(get_army) else getattr(unit, "parent_army", None)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                army = None
            player = getattr(army, "player", None) if army is not None else None
            game_get_enemy_units = getattr(game, "get_enemy_units", None)
            if callable(game_get_enemy_units) and player is not None:
                try:
                    enemies = list(game_get_enemy_units(player) or [])
                except (AttributeError, RuntimeError, TypeError, ValueError):
                    enemies = []
            else:
                enemies = []
        by_id: dict[str, object] = {}
        for enemy in enemies:
            if enemy is None:
                continue
            root_getter = getattr(enemy, "get_attached_unit_root", None)
            root = root_getter() if callable(root_getter) else enemy
            enemy_id = str(maybe_entity_id(root) or "")
            if not enemy_id or enemy_id in by_id:
                continue
            if not cls._alive(root):
                continue
            if not bool(getattr(root, "deployed", True)):
                continue
            reserve_check = getattr(root, "is_in_reserves", None)
            if callable(reserve_check) and bool(reserve_check()):
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            by_id[enemy_id] = root
        return [by_id[enemy_id] for enemy_id in sorted(by_id.keys())]

    @staticmethod
    def _profile_is_plasma_warhead(profile: object) -> bool:
        is_plasma_warhead = getattr(profile, "is_plasma_warhead", None)
        if callable(is_plasma_warhead):
            try:
                return bool(is_plasma_warhead())
            except (AttributeError, RuntimeError, TypeError, ValueError):
                return False
        return False

    @staticmethod
    def _profile_damage_score(profile: object, target_unit: object | None) -> float:
        score_fn = getattr(profile, "get_damage_potential", None)
        if not callable(score_fn):
            return 0.0
        try:
            return float(score_fn(target_unit) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _profile_hit_probability(profile: object) -> float:
        is_torrent = getattr(profile, "is_torrent", None)
        if callable(is_torrent):
            try:
                if bool(is_torrent()):
                    return 1.0
            except (AttributeError, RuntimeError, TypeError, ValueError):
                pass
        try:
            skill = int(getattr(profile, "skill", 0) or 0)
        except (TypeError, ValueError):
            skill = 0
        if skill <= 0:
            return 1.0
        needed = max(2, min(6, int(skill)))
        return max(0.0, min(1.0, float(7 - needed) / 6.0))

    @staticmethod
    def _target_has_keyword(target_unit: object | None, keyword: str) -> bool:
        if target_unit is None:
            return False
        text = str(keyword or "").strip().upper()
        if not text:
            return False
        has_keyword = getattr(target_unit, "has_keyword", None)
        if callable(has_keyword):
            try:
                if bool(has_keyword(text)):
                    return True
            except (AttributeError, RuntimeError, TypeError, ValueError):
                pass
        has_any_keyword = getattr(target_unit, "has_any_keyword", None)
        if callable(has_any_keyword):
            try:
                return bool(has_any_keyword(text))
            except (AttributeError, RuntimeError, TypeError, ValueError):
                return False
        keywords = getattr(target_unit, "keywords", None)
        if isinstance(keywords, (list, tuple, set)):
            return text in {str(value or "").strip().upper() for value in keywords}
        return False

    @classmethod
    def _profile_wound_probability(cls, profile: object, target_unit: object | None) -> float:
        chance_to_wound = 0.5
        try:
            strength = int(getattr(profile, "strength", 0) or 0)
        except (TypeError, ValueError):
            strength = 0
        try:
            target_toughness = int(getattr(target_unit, "toughness", 0) or 0)
        except (TypeError, ValueError):
            target_toughness = 0
        if strength > 0 and target_toughness > 0:
            if strength >= target_toughness * 2:
                chance_to_wound = 5.0 / 6.0
            elif strength > target_toughness:
                chance_to_wound = 4.0 / 6.0
            elif strength == target_toughness:
                chance_to_wound = 3.0 / 6.0
            elif strength <= target_toughness / 2.0:
                chance_to_wound = 1.0 / 6.0
            else:
                chance_to_wound = 2.0 / 6.0

        get_anti_specs = getattr(profile, "get_anti_specs", None)
        if callable(get_anti_specs):
            try:
                anti_specs = list(get_anti_specs() or [])
            except (AttributeError, RuntimeError, TypeError, ValueError):
                anti_specs = []
            for keyword, threshold in anti_specs:
                if not cls._target_has_keyword(target_unit, str(keyword or "")):
                    continue
                try:
                    needed = max(2, min(6, int(threshold)))
                except (TypeError, ValueError):
                    continue
                chance_to_wound = max(chance_to_wound, float(7 - needed) / 6.0)

        is_twin_linked = getattr(profile, "is_twin_linked", None)
        if callable(is_twin_linked):
            try:
                if bool(is_twin_linked()):
                    chance_to_wound = 1.0 - (1.0 - chance_to_wound) ** 2
            except (AttributeError, RuntimeError, TypeError, ValueError):
                pass
        return max(0.0, min(1.0, float(chance_to_wound)))

    @classmethod
    def _profile_accuracy_key(cls, profile: object, target_unit: object | None) -> tuple[float, float, float, float]:
        hit_prob = cls._profile_hit_probability(profile)
        wound_prob = cls._profile_wound_probability(profile, target_unit)
        return (
            float(hit_prob * wound_prob),
            float(hit_prob),
            float(wound_prob),
            cls._profile_damage_score(profile, target_unit),
        )

    @staticmethod
    def _shooting_profile_valid(
        unit: object,
        model: object,
        profile: object,
        target_unit: object,
        game_map: object | None,
    ) -> bool:
        validate = getattr(unit, "_validate_shooting_declaration", None)
        if callable(validate):
            try:
                validation = validate(profile, target_unit, [model], game_map)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                return False
            return bool(isinstance(validation, dict) and validation.get("valid", False))
        can_shoot = getattr(unit, "_can_model_shoot_weapon_at_target", None)
        if callable(can_shoot):
            try:
                return bool(can_shoot(model, profile, target_unit, game_map))
            except (AttributeError, RuntimeError, TypeError, ValueError):
                return False
        return False

    @classmethod
    def _default_shooting_declarations(
        cls,
        game: object | None,
        request: DecisionRequest,
        payload: dict[str, Any],
    ) -> list[dict[str, object]]:
        ctx = dict(getattr(request, "context", {}) or {})
        unit_id = str(payload.get("unit_id", "") or ctx.get("unit_id", "") or "").strip()
        unit = cls._resolve_unit(game, unit_id)
        if unit is None:
            return []
        game_map = getattr(game, "map", None) if game is not None else None
        allowed_model_ids = {
            str(value or "").strip()
            for value in list(ctx.get("allowed_model_ids", []) or [])
            if str(value or "").strip()
        }
        allowed_wargear_ids = {
            str(value or "").strip()
            for value in list(ctx.get("allowed_wargear_ids", []) or [])
            if str(value or "").strip()
        }
        force_target_id = str(ctx.get("force_target_unit_id", "") or "").strip()
        try:
            max_declarations = int(ctx.get("max_declarations", 0) or 0)
        except (TypeError, ValueError):
            max_declarations = 0
        targets = cls._enemy_units_for_shooting(game, unit)
        if force_target_id:
            targets = [target for target in targets if str(maybe_entity_id(target) or "") == force_target_id]
        declarations: list[dict[str, object]] = []
        out_of_phase = bool(ctx.get("out_of_phase", False))
        for model in cls._attached_alive_models(unit):
            model_id = str(maybe_entity_id(model) or "")
            if not model_id:
                continue
            if allowed_model_ids and model_id not in allowed_model_ids:
                continue
            wargear_items = sorted(
                list(getattr(model, "wargear", []) or []),
                key=lambda item: (str(maybe_entity_id(item) or ""), str(getattr(item, "name", "") or "")),
            )
            for wargear in wargear_items:
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged):
                    continue
                try:
                    ranged = bool(is_ranged())
                except (AttributeError, RuntimeError, TypeError, ValueError):
                    ranged = False
                if not ranged:
                    continue
                wargear_id = str(maybe_entity_id(wargear) or "")
                if not wargear_id:
                    continue
                if allowed_wargear_ids and wargear_id not in allowed_wargear_ids:
                    continue
                profiles = dict(getattr(wargear, "profiles", {}) or {})
                best_declaration: dict[str, object] | None = None
                best_key: tuple[float, float, float, float, str, str] | None = None
                for profile_name, profile in sorted(profiles.items(), key=lambda item: str(item[0])):
                    if profile is None:
                        continue
                    if cls._profile_is_plasma_warhead(profile):
                        can_shoot = getattr(profile, "can_shoot_plasma_warhead", None)
                        allowed = True
                        if callable(can_shoot):
                            try:
                                allowed, _reason = can_shoot(model, game_map=game_map, out_of_phase=out_of_phase)
                            except (AttributeError, RuntimeError, TypeError, ValueError):
                                allowed = False
                        if allowed:
                            key = (
                                0.0,
                                0.0,
                                0.0,
                                cls._profile_damage_score(profile, None),
                                "",
                                str(profile_name or ""),
                            )
                            if best_key is None or key > best_key:
                                best_key = key
                                best_declaration = {
                                    "wargear_id": wargear_id,
                                    "profile_name": str(profile_name or ""),
                                    "model_ids": [model_id],
                                }
                        continue
                    for target in targets:
                        target_id = str(maybe_entity_id(target) or "")
                        if not target_id:
                            continue
                        if not cls._shooting_profile_valid(unit, model, profile, target, game_map):
                            continue
                        accuracy_key = cls._profile_accuracy_key(profile, target)
                        key = (
                            accuracy_key[0],
                            accuracy_key[1],
                            accuracy_key[2],
                            accuracy_key[3],
                            target_id,
                            str(profile_name or ""),
                        )
                        if best_key is None or key > best_key:
                            best_key = key
                            best_declaration = {
                                "wargear_id": wargear_id,
                                "profile_name": str(profile_name or ""),
                                "model_ids": [model_id],
                                "target_unit_id": target_id,
                            }
                if best_declaration is not None:
                    declarations.append(best_declaration)
                    if max_declarations > 0 and len(declarations) >= max_declarations:
                        return declarations[:max_declarations]
        return declarations

    @staticmethod
    def _candidate_requests_skip(candidate: CandidateAction | None) -> bool:
        if candidate is None:
            return False
        params = dict(getattr(candidate, "params", {}) or {})
        return bool(
            params.get("skipped", False)
            or params.get("skip", False)
            or str(params.get("action", "") or "").strip().lower() in {"skip", "pass"}
        )

    @staticmethod
    def _is_reserves_arrival_request(request: DecisionRequest) -> bool:
        if str(getattr(request, "decision_type", "") or "") != DECISION_MOVE_UNIT:
            return False
        context = dict(getattr(request, "context", {}) or {})
        return str(context.get("placement_kind", "") or "") in {
            "reserves_arrival",
            "hyperphasic_recall",
            "subterranean_tunnel_network",
        }

    @staticmethod
    def _option_payload(request: DecisionRequest, option_id: str) -> dict[str, Any]:
        for option in list(getattr(request, "options", []) or []):
            if str(getattr(option, "option_id", "") or "") == str(option_id or ""):
                return dict(getattr(option, "payload", {}) or {})
        return {}

    def _option_id_for_action_id(self, request: DecisionRequest, action_id: str) -> str:
        if not action_id:
            return ""
        for option in list(getattr(request, "options", []) or []):
            option_id = str(getattr(option, "option_id", "") or "")
            if not option_id:
                continue
            if request.action_id_for_option_id(option_id) == action_id:
                return option_id
        return ""

    @staticmethod
    def _candidate_from_option_payload(action_id: str, option_payload: dict[str, Any]) -> CandidateAction:
        params = dict(option_payload or {})
        params.pop("action_id", None)
        return CandidateAction(action_id=str(action_id or ""), params=params, metadata={})

    def _result_payload_is_structurally_resolvable(self, request: DecisionRequest, payload: dict[str, Any]) -> bool:
        if str(getattr(request, "decision_type", "") or "") == DECISION_MOVE_UNIT:
            params = dict(payload or {})
            action = str(params.get("action", "") or "").strip().lower()
            if action in {"pass", "skip"} or bool(params.get("skip", False)) or bool(params.get("skipped", False)):
                return True
            model_positions = params.get("model_positions")
            if isinstance(model_positions, list) and bool(model_positions):
                return True
            return self._move_request_can_synthesize_positions(request, params)
        if str(getattr(request, "decision_type", "") or "") != DECISION_DECLARE_SHOTS:
            return True
        params = dict(payload or {})
        action = str(params.get("action", "") or "").strip().lower()
        if action in {"pass", "skip"} or bool(params.get("skip", False)) or bool(params.get("skipped", False)):
            return True
        declarations = params.get("declarations")
        return isinstance(declarations, list) and bool(declarations)

    @classmethod
    def _candidate_passes_current_game_precheck(
        cls,
        game: object | None,
        request: DecisionRequest,
        option_id: str,
    ) -> bool:
        decision_type = str(getattr(request, "decision_type", "") or "")
        if decision_type == DECISION_ATTACH_LEADER:
            return cls._leader_attachment_option_is_currently_valid(game, request, option_id)
        if decision_type == DECISION_ATTACH_SUPPORT_ARTILLERY:
            return cls._support_attachment_option_is_currently_valid(game, request, option_id)
        if decision_type == DECISION_ASSIGN_TRANSPORT:
            return cls._transport_assignment_option_is_currently_valid(game, request, option_id)
        if decision_type == DECISION_SELECT_UNIT:
            return cls._select_unit_option_is_currently_valid(game, request, option_id)
        return True

    @classmethod
    def _select_unit_option_is_currently_valid(
        cls,
        game: object | None,
        request: DecisionRequest,
        option_id: str,
    ) -> bool:
        payload = cls._option_payload(request, option_id)
        action = str(payload.get("action", "") or "").strip().lower()
        if action in {"pass", "skip"} or bool(payload.get("skip", False)) or bool(payload.get("skipped", False)):
            return True

        ctx = dict(getattr(request, "context", {}) or {})
        phase_name = str(ctx.get("phase_name", "") or "").strip().upper()
        phase_step = str(ctx.get("phase_step", "") or "").strip().upper()
        selection_purpose = str(ctx.get("selection_purpose", "") or "").strip().upper()
        if (
            phase_name == "SHOOTING_PHASE"
            and phase_step == "SHOOT_UNITS"
            and selection_purpose == "ACTIVATE_SHOOTING_UNIT"
        ):
            unit_id = str(payload.get("unit_id", "") or "").strip()
            if not unit_id:
                return False
            declarations = cls._default_shooting_declarations(game, request, {"unit_id": unit_id})
            return bool(declarations)

        return True

    @classmethod
    def _leader_attachment_option_is_currently_valid(
        cls,
        game: object | None,
        request: DecisionRequest,
        option_id: str,
    ) -> bool:
        payload = cls._option_payload(request, option_id)
        leader_id = str(payload.get("leader_id", "") or "")
        if not leader_id:
            return False
        leader = cls._resolve_unit(game, leader_id)
        if leader is None or not bool(getattr(leader, "is_leader", False)):
            return False
        bodyguard_id = payload.get("bodyguard_id")
        if bodyguard_id is None:
            return True
        bodyguard = cls._resolve_unit(game, str(bodyguard_id or ""))
        if bodyguard is None:
            return False
        can_attach = getattr(leader, "can_attach_to", None)
        if not callable(can_attach):
            return False
        try:
            return bool(can_attach(bodyguard))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return False

    @classmethod
    def _support_attachment_option_is_currently_valid(
        cls,
        game: object | None,
        request: DecisionRequest,
        option_id: str,
    ) -> bool:
        payload = cls._option_payload(request, option_id)
        support_id = str(payload.get("support_unit_id", "") or "")
        if not support_id:
            return False
        support = cls._resolve_unit(game, support_id)
        has_support = getattr(support, "has_joined_support_ability", None) if support is not None else None
        if support is None or not callable(has_support):
            return False
        try:
            if not bool(has_support()):
                return False
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return False
        bodyguard_id = payload.get("bodyguard_id")
        if bodyguard_id is None:
            requires_attach = getattr(support, "joined_support_requires_attachment", None)
            if not callable(requires_attach):
                return True
            try:
                return not bool(requires_attach())
            except (AttributeError, RuntimeError, TypeError, ValueError):
                return False
        bodyguard = cls._resolve_unit(game, str(bodyguard_id or ""))
        if bodyguard is None:
            return False
        can_join = getattr(support, "can_join_support_artillery", None)
        if not callable(can_join):
            return False
        try:
            return bool(can_join(bodyguard))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return False

    @classmethod
    def _transport_assignment_option_is_currently_valid(
        cls,
        game: object | None,
        request: DecisionRequest,
        option_id: str,
    ) -> bool:
        payload = cls._option_payload(request, option_id)
        unit_id = str(payload.get("unit_id", "") or "")
        if not unit_id:
            return False
        unit = cls._resolve_unit(game, unit_id)
        if unit is None:
            return False
        transport_id = payload.get("transport_id")
        if transport_id is None:
            return True
        transport = cls._resolve_unit(game, str(transport_id or ""))
        if transport is None or not bool(getattr(transport, "is_transport", False)):
            return False
        can_transport = getattr(transport, "can_transport", None)
        if not callable(can_transport):
            return False
        try:
            return bool(can_transport(unit))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return False

    def _candidate_is_structurally_resolvable(self, request: DecisionRequest, candidate: CandidateAction | None) -> bool:
        if candidate is None:
            return False
        params = dict(getattr(candidate, "params", {}) or {})
        action = str(params.get("action", "") or "").strip().lower()
        if action in {"pass", "skip"} or bool(params.get("skip", False)) or bool(params.get("skipped", False)):
            return True
        if str(getattr(request, "decision_type", "") or "") == DECISION_MOVE_UNIT:
            model_positions = params.get("model_positions")
            if isinstance(model_positions, list) and bool(model_positions):
                return True
            return self._move_request_can_synthesize_positions(request, params)
        if str(getattr(request, "decision_type", "") or "") == DECISION_DECLARE_SHOTS:
            declarations = params.get("declarations")
            if isinstance(declarations, list) and bool(declarations):
                return True
            return action == "confirm"
        return True

    @staticmethod
    def _command_metadata_for_candidate(candidate: CandidateAction | None, *, strategy: str) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "controller": "headless_policy",
            "resolution_strategy": str(strategy or ""),
        }
        if candidate is None:
            return metadata
        candidate_metadata = dict(getattr(candidate, "metadata", {}) or {})
        candidate_action_id = str(getattr(candidate, "action_id", "") or "")
        if candidate_action_id:
            metadata["candidate_action_id"] = candidate_action_id
        candidate_kind = str(candidate_metadata.get("candidate_kind", "") or "").strip()
        if candidate_kind:
            metadata["candidate_kind"] = candidate_kind
        candidate_source = str(candidate_metadata.get("source", "") or "").strip()
        if candidate_source:
            metadata["candidate_source"] = candidate_source
        return metadata

    @staticmethod
    def _candidate_for_action_id(request: DecisionRequest, action_id: str) -> CandidateAction | None:
        if not action_id:
            return None
        for candidate in list(getattr(request, "candidates", []) or []):
            if str(getattr(candidate, "action_id", "") or "") == action_id:
                return candidate
        return None

    def _try_resolve_reserves_arrival_bruteforce(self, game: object, request: DecisionRequest) -> bool:
        if str(getattr(request, "decision_type", "") or "") != DECISION_MOVE_UNIT:
            return False
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("placement_kind", "") or "") not in {
            "reserves_arrival",
            "hyperphasic_recall",
            "subterranean_tunnel_network",
        }:
            return False

        options = list(getattr(request, "options", []) or [])
        confirm_option_id = ""
        skip_option_id = ""
        confirm_action_id = ""
        skip_is_forced_arrival_failure = False
        for option in options:
            option_id = str(getattr(option, "option_id", "") or "")
            if not option_id:
                continue
            payload = dict(getattr(option, "payload", {}) or {})
            if str(payload.get("action", "") or "").strip().lower() == "skip":
                skip_option_id = option_id
                skip_is_forced_arrival_failure = bool(
                    payload.get("forced_arrival_failed", False)
                    or payload.get("forced_arrival_failure", False)
                )
            else:
                confirm_option_id = option_id
                confirm_action_id = request.action_id_for_option_id(option_id)
        if not confirm_option_id:
            return False
        confirm_option_payload = self._option_payload(request, confirm_option_id)

        unit_id = str(context.get("unit_id", "") or "")
        unit = self._resolve_unit_by_id(game, unit_id)
        if unit is None:
            return False

        boundary_repulsors = self._reserve_boundary_repulsors(game, unit)
        search_context = self._build_reserves_search_context(
            game,
            unit,
            boundary_repulsors=boundary_repulsors,
        )
        started = time.perf_counter()
        deadline = started + float(self._max_reserves_arrival_seconds)
        metric = self._new_reserves_metric(game, unit, context=context)
        attempted = 0
        try:
            anchor_groups = self._reserves_arrival_anchor_candidate_groups(game, unit, context=context)
        except TypeError:
            anchor_groups = [("fallback", self._reserves_arrival_anchor_points(game, unit))]
        consumed = 0
        seen: set[tuple[float, float]] = set()
        for source, anchors in list(anchor_groups or []):
            if str(source or "").endswith("exhaustive"):
                metric["exhaustive_fallback_used"] = True
            for x, y in list(anchors or []):
                now = time.perf_counter()
                if now >= deadline:
                    break
                metric["anchor_attempts"] = int(metric.get("anchor_attempts", 0) or 0) + 1
                self._bump_metric_counter(metric, "source_attempt_counts", str(source))
                key = (round(float(x), 3), round(float(y), 3))
                if key in seen:
                    continue
                seen.add(key)
                if self._quick_reject_reserves_anchor(game, unit, x=float(x), y=float(y), _context=context):
                    metric["quick_rejects"] = int(metric.get("quick_rejects", 0) or 0) + 1
                    self._bump_metric_counter(metric, "source_quick_rejects", str(source))
                    continue
                attempted += 1
                consumed += 1
                metric["build_calls"] = int(metric.get("build_calls", 0) or 0) + 1
                self._bump_metric_counter(metric, "source_build_calls", str(source))
                model_positions = call_with_supported_kwargs(
                    self._build_model_positions_from_anchor,
                    game,
                    unit,
                    x=float(x),
                    y=float(y),
                    search_context=search_context,
                )
                if not model_positions:
                    continue
                validation_errors = validate_move_unit_payload(
                    game,
                    request,
                    option_payload=confirm_option_payload,
                    result_payload={"model_positions": model_positions},
                )
                if validation_errors:
                    metric["validation_rejects"] = int(metric.get("validation_rejects", 0) or 0) + 1
                    self._bump_metric_counter(metric, "source_validation_rejects", str(source))
                    continue
                metric["resolve_attempts"] = int(metric.get("resolve_attempts", 0) or 0) + 1
                command_count_before = self._speculative_command_count(game)
                apply_result = self._safe_resolve_decision_command(
                    game,
                    request,
                    confirm_option_id,
                    result_payload={"model_positions": model_positions},
                    player_id=getattr(request, "player_id", None),
                    metadata={
                        "controller": "headless_policy",
                        "resolution_strategy": "reserves_arrival_bruteforce",
                        "candidate_action_id": str(confirm_action_id or ""),
                        "candidate_kind": "reserves_arrival_bruteforce",
                    },
                )
                if apply_result is not None and bool(getattr(apply_result, "ok", False)):
                    metric["consumed_anchor_count"] = int(consumed)
                    metric["returned_candidate_count"] = 1
                    metric["first_valid_source"] = str(source or "")
                    if metric.get("calls_to_first_valid") is None:
                        metric["calls_to_first_valid"] = int(metric.get("build_calls", 0) or 0)
                    metric["elapsed_ms"] = int(round((time.perf_counter() - started) * 1000.0))
                    self._record_reserves_metric(metric)
                    return True
                self._discard_failed_speculative_command(game, command_count_before)
            if time.perf_counter() >= deadline:
                break

        timed_out = bool(time.perf_counter() >= deadline)
        failure_reason = "timed_out" if timed_out else "no_valid_arrival_position"
        metric["timed_out"] = bool(timed_out)
        if timed_out:
            logger.warning(
                "Headless reserves-arrival search timed out for unit %s after %.2fs (%d anchors attempted).",
                unit_id,
                float(time.perf_counter() - started),
                int(attempted),
            )

        allow_skip = bool(context.get("allow_skip", True))
        if skip_option_id and (allow_skip or skip_is_forced_arrival_failure):
            apply_result = self._safe_resolve_decision_command(
                game,
                request,
                skip_option_id,
                result_payload={
                    "skipped": True,
                    "forced_arrival_failed": bool(skip_is_forced_arrival_failure),
                },
                player_id=getattr(request, "player_id", None),
            )
            metric["skipped"] = bool(apply_result is not None and getattr(apply_result, "ok", False))
            metric["forced_arrival_failed"] = bool(skip_is_forced_arrival_failure)
            metric["consumed_anchor_count"] = int(consumed)
            metric["returned_candidate_count"] = 0
            metric["elapsed_ms"] = int(round((time.perf_counter() - started) * 1000.0))
            metric["failure_reason"] = "forced_arrival_failed" if skip_is_forced_arrival_failure else failure_reason
            self._record_reserves_arrival_failure(unit, reason=str(metric["failure_reason"]), metric=metric)
            self._record_reserves_metric(metric)
            return bool(apply_result is not None and getattr(apply_result, "ok", False))
        if timed_out and skip_option_id:
            apply_result = self._safe_resolve_decision_command(
                game,
                request,
                skip_option_id,
                result_payload={"skipped": True},
                player_id=getattr(request, "player_id", None),
            )
            metric["skipped"] = bool(apply_result is not None and getattr(apply_result, "ok", False))
            metric["consumed_anchor_count"] = int(consumed)
            metric["returned_candidate_count"] = 0
            metric["elapsed_ms"] = int(round((time.perf_counter() - started) * 1000.0))
            metric["failure_reason"] = failure_reason
            self._record_reserves_arrival_failure(unit, reason=failure_reason, metric=metric)
            self._record_reserves_metric(metric)
            if apply_result is not None and bool(getattr(apply_result, "ok", False)):
                return True
        metric["timed_out"] = bool(timed_out)
        metric["consumed_anchor_count"] = int(consumed)
        metric["returned_candidate_count"] = 0
        metric["elapsed_ms"] = int(round((time.perf_counter() - started) * 1000.0))
        metric["failure_reason"] = failure_reason
        self._record_reserves_arrival_failure(unit, reason=failure_reason, metric=metric)
        self._record_reserves_metric(metric)
        return False

    def get_reserves_arrival_search_metrics(self) -> list[dict[str, object]]:
        return [dict(entry or {}) for entry in list(self._reserves_arrival_search_metrics or [])]

    def reset_reserves_arrival_search_metrics(self) -> None:
        self._reserves_arrival_search_metrics.clear()

    def _reserve_boundary_repulsors(self, game: object, unit: object) -> list[object]:
        repulsor_fn = getattr(game, "get_boundary_repulsors", None)
        if callable(repulsor_fn):
            return list(repulsor_fn(unit, context="reserves_arrival") or [])
        game_map = getattr(game, "map", None)
        get_repulsors = getattr(game_map, "get_battlefield_edge_repulsors", None)
        if callable(get_repulsors):
            return list(get_repulsors() or [])
        return []

    def _build_reserves_search_context(
        self,
        game: object,
        unit: object,
        *,
        boundary_repulsors: list[object],
    ) -> object | None:
        game_map = getattr(game, "map", None)
        if game_map is None:
            return None
        return build_placement_search_context(
            unit,
            game_map,
            avoid_friendly_units=False,
            boundary_repulsors=boundary_repulsors,
        )

    def _new_reserves_metric(self, game: object, unit: object, *, context: dict[str, object]) -> dict[str, object]:
        footprint = estimate_unit_pack_footprint(unit)
        in_strategic_attr = getattr(unit, "is_in_strategic_reserves", None)
        in_strategic = bool(in_strategic_attr()) if callable(in_strategic_attr) else bool(in_strategic_attr)
        return {
            "unit_id": str(get_entity_id(unit) or ""),
            "unit_name": str(getattr(unit, "name", "") or "Unit"),
            "placement_kind": str(context.get("placement_kind", "") or ""),
            "in_strategic_reserves": bool(in_strategic),
            "max_anchor_points": int(self._max_reserves_anchor_points),
            "anchor_attempts": 0,
            "quick_rejects": 0,
            "build_calls": 0,
            "validation_rejects": 0,
            "resolve_attempts": 0,
            "calls_to_first_valid": None,
            "first_valid_source": "",
            "returned_candidate_count": 0,
            "consumed_anchor_count": 0,
            "source_attempt_counts": {},
            "source_quick_rejects": {},
            "source_build_calls": {},
            "source_validation_rejects": {},
            "exhaustive_fallback_used": False,
            "footprint_width": float(footprint["width"]),
            "footprint_depth": float(footprint["depth"]),
            "footprint_radius": float(footprint["radius"]),
            "board_width": float(self._board_dimensions(game)[0]),
            "board_height": float(self._board_dimensions(game)[1]),
        }

    @staticmethod
    def _bump_metric_counter(metric: dict[str, object], key: str, source: str) -> None:
        counters = dict(metric.get(key, {}) or {})
        counters[str(source or "unknown")] = int(counters.get(str(source or "unknown"), 0) or 0) + 1
        metric[key] = counters

    def _record_reserves_metric(self, metric: dict[str, object]) -> None:
        self._reserves_arrival_search_metrics.append(dict(metric or {}))

    @staticmethod
    def _speculative_command_count(game: object) -> int | None:
        commands = getattr(game, "commands", None)
        if not isinstance(commands, list):
            return None
        return int(len(commands))

    @staticmethod
    def _discard_failed_speculative_command(game: object, command_count_before: int | None) -> None:
        if command_count_before is None:
            return
        commands = getattr(game, "commands", None)
        if not isinstance(commands, list):
            return
        while len(commands) > int(command_count_before):
            commands.pop()

    @staticmethod
    def _record_reserves_arrival_failure(unit: object, *, reason: str, metric: dict[str, object]) -> None:
        reason_text = str(reason or "no_valid_arrival_position").strip() or "no_valid_arrival_position"
        payload = {
            "reason": reason_text,
            "anchor_attempts": int(metric.get("anchor_attempts", 0) or 0),
            "build_calls": int(metric.get("build_calls", 0) or 0),
            "validation_rejects": int(metric.get("validation_rejects", 0) or 0),
            "quick_rejects": int(metric.get("quick_rejects", 0) or 0),
            "timed_out": bool(metric.get("timed_out", False)),
            "elapsed_ms": int(metric.get("elapsed_ms", 0) or 0),
        }
        special_rules = getattr(unit, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        special_rules["reserve_last_arrival_failure"] = dict(payload)
        unit.special_rules = special_rules
        setattr(unit, "reserve_last_arrival_failure", dict(payload))

    @staticmethod
    def _normalize_reserve_policy(value: str) -> str:
        policy = str(value or "").strip().lower()
        if policy in {"forced_only", "balanced"}:
            return policy
        raise ValueError(f"Unknown reserve policy: {value!r}. Expected 'forced_only' or 'balanced'.")

    @staticmethod
    def _should_skip_request(request: DecisionRequest) -> bool:
        decision_type = str(getattr(request, "decision_type", "") or "")
        if decision_type in _DRIVER_MANAGED_DECISION_TYPES:
            return True
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("decision_owner", "") or "").strip().lower() != "deployment_manager":
            return False
        if decision_type in {
            DECISION_CHOOSE_DEPLOYMENT_ZONE,
            DECISION_DECLARE_RESERVES,
            DECISION_SELECT_NEXT_DEPLOY_UNIT,
        }:
            return True
        if decision_type != DECISION_MOVE_UNIT:
            return False
        return str(context.get("placement_kind", "") or "").strip().lower() == "deployment"

    def _resolve_unit_by_id(self, game: object, unit_id: str) -> object | None:
        if not unit_id:
            return None
        resolver = getattr(game, "_resolve_unit_by_id", None)
        if callable(resolver):
            unit = resolver(unit_id)
            if unit is not None:
                return unit
        for player in list(getattr(game, "players", []) or []):
            army = getattr(player, "army", None)
            if army is None:
                get_army = getattr(player, "get_army", None)
                army = get_army() if callable(get_army) else None
            for unit in list(getattr(army, "units", []) or []):
                if str(get_entity_id(unit) or "") == str(unit_id):
                    return unit
        return None

    def _reserves_arrival_anchor_points(
        self,
        game: object,
        unit: object,
        *,
        context: dict | None = None,
    ) -> list[tuple[float, float]]:
        groups = self._reserves_arrival_anchor_candidate_groups(game, unit, context=context)
        points: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        max_points = int(self._max_reserves_anchor_points)
        for _source, anchors in list(groups or []):
            for x, y in list(anchors or []):
                key = (round(float(x), 3), round(float(y), 3))
                if key in seen:
                    continue
                seen.add(key)
                points.append((float(x), float(y)))
                if max_points > 0 and len(points) >= max_points:
                    return points
        return points

    def _reserves_arrival_anchor_candidate_groups(
        self,
        game: object,
        unit: object,
        *,
        context: dict | None = None,
    ) -> list[tuple[str, list[tuple[float, float]]]]:
        width, height = self._board_dimensions(game)
        ctx = dict(context or {})
        groups: list[tuple[str, list[tuple[float, float]]]] = []

        anchor_ring = self._anchor_unit_ring_points(game, context=ctx)
        if anchor_ring:
            groups.append(("anchor_ring", anchor_ring))

        tunnel_ring = self._tunnel_marker_ring_points(unit, context=ctx)
        if tunnel_ring:
            groups.append(("tunnel_marker_ring", tunnel_ring))

        in_strategic_fn = getattr(unit, "is_in_strategic_reserves", None)
        in_strategic = bool(in_strategic_fn()) if callable(in_strategic_fn) else False
        if in_strategic:
            strategic_edge_groups = list(self._strategic_edge_anchor_groups(unit, width=width, height=height) or [])
            if strategic_edge_groups:
                groups.append(strategic_edge_groups[0])
            groups.extend(
                self._reserves_zone_anchor_candidate_groups(
                    game,
                    unit,
                    context=ctx,
                    width=width,
                    height=height,
                )
            )
            groups.extend(strategic_edge_groups[1:])
            if self._strategic_reserves_can_use_gap_search(ctx, unit):
                gap_points = self._reserves_gap_anchor_points(game, unit, context=ctx)
                if gap_points:
                    groups.append(("gap_openings", gap_points))
                groups.extend(self._deep_strike_scan_anchor_groups(unit, width=width, height=height))
        else:
            groups.append(("board_landmarks", self._board_landmark_anchor_points(width=width, height=height)))
            groups.extend(
                self._reserves_zone_anchor_candidate_groups(
                    game,
                    unit,
                    context=ctx,
                    width=width,
                    height=height,
                )
            )
            gap_points = self._reserves_gap_anchor_points(game, unit, context=ctx)
            if gap_points:
                groups.append(("gap_openings", gap_points))
            groups.extend(self._deep_strike_scan_anchor_groups(unit, width=width, height=height))

        trimmed: list[tuple[str, list[tuple[float, float]]]] = []
        consumed = 0
        seen: set[tuple[float, float]] = set()
        for source, anchors in list(groups or []):
            deduped: list[tuple[float, float]] = []
            for x, y in list(anchors or []):
                key = (round(float(x), 3), round(float(y), 3))
                if key in seen:
                    continue
                seen.add(key)
                deduped.append((float(x), float(y)))
                consumed += 1
                if consumed >= int(self._max_reserves_anchor_points):
                    break
            if deduped:
                trimmed.append((str(source or ""), deduped))
            if consumed >= int(self._max_reserves_anchor_points):
                break
        return trimmed

    def _reserves_zone_anchor_candidate_groups(
        self,
        game: object,
        unit: object,
        *,
        context: dict[str, object],
        width: float,
        height: float,
    ) -> list[tuple[str, list[tuple[float, float]]]]:
        footprint = estimate_unit_pack_footprint(unit)
        occupied_units = list(self._iter_deployed_units(game, exclude_unit=unit) or [])
        zone_sets = self._reserves_zone_heuristic_zones(
            game,
            unit,
            context=context,
            width=width,
            height=height,
            footprint=footprint,
        )
        default_bounds = (0.0, float(width), 0.0, float(height))
        occupied_count = int(len(occupied_units))
        unit_id = str(get_entity_id(unit) or "")
        groups: list[tuple[str, list[tuple[float, float]]]] = []

        for zone_name, zone in list(zone_sets.get("gap", []) or []):
            anchors = _gap_anchor_candidates_shared(
                zone,
                occupied_units=occupied_units,
                footprint=footprint,
                default_bounds=default_bounds,
            )
            if anchors:
                groups.append((f"zone_packer_gap:{zone_name}", anchors))

        for zone_name, zone in list(zone_sets.get("rows", []) or []):
            anchors = _packing_row_anchor_candidates_shared(
                zone,
                board_width=float(width),
                board_height=float(height),
                footprint=footprint,
                lattice_step=2.0,
                default_bounds=default_bounds,
            )
            if anchors:
                groups.append((f"zone_packer_rows:{zone_name}", anchors))

        for zone_name, zone in list(zone_sets.get("lattice", []) or []):
            anchors = _lattice_candidate_positions_shared(
                zone,
                unit_id=unit_id,
                occupied_count=occupied_count,
                lattice_step=2.0,
                default_bounds=default_bounds,
            )
            if anchors:
                groups.append((f"zone_lattice:{zone_name}", anchors))

        for zone_name, zone in list(zone_sets.get("exhaustive", []) or []):
            anchors = _exhaustive_lattice_candidate_positions_shared(
                zone,
                unit_id=unit_id,
                exhaustive_lattice_step=1.0,
                exhaustive_anchor_limit=int(self._reserves_exhaustive_anchor_limit),
                default_bounds=default_bounds,
            )
            if anchors:
                groups.append((f"zone_lattice_exhaustive:{zone_name}", anchors))
        return groups

    def _reserves_zone_heuristic_zones(
        self,
        game: object,
        unit: object,
        *,
        context: dict[str, object],
        width: float,
        height: float,
        footprint: dict[str, float],
    ) -> dict[str, list[tuple[str, dict[str, object]]]]:
        in_strategic_fn = getattr(unit, "is_in_strategic_reserves", None)
        in_strategic = bool(in_strategic_fn()) if callable(in_strategic_fn) else False
        if not in_strategic:
            return self._deep_strike_zone_heuristic_zones(width=width, height=height)

        strategic = self._strategic_edge_zone_heuristic_zones(
            game,
            unit,
            context=context,
            width=width,
            height=height,
            footprint=footprint,
        )
        if not self._strategic_reserves_can_use_gap_search(context, unit):
            return strategic

        deep_strike = self._deep_strike_zone_heuristic_zones(width=width, height=height)
        merged: dict[str, list[tuple[str, dict[str, object]]]] = {}
        for key in ("gap", "rows", "lattice", "exhaustive"):
            merged[key] = list(strategic.get(key, []) or []) + [
                (f"deep_strike_{name}", dict(zone or {}))
                for name, zone in list(deep_strike.get(key, []) or [])
            ]
        return merged

    @staticmethod
    def _deep_strike_zone_heuristic_zones(
        *,
        width: float,
        height: float,
    ) -> dict[str, list[tuple[str, dict[str, object]]]]:
        battlefield_zone = {
            "name": "battlefield",
            "x_range": [0.0, float(width)],
            "y_range": [0.0, float(height)],
        }
        mid_x = float(width) * 0.5
        mid_y = float(height) * 0.5
        row_zones = [
            (
                "own_half",
                {
                    "name": "own_half",
                    "x_range": [0.0, float(width)],
                    "y_range": [0.0, mid_y],
                    "forward_axis": "y",
                    "forward_positive": True,
                },
            ),
            (
                "enemy_half",
                {
                    "name": "enemy_half",
                    "x_range": [0.0, float(width)],
                    "y_range": [mid_y, float(height)],
                    "forward_axis": "y",
                    "forward_positive": False,
                },
            ),
            (
                "left_half",
                {
                    "name": "left_half",
                    "x_range": [0.0, mid_x],
                    "y_range": [0.0, float(height)],
                    "forward_axis": "x",
                    "forward_positive": True,
                },
            ),
            (
                "right_half",
                {
                    "name": "right_half",
                    "x_range": [mid_x, float(width)],
                    "y_range": [0.0, float(height)],
                    "forward_axis": "x",
                    "forward_positive": False,
                },
            ),
        ]
        return {
            "gap": [("battlefield", dict(battlefield_zone))],
            "rows": row_zones,
            "lattice": [("battlefield", dict(battlefield_zone))],
            "exhaustive": [],
        }

    def _strategic_edge_zone_heuristic_zones(
        self,
        game: object,
        unit: object,
        *,
        context: dict[str, object],
        width: float,
        height: float,
        footprint: dict[str, float],
    ) -> dict[str, list[tuple[str, dict[str, object]]]]:
        del context
        band = max(6.0, min(max(float(width), float(height)), 8.0 + float(footprint["radius"])))
        zones: list[tuple[str, dict[str, object]]] = []
        for edge in self._strategic_reserves_search_edges(game, unit):
            if edge == "own":
                zone = {
                    "name": "edge_own",
                    "x_range": [0.0, float(width)],
                    "y_range": [0.0, min(float(height), float(band))],
                    "forward_axis": "y",
                    "forward_positive": True,
                }
            elif edge == "enemy":
                zone = {
                    "name": "edge_enemy",
                    "x_range": [0.0, float(width)],
                    "y_range": [max(0.0, float(height) - float(band)), float(height)],
                    "forward_axis": "y",
                    "forward_positive": False,
                }
            elif edge == "left":
                zone = {
                    "name": "edge_left",
                    "x_range": [0.0, min(float(width), float(band))],
                    "y_range": [0.0, float(height)],
                    "forward_axis": "x",
                    "forward_positive": True,
                }
            else:
                zone = {
                    "name": "edge_right",
                    "x_range": [max(0.0, float(width) - float(band)), float(width)],
                    "y_range": [0.0, float(height)],
                    "forward_axis": "x",
                    "forward_positive": False,
                }
            zones.append((str(zone["name"]), zone))
        return {
            "gap": list(zones),
            "rows": list(zones),
            "lattice": [],
            "exhaustive": [],
        }

    def _strategic_reserves_search_edges(self, game: object, unit: object) -> list[str]:
        try:
            effective_turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            effective_turn = 0
        strategic_setup_turn = getattr(unit, "get_strategic_reserves_setup_turn", None)
        if callable(strategic_setup_turn):
            try:
                effective_turn = int(strategic_setup_turn(game=game, current_turn=effective_turn))
            except (TypeError, ValueError):
                pass

        valid_edges: list[str] = []
        checker = getattr(game, "is_valid_strategic_reserves_edge", None)
        for edge in list(_strategic_reserves_edges()):
            if callable(checker):
                try:
                    if not bool(checker(edge, turn=effective_turn)):
                        continue
                except (TypeError, ValueError):
                    continue
            elif not _is_valid_strategic_reserves_edge(game, edge, turn=effective_turn):
                continue
            if edge == "enemy" and effective_turn == 2 and not masters_of_void_enemy_dz_override_active(unit, game):
                continue
            valid_edges.append(str(edge))
        return valid_edges

    def _anchor_unit_ring_points(self, game: object, *, context: dict[str, object]) -> list[tuple[float, float]]:
        anchor_unit_id = str(context.get("reserves_arrival_anchor_unit_id", "") or "").strip()
        anchor_range_raw = context.get("reserves_arrival_anchor_range", 0.0)
        try:
            anchor_range = float(anchor_range_raw) if anchor_range_raw is not None else 0.0
        except (TypeError, ValueError):
            anchor_range = 0.0
        if not anchor_unit_id or anchor_range <= 0.0:
            return []
        anchor_unit = self._resolve_unit_by_id(game, anchor_unit_id)
        if anchor_unit is None:
            return []
        get_root = getattr(anchor_unit, "get_attached_unit_root", None)
        anchor_root = get_root() if callable(get_root) else anchor_unit
        anchor_positions: list[tuple[float, float]] = []
        for model in list(getattr(anchor_root, "models", []) or []):
            if not getattr(model, "is_alive", True):
                continue
            get_location = getattr(model, "get_location", None)
            if not callable(get_location):
                continue
            loc = get_location()
            if isinstance(loc, (tuple, list)) and len(loc) >= 2:
                anchor_positions.append((float(loc[0]), float(loc[1])))
        if not anchor_positions:
            anchor_pos = getattr(anchor_root, "position", None)
            if isinstance(anchor_pos, (tuple, list)) and len(anchor_pos) >= 2:
                anchor_positions.append((float(anchor_pos[0]), float(anchor_pos[1])))
        points: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        radii = (
            0.0,
            max(0.5, float(anchor_range) * 0.33),
            max(0.5, float(anchor_range) * 0.66),
            float(anchor_range),
        )
        for ax, ay in list(anchor_positions or []):
            for radius in radii:
                for deg in range(0, 360, 45):
                    rad = math.radians(float(deg))
                    x = float(ax + math.cos(rad) * float(radius))
                    y = float(ay + math.sin(rad) * float(radius))
                    key = (round(x, 3), round(y, 3))
                    if key in seen:
                        continue
                    seen.add(key)
                    points.append((x, y))
        points.sort(
            key=lambda point: (
                min((point[0] - ax) ** 2 + (point[1] - ay) ** 2 for ax, ay in anchor_positions),
                hashlib.sha256(f"anchor:{point[0]:.3f}:{point[1]:.3f}".encode("utf-8")).hexdigest(),
            )
        )
        return points

    def _tunnel_marker_ring_points(self, unit: object, *, context: dict[str, object]) -> list[tuple[float, float]]:
        tunnel_allowed_ids = {
            str(item or "").strip()
            for item in list(context.get("tunnel_marker_allowed_ids") or [])
            if str(item or "").strip()
        }
        tunnel_excluded_ids = {
            str(item or "").strip()
            for item in list(context.get("tunnel_marker_excluded_ids") or [])
            if str(item or "").strip()
        }
        army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
        tyr_mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
        get_markers = getattr(tyr_mgr, "get_active_tunnel_markers", None) if tyr_mgr is not None else None
        if not callable(get_markers):
            return []
        points: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        for marker in list(get_markers() or []):
            marker_id = str(getattr(marker, "marker_id", "") or "").strip()
            if tunnel_allowed_ids and marker_id not in tunnel_allowed_ids:
                continue
            if tunnel_excluded_ids and marker_id in tunnel_excluded_ids:
                continue
            mx = float(getattr(marker, "x", 0.0) or 0.0)
            my = float(getattr(marker, "y", 0.0) or 0.0)
            for radius in (0.0, 3.0, 6.0, 9.0):
                for deg in range(0, 360, 45):
                    rad = math.radians(float(deg))
                    x = float(mx + math.cos(rad) * float(radius))
                    y = float(my + math.sin(rad) * float(radius))
                    key = (round(x, 3), round(y, 3))
                    if key in seen:
                        continue
                    seen.add(key)
                    points.append((x, y))
        return points

    @staticmethod
    def _board_landmark_anchor_points(*, width: float, height: float) -> list[tuple[float, float]]:
        quarter_x = float(width) * 0.25
        quarter_y = float(height) * 0.25
        return [
            (float(width) * 0.5, float(height) * 0.5),
            (quarter_x, quarter_y),
            (quarter_x, float(height) - quarter_y),
            (float(width) - quarter_x, quarter_y),
            (float(width) - quarter_x, float(height) - quarter_y),
            (quarter_x, float(height) * 0.5),
            (float(width) - quarter_x, float(height) * 0.5),
            (float(width) * 0.5, quarter_y),
            (float(width) * 0.5, float(height) - quarter_y),
        ]

    def _reserves_gap_anchor_points(
        self,
        game: object,
        unit: object,
        *,
        context: dict[str, object],
    ) -> list[tuple[float, float]]:
        width, height = self._board_dimensions(game)
        footprint = estimate_unit_pack_footprint(unit)
        required_enemy_distance = self._reserves_min_enemy_distance_hint(game, context=context)
        clearance = max(1.0, float(footprint["largest_radius"]) + float(required_enemy_distance) * 0.35)
        points: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()

        def _add(x: float, y: float) -> None:
            clamped_x = float(max(0.0, min(float(width), float(x))))
            clamped_y = float(max(0.0, min(float(height), float(y))))
            key = (round(clamped_x, 3), round(clamped_y, 3))
            if key in seen:
                return
            seen.add(key)
            points.append((clamped_x, clamped_y))

        for candidate in list(self._iter_deployed_units(game, exclude_unit=unit) or []):
            bounds = deployed_unit_bounds(candidate)
            if bounds is None:
                continue
            bx0, by0, bx1, by1 = bounds
            cx = (float(bx0) + float(bx1)) * 0.5
            cy = (float(by0) + float(by1)) * 0.5
            options = (
                (float(bx0) - clearance, cy),
                (float(bx1) + clearance, cy),
                (cx, float(by0) - clearance),
                (cx, float(by1) + clearance),
                (float(bx0) - clearance, float(by0) - clearance),
                (float(bx0) - clearance, float(by1) + clearance),
                (float(bx1) + clearance, float(by0) - clearance),
                (float(bx1) + clearance, float(by1) + clearance),
            )
            for x, y in options:
                _add(x, y)
        for x, y in self._board_landmark_anchor_points(width=width, height=height):
            _add(x, y)

        center_x = float(width) * 0.5
        center_y = float(height) * 0.5
        points.sort(
            key=lambda point: (
                -self._gap_clearance_score(game, point),
                (float(point[0]) - center_x) ** 2 + (float(point[1]) - center_y) ** 2,
                hashlib.sha256(f"gap:{point[0]:.3f}:{point[1]:.3f}".encode("utf-8")).hexdigest(),
            )
        )
        return points

    def _strategic_reserves_can_use_gap_search(self, context: dict[str, object], unit: object) -> bool:
        if bool(context.get("reserves_arrival_ignore_battlefield_edge_requirement", False)):
            return True
        has_deep_strike = getattr(unit, "has_deep_strike", None)
        return bool(has_deep_strike()) if callable(has_deep_strike) else False

    def _strategic_edge_anchor_groups(
        self,
        unit: object,
        *,
        width: float,
        height: float,
    ) -> list[tuple[str, list[tuple[float, float]]]]:
        along_step = self._strategic_edge_scan_step(unit, width=width, height=height)
        preferred_offset = self._strategic_edge_offset_preference(unit)
        groups: list[tuple[str, list[tuple[float, float]]]] = []

        primary: list[tuple[float, float]] = []
        edge_touch_dense: list[tuple[float, float]] = []
        staggered: list[tuple[float, float]] = []
        fallback: list[tuple[float, float]] = []
        largest_radius = self._largest_model_radius(unit)
        along_margin = (
            max(0.0, min(width * 0.5, height * 0.5, largest_radius))
            if largest_radius > 3.0
            else 0.0
        )

        def _valid_edge_offsets(raw_offsets: list[float]) -> list[float]:
            if largest_radius <= 0.0:
                return list(raw_offsets or [])
            min_offset = float(largest_radius)
            max_offset = float(largest_radius + 0.25) if largest_radius > 3.0 else float(6.0 - largest_radius)
            filtered = [
                float(value)
                for value in list(raw_offsets or [])
                if float(value) + 1e-6 >= min_offset and float(value) <= max_offset + 1e-6
            ]
            return filtered or [float(preferred_offset)]

        def _edge_band(step: float, offset_values: list[float], *, half_step: bool, out: list[tuple[float, float]]) -> None:
            axis_offset = (step / 2.0) if half_step else 0.0
            xs = self._axis_points(along_margin, width - along_margin, step=step, offset=axis_offset)
            ys = self._axis_points(along_margin, height - along_margin, step=step, offset=axis_offset)
            for edge_offset in list(offset_values or []):
                for x in xs:
                    out.append((float(x), float(edge_offset)))
                    out.append((float(x), max(0.0, float(height) - float(edge_offset))))
                for y in ys:
                    out.append((float(edge_offset), float(y)))
                    out.append((max(0.0, float(width) - float(edge_offset)), float(y)))

        offsets = _valid_edge_offsets(self._strategic_edge_offsets(preferred_offset))
        _edge_band(along_step, offsets[:4], half_step=False, out=primary)
        if largest_radius > 3.0:
            _edge_band(1.0, [float(largest_radius)], half_step=False, out=edge_touch_dense)
            _edge_band(1.0, [float(largest_radius)], half_step=True, out=edge_touch_dense)
        _edge_band(along_step, offsets[:4], half_step=True, out=staggered)
        _edge_band(
            max(1.5, along_step * 1.5),
            _valid_edge_offsets(self._strategic_edge_offsets(0.0)),
            half_step=False,
            out=fallback,
        )
        fallback.extend(
            [
                (0.0, 0.0),
                (0.0, float(height)),
                (float(width), 0.0),
                (float(width), float(height)),
            ]
        )
        groups.append(("strategic_edge_band", primary))
        if edge_touch_dense:
            groups.append(("strategic_edge_touch_dense", edge_touch_dense))
        groups.append(("strategic_edge_staggered", staggered))
        groups.append(("strategic_edge_exhaustive", fallback[: self._reserves_exhaustive_anchor_limit]))
        return groups

    def _deep_strike_scan_anchor_groups(
        self,
        unit: object,
        *,
        width: float,
        height: float,
    ) -> list[tuple[str, list[tuple[float, float]]]]:
        groups: list[tuple[str, list[tuple[float, float]]]] = []
        deep_steps = self._deep_strike_scan_steps(unit)
        labels = ("deep_strike_coarse", "deep_strike_medium", "deep_strike_exhaustive")
        for label, step in zip(labels, deep_steps):
            anchors: list[tuple[float, float]] = []
            xs = self._axis_points(0.0, width, step=step, offset=0.0)
            ys = self._axis_points(0.0, height, step=step, offset=0.0)
            xs_half = self._axis_points(0.0, width, step=step, offset=(step / 2.0))
            ys_half = self._axis_points(0.0, height, step=step, offset=(step / 2.0))
            for y in ys:
                for x in xs:
                    anchors.append((float(x), float(y)))
            for y in ys_half:
                for x in xs_half:
                    anchors.append((float(x), float(y)))
            if str(label).endswith("exhaustive"):
                anchors = anchors[: self._reserves_exhaustive_anchor_limit]
            groups.append((str(label), anchors))
        return groups

    def _iter_deployed_units(self, game: object, *, exclude_unit: object | None = None) -> list[object]:
        units: list[object] = []
        for player in list(getattr(game, "players", []) or []):
            army = getattr(player, "army", None)
            get_army = getattr(player, "get_army", None)
            if army is None and callable(get_army):
                army = get_army()
            for unit in list(getattr(army, "units", []) or []):
                if unit is None or unit is exclude_unit:
                    continue
                is_alive = getattr(unit, "is_alive", None)
                if callable(is_alive) and not bool(is_alive()):
                    continue
                if getattr(unit, "deployed", True) is False:
                    continue
                if str(getattr(unit, "reserve_status", "deployed") or "deployed") != "deployed":
                    continue
                if getattr(unit, "embarked_in", None) is not None or bool(getattr(unit, "is_embarked", False)):
                    continue
                units.append(unit)
        units.sort(key=lambda candidate: str(get_entity_id(candidate) or ""))
        return units

    def _gap_clearance_score(self, game: object, point: tuple[float, float]) -> float:
        x = float(point[0])
        y = float(point[1])
        bounds_list = [
            bounds
            for bounds in (
                deployed_unit_bounds(unit) for unit in list(self._iter_deployed_units(game) or [])
            )
            if bounds is not None
        ]
        if not bounds_list:
            return 0.0
        clearances = [self._distance_to_bounds(x, y, bounds) for bounds in bounds_list]
        return float(min(clearances))

    @staticmethod
    def _distance_to_bounds(x: float, y: float, bounds: tuple[float, float, float, float]) -> float:
        bx0, by0, bx1, by1 = bounds
        dx = max(float(bx0) - float(x), 0.0, float(x) - float(bx1))
        dy = max(float(by0) - float(y), 0.0, float(y) - float(by1))
        return math.hypot(dx, dy)

    def _reserves_min_enemy_distance_hint(self, game: object, *, context: dict[str, object]) -> float:
        override = context.get("reserves_arrival_min_enemy_distance_override")
        if override is not None:
            try:
                return max(0.0, float(override))
            except (TypeError, ValueError):
                return 0.0
        profile = geometry_profile_for_game(game, context=dict(context or {}))
        return float(getattr(profile, "ingress_exclusion_distance", 9.0) or 9.0)

    def _quick_reject_reserves_anchor(
        self,
        game: object,
        unit: object,
        *,
        x: float,
        y: float,
        _context: dict,
    ) -> bool:
        width, height = self._board_dimensions(game)
        if float(x) < 0.0 or float(x) > float(width):
            return True
        if float(y) < 0.0 or float(y) > float(height):
            return True
        footprint = estimate_unit_pack_footprint(unit)
        if self._context_anchor_range_reject(game, unit, x=float(x), y=float(y), context=dict(_context or {}), footprint=footprint):
            return True
        if self._enemy_distance_envelope_reject(
            game,
            unit=unit,
            x=float(x),
            y=float(y),
            context=dict(_context or {}),
            footprint=footprint,
        ):
            return True
        in_strategic_fn = getattr(unit, "is_in_strategic_reserves", None)
        in_strategic = bool(in_strategic_fn()) if callable(in_strategic_fn) else False
        if not in_strategic:
            return False
        edge_dist = min(float(x), float(y), float(max(0.0, width - x)), float(max(0.0, height - y)))
        max_edge_band = 8.0 + float(footprint["radius"])
        if edge_dist > max_edge_band and not self._strategic_reserves_can_use_gap_search(dict(_context or {}), unit):
            return True
        return False

    def _context_anchor_range_reject(
        self,
        game: object,
        unit: object,
        *,
        x: float,
        y: float,
        context: dict[str, object],
        footprint: dict[str, float],
    ) -> bool:
        anchor_unit_id = str(context.get("reserves_arrival_anchor_unit_id", "") or "").strip()
        anchor_range_raw = context.get("reserves_arrival_anchor_range", 0.0)
        if not anchor_unit_id:
            return False
        try:
            anchor_range = float(anchor_range_raw or 0.0)
        except (TypeError, ValueError):
            return False
        if anchor_range <= 0.0:
            return False
        anchor_unit = self._resolve_unit_by_id(game, anchor_unit_id)
        if anchor_unit is None:
            return False
        bounds = deployed_unit_bounds(anchor_unit)
        if bounds is None:
            return False
        distance = self._distance_to_bounds(float(x), float(y), bounds)
        return bool(distance > float(anchor_range) + float(footprint["radius"]) + 0.5)

    def _enemy_distance_envelope_reject(
        self,
        game: object,
        *,
        unit: object,
        x: float,
        y: float,
        context: dict[str, object],
        footprint: dict[str, float],
    ) -> bool:
        min_enemy_distance = self._reserves_min_enemy_distance_hint(game, context=context)
        if min_enemy_distance <= 0.0 and not bool(context.get("reserves_arrival_require_not_engagement", False)):
            return False
        engagement_horizontal = float(getattr(geometry_profile_for_game(game, context=context), "engagement_range_horizontal", 1.0) or 1.0)
        required_distance = max(float(min_enemy_distance), engagement_horizontal if bool(context.get("reserves_arrival_require_not_engagement", False)) else 0.0)
        clearance = float(required_distance) + float(footprint["largest_radius"])
        for enemy_unit in list(self._iter_enemy_units(game, unit=unit) or []):
            bounds = deployed_unit_bounds(enemy_unit)
            if bounds is None:
                continue
            if self._distance_to_bounds(float(x), float(y), bounds) < clearance:
                return True
        return False

    def _iter_enemy_units(self, game: object, *, unit: object) -> list[object]:
        army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
        player = getattr(army, "player", None) if army is not None else None
        player_id = str(getattr(player, "id", "") or "")
        enemies: list[object] = []
        for candidate in list(self._iter_deployed_units(game, exclude_unit=unit) or []):
            candidate_army = candidate.get_parent_army() if hasattr(candidate, "get_parent_army") else None
            candidate_player = getattr(candidate_army, "player", None) if candidate_army is not None else None
            candidate_player_id = str(getattr(candidate_player, "id", "") or "")
            if player_id and candidate_player_id and candidate_player_id == player_id:
                continue
            enemies.append(candidate)
        return enemies

    @staticmethod
    def _deep_strike_scan_steps(unit: object) -> tuple[float, float, float]:
        largest = HeadlessPolicyDecisionController._largest_model_radius(unit)
        models = int(len(list(getattr(unit, "models", []) or [])) or 1)
        base_step = max(1.5, min(5.0, (largest * 2.0) + (0.2 * models)))
        return (base_step * 2.0, base_step, max(1.0, base_step / 2.0))

    @staticmethod
    def _strategic_edge_scan_step(unit: object, *, width: float, height: float) -> float:
        largest = HeadlessPolicyDecisionController._largest_model_radius(unit)
        models = int(len(list(getattr(unit, "models", []) or [])) or 1)
        unit_span = max(2.0, (largest * 2.0) + (0.4 * models))
        board_min = max(1.0, min(float(width), float(height)))
        return float(max(1.0, min(4.0, min(unit_span, board_min / 8.0))))

    @staticmethod
    def _largest_model_radius(unit: object) -> float:
        largest = 0.0
        for model in list(getattr(unit, "models", []) or []):
            base = getattr(model, "model_base", None)
            if base is None:
                continue
            radius = 0.0
            if bool(getattr(base, "has_circular_base", False)):
                get_radius = getattr(base, "get_radius", None)
                radius = float(get_radius()) if callable(get_radius) else 0.0
            else:
                get_longest = getattr(base, "get_longest_radius", None)
                if callable(get_longest):
                    radius = float(get_longest())
                else:
                    get_radius = getattr(base, "get_radius", None)
                    radius = float(get_radius()) if callable(get_radius) else 0.0
            largest = max(float(largest), float(max(0.0, radius)))
        return float(largest)

    @staticmethod
    def _strategic_edge_offsets(preferred_offset: float) -> list[float]:
        candidates = [
            float(preferred_offset),
            float(preferred_offset) + 0.25,
            float(preferred_offset) - 0.25,
            float(preferred_offset) + 0.5,
            float(preferred_offset) - 0.5,
            float(preferred_offset) + 1.0,
            float(preferred_offset) - 1.0,
            0.0,
            1.0,
            2.0,
            4.0,
            6.0,
        ]
        normalized: list[float] = []
        seen: set[float] = set()
        for value in candidates:
            bounded = float(max(0.0, value))
            key = round(bounded, 3)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(float(key))
        return normalized

    @staticmethod
    def _axis_points(start: float, end: float, *, step: float, offset: float) -> list[float]:
        lo = float(min(start, end))
        hi = float(max(start, end))
        if hi - lo <= 1e-6:
            return [lo]
        values: list[float] = []
        cursor = lo + float(offset)
        if cursor > hi:
            cursor = lo
        while cursor <= hi + 1e-6:
            values.append(round(float(cursor), 4))
            cursor += float(step)
        if not values:
            values = [round((lo + hi) / 2.0, 4)]
        return values

    @staticmethod
    def _board_dimensions(game: object) -> tuple[float, float]:
        battlefield = getattr(game, "battlefield", None)
        width = float(getattr(battlefield, "width", 0.0) or 0.0)
        height = float(getattr(battlefield, "height", 0.0) or 0.0)
        if width > 0.0 and height > 0.0:
            return (width, height)
        game_map = getattr(game, "map", None)
        map_width = float(getattr(game_map, "width", 60.0) or 60.0)
        map_height = float(getattr(game_map, "height", 44.0) or 44.0)
        return (map_width, map_height)

    @staticmethod
    def _strategic_edge_offset_preference(unit: object) -> float:
        largest_model_radius = 0.0
        for model in list(getattr(unit, "models", []) or []):
            base = getattr(model, "model_base", None)
            if base is None:
                continue
            radius = 0.0
            try:
                if bool(getattr(base, "has_circular_base", False)):
                    radius = float(getattr(base, "get_radius", lambda: 0.0)())
                else:
                    longest_radius_fn = getattr(base, "get_longest_radius", None)
                    if callable(longest_radius_fn):
                        radius = float(longest_radius_fn())
                    else:
                        radius = float(getattr(base, "get_radius", lambda: 0.0)())
            except (AttributeError, TypeError, ValueError):
                continue
            largest_model_radius = max(float(largest_model_radius), float(max(0.0, radius)))
        if largest_model_radius <= 0.0:
            return 1.0
        if largest_model_radius > 3.0:
            return float(largest_model_radius)
        max_wholly_within_offset = max(float(largest_model_radius), 6.0 - float(largest_model_radius))
        preferred = min(float(largest_model_radius) + 0.25, float(max_wholly_within_offset))
        # Strategic reserves usually need a small but non-zero edge offset to satisfy wholly-on-board placement.
        return float(max(0.5, preferred))

    def _build_model_positions_from_anchor(
        self,
        game: object,
        unit: object,
        *,
        x: float,
        y: float,
        search_context: object | None = None,
    ) -> list[dict]:
        return list(
            _build_reserves_model_positions_from_anchor(
                game,
                unit,
                x=float(x),
                y=float(y),
                avoid_friendly_units=False,
                search_context=search_context,
            )
        )

    def _rank_legal_candidates(self, request: DecisionRequest) -> list[CandidateAction]:
        candidates = list(getattr(request, "candidates", []) or [])
        mask = list(getattr(request, "mask", []) or [])
        legal: list[CandidateAction] = []
        for idx, candidate in enumerate(candidates):
            allowed = True
            if idx < len(mask):
                allowed = bool(mask[idx])
            if not allowed:
                continue
            if not self._candidate_is_structurally_resolvable(request, candidate):
                continue
            legal.append(candidate)
        if not legal:
            return []

        ranked = sorted(
            legal,
            key=lambda candidate: (
                -self._semantic_score(request, candidate),
                self._stable_tie_break(request, candidate),
            ),
        )

        if self._exploration_epsilon <= 0.0 or len(ranked) <= 1:
            return ranked
        if self._u01(f"{request.decision_id}:explore:{self._tie_break_salt}") >= self._exploration_epsilon:
            return ranked
        index = int(self._u01(f"{request.decision_id}:pick:{self._tie_break_salt}") * len(ranked))
        index = max(0, min(index, len(ranked) - 1))
        selected = ranked[index]
        return [selected] + [candidate for candidate in ranked if candidate is not selected]

    def _semantic_score(self, request: DecisionRequest, candidate: CandidateAction) -> float:
        metadata = dict(getattr(candidate, "metadata", {}) or {})
        params = dict(getattr(candidate, "params", {}) or {})
        request_context = dict(getattr(request, "context", {}) or {})
        weights = self._weights
        score = 0.0
        score += weights.score_next_window * self._num(metadata.get("projected_score_delta_next_window"))
        score += weights.score_round * self._num(metadata.get("projected_score_delta_round"))
        score += weights.deny_next_window * self._num(metadata.get("projected_deny_delta_next_window"))
        score += weights.control_delta * self._num(metadata.get("projected_control_delta"))
        score += weights.action_enablement_delta * self._num(metadata.get("projected_action_enablement_delta"))
        score += weights.trade_ev * self._num(metadata.get("projected_trade_ev"))
        score += weights.exposure_delta * self._num(metadata.get("projected_exposure_delta"))
        score += weights.cover_delta * self._num(metadata.get("cover_delta"))
        score += weights.los_delta * self._num(metadata.get("los_delta"))
        score += weights.resource_delta * self._num(metadata.get("resource_delta"))
        if bool(metadata.get("fallback_mode", False)):
            score -= 0.1
        if str(metadata.get("candidate_kind", "") or "").strip().lower() == "noop":
            score -= 0.05
        if str(getattr(request, "decision_type", "") or "") == DECISION_DECLARE_RESERVES:
            strategy_id = str(params.get("strategy_id", "") or "").strip().lower()
            if self._reserve_policy == "forced_only":
                score -= 100.0 * self._num(params.get("reserve_units"))
                score -= 10.0 * self._num(params.get("reserve_points_ratio"))
                score -= 5.0 * self._num(params.get("strategic_points_ratio"))
                if strategy_id == "forced_only":
                    score += 1000.0
        action = str(params.get("action", "") or "").strip().lower()
        if action in {"pass", "skip"} or bool(params.get("skipped", False)):
            score -= 1.0
        if str(getattr(request, "decision_type", "") or "") == "SELECT_UNIT":
            phase_step = str(request_context.get("phase_step", "") or "").strip().upper()
            if action == "pass" and phase_step in {
                "MOVE_UNITS",
                "REINFORCEMENTS",
                "SHOOT_UNITS",
                "DECLARE_CHARGES",
                "FIGHT_FIRST",
                "REMAINING_COMBATANTS",
            }:
                score -= 5.0
            unit_id = str(params.get("unit_id", "") or "").strip()
            must_arrive_ids = {
                str(value or "").strip()
                for value in list(request_context.get("pending_must_arrival_unit_ids", []) or [])
                if str(value or "").strip()
            }
            if phase_step == "REINFORCEMENTS" and unit_id and unit_id in must_arrive_ids:
                score += 2.0
        return float(score)

    def _stable_tie_break(self, request: DecisionRequest, candidate: CandidateAction) -> str:
        token = f"{request.decision_id}:{candidate.action_id}:{self._tie_break_salt}"
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _u01(self, token: str) -> float:
        digest = hashlib.sha256(str(token).encode("utf-8")).digest()
        value = int.from_bytes(digest[:8], byteorder="big", signed=False)
        return float(value / float(2**64 - 1))

    @staticmethod
    def _num(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
