from __future__ import annotations

import hashlib
from typing import Iterable

from .decision_dispatcher import validate_decision
from .decision_kinds import DECISION_MOVE_UNIT
from .decisions import DecisionOption, DecisionRequest, DecisionResult
from .deployment import DeploymentDecisionMaker
from ..roster.player import Player
from ..utility.entity_ids import get_entity_id


class DeterministicDeploymentDecisionMaker(DeploymentDecisionMaker):
    """
    Non-interactive deployment policy for headless/self-play runs.

    Priorities:
    - deterministic behavior
    - legality-first placement via `Game.is_valid_deployment_position`
    - avoid reserves complexity unless forced by rules
    """

    def __init__(
        self,
        game: object,
        *,
        lattice_step: float = 2.0,
        exhaustive_lattice_step: float = 1.0,
    ) -> None:
        self.game = game
        self.lattice_step = float(max(0.5, lattice_step))
        self.exhaustive_lattice_step = float(max(0.25, exhaustive_lattice_step))

    def choose_deployment_zone(self, available_zones: list[dict]) -> dict:
        zones = [dict(zone or {}) for zone in list(available_zones or [])]
        if not zones:
            raise ValueError("No deployment zones were provided.")
        for zone in zones:
            if str(zone.get("zone_type", "") or "").strip().lower() == "defender":
                return zone
        zones.sort(key=self._zone_sort_key)
        return zones[0]

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
                score = self._reserve_candidate_score(unit, reserve_status=reserve_status)
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

            validation = dict(validate_fn(decisions) or {})
            if not bool(validation.get("valid", True)) and callable(enforce_fn):
                enforced = dict(enforce_fn(decisions) or {})
                if enforced:
                    return enforced
        elif callable(validate_fn):
            validation = dict(validate_fn(decisions) or {})
            if not bool(validation.get("valid", True)) and callable(enforce_fn):
                enforced = dict(enforce_fn(decisions) or {})
                if enforced:
                    return enforced
        return decisions

    def _preferred_reserve_status(self, army: object, unit: object) -> str:
        if bool(getattr(unit, "is_fortification", False)):
            return ""
        has_deep_strike_fn = getattr(unit, "has_deep_strike", None)
        has_deep_strike = bool(has_deep_strike_fn()) if callable(has_deep_strike_fn) else False
        ride_the_wind_fn = getattr(army, "_ride_the_wind_allows_standard_reserves", None)
        ride_the_wind_ok = bool(ride_the_wind_fn(unit)) if callable(ride_the_wind_fn) else False
        return "reserves" if (has_deep_strike or ride_the_wind_ok) else "strategic_reserves"

    def _reserve_candidate_score(self, unit: object, *, reserve_status: str) -> float:
        base = 0.0
        if str(reserve_status or "") == "reserves":
            base += 10000.0
        cost_fn = getattr(unit, "get_unit_cost", None)
        points = float(cost_fn()) if callable(cost_fn) else 0.0
        base += points
        base += 20.0 * self._unit_footprint_score(unit)
        return float(base)

    def _unit_footprint_score(self, unit: object) -> float:
        models = list(getattr(unit, "models", []) or [])
        if not models:
            return 0.0
        score = 0.0
        for model in models:
            model_base = getattr(model, "model_base", None)
            if model_base is None:
                continue
            get_longest_radius = getattr(model_base, "get_longest_radius", None)
            if callable(get_longest_radius):
                radius = float(get_longest_radius() or 0.0)
            else:
                get_radius = getattr(model_base, "get_radius", None)
                radius = float(get_radius() or 0.0) if callable(get_radius) else 0.0
            score += max(0.25, radius)
        score += 0.5 * float(len(models))
        return float(score)

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

        for x, y in self._candidate_positions(unit, deployment_zone, already_deployed):
            if self._is_valid_deployment_candidate(
                unit,
                player_id=str(player_id),
                x=float(x),
                y=float(y),
                fast_validate_fn=validate_fn,
            ):
                return (float(x), float(y))
        for x, y in self._candidate_positions_exhaustive(unit, deployment_zone):
            if self._is_valid_deployment_candidate(
                unit,
                player_id=str(player_id),
                x=float(x),
                y=float(y),
                fast_validate_fn=validate_fn,
            ):
                return (float(x), float(y))

        raise RuntimeError(
            f"No valid deployment position found for unit {getattr(unit, 'name', 'Unit')} "
            f"(player_id={player_id})."
        )

    def _is_valid_deployment_candidate(
        self,
        unit: object,
        *,
        player_id: str,
        x: float,
        y: float,
        fast_validate_fn,
    ) -> bool:
        if not bool(fast_validate_fn(unit, float(x), float(y), str(player_id))):
            return False
        model_positions = self._build_model_positions(unit, x=float(x), y=float(y))
        if not model_positions:
            return False
        unit_id = str(get_entity_id(unit) or "")
        if not unit_id:
            return False
        allowed_model_ids = [str(entry.get("model_id", "") or "") for entry in list(model_positions or [])]
        if not all(allowed_model_ids):
            return False
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
            return False
        result = DecisionResult(
            decision_id=str(request.decision_id or ""),
            player_id=str(player_id),
            option_id=str(option_id),
            payload={"model_positions": list(model_positions)},
        )
        errors = tuple(validate_decision(self.game, request, result) or ())
        return not errors

    def _build_model_positions(self, unit: object, *, x: float, y: float) -> list[dict]:
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return []
        use_repulsors = True
        has_infiltrate = getattr(unit, "has_infiltrate", None)
        if callable(has_infiltrate) and has_infiltrate():
            use_repulsors = False
        boundary_repulsors = None
        if use_repulsors:
            repulsor_fn = getattr(self.game, "get_boundary_repulsors", None)
            if callable(repulsor_fn):
                boundary_repulsors = repulsor_fn(unit, context="deployment")
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
        mission_zones = list(deployment_zone.get("mission_zones", []) or [])
        if mission_zones:
            xs: list[float] = []
            ys: list[float] = []
            for mission_zone in mission_zones:
                vertices = list(getattr(mission_zone, "vertices", []) or [])
                for vertex in vertices:
                    if len(vertex) >= 2:
                        xs.append(float(vertex[0]))
                        ys.append(float(vertex[1]))
            if xs and ys:
                return (sum(xs) / float(len(xs)), sum(ys) / float(len(ys)))
        x_range = deployment_zone.get("x_range")
        y_range = deployment_zone.get("y_range")
        if isinstance(x_range, (list, tuple)) and isinstance(y_range, (list, tuple)) and len(x_range) >= 2 and len(y_range) >= 2:
            return (float(x_range[0] + x_range[1]) / 2.0, float(y_range[0] + y_range[1]) / 2.0)
        game = self.game
        battlefield = getattr(game, "battlefield", None)
        width = float(getattr(battlefield, "width", 60.0) or 60.0)
        height = float(getattr(battlefield, "height", 44.0) or 44.0)
        return (width / 2.0, height / 2.0)

    def _candidate_positions(
        self,
        unit: object,
        deployment_zone: dict,
        already_deployed: list[object],
    ) -> list[tuple[float, float]]:
        center_x, center_y = self._zone_center(deployment_zone)
        offsets = self._ordered_offsets(unit=unit, already_deployed=already_deployed)
        candidates: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        mission_zones = list(deployment_zone.get("mission_zones", []) or [])

        for dx, dy in offsets:
            x = float(center_x + dx)
            y = float(center_y + dy)
            key = (round(x, 3), round(y, 3))
            if key in seen:
                continue
            if not self._point_in_zone(deployment_zone, x, y):
                    continue
            seen.add(key)
            candidates.append((x, y))

        if candidates:
            return candidates
        return [(center_x, center_y)]

    def _candidate_positions_exhaustive(self, unit: object, deployment_zone: dict) -> list[tuple[float, float]]:
        bounds = self._zone_bounds(deployment_zone)
        if bounds is None:
            return []
        min_x, max_x, min_y, max_y = bounds
        if min_x > max_x or min_y > max_y:
            return []

        center_x, center_y = self._zone_center(deployment_zone)
        unit_id = str(get_entity_id(unit) or "")
        candidates: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        step_primary = float(self.exhaustive_lattice_step)
        step_secondary = max(0.25, step_primary / 2.0)
        for step in (step_primary, step_secondary):
            offsets = (0.0, step / 2.0)
            for off_y in offsets:
                ys = self._axis_points(min_y, max_y, step=step, offset=off_y)
                if not ys:
                    continue
                for off_x in offsets:
                    xs = self._axis_points(min_x, max_x, step=step, offset=off_x)
                    if not xs:
                        continue
                    for y in ys:
                        for x in xs:
                            key = (round(float(x), 3), round(float(y), 3))
                            if key in seen:
                                continue
                            seen.add(key)
                            candidates.append((float(x), float(y)))

        def _scan_sort_key(point: tuple[float, float]) -> tuple[float, str]:
            x, y = point
            dist_sq = (float(x) - float(center_x)) ** 2 + (float(y) - float(center_y)) ** 2
            token = f"{unit_id}:{x:.3f}:{y:.3f}"
            tie = hashlib.sha256(token.encode("utf-8")).hexdigest()
            return (float(dist_sq), tie)

        candidates.sort(key=_scan_sort_key)
        return candidates

    @staticmethod
    def _axis_points(start: float, end: float, *, step: float, offset: float) -> list[float]:
        lo = float(min(start, end))
        hi = float(max(start, end))
        if hi - lo <= 1e-6:
            return [lo]
        values: list[float] = []
        first = lo + float(offset)
        if first > hi:
            first = lo
        cursor = first
        while cursor <= hi + 1e-6:
            values.append(round(float(cursor), 4))
            cursor += float(step)
        if not values:
            values = [round((lo + hi) / 2.0, 4)]
        return values

    def _zone_bounds(self, deployment_zone: dict) -> tuple[float, float, float, float] | None:
        mission_zones = list(deployment_zone.get("mission_zones", []) or [])
        xs: list[float] = []
        ys: list[float] = []
        for mission_zone in mission_zones:
            vertices = list(getattr(mission_zone, "vertices", []) or [])
            for vertex in vertices:
                if isinstance(vertex, (list, tuple)) and len(vertex) >= 2:
                    xs.append(float(vertex[0]))
                    ys.append(float(vertex[1]))
        if xs and ys:
            return (min(xs), max(xs), min(ys), max(ys))
        x_range = deployment_zone.get("x_range")
        y_range = deployment_zone.get("y_range")
        if (
            isinstance(x_range, (list, tuple))
            and isinstance(y_range, (list, tuple))
            and len(x_range) >= 2
            and len(y_range) >= 2
        ):
            return (
                float(min(x_range[0], x_range[1])),
                float(max(x_range[0], x_range[1])),
                float(min(y_range[0], y_range[1])),
                float(max(y_range[0], y_range[1])),
            )
        battlefield = getattr(self.game, "battlefield", None)
        width = float(getattr(battlefield, "width", 0.0) or 0.0)
        height = float(getattr(battlefield, "height", 0.0) or 0.0)
        if width > 0.0 and height > 0.0:
            return (0.0, width, 0.0, height)
        return None

    def _point_in_zone(self, deployment_zone: dict, x: float, y: float) -> bool:
        mission_zones = list(deployment_zone.get("mission_zones", []) or [])
        if mission_zones:
            for mission_zone in mission_zones:
                contains_fn = getattr(mission_zone, "contains_point", None)
                if callable(contains_fn) and bool(contains_fn(float(x), float(y))):
                    return True
            return False
        x_range = deployment_zone.get("x_range")
        y_range = deployment_zone.get("y_range")
        if (
            isinstance(x_range, (list, tuple))
            and isinstance(y_range, (list, tuple))
            and len(x_range) >= 2
            and len(y_range) >= 2
        ):
            lo_x = float(min(x_range[0], x_range[1]))
            hi_x = float(max(x_range[0], x_range[1]))
            lo_y = float(min(y_range[0], y_range[1]))
            hi_y = float(max(y_range[0], y_range[1]))
            return lo_x <= float(x) <= hi_x and lo_y <= float(y) <= hi_y
        return True

    def _ordered_offsets(self, *, unit: object, already_deployed: Iterable[object]) -> list[tuple[float, float]]:
        base: list[tuple[float, float]] = [(0.0, 0.0)]
        rings = [1, 2, 3, 4, 5, 6, 8, 10, 12]
        for ring in rings:
            step = float(ring) * self.lattice_step
            base.extend(
                [
                    (step, 0.0),
                    (-step, 0.0),
                    (0.0, step),
                    (0.0, -step),
                    (step, step),
                    (step, -step),
                    (-step, step),
                    (-step, -step),
                ]
            )

        unit_id = str(get_entity_id(unit) or "")
        deployed_count = int(len(list(already_deployed or [])))
        seed = f"{unit_id}:{deployed_count}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        rotate_by = int(digest[:8], 16) % max(1, len(base))
        return base[rotate_by:] + base[:rotate_by]
