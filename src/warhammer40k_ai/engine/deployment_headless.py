from __future__ import annotations

import hashlib
import math
import time
from typing import Iterable, Optional

from .decision_dispatcher import validate_decision
from .decision_kinds import DECISION_MOVE_UNIT
from .decisions import DecisionOption, DecisionRequest, DecisionResult
from .deployment import DeploymentDecisionMaker
from .deployment_ranker import DeploymentCandidateRanker
from .placement_zone_heuristics import (
    axis_points as _axis_points_shared,
    back_to_front_axis_points as _back_to_front_axis_points_shared,
    edge_first_axis_points as _edge_first_axis_points_shared,
    exhaustive_lattice_candidate_positions as _exhaustive_lattice_candidate_positions_shared,
    gap_anchor_candidates as _gap_anchor_candidates_shared,
    lattice_candidate_positions as _lattice_candidate_positions_shared,
    ordered_offsets as _ordered_offsets_shared,
    packing_row_anchor_candidates as _packing_row_anchor_candidates_shared,
    point_in_zone as _point_in_zone_shared,
    zone_bounds as _zone_bounds_shared,
    zone_center as _zone_center_shared,
)
from .pregame_deployment_agent import PregameDeploymentAgent
from .prospective_positions import calculate_prospective_model_positions
from .reserve_metadata import set_reserve_start_metadata
from ..roster.player import Player
from ..utility.call_utils import call_with_supported_kwargs
from ..utility.entity_ids import get_entity_id
from ..utility.placement_search import (
    build_placement_search_context,
    deployed_unit_bounds,
    estimate_unit_pack_footprint,
    model_longest_radius,
    stable_board_occupancy_key,
)
from ..utility.profiling_sections import profiled_section


