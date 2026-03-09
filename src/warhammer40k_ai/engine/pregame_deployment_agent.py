from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Iterable, Optional

from .board_affordances import (
    BoardAffordanceSummary,
    compute_board_affordance_summary,
    deployment_zone_from_player,
    sorted_units,
    zone_area_frontage_depth,
)
from .unit_role_inference import (
    ROLE_ANCHOR,
    ROLE_AURA_HUB,
    ROLE_COUNTERCHARGE,
    ROLE_FRAGILE_GUNLINE,
    ROLE_HOME_HOLDER,
    ROLE_INFILTRATOR,
    ROLE_MELEE_MISSILE,
    ROLE_RESERVE_DROPPER,
    ROLE_SCREEN,
    ROLE_SCOUT,
    UnitRoleProfile,
    infer_army_role_profiles,
)
from ..utility.entity_ids import maybe_entity_id


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _round6(value: float) -> float:
    return float(round(float(value), 6))


def _clamp(value: float, *, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _board_dimensions(game: object) -> tuple[float, float]:
    game_map = getattr(game, "map", None)
    width = _safe_float(getattr(game_map, "width", 60.0), 60.0)
    height = _safe_float(getattr(game_map, "height", 44.0), 44.0)
    return (width, height)


def _zone_center(zone: dict | None, *, board_width: float, board_height: float) -> tuple[float, float]:
    area, frontage, depth = zone_area_frontage_depth(zone, board_width=board_width, board_height=board_height)
    del area, frontage, depth
    zone_data = dict(zone or {})
    mission_zones = list(zone_data.get("mission_zones", []) or [])
    xs: list[float] = []
    ys: list[float] = []
    for mission_zone in mission_zones:
        for vertex in list(getattr(mission_zone, "vertices", []) or []):
            if not isinstance(vertex, (list, tuple)) or len(vertex) < 2:
                continue
            xs.append(_safe_float(vertex[0]))
            ys.append(_safe_float(vertex[1]))
    if xs and ys:
        return (float(sum(xs) / float(len(xs))), float(sum(ys) / float(len(ys))))
    x_range = zone_data.get("x_range")
    y_range = zone_data.get("y_range")
    if isinstance(x_range, (list, tuple)) and isinstance(y_range, (list, tuple)) and len(x_range) >= 2 and len(y_range) >= 2:
        return (
            float((_safe_float(x_range[0]) + _safe_float(x_range[1])) * 0.5),
            float((_safe_float(y_range[0]) + _safe_float(y_range[1])) * 0.5),
        )
    return (float(board_width) * 0.5, float(board_height) * 0.5)


def _zone_bounds(zone: dict | None, *, board_width: float, board_height: float) -> tuple[float, float, float, float]:
    zone_data = dict(zone or {})
    mission_zones = list(zone_data.get("mission_zones", []) or [])
    xs: list[float] = []
    ys: list[float] = []
    for mission_zone in mission_zones:
        for vertex in list(getattr(mission_zone, "vertices", []) or []):
            if not isinstance(vertex, (list, tuple)) or len(vertex) < 2:
                continue
            xs.append(_safe_float(vertex[0]))
            ys.append(_safe_float(vertex[1]))
    if xs and ys:
        return (min(xs), max(xs), min(ys), max(ys))
    x_range = zone_data.get("x_range")
    y_range = zone_data.get("y_range")
    if isinstance(x_range, (list, tuple)) and isinstance(y_range, (list, tuple)) and len(x_range) >= 2 and len(y_range) >= 2:
        return (
            min(_safe_float(x_range[0]), _safe_float(x_range[1])),
            max(_safe_float(x_range[0]), _safe_float(x_range[1])),
            min(_safe_float(y_range[0]), _safe_float(y_range[1])),
            max(_safe_float(y_range[0]), _safe_float(y_range[1])),
        )
    return (0.0, float(board_width), 0.0, float(board_height))


def _normalized_vector(dx: float, dy: float) -> tuple[float, float]:
    mag = float((float(dx) * float(dx) + float(dy) * float(dy)) ** 0.5)
    if mag <= 1e-9:
        return (0.0, 0.0)
    return (float(dx) / mag, float(dy) / mag)


@dataclass(frozen=True)
class ArmyRoleSummary:
    unit_count: int
    screen_score: float
    anchor_score: float
    melee_score: float
    gunline_score: float
    reserve_dropper_score: float
    scout_score: float
    infiltrator_score: float
    aura_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_count": int(self.unit_count),
            "screen_score": float(self.screen_score),
            "anchor_score": float(self.anchor_score),
            "melee_score": float(self.melee_score),
            "gunline_score": float(self.gunline_score),
            "reserve_dropper_score": float(self.reserve_dropper_score),
            "scout_score": float(self.scout_score),
            "infiltrator_score": float(self.infiltrator_score),
            "aura_score": float(self.aura_score),
        }


