from __future__ import annotations

import hashlib
import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Iterable

from .decision_controller import DecisionController
from .decision_kinds import DECISION_MOVE_UNIT, DECISION_REQUEST_DICE_ROLL, DECISION_SELECT_DICE_REROLL
from .decisions import CandidateAction, DecisionRequest
from ..utility.decision_utils import resolve_decision_command
from ..utility.entity_ids import get_entity_id

_DEFAULT_SKIPPED_DECISION_TYPES = {
    DECISION_REQUEST_DICE_ROLL,
    DECISION_SELECT_DICE_REROLL,
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
        max_reserves_anchor_points: int = 20000,
        max_reserves_arrival_seconds: float = 10.0,
        require_authoritative: bool = True,
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
        self._max_reserves_arrival_seconds = float(max(0.1, float(max_reserves_arrival_seconds or 0.1)))
        self._require_authoritative = bool(require_authoritative)
        self._attached = False
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

    def on_decision_requested(self, game: object, request: DecisionRequest) -> None:
        if request is None:
            return
        observed_game = game if game is not None else self._game
        if observed_game is None:
            return
        resolution_game = self._game if self._game is not None else observed_game
        if self._require_authoritative and not bool(getattr(observed_game, "is_authoritative", True)):
            return
        if str(getattr(request, "decision_type", "") or "") in self._skip_decision_types:
            return

        ranked = self._rank_legal_candidates(request)
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
            result_payload: dict[str, Any] = {}
            if bool(option_payload.get("skip", False)):
                result_payload["skipped"] = True
            if str(option_payload.get("action", "") or "").strip().lower() == "skip":
                result_payload["skipped"] = True
            apply_result = resolve_decision_command(
                game,
                request,
                option_id,
                result_payload=result_payload,
                player_id=getattr(request, "player_id", None),
            )
            if bool(getattr(apply_result, "ok", False)):
                return

    def _try_resolve_candidate(self, game: object, request: DecisionRequest, candidate: CandidateAction) -> bool:
        option_id = self._option_id_for_action_id(request, str(candidate.action_id or ""))
        if not option_id:
            return False
        payload = dict(getattr(candidate, "params", {}) or {})
        if bool(payload.get("skip", False)):
            payload["skipped"] = True
        if str(payload.get("action", "") or "").strip().lower() == "skip":
            payload["skipped"] = True
        apply_result = resolve_decision_command(
            game,
            request,
            option_id,
            result_payload=payload,
            player_id=getattr(request, "player_id", None),
        )
        return bool(getattr(apply_result, "ok", False))

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

    def _try_resolve_reserves_arrival_bruteforce(self, game: object, request: DecisionRequest) -> bool:
        if str(getattr(request, "decision_type", "") or "") != DECISION_MOVE_UNIT:
            return False
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("placement_kind", "") or "") != "reserves_arrival":
            return False

        options = list(getattr(request, "options", []) or [])
        confirm_option_id = ""
        skip_option_id = ""
        for option in options:
            option_id = str(getattr(option, "option_id", "") or "")
            if not option_id:
                continue
            payload = dict(getattr(option, "payload", {}) or {})
            if str(payload.get("action", "") or "").strip().lower() == "skip":
                skip_option_id = option_id
            else:
                confirm_option_id = option_id
        if not confirm_option_id:
            return False

        unit_id = str(context.get("unit_id", "") or "")
        unit = self._resolve_unit_by_id(game, unit_id)
        if unit is None:
            return False

        started = time.perf_counter()
        deadline = started + float(self._max_reserves_arrival_seconds)
        attempted = 0
        try:
            anchors = self._reserves_arrival_anchor_points(game, unit, context=context)
        except TypeError:
            anchors = self._reserves_arrival_anchor_points(game, unit)
        for x, y in anchors:
            now = time.perf_counter()
            if now >= deadline:
                break
            if self._quick_reject_reserves_anchor(game, unit, x=float(x), y=float(y), _context=context):
                continue
            attempted += 1
            model_positions = self._build_model_positions_from_anchor(game, unit, x=float(x), y=float(y))
            if not model_positions:
                continue
            apply_result = resolve_decision_command(
                game,
                request,
                confirm_option_id,
                result_payload={"model_positions": model_positions},
                player_id=getattr(request, "player_id", None),
            )
            if bool(getattr(apply_result, "ok", False)):
                return True

        timed_out = bool(time.perf_counter() >= deadline)
        if timed_out:
            logger.warning(
                "Headless reserves-arrival search timed out for unit %s after %.2fs (%d anchors attempted).",
                unit_id,
                float(time.perf_counter() - started),
                int(attempted),
            )

        allow_skip = bool(context.get("allow_skip", True))
        if allow_skip and skip_option_id:
            apply_result = resolve_decision_command(
                game,
                request,
                skip_option_id,
                result_payload={"skipped": True},
                player_id=getattr(request, "player_id", None),
            )
            return bool(getattr(apply_result, "ok", False))
        if timed_out and skip_option_id:
            apply_result = resolve_decision_command(
                game,
                request,
                skip_option_id,
                result_payload={"skipped": True},
                player_id=getattr(request, "player_id", None),
            )
            if bool(getattr(apply_result, "ok", False)):
                return True
        return False

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
        width, height = self._board_dimensions(game)
        unit_id = str(get_entity_id(unit) or "")
        ctx = dict(context or {})
        points: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()

        def _add(x: float, y: float) -> None:
            key = (round(float(x), 3), round(float(y), 3))
            if key in seen:
                return
            seen.add(key)
            points.append((float(x), float(y)))

        anchor_unit_id = str(ctx.get("reserves_arrival_anchor_unit_id", "") or "").strip()
        try:
            anchor_range = float(ctx.get("reserves_arrival_anchor_range", 0.0) or 0.0)
        except (TypeError, ValueError):
            anchor_range = 0.0
        if anchor_unit_id and anchor_range > 0.0:
            anchor_unit = self._resolve_unit_by_id(game, anchor_unit_id)
            if anchor_unit is not None:
                get_root = getattr(anchor_unit, "get_attached_unit_root", None)
                anchor_root = get_root() if callable(get_root) else anchor_unit
                anchor_pos = getattr(anchor_root, "position", None)
                if not (isinstance(anchor_pos, (tuple, list)) and len(anchor_pos) >= 2):
                    anchor_pos = None
                    models = list(getattr(anchor_root, "models", []) or [])
                    for model in models:
                        if not getattr(model, "is_alive", True):
                            continue
                        try:
                            loc = model.get_location()
                        except Exception:
                            continue
                        if isinstance(loc, (tuple, list)) and len(loc) >= 2:
                            anchor_pos = loc
                            break
                if isinstance(anchor_pos, (tuple, list)) and len(anchor_pos) >= 2:
                    ax = float(anchor_pos[0])
                    ay = float(anchor_pos[1])
                    _add(ax, ay)
                    radius_steps = (
                        max(0.5, float(anchor_range) * 0.33),
                        max(0.5, float(anchor_range) * 0.66),
                        float(anchor_range),
                    )
                    for radius in radius_steps:
                        for deg in range(0, 360, 45):
                            rad = math.radians(float(deg))
                            _add(ax + math.cos(rad) * float(radius), ay + math.sin(rad) * float(radius))

        in_strategic_fn = getattr(unit, "is_in_strategic_reserves", None)
        in_strategic = bool(in_strategic_fn()) if callable(in_strategic_fn) else False
        if in_strategic:
            along_step = self._strategic_edge_scan_step(unit, width=width, height=height)
            preferred_offset = self._strategic_edge_offset_preference(unit)
            offsets = self._strategic_edge_offsets(preferred_offset)
            xs_primary = self._axis_points(0.0, width, step=along_step, offset=0.0)
            ys_primary = self._axis_points(0.0, height, step=along_step, offset=0.0)
            xs_secondary = self._axis_points(0.0, width, step=along_step, offset=(along_step / 2.0))
            ys_secondary = self._axis_points(0.0, height, step=along_step, offset=(along_step / 2.0))
            for edge_offset in offsets:
                for x in xs_primary:
                    _add(x, edge_offset)
                    _add(x, max(0.0, height - edge_offset))
                for y in ys_primary:
                    _add(edge_offset, y)
                    _add(max(0.0, width - edge_offset), y)
                for x in xs_secondary:
                    _add(x, edge_offset)
                    _add(x, max(0.0, height - edge_offset))
                for y in ys_secondary:
                    _add(edge_offset, y)
                    _add(max(0.0, width - edge_offset), y)
                _add(edge_offset, edge_offset)
                _add(edge_offset, max(0.0, height - edge_offset))
                _add(max(0.0, width - edge_offset), edge_offset)
                _add(max(0.0, width - edge_offset), max(0.0, height - edge_offset))
            # Always include corners as fallbacks (some rules/test doubles require exact edge touch at 0").
            _add(0.0, 0.0)
            _add(0.0, float(height))
            _add(float(width), 0.0)
            _add(float(width), float(height))

            # Sparse fallback edge bands in case preferred offsets are blocked.
            fallback_step = max(1.5, along_step * 1.5)
            fallback_offsets = self._strategic_edge_offsets(0.0)
            xs_fallback = self._axis_points(0.0, width, step=fallback_step, offset=0.0)
            ys_fallback = self._axis_points(0.0, height, step=fallback_step, offset=0.0)
            for edge_offset in fallback_offsets:
                for x in xs_fallback:
                    _add(x, edge_offset)
                    _add(x, max(0.0, height - edge_offset))
                for y in ys_fallback:
                    _add(edge_offset, y)
                    _add(max(0.0, width - edge_offset), y)
        else:
            deep_steps = self._deep_strike_scan_steps(unit)
            for step in deep_steps:
                xs = self._axis_points(0.0, width, step=step, offset=0.0)
                ys = self._axis_points(0.0, height, step=step, offset=0.0)
                xs_half = self._axis_points(0.0, width, step=step, offset=(step / 2.0))
                ys_half = self._axis_points(0.0, height, step=step, offset=(step / 2.0))
                for y in ys:
                    for x in xs:
                        _add(x, y)
                for y in ys_half:
                    for x in xs_half:
                        _add(x, y)

        center_x = width / 2.0
        center_y = height / 2.0
        strategic_edge_preference = self._strategic_edge_offset_preference(unit)

        def _sort_key(point: tuple[float, float]) -> tuple[float, float, str]:
            x, y = point
            edge_dist = min(float(x), float(y), float(max(0.0, width - x)), float(max(0.0, height - y)))
            center_dist_sq = (float(x) - center_x) ** 2 + (float(y) - center_y) ** 2
            tie = hashlib.sha256(f"{unit_id}:{x:.3f}:{y:.3f}".encode("utf-8")).hexdigest()
            if in_strategic:
                edge_priority = abs(float(edge_dist) - float(strategic_edge_preference))
                d_left = float(x)
                d_right = float(max(0.0, width - x))
                d_bottom = float(y)
                d_top = float(max(0.0, height - y))
                nearest = min(d_left, d_right, d_bottom, d_top)
                if nearest == d_left or nearest == d_right:
                    along = float(y)
                    along_max = float(height)
                else:
                    along = float(x)
                    along_max = float(width)
                along_center = along_max / 2.0
                along_priority = min(abs(along - along_center), along, max(0.0, along_max - along))
                return (edge_priority, along_priority, abs(along - along_center), tie)
            return (center_dist_sq, edge_dist, tie)

        points.sort(key=_sort_key)
        max_points = int(self._max_reserves_anchor_points)
        if max_points > 0 and len(points) > max_points:
            return points[:max_points]
        return points

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
        in_strategic_fn = getattr(unit, "is_in_strategic_reserves", None)
        in_strategic = bool(in_strategic_fn()) if callable(in_strategic_fn) else False
        if not in_strategic:
            return False
        largest_radius = self._largest_model_radius(unit)
        edge_dist = min(float(x), float(y), float(max(0.0, width - x)), float(max(0.0, height - y)))
        # Strategic-reserves setups must end wholly within 6" of an edge; very deep interior anchors are never viable.
        if edge_dist > 10.0 + float(largest_radius):
            return True
        return False

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
            bounded = float(max(0.0, min(8.0, value)))
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
        # Strategic reserves usually need a small but non-zero edge offset to satisfy wholly-on-board placement.
        return float(max(0.5, min(4.0, largest_model_radius + 0.25)))

    def _build_model_positions_from_anchor(self, game: object, unit: object, *, x: float, y: float) -> list[dict]:
        game_map = getattr(game, "map", None)
        if game_map is None:
            return []
        boundary_repulsors = None
        repulsor_fn = getattr(game, "get_boundary_repulsors", None)
        if callable(repulsor_fn):
            boundary_repulsors = repulsor_fn(unit, context="reserves_arrival")
        model_positions = unit.calculate_model_positions(
            float(x),
            float(y),
            game_map,
            avoid_friendly_units=False,
            boundary_repulsors=boundary_repulsors,
        )
        models = list(getattr(unit, "models", []) or [])
        if not model_positions or len(model_positions) != len(models):
            return []
        payload: list[dict] = []
        for model, pos in zip(models, model_positions):
            model_id = str(get_entity_id(model) or "")
            if not model_id:
                return []
            model_x, model_y, model_z, model_facing = pos
            payload.append(
                {
                    "model_id": model_id,
                    "position": [float(model_x), float(model_y), float(model_z)],
                    "facing": float(model_facing),
                }
            )
        return payload

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
        action = str(params.get("action", "") or "").strip().lower()
        if action in {"pass", "skip"} or bool(params.get("skipped", False)):
            score -= 1.0
        if str(getattr(request, "decision_type", "") or "") == "SELECT_UNIT":
            phase_step = str(request_context.get("phase_step", "") or "").strip().upper()
            if action == "pass" and phase_step in {"MOVE_UNITS", "REINFORCEMENTS"}:
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