class DeterministicDeploymentDecisionMaker(DeploymentDecisionMaker):
    """
    Non-interactive deployment policy for headless/self-play runs.

    Priorities:
    - deterministic behavior
    - legality-first placement via `Game.is_valid_deployment_position`
    - avoid reserves complexity unless forced by rules
    """

    _DEFAULT_EXHAUSTIVE_ANCHOR_LIMIT = 256

    def __init__(
        self,
        game: object,
        *,
        lattice_step: float = 2.0,
        exhaustive_lattice_step: float = 1.0,
        reserve_policy: str = "forced_only",
        use_pregame_teacher: bool = True,
        ranker_model_path: str | None = None,
        placement_candidate_limit: int = 2,
        exhaustive_anchor_limit: int = 256,
    ) -> None:
        self.game = game
        self.lattice_step = float(max(0.5, lattice_step))
        self.exhaustive_lattice_step = float(max(0.25, exhaustive_lattice_step))
        self.reserve_policy = self._normalize_reserve_policy(reserve_policy)
        self._pregame_agent = PregameDeploymentAgent(game) if bool(use_pregame_teacher) else None
        self._deployment_ranker = (
            DeploymentCandidateRanker.from_json_file(ranker_model_path)
            if str(ranker_model_path or "").strip()
            else None
        )
        self._active_player_id: str = ""
        self._selected_payload_by_unit_id: dict[str, tuple[tuple[float, float], list[dict]]] = {}
        self._placement_candidate_limit = int(max(1, placement_candidate_limit))
        self._exhaustive_anchor_limit = int(max(16, exhaustive_anchor_limit))
        self._relaxed_anchor_limit_uses_default = (
            int(exhaustive_anchor_limit) == self._DEFAULT_EXHAUSTIVE_ANCHOR_LIMIT
        )
        self._deployment_search_metrics: list[dict[str, object]] = []

    def choose_deployment_zone(self, available_zones: list[dict]) -> dict:
        zones = [dict(zone or {}) for zone in list(available_zones or [])]
        if not zones:
            raise ValueError("No deployment zones were provided.")
        player = self._resolve_player_by_id(self._active_player_id)
        if self._pregame_agent is not None and player is not None:
            chosen = self._pregame_agent.choose_deployment_zone(
                player=player,
                available_zones=zones,
            )
            matched = self._match_zone_choice(chosen, zones)
            if matched is not None:
                return matched
        for zone in zones:
            if str(zone.get("zone_type", "") or "").strip().lower() == "defender":
                return zone
        zones.sort(key=self._zone_sort_key)
        return zones[0]

    def choose_next_deploy_unit(
        self,
        deployable_units: list[object],
        deployment_zone: dict,
        already_deployed: list[object],
    ) -> object:
        if not deployable_units:
            raise ValueError("No deployable units were provided.")
        player = self._resolve_player_for_units(deployable_units)
        if player is None and self._active_player_id:
            player = self._resolve_player_by_id(self._active_player_id)
        teacher_rank: dict[str, int] = {}
        if self._pregame_agent is not None and player is not None:
            ordered = self._pregame_agent.ordered_deploy_units(
                player=player,
                deployable_units=list(deployable_units),
                deployment_zone=dict(deployment_zone or {}),
                already_deployed=list(already_deployed or []),
            )
            teacher_rank = {
                str(get_entity_id(candidate) or ""): int(index)
                for index, candidate in enumerate(list(ordered or []))
                if str(get_entity_id(candidate) or "")
            }
        ranked = sorted(
            list(deployable_units or []),
            key=lambda candidate: (
                -self._unit_pack_priority(candidate, player=player),
                int(teacher_rank.get(str(get_entity_id(candidate) or ""), 10**6)),
                str(get_entity_id(candidate) or ""),
            ),
        )
        return ranked[0]

    def choose_deployment_zone_option(
        self,
        request: DecisionRequest,
        available_zones: list[dict],
    ) -> Optional[str]:
        del available_zones
        return self._ranked_option_id(request)

    def choose_next_deploy_unit_option(
        self,
        request: DecisionRequest,
        deployable_units: list[object],
        deployment_zone: dict,
        already_deployed: list[object],
    ) -> Optional[str]:
        del deployable_units, deployment_zone, already_deployed
        return self._ranked_option_id(request)

    def choose_reserves_allocation_option(
        self,
        request: DecisionRequest,
        player: Player,
        proposed_decisions: dict[str, str],
    ) -> Optional[str]:
        del player, proposed_decisions
        return self._ranked_option_id(request)

    def choose_deployment_move_option(
        self,
        request: DecisionRequest,
        unit: object,
        deployment_zone: dict,
        already_deployed: list[object],
    ) -> Optional[str]:
        del unit, deployment_zone, already_deployed
        option_id = self._ranked_option_id(request)
        if option_id:
            return option_id
        return self._lookahead_option_id(request)

    def handle_unplaceable_deployment_unit(
        self,
        unit: object,
        *,
        player: Player,
        reason: str,
    ) -> bool:
        del reason
        army = player.get_army() if player is not None else None
        if army is None:
            return False
        reserve_status = self._preferred_reserve_status(army, unit)
        if not reserve_status:
            return False
        set_reserve_start_metadata(
            unit,
            started=True,
            reserve_status=reserve_status,
            source="deployment_overflow",
            mandatory_start=False,
            latest_arrival_round=3,
        )
        setattr(unit, "deployed", False)
        return True

    def declare_reserves(self, player: Player) -> dict:
        army = player.get_army() if player is not None else None
        if army is None:
            return {}
        decisions: dict[str, str] = {}
        roots = self._reserve_group_roots(army)
        for unit in roots:
            unit_id = str(get_entity_id(unit) or "")
            if not unit_id:
                continue
            must_start_fn = getattr(unit, "must_start_in_reserves", None)
            must_start = bool(must_start_fn()) if callable(must_start_fn) else False
            decisions[unit_id] = "reserves" if must_start else "deploy"

        if self.reserve_policy == "forced_only":
            decisions = self._apply_forced_policy_oversized_overflow_reserves(army, decisions, roots=roots, player=player)
            return self._finalize_reserves_decisions(army, decisions)

        limits_fn = getattr(army, "get_reserve_limits", None)
        validate_fn = getattr(army, "validate_reserves_decisions", None)
        enforce_fn = getattr(army, "enforce_reserves_limits", None)
        if callable(limits_fn) and callable(validate_fn):
            limits = dict(limits_fn() or {})
            max_units = int(limits.get("max_units", 0) or 0)
            max_points = int(limits.get("max_points", 0) or 0)
            battle_size_points = int(limits.get("battle_size_points", 0) or 0)
            target_units = min(max_units, max(0, len(roots) // 4))
            target_points = min(max_points, max(0, int(battle_size_points * 0.35)))

            candidates: list[tuple[float, str, object, str]] = []
            for unit in roots:
                unit_id = str(get_entity_id(unit) or "")
                if not unit_id:
                    continue
                if decisions.get(unit_id, "deploy") != "deploy":
                    continue
                reserve_status = self._preferred_reserve_status(army, unit)
                if not reserve_status:
                    continue
                score = self._reserve_candidate_score(
                    unit,
                    reserve_status=reserve_status,
                    player=player,
                )
                candidates.append((float(score), unit_id, unit, reserve_status))
            candidates.sort(key=lambda item: (-float(item[0]), str(item[1])))

            for _score, unit_id, _unit, reserve_status in candidates:
                trial = dict(decisions)
                trial[unit_id] = reserve_status
                validation = dict(validate_fn(trial) or {})
                if not bool(validation.get("valid", False)):
                    continue
                reserve_units = int(validation.get("reserve_units", 0) or 0)
                reserve_points = int(validation.get("reserve_points", 0) or 0)
                if reserve_units > target_units and reserve_points > target_points:
                    continue
                decisions = trial
                if reserve_units >= target_units and reserve_points >= target_points:
                    break
        return self._finalize_reserves_decisions(army, decisions)

    @staticmethod
    def _normalize_reserve_policy(value: str) -> str:
        policy = str(value or "").strip().lower()
        if policy in {"forced_only", "balanced"}:
            return policy
        raise ValueError(f"Unknown reserve policy: {value!r}. Expected 'forced_only' or 'balanced'.")

    @staticmethod
    def _finalize_reserves_decisions(army: object, decisions: dict[str, str]) -> dict[str, str]:
        validate_fn = getattr(army, "validate_reserves_decisions", None)
        enforce_fn = getattr(army, "enforce_reserves_limits", None)
        if not callable(validate_fn):
            return dict(decisions)
        validation = dict(validate_fn(decisions) or {})
        if bool(validation.get("valid", True)):
            return dict(decisions)
        if callable(enforce_fn):
            enforced = dict(enforce_fn(decisions) or {})
            if enforced:
                return enforced
        return dict(decisions)

    def _apply_forced_policy_oversized_overflow_reserves(
        self,
        army: object,
        decisions: dict[str, str],
        *,
        roots: list[object],
        player: Player,
    ) -> dict[str, str]:
        validate_fn = getattr(army, "validate_reserves_decisions", None)
        if not callable(validate_fn):
            return dict(decisions)

        oversized: list[tuple[float, str, object, str]] = []
        for unit in list(roots or []):
            unit_id = str(get_entity_id(unit) or "")
            if not unit_id or str(decisions.get(unit_id, "deploy") or "") != "deploy":
                continue
            reserve_status = self._preferred_reserve_status(army, unit)
            if not reserve_status:
                continue
            footprint = estimate_unit_pack_footprint(unit)
            is_oversized = (
                bool(getattr(unit, "is_titanic", False))
                or float(footprint["radius"]) >= 4.0
                or float(footprint["width"]) >= 8.0
                or float(footprint["depth"]) >= 8.0
            )
            if not is_oversized:
                continue
            score = self._reserve_candidate_score(unit, reserve_status=reserve_status, player=player)
            oversized.append((float(score), unit_id, unit, reserve_status))

        if len(oversized) <= 2:
            return dict(decisions)

        next_decisions = dict(decisions)
        reserved_count = 0
        oversized.sort(key=lambda item: (-float(item[0]), str(item[1])))
        for _score, unit_id, _unit, reserve_status in oversized:
            trial = dict(next_decisions)
            trial[unit_id] = reserve_status
            validation = dict(validate_fn(trial) or {})
            if not bool(validation.get("valid", False)):
                continue
            next_decisions = trial
            reserved_count += 1
            if len(oversized) - reserved_count <= 2:
                break
        return next_decisions

    def _preferred_reserve_status(self, army: object, unit: object) -> str:
        if bool(getattr(unit, "is_fortification", False)):
            return ""
        has_deep_strike_fn = getattr(unit, "has_deep_strike", None)
        has_deep_strike = bool(has_deep_strike_fn()) if callable(has_deep_strike_fn) else False
        ride_the_wind_fn = getattr(army, "_ride_the_wind_allows_standard_reserves", None)
        ride_the_wind_ok = bool(ride_the_wind_fn(unit)) if callable(ride_the_wind_fn) else False
        return "reserves" if (has_deep_strike or ride_the_wind_ok) else "strategic_reserves"

    def _reserve_candidate_score(
        self,
        unit: object,
        *,
        reserve_status: str,
        player: Optional[Player] = None,
    ) -> float:
        base = 0.0
        if str(reserve_status or "") == "reserves":
            base += 10000.0
        cost_fn = getattr(unit, "get_unit_cost", None)
        points = float(cost_fn()) if callable(cost_fn) else 0.0
        base += points
        base += 20.0 * self._unit_footprint_score(unit)
        if self._pregame_agent is not None and player is not None:
            preference = self._pregame_agent.reserve_preference_score(
                player=player,
                unit=unit,
                reserve_status=str(reserve_status or ""),
            )
            base += 200.0 * float(preference)
        return float(base)

    def _unit_footprint_score(self, unit: object) -> float:
        footprint = estimate_unit_pack_footprint(unit)
        return float(footprint["radius"] + (0.35 * footprint["width"]) + (0.25 * footprint["depth"]))

    def deployment_candidate_limit(
        self,
        *,
        unit: object | None = None,
        deployment_zone: dict | None = None,
        already_deployed: list[object] | None = None,
    ) -> int:
        del unit, deployment_zone, already_deployed
        return int(self._placement_candidate_limit)

    def get_deployment_search_metrics(self) -> list[dict[str, object]]:
        return [dict(entry or {}) for entry in list(self._deployment_search_metrics or [])]

    def reset_deployment_search_metrics(self) -> None:
        self._deployment_search_metrics.clear()

    def _unit_pack_priority(self, unit: object, *, player: Optional[Player]) -> float:
        del player
        footprint = estimate_unit_pack_footprint(unit)
        score = float(footprint["radius"] * 20.0 + footprint["width"] * 2.5 + footprint["depth"] * 2.0)
        if bool(getattr(unit, "is_titanic", False)):
            score += 120.0
        if bool(getattr(unit, "is_transport", False)):
            score += 35.0
        if bool(getattr(unit, "is_monster", False)):
            score += 25.0
        if bool(getattr(unit, "is_vehicle", False)):
            score += 25.0
        if self._unit_has_infiltrate(unit):
            score -= 45.0
        if self._unit_has_scout(unit):
            score -= 30.0
        if self._unit_has_deep_strike(unit):
            score -= 12.0
        return float(score)

    @staticmethod
    def _unit_has_scout(unit: object) -> bool:
        has_scout = getattr(unit, "has_scout", None)
        if callable(has_scout):
            value = has_scout()
            if isinstance(value, (list, tuple)):
                return bool(value[0]) if value else False
            return bool(value)
        return bool(getattr(unit, "scout_move_distance", 0.0))

    @staticmethod
    def _unit_has_deep_strike(unit: object) -> bool:
        has_deep_strike = getattr(unit, "has_deep_strike", None)
        return bool(has_deep_strike()) if callable(has_deep_strike) else False

    def _deployment_boundary_repulsors(self, unit: object) -> list[object]:
        if self._unit_has_infiltrate(unit):
            return []
        repulsor_fn = getattr(self.game, "get_boundary_repulsors", None)
        if callable(repulsor_fn):
            return list(repulsor_fn(unit, context="deployment") or [])
        return []

    def _build_deployment_search_context(
        self,
        unit: object,
        *,
        boundary_repulsors: list[object],
    ):
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return None
        return build_placement_search_context(
            unit,
            game_map,
            avoid_friendly_units=True,
            boundary_repulsors=boundary_repulsors,
        )

    def _new_deployment_metric(
        self,
        *,
        unit: object,
        player_id: str,
        candidate_limit: int,
        already_deployed: list[object],
    ) -> dict[str, object]:
        unit_id = str(get_entity_id(unit) or "")
        metric = {
            "unit_id": unit_id,
            "unit_name": str(getattr(unit, "name", "") or unit_id or "Unit"),
            "player_id": str(player_id or ""),
            "candidate_limit": int(candidate_limit),
            "anchor_attempts": 0,
            "quick_rejects": 0,
            "validate_calls": 0,
            "full_validation_calls": 0,
            "calls_to_first_valid": None,
            "first_valid_source": "",
            "returned_candidate_count": 0,
            "returned_candidate_sources": [],
            "source_attempt_counts": {},
            "source_validate_calls": {},
            "source_quick_rejects": {},
            "exhaustive_fallback_used": False,
            "relaxed_fallback_used": False,
            "already_deployed_count": int(len(list(already_deployed or []))),
            "board_occupancy_key": list(stable_board_occupancy_key(already_deployed)),
        }
        return metric

    @staticmethod
    def _bump_metric_counter(metric: dict[str, object], key: str, source: str) -> None:
        counters = dict(metric.get(key, {}) or {})
        counters[str(source or "unknown")] = int(counters.get(str(source or "unknown"), 0) or 0) + 1
        metric[key] = counters

    def _record_deployment_metric(self, metric: dict[str, object]) -> None:
        self._deployment_search_metrics.append(dict(metric or {}))

    def choose_unit_deployment_position(
        self,
        unit: object,
        deployment_zone: dict,
        already_deployed: list[object],
    ) -> tuple[float, float]:
        player_id = self._player_id_for_unit(unit)
        if not player_id:
            return self._zone_center(deployment_zone)

        validate_fn = getattr(self.game, "is_valid_deployment_position", None)
        if not callable(validate_fn):
            return self._zone_center(deployment_zone)
        candidates = self.build_deployment_move_candidates(
            unit,
            deployment_zone,
            list(already_deployed or []),
            max_candidates=1,
        )
        if candidates:
            first = dict(candidates[0] or {})
            anchor = list(first.get("anchor", []) or [])
            if len(anchor) >= 2:
                return (float(anchor[0]), float(anchor[1]))
        raise RuntimeError(
            f"No valid deployment position found for unit {getattr(unit, 'name', 'Unit')} "
            f"(player_id={player_id})."
        )

    @profiled_section("deployment.headless_build_move_candidates")
    def build_deployment_move_candidates(
        self,
        unit: object,
        deployment_zone: dict,
        already_deployed: list[object],
        *,
        max_candidates: int = 8,
    ) -> list[dict]:
        player_id = self._player_id_for_unit(unit)
        if not player_id:
            return []
        validate_fn = getattr(self.game, "is_valid_deployment_position", None)
        if not callable(validate_fn):
            return []

        unit_id = str(get_entity_id(unit) or "")
        if unit_id:
            self._selected_payload_by_unit_id.pop(unit_id, None)

        candidate_limit = max(
            1,
            min(
                int(max_candidates),
                int(
                    self.deployment_candidate_limit(
                        unit=unit,
                        deployment_zone=deployment_zone,
                        already_deployed=list(already_deployed or []),
                    )
                ),
            ),
        )
        player = self._resolve_player_for_unit(unit)
        boundary_repulsors = self._deployment_boundary_repulsors(unit)
        search_context = self._build_deployment_search_context(
            unit,
            boundary_repulsors=boundary_repulsors,
        )
        metric = self._new_deployment_metric(
            unit=unit,
            player_id=str(player_id),
            candidate_limit=int(candidate_limit),
            already_deployed=list(already_deployed or []),
        )
        position_cache: dict[tuple[str, str, float, float], list[list[dict]]] = {}
        started = time.perf_counter()
        footprint = estimate_unit_pack_footprint(unit)
        candidate_groups = self._deployment_anchor_candidate_groups(
            unit,
            deployment_zone,
            already_deployed=list(already_deployed or []),
            player=player,
            footprint=footprint,
        )
        seen_anchor: set[tuple[float, float]] = set()
        seen_payload: set[tuple[tuple[str, float, float, float, float], ...]] = set()
        candidates: list[dict] = []

        for source, anchors in list(candidate_groups or []):
            if str(source or "").startswith("lattice_exhaustive"):
                metric["exhaustive_fallback_used"] = True
            for x, y in list(anchors or []):
                metric["anchor_attempts"] = int(metric.get("anchor_attempts", 0) or 0) + 1
                self._bump_metric_counter(metric, "source_attempt_counts", str(source))
                key = (round(float(x), 3), round(float(y), 3))
                if key in seen_anchor:
                    continue
                seen_anchor.add(key)
                if self._quick_reject_deployment_anchor(
                    unit,
                    deployment_zone,
                    already_deployed=list(already_deployed or []),
                    footprint=footprint,
                    x=float(x),
                    y=float(y),
                ):
                    metric["quick_rejects"] = int(metric.get("quick_rejects", 0) or 0) + 1
                    self._bump_metric_counter(metric, "source_quick_rejects", str(source))
                    continue
                payload = self._select_valid_deployment_payload(
                    unit,
                    player_id=str(player_id),
                    x=float(x),
                    y=float(y),
                    fast_validate_fn=validate_fn,
                    boundary_repulsors=boundary_repulsors,
                    search_context=search_context,
                    metric=metric,
                    source=str(source),
                    position_cache=position_cache,
                )
                if not payload:
                    continue
                payload_sig = self._model_positions_signature(payload)
                if payload_sig in seen_payload:
                    continue
                seen_payload.add(payload_sig)
                candidates.append(
                    {
                        "anchor": [float(x), float(y)],
                        "model_positions": [dict(entry or {}) for entry in list(payload or [])],
                        "source": str(source or "heuristic").strip().lower() or "heuristic",
                    }
                )
                if len(candidates) >= candidate_limit:
                    break
            if len(candidates) >= candidate_limit:
                break

        if not candidates:
            source = (
                "infiltrate_relaxed_no_quick_reject"
                if self._unit_has_infiltrate(unit)
                else "lattice_relaxed_no_quick_reject"
            )
            metric["relaxed_fallback_used"] = True
            rescue_seen_anchor: set[tuple[float, float]] = set()
            for x, y in self._relaxed_deployment_anchor_candidates(
                unit,
                deployment_zone,
                already_deployed=list(already_deployed or []),
            ):
                metric["anchor_attempts"] = int(metric.get("anchor_attempts", 0) or 0) + 1
                self._bump_metric_counter(metric, "source_attempt_counts", source)
                key = (round(float(x), 3), round(float(y), 3))
                if key in rescue_seen_anchor:
                    continue
                rescue_seen_anchor.add(key)
                if self._quick_reject_deployment_anchor(
                    unit,
                    deployment_zone,
                    already_deployed=[],
                    footprint=footprint,
                    x=float(x),
                    y=float(y),
                ):
                    metric["quick_rejects"] = int(metric.get("quick_rejects", 0) or 0) + 1
                    self._bump_metric_counter(metric, "source_quick_rejects", source)
                    continue
                payload = self._select_valid_deployment_payload(
                    unit,
                    player_id=str(player_id),
                    x=float(x),
                    y=float(y),
                    fast_validate_fn=validate_fn,
                    boundary_repulsors=boundary_repulsors,
                    search_context=search_context,
                    metric=metric,
                    source=source,
                    position_cache=position_cache,
                )
                if not payload:
                    continue
                payload_sig = self._model_positions_signature(payload)
                if payload_sig in seen_payload:
                    continue
                seen_payload.add(payload_sig)
                candidates.append(
                    {
                        "anchor": [float(x), float(y)],
                        "model_positions": [dict(entry or {}) for entry in list(payload or [])],
                        "source": source,
                    }
                )
                if len(candidates) >= candidate_limit:
                    break

        metric["returned_candidate_count"] = int(len(candidates))
        metric["returned_candidate_sources"] = [
            str(dict(candidate or {}).get("source", "") or "")
            for candidate in list(candidates or [])
        ]
        metric["elapsed_ms"] = int(round((time.perf_counter() - started) * 1000.0))
        self._record_deployment_metric(metric)

        if unit_id and candidates:
            first = dict(candidates[0] or {})
            first_anchor = list(first.get("anchor", []) or [])
            first_positions = [dict(entry or {}) for entry in list(first.get("model_positions", []) or [])]
            if len(first_anchor) >= 2 and first_positions:
                self._selected_payload_by_unit_id[unit_id] = (
                    (float(first_anchor[0]), float(first_anchor[1])),
                    list(first_positions),
                )
        return candidates

    def _deployment_anchor_candidate_groups(
        self,
        unit: object,
        deployment_zone: dict,
        *,
        already_deployed: list[object],
        player: Optional[Player],
        footprint: dict[str, float],
    ) -> list[tuple[str, list[tuple[float, float]]]]:
        groups: list[tuple[str, list[tuple[float, float]]]] = [
            (
                "packer_gap",
                self._gap_anchor_candidates(
                    unit,
                    deployment_zone,
                    already_deployed=already_deployed,
                    footprint=footprint,
                ),
            ),
            (
                "packer_rows",
                self._packing_row_anchor_candidates(
                    unit,
                    deployment_zone,
                    already_deployed=already_deployed,
                    footprint=footprint,
                ),
            ),
            (
                "semantic_anchor",
                self._semantic_anchor_candidates(
                    unit,
                    deployment_zone,
                    already_deployed=already_deployed,
                    player=player,
                ),
            ),
            ("lattice", self._candidate_positions(unit, deployment_zone, already_deployed)),
            (
                "footprint_safe_lattice",
                self._footprint_safe_anchor_candidates(
                    unit,
                    deployment_zone,
                    footprint=footprint,
                ),
            ),
            (
                "edge_sweep",
                self._edge_sweep_anchor_candidates(
                    unit,
                    deployment_zone,
                    already_deployed=already_deployed,
                    footprint=footprint,
                ),
            ),
            ("lattice_exhaustive", self._candidate_positions_exhaustive(unit, deployment_zone)),
        ]
        if self._unit_has_infiltrate(unit):
            infiltrate_groups = self._infiltrate_candidate_groups(unit, already_deployed=already_deployed)
            for idx, anchors in enumerate(list(infiltrate_groups or [])):
                groups.insert(int(idx), (f"infiltrate_{int(idx)}", list(anchors or [])))
        return groups

    def _relaxed_deployment_anchor_candidates(
        self,
        unit: object,
        deployment_zone: dict,
        *,
        already_deployed: list[object],
    ) -> list[tuple[float, float]]:
        del already_deployed
        bounds = (
            self._zone_bounds({})
            if self._unit_has_infiltrate(unit)
            else self._zone_bounds(deployment_zone)
        )
        if bounds is None:
            return []
        alive_models = [
            model
            for model in list(getattr(unit, "models", []) or [])
            if model is not None and bool(getattr(model, "is_alive", True))
        ]
        if len(alive_models) <= 5:
            if self._relaxed_anchor_limit_uses_default:
                relaxed_limit = 3072
            else:
                relaxed_limit = min(4096, max(64, int(self._exhaustive_anchor_limit)))
        else:
            relaxed_limit = min(128, max(32, int(self._exhaustive_anchor_limit)))
        anchors: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()

        edge_candidates = self._edge_sweep_anchor_candidates(
            unit,
            deployment_zone if not self._unit_has_infiltrate(unit) else {"bounds": list(bounds)},
            already_deployed=[],
            footprint=estimate_unit_pack_footprint(unit),
        )
        for anchor in list(edge_candidates or []):
            key = (round(float(anchor[0]), 3), round(float(anchor[1]), 3))
            if key in seen:
                continue
            seen.add(key)
            anchors.append((float(anchor[0]), float(anchor[1])))
            if len(anchors) >= int(relaxed_limit):
                return anchors

        footprint_safe_candidates = self._footprint_safe_anchor_candidates(
            unit,
            deployment_zone if not self._unit_has_infiltrate(unit) else {"bounds": list(bounds)},
            footprint=estimate_unit_pack_footprint(unit),
            anchor_limit=int(relaxed_limit),
        )
        for anchor in list(footprint_safe_candidates or []):
            key = (round(float(anchor[0]), 3), round(float(anchor[1]), 3))
            if key in seen:
                continue
            seen.add(key)
            anchors.append((float(anchor[0]), float(anchor[1])))
            if len(anchors) >= int(relaxed_limit):
                return anchors

        if len(alive_models) <= 5:
            home_corner_candidates = self._home_corner_dense_anchor_candidates(
                deployment_zone if not self._unit_has_infiltrate(unit) else {"bounds": list(bounds)},
                anchor_limit=int(relaxed_limit),
            )
            for anchor in list(home_corner_candidates or []):
                key = (round(float(anchor[0]), 3), round(float(anchor[1]), 3))
                if key in seen:
                    continue
                seen.add(key)
                anchors.append((float(anchor[0]), float(anchor[1])))
                if len(anchors) >= int(relaxed_limit):
                    return anchors

        exhaustive_candidates = self._candidate_positions_exhaustive_for_bounds(
            unit,
            bounds=bounds,
            anchor_limit=int(relaxed_limit),
        )
        for anchor in list(exhaustive_candidates or []):
            key = (round(float(anchor[0]), 3), round(float(anchor[1]), 3))
            if key in seen:
                continue
            seen.add(key)
            anchors.append((float(anchor[0]), float(anchor[1])))
            if len(anchors) >= int(relaxed_limit):
                break
        return anchors

    @staticmethod
    def _model_positions_signature(model_positions: list[dict]) -> tuple[tuple[str, float, float, float, float], ...]:
        signature: list[tuple[str, float, float, float, float]] = []
        for entry in list(model_positions or []):
            if not isinstance(entry, dict):
                continue
            model_id = str(entry.get("model_id", "") or "")
            pos = list(entry.get("position", []) or [])
            if not model_id or len(pos) < 2:
                continue
            try:
                x = float(pos[0])
                y = float(pos[1])
                z = float(pos[2]) if len(pos) >= 3 else 0.0
                facing = float(entry.get("facing", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            signature.append((model_id, round(x, 4), round(y, 4), round(z, 4), round(facing, 4)))
        signature.sort(key=lambda item: item[0])
        return tuple(signature)

    def _local_anchor_search_points(
        self,
        unit: object,
        *,
        x: float,
        y: float,
    ) -> list[tuple[float, float]]:
        footprint = estimate_unit_pack_footprint(unit)
        base_step = max(0.25, min(1.0, float(footprint.get("spacing", 0.5) or 0.5) * 0.5))
        wide_step = max(base_step, min(1.5, base_step * 2.0))
        offsets = (
            (-base_step, 0.0),
            (base_step, 0.0),
            (0.0, -base_step),
            (0.0, base_step),
            (-base_step, -base_step),
            (-base_step, base_step),
            (base_step, -base_step),
            (base_step, base_step),
            (-wide_step, 0.0),
            (wide_step, 0.0),
            (0.0, -wide_step),
            (0.0, wide_step),
        )
        return [(float(x) + float(dx), float(y) + float(dy)) for dx, dy in offsets]

    def _quick_reject_deployment_anchor(
        self,
        unit: object,
        deployment_zone: dict,
        *,
        already_deployed: list[object],
        footprint: dict[str, float] | None = None,
        x: float,
        y: float,
    ) -> bool:
        if not self._unit_has_infiltrate(unit) and not self._point_in_zone(deployment_zone, float(x), float(y)):
            return True
        footprint = dict(footprint or estimate_unit_pack_footprint(unit))
        clearance = max(0.25, float(footprint.get("radius", footprint.get("largest_radius", 0.0)) or 0.0) + 0.25)
        for deployed_unit in list(already_deployed or []):
            unit_bounds = deployed_unit_bounds(deployed_unit)
            if unit_bounds is None:
                continue
            bx0, by0, bx1, by1 = unit_bounds
            if (
                float(bx0) - clearance <= float(x) <= float(bx1) + clearance
                and float(by0) - clearance <= float(y) <= float(by1) + clearance
            ):
                return True
        return False

    def _packing_row_anchor_candidates(
        self,
        unit: object,
        deployment_zone: dict,
        *,
        already_deployed: list[object],
        footprint: dict[str, float],
    ) -> list[tuple[float, float]]:
        del already_deployed
        battlefield = getattr(self.game, "battlefield", None)
        board_width = float(getattr(battlefield, "width", 60.0) or 60.0)
        board_height = float(getattr(battlefield, "height", 44.0) or 44.0)
        return _packing_row_anchor_candidates_shared(
            deployment_zone,
            board_width=board_width,
            board_height=board_height,
            footprint=footprint,
            lattice_step=float(self.lattice_step),
            default_bounds=(0.0, board_width, 0.0, board_height),
        )

    def _gap_anchor_candidates(
        self,
        unit: object,
        deployment_zone: dict,
        *,
        already_deployed: list[object],
        footprint: dict[str, float],
    ) -> list[tuple[float, float]]:
        if not already_deployed:
            return []
        battlefield = getattr(self.game, "battlefield", None)
        board_width = float(getattr(battlefield, "width", 60.0) or 60.0)
        board_height = float(getattr(battlefield, "height", 44.0) or 44.0)
        return _gap_anchor_candidates_shared(
            deployment_zone,
            occupied_units=list(already_deployed or []),
            footprint=footprint,
            default_bounds=(0.0, board_width, 0.0, board_height),
        )

    def _footprint_safe_anchor_candidates(
        self,
        unit: object,
        deployment_zone: dict,
        *,
        footprint: dict[str, float],
        anchor_limit: int | None = None,
    ) -> list[tuple[float, float]]:
        bounds = self._zone_bounds(deployment_zone)
        if bounds is None:
            return []
        min_x, max_x, min_y, max_y = bounds
        width = max(0.0, float(max_x) - float(min_x))
        height = max(0.0, float(max_y) - float(min_y))
        if width <= 0.0 or height <= 0.0:
            return []
        largest_radius = max(
            0.0,
            float(footprint.get("largest_radius", footprint.get("radius", 0.0)) or 0.0),
        )
        margin = min(width * 0.5, height * 0.5, largest_radius + 0.25)
        step = max(0.5, min(2.0, max(1.0, largest_radius)))
        limit = int(anchor_limit) if anchor_limit is not None else 768

        xs = self._edge_first_axis_points(min_x, max_x, step=step, margin=margin)
        ys = self._edge_first_axis_points(min_y, max_y, step=step, margin=margin)
        center_x, center_y = self._zone_center(deployment_zone)
        candidates: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        for row_idx, y in enumerate(list(ys or [])):
            x_values = list(xs or [])
            if row_idx % 2 == 1:
                x_values.reverse()
            for x in x_values:
                anchor = (float(x), float(y))
                key = (round(anchor[0], 3), round(anchor[1], 3))
                if key in seen:
                    continue
                seen.add(key)
                if not self._point_in_zone(deployment_zone, anchor[0], anchor[1]):
                    continue
                candidates.append(anchor)
                if len(candidates) >= max(0, limit):
                    return candidates
        center_anchor = (float(center_x), float(center_y))
        center_key = (round(center_anchor[0], 3), round(center_anchor[1], 3))
        if center_key not in seen and self._point_in_zone(deployment_zone, center_anchor[0], center_anchor[1]):
            candidates.append(center_anchor)
        return candidates[: max(0, limit)]

    def _edge_sweep_anchor_candidates(
        self,
        unit: object,
        deployment_zone: dict,
        *,
        already_deployed: list[object],
        footprint: dict[str, float],
    ) -> list[tuple[float, float]]:
        del already_deployed, footprint
        bounds = self._zone_bounds(deployment_zone)
        if bounds is None:
            return []
        min_x, max_x, min_y, max_y = bounds
        alive_models = [
            model
            for model in list(getattr(unit, "models", []) or [])
            if model is not None and bool(getattr(model, "is_alive", True))
        ]
        edge_step = 0.5 if len(alive_models) <= 3 else 1.0
        edge_limit = 512 if len(alive_models) <= 3 else 256
        xs = self._edge_first_axis_points(min_x, max_x, step=edge_step, margin=0.0)
        ys = self._edge_first_axis_points(min_y, max_y, step=edge_step, margin=0.0)

        candidates: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        for row_idx, y in enumerate(list(ys or [])):
            x_values = list(xs or [])
            if row_idx % 2 == 1:
                x_values.reverse()
            for x in x_values:
                anchor = (float(x), float(y))
                key = (round(anchor[0], 3), round(anchor[1], 3))
                if key in seen:
                    continue
                seen.add(key)
                if not self._point_in_zone(deployment_zone, anchor[0], anchor[1]):
                    continue
                candidates.append(anchor)
                if len(candidates) >= int(edge_limit):
                    return candidates
        return candidates

    def _edge_first_axis_points(self, lo: float, hi: float, *, step: float, margin: float) -> list[float]:
        return _edge_first_axis_points_shared(lo, hi, step=step, margin=margin)

    def _home_corner_dense_anchor_candidates(
        self,
        deployment_zone: dict,
        *,
        anchor_limit: int,
    ) -> list[tuple[float, float]]:
        bounds = self._zone_bounds(deployment_zone)
        if bounds is None:
            return []
        min_x, max_x, min_y, max_y = bounds
        x_values = self._axis_points(min_x, max_x, step=0.5, offset=0.0)
        y_values = self._axis_points(min_y, max_y, step=0.5, offset=0.0)

        battlefield = getattr(self.game, "battlefield", None)
        board_width = float(getattr(battlefield, "width", 60.0) or 60.0)
        board_height = float(getattr(battlefield, "height", 44.0) or 44.0)
        zone_center_x, zone_center_y = self._zone_center(deployment_zone)
        if float(zone_center_x) >= (board_width * 0.5):
            x_values = list(reversed(x_values))
        if float(zone_center_y) >= (board_height * 0.5):
            y_values = list(reversed(y_values))

        candidates: list[tuple[float, float]] = []
        for y in list(y_values or []):
            for x in list(x_values or []):
                if not self._point_in_zone(deployment_zone, float(x), float(y)):
                    continue
                candidates.append((float(x), float(y)))
                if len(candidates) >= int(anchor_limit):
                    return candidates
        return candidates

    @staticmethod
    def _back_to_front_axis_points(
        lo: float,
        hi: float,
        *,
        step: float,
        margin: float,
        forward_positive: bool,
    ) -> list[float]:
        return _back_to_front_axis_points_shared(
            lo,
            hi,
            step=step,
            margin=margin,
            forward_positive=forward_positive,
        )

    @profiled_section("deployment.position_validation")
    def _select_valid_deployment_payload(
        self,
        unit: object,
        *,
        player_id: str,
        x: float,
        y: float,
        fast_validate_fn,
        boundary_repulsors: list[object],
        search_context,
        metric: dict[str, object],
        source: str,
        position_cache: dict[tuple[str, str, float, float], list[list[dict]]] | None = None,
    ) -> list[dict]:
        metric["validate_calls"] = int(metric.get("validate_calls", 0) or 0) + 1
        self._bump_metric_counter(metric, "source_validate_calls", str(source))
        unit_id = str(get_entity_id(unit) or "")
        if not unit_id:
            return []

        for model_positions in self._iter_model_positions_variants(
            unit,
            x=float(x),
            y=float(y),
            boundary_repulsors=boundary_repulsors,
            search_context=search_context,
            position_cache=position_cache,
            metric=metric,
        ):
            allowed_model_ids = [str(entry.get("model_id", "") or "") for entry in list(model_positions or [])]
            if not all(allowed_model_ids):
                continue
            tuple_positions = self._tuple_positions_from_payload(model_positions)
            if not tuple_positions:
                continue
            if not bool(
                call_with_supported_kwargs(
                    fast_validate_fn,
                    unit,
                    float(x),
                    float(y),
                    str(player_id),
                    boundary_repulsors=boundary_repulsors,
                    search_context=search_context,
                    model_positions=tuple_positions,
                )
            ):
                metric["fast_validation_rejects"] = int(metric.get("fast_validation_rejects", 0) or 0) + 1
                self._bump_metric_counter(metric, "source_fast_validation_rejects", str(source))
                continue
            metric["full_validation_calls"] = int(metric.get("full_validation_calls", 0) or 0) + 1
            request = DecisionRequest.create(
                DECISION_MOVE_UNIT,
                f"Deploy {getattr(unit, 'name', 'Unit')}",
                player_id=str(player_id),
                options=[
                    DecisionOption.create(
                        "Confirm",
                        payload={"unit_id": unit_id, "movement_type": "deploy", "action": "confirm"},
                    )
                ],
                context={
                    "unit_id": unit_id,
                    "movement_type": "deploy",
                    "placement_kind": "deployment",
                    "allowed_model_ids": list(allowed_model_ids),
                    "allow_skip": False,
                    "max_distance": 0.0,
                },
            )
            option_id = request.options[0].option_id if getattr(request, "options", None) else ""
            if not option_id:
                continue
            result = DecisionResult(
                decision_id=str(request.decision_id or ""),
                player_id=str(player_id),
                option_id=str(option_id),
                payload={"model_positions": list(model_positions)},
            )
            errors = tuple(validate_decision(self.game, request, result) or ())
            if not errors:
                if metric.get("calls_to_first_valid", None) is None:
                    metric["calls_to_first_valid"] = int(metric.get("validate_calls", 0) or 0)
                    metric["first_valid_source"] = str(source or "")
                return list(model_positions)
        return []

    @staticmethod
    def _tuple_positions_from_payload(model_positions: list[dict]) -> list[tuple[float, float, float, float]]:
        tuple_positions: list[tuple[float, float, float, float]] = []
        for entry in list(model_positions or []):
            if not isinstance(entry, dict):
                return []
            pos = list(entry.get("position", []) or [])
            if len(pos) < 2:
                return []
            try:
                x = float(pos[0])
                y = float(pos[1])
                z = float(pos[2]) if len(pos) >= 3 else 0.0
                facing = float(entry.get("facing", 0.0) or 0.0)
            except (TypeError, ValueError):
                return []
            tuple_positions.append((x, y, z, facing))
        return tuple_positions

    def _iter_model_positions_variants(
        self,
        unit: object,
        *,
        x: float,
        y: float,
        boundary_repulsors: list[object],
        search_context,
        position_cache: dict[tuple[str, str, float, float], list[list[dict]]] | None = None,
        metric: dict[str, object] | None = None,
    ):
        fast_positions = self._build_fast_grid_model_positions(unit, x=float(x), y=float(y))
        if fast_positions:
            yield list(fast_positions)
            for alt_x, alt_y in self._local_anchor_search_points(unit, x=float(x), y=float(y)):
                alt_positions = self._build_fast_grid_model_positions(unit, x=float(alt_x), y=float(alt_y))
                if alt_positions:
                    yield list(alt_positions)
            if self._uses_fast_grid_deployment(unit):
                return

        cache_key = self._model_position_cache_key(unit, mode="detailed", x=float(x), y=float(y))
        cached_variants = None
        if position_cache is not None:
            cached_variants = position_cache.get(cache_key)
        if cached_variants is not None:
            if metric is not None:
                metric["position_cache_hits"] = int(metric.get("position_cache_hits", 0) or 0) + 1
            variants = [[dict(entry or {}) for entry in list(variant or [])] for variant in cached_variants]
        else:
            if metric is not None:
                metric["position_cache_misses"] = int(metric.get("position_cache_misses", 0) or 0) + 1
            variants = self._build_detailed_model_positions_variants(
                unit,
                x=float(x),
                y=float(y),
                boundary_repulsors=boundary_repulsors,
                search_context=search_context,
                refine_surfaces=self._refines_surface_variants(unit),
            )
            if position_cache is not None:
                position_cache[cache_key] = [
                    [dict(entry or {}) for entry in list(variant or [])]
                    for variant in list(variants or [])
                ]
        for variant in variants:
            yield list(variant)

    def _build_fast_grid_model_positions(self, unit: object, *, x: float, y: float) -> list[dict]:
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return []
        models = [model for model in list(getattr(unit, "models", []) or []) if model is not None]
        if not self._can_build_fast_grid_deployment(unit):
            return []
        radii = [max(0.1, float(model_longest_radius(model) or 0.0)) for model in models]
        largest_radius = max(radii) if radii else 0.5
        spacing = max(0.5, (2.0 * float(largest_radius)) + 0.1)
        cols = int(max(1, math.ceil(math.sqrt(len(models)))))
        rows = int(max(1, math.ceil(float(len(models)) / float(cols))))
        x_origin = float(x) - (float(cols - 1) * float(spacing) * 0.5)
        y_origin = float(y) - (float(rows - 1) * float(spacing) * 0.5)

        payload_positions: list[dict] = []
        for index, model in enumerate(models):
            model_id = str(get_entity_id(model) or "")
            if not model_id:
                return []
            col = int(index % cols)
            row = int(index // cols)
            model_x = float(x_origin + (float(col) * float(spacing)))
            model_y = float(y_origin + (float(row) * float(spacing)))
            payload_positions.append(
                {
                    "model_id": model_id,
                    "position": [float(model_x), float(model_y), 0.0],
                    "facing": 0.0,
                }
            )
        return payload_positions

    @staticmethod
    def _can_build_fast_grid_deployment(unit: object) -> bool:
        count = len([model for model in list(getattr(unit, "models", []) or []) if model is not None])
        return count == 1 or count >= 6

    @staticmethod
    def _uses_fast_grid_deployment(unit: object) -> bool:
        count = len([model for model in list(getattr(unit, "models", []) or []) if model is not None])
        return count >= 6

    @staticmethod
    def _refines_surface_variants(unit: object) -> bool:
        count = len([model for model in list(getattr(unit, "models", []) or []) if model is not None])
        return count <= 5

    @staticmethod
    def _model_position_cache_key(
        unit: object,
        *,
        mode: str,
        x: float,
        y: float,
    ) -> tuple[str, str, float, float]:
        unit_id = str(get_entity_id(unit) or "")
        return (
            str(unit_id),
            str(mode or ""),
            round(float(x), 3),
            round(float(y), 3),
        )

    def _build_model_positions(
        self,
        unit: object,
        *,
        x: float,
        y: float,
        boundary_repulsors: list[object],
        search_context,
    ) -> list[dict]:
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return []
        model_positions = calculate_prospective_model_positions(
            unit,
            float(x),
            float(y),
            game_map,
            avoid_friendly_units=True,
            boundary_repulsors=boundary_repulsors,
            search_context=search_context,
            calculate_facing=False,
            resolve_surface_height=False,
        )
        models = list(getattr(unit, "models", []) or [])
        if not model_positions or len(model_positions) != len(models):
            return []
        payload_positions: list[dict] = []
        for model, pos in zip(models, model_positions):
            model_id = str(get_entity_id(model) or "")
            if not model_id:
                return []
            model_x, model_y, model_z, model_facing = pos
            payload_positions.append(
                {
                    "model_id": model_id,
                    "position": [float(model_x), float(model_y), float(model_z)],
                    "facing": float(model_facing),
                }
            )
        return payload_positions

    def _build_model_positions_variants(
        self,
        unit: object,
        *,
        x: float,
        y: float,
        boundary_repulsors: list[object],
        search_context,
        refine_surfaces: bool = True,
    ) -> list[list[dict]]:
        return list(
            self._build_detailed_model_positions_variants(
                unit,
                x=float(x),
                y=float(y),
                boundary_repulsors=boundary_repulsors,
                search_context=search_context,
                refine_surfaces=bool(refine_surfaces),
            )
        )

    def _build_detailed_model_positions_variants(
        self,
        unit: object,
        *,
        x: float,
        y: float,
        boundary_repulsors: list[object],
        search_context,
        refine_surfaces: bool = False,
    ) -> list[list[dict]]:
        base_positions = self._build_model_positions(
            unit,
            x=float(x),
            y=float(y),
            boundary_repulsors=boundary_repulsors,
            search_context=search_context,
        )
        position_sets: list[list[dict]] = []
        if base_positions:
            position_sets.append(list(base_positions))
        else:
            for alt_x, alt_y in self._local_anchor_search_points(unit, x=float(x), y=float(y)):
                alt_positions = self._build_model_positions(
                    unit,
                    x=float(alt_x),
                    y=float(alt_y),
                    boundary_repulsors=boundary_repulsors,
                    search_context=search_context,
                )
                if alt_positions:
                    position_sets.append(list(alt_positions))
        if not position_sets:
            return []
        if not bool(refine_surfaces):
            return [
                [dict(entry or {}) for entry in list(base_positions or [])]
                for base_positions in list(position_sets or [])
                if base_positions
            ]
        models = list(getattr(unit, "models", []) or [])
        per_model_surfaces: list[list[float]] = []

        variants: list[list[dict]] = []
        seen: set[tuple[tuple[str, float, float, float, float], ...]] = set()

        def _add_variant(positions: list[dict]) -> None:
            key_tuple = self._model_positions_signature(positions)
            if not key_tuple:
                return
            if key_tuple in seen:
                return
            seen.add(key_tuple)
            variants.append(positions)

        for base_positions in position_sets:
            if not models or len(models) != len(base_positions):
                _add_variant(list(base_positions))
                continue

            per_model_surfaces = []
            for model, entry in zip(models, base_positions):
                pos = list(entry.get("position", []) or [])
                if len(pos) < 3:
                    per_model_surfaces = []
                    break
                per_model_surfaces.append(
                    self._ruins_surface_z_options_for_model(
                        model,
                        x=float(pos[0]),
                        y=float(pos[1]),
                        current_z=float(pos[2]),
                    )
                )

            if not per_model_surfaces or len(per_model_surfaces) != len(base_positions):
                _add_variant(list(base_positions))
                continue

            mixed_high = self._with_model_surface_selection(base_positions, per_model_surfaces, select_max=True)
            if mixed_high:
                _add_variant(mixed_high)

            common_surfaces: set[float] = set(round(v, 3) for v in list(per_model_surfaces[0] or []))
            for values in per_model_surfaces[1:]:
                common_surfaces &= set(round(v, 3) for v in list(values or []))
            for surface_z in sorted(common_surfaces, reverse=True):
                uniform = self._with_uniform_surface(base_positions, z_surface=float(surface_z))
                _add_variant(uniform)

            _add_variant(list(base_positions))
        return variants

    @staticmethod
    def _with_uniform_surface(base_positions: list[dict], *, z_surface: float) -> list[dict]:
        updated: list[dict] = []
        for entry in list(base_positions or []):
            pos = list(entry.get("position", []) or [])
            if len(pos) < 3:
                continue
            next_entry = dict(entry)
            next_entry["position"] = [float(pos[0]), float(pos[1]), float(z_surface)]
            updated.append(next_entry)
        return updated

    @staticmethod
    def _with_model_surface_selection(
        base_positions: list[dict],
        per_model_surfaces: list[list[float]],
        *,
        select_max: bool,
    ) -> list[dict]:
        updated: list[dict] = []
        for entry, surfaces in zip(list(base_positions or []), list(per_model_surfaces or [])):
            pos = list(entry.get("position", []) or [])
            if len(pos) < 3:
                continue
            z_surface = float(pos[2])
            if surfaces:
                z_surface = float(max(surfaces)) if select_max else float(min(surfaces))
            next_entry = dict(entry)
            next_entry["position"] = [float(pos[0]), float(pos[1]), float(z_surface)]
            updated.append(next_entry)
        return updated

    def _ruins_surface_z_options_for_model(self, model: object, *, x: float, y: float, current_z: float) -> list[float]:
        options: set[float] = {round(float(current_z), 3)}
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return sorted(options)

        base = getattr(model, "model_base", None)
        base_geom = None
        if base is not None:
            get_shape_at = getattr(base, "get_base_shape_at", None)
            if callable(get_shape_at):
                facing = float(getattr(base, "facing", 0.0) or 0.0)
                base_geom = get_shape_at(float(x), float(y), facing)

        for terrain in list(getattr(game_map, "terrain_features", []) or []):
            terrain_type = str(getattr(getattr(terrain, "terrain_type", None), "name", "") or "")
            if terrain_type != "RUINS":
                continue
            footprint = getattr(terrain, "footprint", None)
            if footprint is None:
                continue
            if base_geom is None:
                contains = getattr(footprint, "contains", None)
                if not callable(contains):
                    continue
                from shapely.geometry import Point
                if not bool(contains(Point(float(x), float(y)))):
                    continue
            else:
                intersects = getattr(base_geom, "intersects", None)
                if not callable(intersects):
                    continue
                if not bool(intersects(footprint)):
                    continue

            for floor in list(getattr(terrain, "floors", []) or []):
                if not isinstance(floor, dict):
                    continue
                poly = floor.get("polygon")
                if poly is None:
                    continue
                if base_geom is None:
                    contains = getattr(poly, "contains", None)
                    if not callable(contains):
                        continue
                    from shapely.geometry import Point
                    if not bool(contains(Point(float(x), float(y)))):
                        continue
                else:
                    covers = getattr(poly, "covers", None)
                    intersects = getattr(poly, "intersects", None)
                    on_floor = bool(covers(base_geom)) if callable(covers) else False
                    if not on_floor and callable(intersects):
                        on_floor = bool(intersects(base_geom))
                    if not on_floor:
                        continue
                elevation = float(floor.get("elevation", 0.0) or 0.0)
                thickness = float(floor.get("thickness", 0.0) or 0.0)
                options.add(round(elevation + thickness, 3))

        return sorted(options)

    def _infiltrate_candidate_groups(self, unit: object, *, already_deployed: Iterable[object]) -> list[list[tuple[float, float]]]:
        board_bounds = self._zone_bounds({})
        if board_bounds is None:
            return []
        min_x, max_x, min_y, max_y = board_bounds
        board_zone = {
            "name": "board",
            "x_range": [min_x, max_x],
            "y_range": [min_y, max_y],
        }
        center_x = (float(min_x) + float(max_x)) / 2.0
        center_y = (float(min_y) + float(max_y)) / 2.0
        offsets = self._ordered_offsets(unit=unit, already_deployed=already_deployed)
        around_center: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        for dx, dy in offsets:
            x = float(center_x + dx)
            y = float(center_y + dy)
            if not self._point_in_zone(board_zone, x, y):
                continue
            key = (round(x, 3), round(y, 3))
            if key in seen:
                continue
            seen.add(key)
            around_center.append((x, y))
        return [
            around_center,
            self._candidate_positions_exhaustive_for_bounds(unit, bounds=(min_x, max_x, min_y, max_y)),
        ]

    def _candidate_positions_exhaustive_for_bounds(
        self,
        unit: object,
        *,
        bounds: tuple[float, float, float, float],
        anchor_limit: int | None = None,
    ) -> list[tuple[float, float]]:
        min_x, max_x, min_y, max_y = bounds
        if min_x > max_x or min_y > max_y:
            return []
        center_x = (float(min_x) + float(max_x)) / 2.0
        center_y = (float(min_y) + float(max_y)) / 2.0
        unit_id = str(get_entity_id(unit) or "")

        candidates: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        for step in (4.0, 2.0, 1.0):
            offsets = (0.0, step / 2.0)
            for off_y in offsets:
                ys = self._axis_points(min_y, max_y, step=step, offset=off_y)
                for off_x in offsets:
                    xs = self._axis_points(min_x, max_x, step=step, offset=off_x)
                    for y in ys:
                        for x in xs:
                            key = (round(float(x), 3), round(float(y), 3))
                            if key in seen:
                                continue
                            seen.add(key)
                            candidates.append((float(x), float(y)))

        def _sort_key(point: tuple[float, float]) -> tuple[float, str]:
            x, y = point
            dist_sq = (float(x) - float(center_x)) ** 2 + (float(y) - float(center_y)) ** 2
            token = f"{unit_id}:{x:.3f}:{y:.3f}"
            tie = hashlib.sha256(token.encode("utf-8")).hexdigest()
            return (float(dist_sq), tie)

        candidates.sort(key=_sort_key)
        limit = int(self._exhaustive_anchor_limit) if anchor_limit is None else int(anchor_limit)
        return candidates[: max(0, limit)]

    @staticmethod
    def _unit_has_infiltrate(unit: object) -> bool:
        has_infiltrate = getattr(unit, "has_infiltrate", None)
        return bool(has_infiltrate()) if callable(has_infiltrate) else False

    def build_deployment_intent(
        self,
        *,
        decision_kind: str,
        player: Optional[Player] = None,
        deployment_zone: Optional[dict] = None,
        unit: Optional[object] = None,
        deployable_units: Optional[list[object]] = None,
        already_deployed: Optional[list[object]] = None,
    ) -> dict:
        resolved_player = player
        if resolved_player is None:
            resolved_player = self._resolve_player_for_unit(unit) if unit is not None else None
        if resolved_player is None:
            resolved_player = self._resolve_player_for_units(deployable_units or [])
        if resolved_player is None and self._active_player_id:
            resolved_player = self._resolve_player_by_id(self._active_player_id)
        if resolved_player is not None:
            player_id = str(getattr(resolved_player, "id", "") or "")
            if player_id:
                self._active_player_id = player_id

        if self._pregame_agent is None or resolved_player is None:
            return {}
        return self._pregame_agent.deployment_intent(
            player=resolved_player,
            decision_kind=str(decision_kind or ""),
            deployment_zone=dict(deployment_zone or {}) if isinstance(deployment_zone, dict) else None,
            unit=unit,
            deployable_units=list(deployable_units or []),
            already_deployed=list(already_deployed or []),
        )

    def build_deployment_decision_context(
        self,
        *,
        decision_kind: str,
        player: Optional[Player] = None,
        deployment_zone: Optional[dict] = None,
        unit: Optional[object] = None,
        deployable_units: Optional[list[object]] = None,
        already_deployed: Optional[list[object]] = None,
    ) -> dict:
        del unit, deployable_units, already_deployed
        resolved_player = player
        if resolved_player is None and self._active_player_id:
            resolved_player = self._resolve_player_by_id(self._active_player_id)
        if self._pregame_agent is None or resolved_player is None:
            return {}
        return self._pregame_agent.decision_context(
            player=resolved_player,
            deployment_zone=dict(deployment_zone or {}) if isinstance(deployment_zone, dict) else None,
            decision_kind=str(decision_kind or ""),
        )

    def build_deployment_model_positions(self, unit: object, position: tuple[float, float]) -> list[dict]:
        unit_id = str(get_entity_id(unit) or "")
        if unit_id:
            cached = self._selected_payload_by_unit_id.pop(unit_id, None)
            if cached is not None:
                (cx, cy), payload = cached
                if abs(float(cx) - float(position[0])) <= 1e-3 and abs(float(cy) - float(position[1])) <= 1e-3:
                    return [dict(entry) for entry in list(payload or [])]

        boundary_repulsors = self._deployment_boundary_repulsors(unit)
        search_context = self._build_deployment_search_context(
            unit,
            boundary_repulsors=boundary_repulsors,
        )
        payload_variants = self._build_model_positions_variants(
            unit,
            x=float(position[0]),
            y=float(position[1]),
            boundary_repulsors=boundary_repulsors,
            search_context=search_context,
        )
        return list(payload_variants[0] if payload_variants else [])

    def _reserve_group_roots(self, army: object) -> list[object]:
        iter_roots = getattr(army, "_iter_reserve_group_roots", None)
        if callable(iter_roots):
            roots = [unit for unit in list(iter_roots() or []) if unit is not None]
            roots.sort(key=lambda unit: str(get_entity_id(unit) or ""))
            return roots
        units = [unit for unit in list(getattr(army, "units", []) or []) if unit is not None]
        units.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return units

    @staticmethod
    def _zone_sort_key(zone: dict) -> tuple[str, str]:
        zone_type = str(zone.get("zone_type", "") or "")
        name = str(zone.get("name", "") or "")
        return (zone_type, name)

    @staticmethod
    def _player_id_for_unit(unit: object) -> str:
        if unit is None:
            return ""
        parent_getter = getattr(unit, "get_parent_army", None)
        army = parent_getter() if callable(parent_getter) else getattr(unit, "parent_army", None)
        player = getattr(army, "player", None) if army is not None else None
        return str(getattr(player, "id", "") or "")

    def _zone_center(self, deployment_zone: dict) -> tuple[float, float]:
        battlefield = getattr(self.game, "battlefield", None)
        width = float(getattr(battlefield, "width", 60.0) or 60.0)
        height = float(getattr(battlefield, "height", 44.0) or 44.0)
        return _zone_center_shared(
            deployment_zone,
            default_bounds=(0.0, width, 0.0, height),
        )

    def _candidate_positions(
        self,
        unit: object,
        deployment_zone: dict,
        already_deployed: list[object],
    ) -> list[tuple[float, float]]:
        battlefield = getattr(self.game, "battlefield", None)
        width = float(getattr(battlefield, "width", 60.0) or 60.0)
        height = float(getattr(battlefield, "height", 44.0) or 44.0)
        return _lattice_candidate_positions_shared(
            deployment_zone,
            unit_id=str(get_entity_id(unit) or ""),
            occupied_count=int(len(list(already_deployed or []))),
            lattice_step=float(self.lattice_step),
            default_bounds=(0.0, width, 0.0, height),
        )

    def _candidate_positions_exhaustive(self, unit: object, deployment_zone: dict) -> list[tuple[float, float]]:
        battlefield = getattr(self.game, "battlefield", None)
        width = float(getattr(battlefield, "width", 60.0) or 60.0)
        height = float(getattr(battlefield, "height", 44.0) or 44.0)
        return _exhaustive_lattice_candidate_positions_shared(
            deployment_zone,
            unit_id=str(get_entity_id(unit) or ""),
            exhaustive_lattice_step=float(self.exhaustive_lattice_step),
            exhaustive_anchor_limit=int(self._exhaustive_anchor_limit),
            default_bounds=(0.0, width, 0.0, height),
        )

    @staticmethod
    def _axis_points(start: float, end: float, *, step: float, offset: float) -> list[float]:
        return _axis_points_shared(start, end, step=step, offset=offset)

    def _zone_bounds(self, deployment_zone: dict) -> tuple[float, float, float, float] | None:
        battlefield = getattr(self.game, "battlefield", None)
        width = float(getattr(battlefield, "width", 0.0) or 0.0)
        height = float(getattr(battlefield, "height", 0.0) or 0.0)
        default_bounds = (0.0, width, 0.0, height) if width > 0.0 and height > 0.0 else None
        return _zone_bounds_shared(deployment_zone, default_bounds=default_bounds)

    def _point_in_zone(self, deployment_zone: dict, x: float, y: float) -> bool:
        return _point_in_zone_shared(deployment_zone, x, y)

    def _ordered_offsets(self, *, unit: object, already_deployed: Iterable[object]) -> list[tuple[float, float]]:
        return _ordered_offsets_shared(
            unit_id=str(get_entity_id(unit) or ""),
            occupied_count=int(len(list(already_deployed or []))),
            lattice_step=float(self.lattice_step),
        )

    def _resolve_player_by_id(self, player_id: str) -> Optional[Player]:
        player_key = str(player_id or "")
        if not player_key:
            return None
        for player in list(getattr(self.game, "players", []) or []):
            if player is None:
                continue
            if str(getattr(player, "id", "") or "") == player_key:
                return player
        return None

    def _resolve_player_for_unit(self, unit: Optional[object]) -> Optional[Player]:
        if unit is None:
            return None
        player_id = self._player_id_for_unit(unit)
        if player_id:
            return self._resolve_player_by_id(player_id)
        return None

    def _resolve_player_for_units(self, units: Iterable[object]) -> Optional[Player]:
        candidates: list[tuple[str, Player]] = []
        for unit in list(units or []):
            player = self._resolve_player_for_unit(unit)
            if player is None:
                continue
            player_id = str(getattr(player, "id", "") or "")
            if not player_id:
                continue
            candidates.append((player_id, player))
        if not candidates:
            return None
        candidates.sort(key=lambda entry: entry[0])
        return candidates[0][1]

    @staticmethod
    def _match_zone_choice(chosen_zone: dict, available_zones: list[dict]) -> Optional[dict]:
        if not isinstance(chosen_zone, dict):
            return None
        for zone in list(available_zones or []):
            if zone is chosen_zone:
                return zone
            if dict(zone or {}) == dict(chosen_zone or {}):
                return zone
        return None

    def _semantic_anchor_candidates(
        self,
        unit: object,
        deployment_zone: dict,
        *,
        already_deployed: Iterable[object],
        player: Optional[Player],
    ) -> list[tuple[float, float]]:
        if self._pregame_agent is None or player is None:
            return []
        anchors = self._pregame_agent.anchor_candidates_for_unit(
            player=player,
            unit=unit,
            deployment_zone=dict(deployment_zone or {}),
            already_deployed=list(already_deployed or []),
        )
        if not anchors:
            return []
        offsets = [0.0, self.lattice_step, -self.lattice_step, self.lattice_step * 0.5, -self.lattice_step * 0.5]
        candidates: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        for anchor_x, anchor_y in list(anchors or []):
            for dx in offsets:
                for dy in offsets:
                    x = float(anchor_x) + float(dx)
                    y = float(anchor_y) + float(dy)
                    key = (round(x, 3), round(y, 3))
                    if key in seen:
                        continue
                    seen.add(key)
                    if not self._point_in_zone(deployment_zone, x, y):
                        continue
                    candidates.append((x, y))
        return candidates

    def _ranked_option_id(self, request: DecisionRequest) -> Optional[str]:
        if self._deployment_ranker is None:
            return None
        action_id = str(self._deployment_ranker.choose_action_id(request) or "")
        if not action_id:
            return None
        return self._option_id_for_action_id(request, action_id)

    def _lookahead_option_id(self, request: DecisionRequest) -> Optional[str]:
        context = dict(getattr(request, "context", {}) or {})
        raw_lookahead = context.get("deployment_lookahead")
        if isinstance(raw_lookahead, dict):
            enabled = self._truthy(raw_lookahead.get("enabled", False))
        else:
            enabled = self._truthy(raw_lookahead)
        if not enabled:
            return None

        candidates = list(getattr(request, "candidates", []) or [])
        mask = [bool(value) for value in list(getattr(request, "mask", []) or [])]
        best_action_id = ""
        best_value = float("-inf")
        best_tie = ""
        has_lookahead_metadata = False
        for idx, candidate in enumerate(candidates):
            if idx < len(mask) and not bool(mask[idx]):
                continue
            metadata = dict(candidate.metadata or {})
            if "lookahead_total_value" not in metadata:
                continue
            has_lookahead_metadata = True
            score = self._safe_float(metadata.get("lookahead_total_value"), default=float("-inf"))
            action_id = str(getattr(candidate, "action_id", "") or "")
            tie = action_id
            if (score > best_value) or (score == best_value and tie < best_tie):
                best_value = float(score)
                best_tie = tie
                best_action_id = action_id
        if not has_lookahead_metadata or not best_action_id:
            return None
        return self._option_id_for_action_id(request, best_action_id)

    @staticmethod
    def _truthy(value: object) -> bool:
        if isinstance(value, bool):
            return bool(value)
        if isinstance(value, (int, float)):
            return bool(value)
        token = str(value or "").strip().lower()
        return token in {"1", "true", "yes", "on", "enabled"}

    @staticmethod
    def _safe_float(value: object, *, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _option_id_for_action_id(request: DecisionRequest, action_id: str) -> Optional[str]:
        if not action_id:
            return None
        for option in list(getattr(request, "options", []) or []):
            option_id = str(getattr(option, "option_id", "") or "")
            if not option_id:
                continue
            if request.action_id_for_option_id(option_id) == action_id:
                return option_id
        return None