class PregameDeploymentAgent:
    def __init__(self, game: object) -> None:
        self.game = game
        self._role_cache: dict[str, dict[str, UnitRoleProfile]] = {}
        self._affordance_cache: dict[str, BoardAffordanceSummary] = {}

    def _cache_key_for_zone(self, zone: dict | None) -> str:
        zone_data = dict(zone or {})
        zone_name = str(zone_data.get("name", "") or "")
        zone_type = str(zone_data.get("zone_type", "") or "")
        payload = f"{zone_type}|{zone_name}|{zone_data.get('x_range')}|{zone_data.get('y_range')}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        return f"zone:{digest}"

    def _player_units(self, player: object) -> list[object]:
        army = getattr(player, "get_army", None)
        if callable(army):
            army = army()
        else:
            army = getattr(player, "army", None)
        return sorted_units(list(getattr(army, "units", []) or []))

    def role_profiles_for_player(self, player: object) -> dict[str, UnitRoleProfile]:
        player_id = str(getattr(player, "id", "") or "")
        if player_id in self._role_cache:
            return dict(self._role_cache[player_id])
        profiles = infer_army_role_profiles(self._player_units(player))
        self._role_cache[player_id] = dict(profiles)
        return dict(profiles)

    def _army_role_summary(self, player: object) -> ArmyRoleSummary:
        profiles = self.role_profiles_for_player(player)
        if not profiles:
            return ArmyRoleSummary(
                unit_count=0,
                screen_score=0.0,
                anchor_score=0.0,
                melee_score=0.0,
                gunline_score=0.0,
                reserve_dropper_score=0.0,
                scout_score=0.0,
                infiltrator_score=0.0,
                aura_score=0.0,
            )
        unit_count = max(1, len(profiles))
        def _avg(role: str) -> float:
            return _round6(
                sum(float(profile.role_scores.get(role, 0.0)) for profile in profiles.values()) / float(unit_count)
            )
        return ArmyRoleSummary(
            unit_count=int(unit_count),
            screen_score=_avg(ROLE_SCREEN),
            anchor_score=_avg(ROLE_ANCHOR),
            melee_score=_avg(ROLE_MELEE_MISSILE),
            gunline_score=_avg(ROLE_FRAGILE_GUNLINE),
            reserve_dropper_score=_avg(ROLE_RESERVE_DROPPER),
            scout_score=_avg(ROLE_SCOUT),
            infiltrator_score=_avg(ROLE_INFILTRATOR),
            aura_score=_avg(ROLE_AURA_HUB),
        )

    def board_affordances(self, *, zone: Optional[dict]) -> BoardAffordanceSummary:
        key = self._cache_key_for_zone(zone)
        if key in self._affordance_cache:
            return self._affordance_cache[key]
        summary = compute_board_affordance_summary(self.game, deployment_zone=zone)
        self._affordance_cache[key] = summary
        return summary

    def _zone_score(self, *, player: object, zone: dict) -> float:
        board_width, board_height = _board_dimensions(self.game)
        area, frontage, depth = zone_area_frontage_depth(zone, board_width=board_width, board_height=board_height)
        affordance = self.board_affordances(zone=zone)
        army_summary = self._army_role_summary(player)

        area_norm = _clamp(area / 850.0, low=0.15, high=2.0)
        frontage_norm = _clamp(frontage / 30.0, low=0.15, high=2.0)
        depth_norm = _clamp(depth / 20.0, low=0.15, high=2.0)
        hidden_count = float(len(affordance.hidden_staging_pockets))
        safe_firing_count = float(len(affordance.safe_firing_pockets))
        nest_count = float(len(affordance.upper_floor_fire_nests))
        corridor_count = float(affordance.breachable_melee_corridors)
        tight_lane_count = float(affordance.opening_constrained_vehicle_corridors)
        hidden_cell_count = float(getattr(affordance, "hidden_staging_cell_count", 0))
        expose_cell_count = float(getattr(affordance, "must_expose_to_advance_cell_count", 0))
        los_tunnel_count = float(getattr(affordance, "los_tunnel_count", 0))
        infantry_approach_quality = float(getattr(affordance, "infantry_objective_approach_quality", 0.0))
        vehicle_approach_quality = float(getattr(affordance, "vehicle_objective_approach_quality", 0.0))

        score = 0.0
        score += area_norm * 0.35
        score += frontage_norm * (0.12 + army_summary.screen_score * 0.22)
        score += depth_norm * (0.12 + army_summary.melee_score * 0.25 + army_summary.anchor_score * 0.08)
        score += hidden_count * (0.08 + army_summary.gunline_score * 0.1)
        score += safe_firing_count * (0.05 + army_summary.gunline_score * 0.09)
        score += nest_count * (0.04 + army_summary.gunline_score * 0.06)
        score += corridor_count * (0.05 + army_summary.melee_score * 0.08)
        score += tight_lane_count * (0.03 + army_summary.screen_score * 0.04)
        score += hidden_cell_count * (0.008 + army_summary.gunline_score * 0.02)
        score -= expose_cell_count * (0.01 + army_summary.gunline_score * 0.015)
        score += los_tunnel_count * (0.04 + army_summary.melee_score * 0.1)
        score += infantry_approach_quality * (0.18 + army_summary.melee_score * 0.16 + army_summary.screen_score * 0.08)
        score += vehicle_approach_quality * (0.08 + army_summary.anchor_score * 0.06)
        score += army_summary.infiltrator_score * 0.05
        score += army_summary.scout_score * 0.04
        score += army_summary.aura_score * 0.03
        return float(score)

    def choose_deployment_zone(self, *, player: object, available_zones: list[dict]) -> dict:
        zones = [dict(zone or {}) for zone in list(available_zones or []) if isinstance(zone, dict)]
        if not zones:
            raise ValueError("No deployment zones were provided.")
        scored: list[tuple[float, str, dict]] = []
        for zone in zones:
            score = self._zone_score(player=player, zone=zone)
            zone_name = str(zone.get("name", "") or "")
            zone_type = str(zone.get("zone_type", "") or "")
            tie = f"{zone_type}:{zone_name}"
            scored.append((float(score), tie, zone))
        scored.sort(key=lambda entry: (-entry[0], entry[1]))
        return dict(scored[0][2])

    def deployment_intent(
        self,
        *,
        player: object,
        decision_kind: str,
        deployment_zone: Optional[dict] = None,
        unit: Optional[object] = None,
        deployable_units: Optional[Iterable[object]] = None,
        already_deployed: Optional[Iterable[object]] = None,
    ) -> dict[str, Any]:
        summary = self._army_role_summary(player)
        affordance = self.board_affordances(zone=deployment_zone)
        desired_affordances = {
            "SAFE_STAGING",
            "SCREEN_DEPTH",
            "RESERVE_DENIAL",
            "COUNTERCHARGE_POCKET",
        }
        if summary.melee_score >= 0.6:
            desired_affordances.add("LOS_TUNNEL_ADVANCE")
            desired_affordances.add("MIDBOARD_STAGING")
        if summary.gunline_score >= 0.55:
            desired_affordances.add("SAFE_FIRING_POCKET")
            desired_affordances.add("HOME_ANCHOR")
        if int(getattr(affordance, "los_tunnel_count", 0)) > 0:
            desired_affordances.add("LOS_TUNNEL_ADVANCE")
        if int(getattr(affordance, "must_expose_to_advance_cell_count", 0)) > 3:
            desired_affordances.add("EXPOSURE_MINIMIZATION")
        if summary.infiltrator_score >= 0.5 or summary.scout_score >= 0.5:
            desired_affordances.add("FORWARD_SCREEN")
        target_objective_ids = [str(entry.get("objective_id", "") or "") for entry in affordance.objective_lane_distances if str(entry.get("objective_id", "") or "")]
        threatened_lane_ids = list(affordance.reserve_entry_lane_quality.keys())
        reserve_targets = []
        for entry in list(affordance.objective_lane_distances or [])[:2]:
            objective_id = str(entry.get("objective_id", "") or "")
            if objective_id:
                reserve_targets.append(f"objective:{objective_id}")

        score_weight = 0.3 + summary.anchor_score * 0.05
        deny_weight = 0.2 + summary.screen_score * 0.08 + summary.infiltrator_score * 0.05
        safety_weight = 0.26 + summary.gunline_score * 0.1 + summary.anchor_score * 0.06
        staging_weight = 0.18 + summary.melee_score * 0.12
        reserve_deny_weight = 0.2 + summary.screen_score * 0.05 + summary.reserve_dropper_score * 0.02
        screen_weight = 0.2 + summary.screen_score * 0.12
        countercharge_weight = 0.15 + summary.melee_score * 0.08
        cover_weight = 0.2 + summary.gunline_score * 0.08
        los_weight = 0.1 + summary.gunline_score * 0.04 + summary.melee_score * 0.03
        aura_weight = 0.1 + summary.aura_score * 0.08

        if str(decision_kind or "") == "placement" and unit is not None:
            unit_id = str(maybe_entity_id(unit) or "")
            profile = self.role_profiles_for_player(player).get(unit_id)
            if profile is not None:
                screen_weight += float(profile.role_scores.get(ROLE_SCREEN, 0.0)) * 0.05
                staging_weight += float(profile.role_scores.get(ROLE_MELEE_MISSILE, 0.0)) * 0.06
                safety_weight += float(profile.role_scores.get(ROLE_HOME_HOLDER, 0.0)) * 0.06
                reserve_deny_weight += float(profile.role_scores.get(ROLE_RESERVE_DROPPER, 0.0)) * 0.05

        intent = {
            "target_objective_ids": sorted(set(target_objective_ids)),
            "desired_affordances": sorted(desired_affordances),
            "threatened_lane_ids": sorted(set(threatened_lane_ids)),
            "reserve_deny_targets": sorted(set(reserve_targets)),
            "weights": {
                "score": _round6(score_weight),
                "deny": _round6(deny_weight),
                "safety": _round6(safety_weight),
                "staging": _round6(staging_weight),
                "reserve_deny": _round6(reserve_deny_weight),
                "screen": _round6(screen_weight),
                "countercharge": _round6(countercharge_weight),
                "cover": _round6(cover_weight),
                "los": _round6(los_weight),
                "aura": _round6(aura_weight),
            },
            "anchors": {
                "deployment_center_x": str(_round6(affordance.deployment_center_x)),
                "deployment_center_y": str(_round6(affordance.deployment_center_y)),
            },
            "constraint_toggles": {
                "decision_kind": str(decision_kind or ""),
                "already_deployed_count": int(len(list(already_deployed or []))),
                "deployable_count": int(len(list(deployable_units or []))),
                "threat_lane_count": int(affordance.threat_lane_count),
            },
        }
        return intent

    def decision_context(
        self,
        *,
        player: object,
        deployment_zone: Optional[dict],
        decision_kind: str = "",
    ) -> dict[str, Any]:
        summary = self._army_role_summary(player)
        affordance = self.board_affordances(zone=deployment_zone)
        decision_kind_key = str(decision_kind or "").strip().lower()
        candidate_kinds: list[str]
        if decision_kind_key == "zone_choice":
            candidate_kinds = ["deployment_zone"]
        elif decision_kind_key == "next_unit":
            candidate_kinds = ["deployment_commit_order"]
        elif decision_kind_key == "reserves":
            candidate_kinds = ["deployment_reserves"]
        elif decision_kind_key == "scout":
            candidate_kinds = ["deployment_scout"]
        elif decision_kind_key == "placement":
            candidate_kinds = ["deployment_move"]
        else:
            candidate_kinds = [
                "deployment_zone",
                "deployment_commit_order",
                "deployment_reserves",
                "deployment_scout",
                "deployment_move",
            ]
        lookahead_depth = 2 if decision_kind_key in {"zone_choice", "reserves", "placement"} else 1
        lookahead_branch_count = 3 if (summary.screen_score >= 0.35 or summary.melee_score >= 0.45) else 2
        lookahead_discount = _round6(
            _clamp(
                0.56 + summary.anchor_score * 0.12 + summary.gunline_score * 0.08,
                low=0.45,
                high=0.85,
            )
        )
        lookahead_score_blend = _round6(
            _clamp(
                0.14 + summary.melee_score * 0.08 + summary.gunline_score * 0.06,
                low=0.08,
                high=0.35,
            )
        )
        continuation_decay = _round6(
            _clamp(
                0.66 + summary.anchor_score * 0.1,
                low=0.45,
                high=0.9,
            )
        )
        return {
            "board_affordances": affordance.to_dict(),
            "army_role_summary": summary.to_dict(),
            "deployment_lookahead": {
                "enabled": True,
                "depth": int(lookahead_depth),
                "branch_count": int(lookahead_branch_count),
                "discount": float(lookahead_discount),
                "continuation_decay": float(continuation_decay),
                "score_blend": float(lookahead_score_blend),
                "candidate_kinds": list(candidate_kinds),
            },
        }

    def ordered_deploy_units(
        self,
        *,
        player: object,
        deployable_units: Iterable[object],
        deployment_zone: Optional[dict],
        already_deployed: Iterable[object],
    ) -> list[object]:
        units = sorted_units(deployable_units)
        profiles = self.role_profiles_for_player(player)
        deployed_count = int(len(list(already_deployed or [])))
        total_count = max(1, deployed_count + len(units))
        progress = _clamp(float(deployed_count) / float(total_count), low=0.0, high=1.0)
        early_phase = 1.0 - progress
        scored: list[tuple[float, str, object]] = []
        for unit in units:
            unit_id = str(maybe_entity_id(unit) or "")
            profile = profiles.get(unit_id)
            if profile is None:
                continue
            score = float(profile.deployment_priority)
            score += float(profile.role_scores.get(ROLE_SCREEN, 0.0)) * 1.1 * early_phase
            score += float(profile.role_scores.get(ROLE_INFILTRATOR, 0.0)) * 1.0 * early_phase
            score += float(profile.role_scores.get(ROLE_SCOUT, 0.0)) * 0.9 * early_phase
            score += float(profile.role_scores.get(ROLE_HOME_HOLDER, 0.0)) * 0.8 * early_phase
            score += float(profile.role_scores.get(ROLE_ANCHOR, 0.0)) * 0.75 * progress
            score += float(profile.role_scores.get(ROLE_COUNTERCHARGE, 0.0)) * 0.7 * progress
            score += float(profile.role_scores.get(ROLE_MELEE_MISSILE, 0.0)) * 0.85 * progress
            if str(profile.reserve_preference or "") != "deploy":
                score -= 0.45
            scored.append((float(score), unit_id, unit))
        scored.sort(key=lambda entry: (-entry[0], entry[1]))
        return [entry[2] for entry in scored]

    def reserve_preference_score(self, *, player: object, unit: object, reserve_status: str) -> float:
        unit_id = str(maybe_entity_id(unit) or "")
        profile = self.role_profiles_for_player(player).get(unit_id)
        if profile is None:
            return 0.0
        score = 0.0
        status = str(reserve_status or "")
        if status == str(profile.reserve_preference or ""):
            score += 1.0
        score += float(profile.role_scores.get(ROLE_RESERVE_DROPPER, 0.0)) * 0.8
        score += float(profile.role_scores.get(ROLE_MELEE_MISSILE, 0.0)) * 0.5
        score += float(profile.role_scores.get(ROLE_COUNTERCHARGE, 0.0)) * 0.2
        score -= float(profile.role_scores.get(ROLE_SCREEN, 0.0)) * 0.7
        score -= float(profile.role_scores.get(ROLE_HOME_HOLDER, 0.0)) * 0.65
        return float(score)

    def anchor_candidates_for_unit(
        self,
        *,
        player: object,
        unit: object,
        deployment_zone: Optional[dict],
        already_deployed: Iterable[object],
    ) -> list[tuple[float, float]]:
        board_width, board_height = _board_dimensions(self.game)
        min_x, max_x, min_y, max_y = _zone_bounds(deployment_zone, board_width=board_width, board_height=board_height)
        center_x, center_y = _zone_center(deployment_zone, board_width=board_width, board_height=board_height)
        board_center_x = float(board_width) * 0.5
        board_center_y = float(board_height) * 0.5
        forward_x, forward_y = _normalized_vector(board_center_x - center_x, board_center_y - center_y)
        side_x, side_y = (-forward_y, forward_x)
        depth = max(2.0, min(max_x - min_x, max_y - min_y))
        frontage = max(2.0, max(max_x - min_x, max_y - min_y))

        unit_id = str(maybe_entity_id(unit) or "")
        profile = self.role_profiles_for_player(player).get(unit_id)
        screen_score = float(profile.role_scores.get(ROLE_SCREEN, 0.0)) if profile is not None else 0.0
        infil_score = float(profile.role_scores.get(ROLE_INFILTRATOR, 0.0)) if profile is not None else 0.0
        scout_score = float(profile.role_scores.get(ROLE_SCOUT, 0.0)) if profile is not None else 0.0
        home_score = float(profile.role_scores.get(ROLE_HOME_HOLDER, 0.0)) if profile is not None else 0.0
        anchor_score = float(profile.role_scores.get(ROLE_ANCHOR, 0.0)) if profile is not None else 0.0
        melee_score = float(profile.role_scores.get(ROLE_MELEE_MISSILE, 0.0)) if profile is not None else 0.0
        countercharge_score = float(profile.role_scores.get(ROLE_COUNTERCHARGE, 0.0)) if profile is not None else 0.0

        forward_push = _clamp(
            0.18 + screen_score * 0.2 + infil_score * 0.2 + scout_score * 0.17 + melee_score * 0.12 - home_score * 0.16,
            low=0.05,
            high=0.6,
        )
        back_pull = _clamp(0.22 + home_score * 0.22 + anchor_score * 0.1, low=0.05, high=0.7)
        lateral_spread = _clamp(0.14 + screen_score * 0.22 + countercharge_score * 0.15, low=0.05, high=0.45)

        points: list[tuple[float, float]] = []
        points.append((center_x - forward_x * depth * back_pull, center_y - forward_y * depth * back_pull))
        points.append((center_x + forward_x * depth * forward_push, center_y + forward_y * depth * forward_push))
        points.append((center_x + side_x * frontage * lateral_spread, center_y + side_y * frontage * lateral_spread))
        points.append((center_x - side_x * frontage * lateral_spread, center_y - side_y * frontage * lateral_spread))
        points.append((center_x + forward_x * depth * (forward_push * 0.55), center_y + forward_y * depth * (forward_push * 0.55)))
        points.append((center_x, center_y))

        if infil_score >= 0.7 or scout_score >= 0.65:
            points.insert(
                0,
                (
                    center_x + forward_x * depth * _clamp(forward_push + 0.12, low=0.2, high=0.75),
                    center_y + forward_y * depth * _clamp(forward_push + 0.12, low=0.2, high=0.75),
                ),
            )

        unique: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        for x, y in points:
            clamped_x = _clamp(x, low=min_x, high=max_x)
            clamped_y = _clamp(y, low=min_y, high=max_y)
            key = (round(float(clamped_x), 3), round(float(clamped_y), 3))
            if key in seen:
                continue
            seen.add(key)
            unique.append((float(clamped_x), float(clamped_y)))
        return unique

    def resolve_player_zone(self, player_id: str) -> Optional[dict]:
        return deployment_zone_from_player(self.game, player_id)
