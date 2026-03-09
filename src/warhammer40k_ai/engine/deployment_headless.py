from __future__ import annotations

import hashlib
from typing import Iterable, Optional

from .decision_dispatcher import validate_decision
from .decision_kinds import DECISION_MOVE_UNIT
from .decisions import DecisionOption, DecisionRequest, DecisionResult
from .deployment import DeploymentDecisionMaker
from .deployment_ranker import DeploymentCandidateRanker
from .pregame_deployment_agent import PregameDeploymentAgent
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
        reserve_policy: str = "forced_only",
        use_pregame_teacher: bool = True,
        ranker_model_path: str | None = None,
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
        if self._pregame_agent is not None and player is not None:
            ordered = self._pregame_agent.ordered_deploy_units(
                player=player,
                deployable_units=list(deployable_units),
                deployment_zone=dict(deployment_zone or {}),
                already_deployed=list(already_deployed or []),
            )
            if ordered:
                return ordered[0]
        return deployable_units[0]

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

        player = self._resolve_player_for_unit(unit)
        candidate_groups = self._deployment_anchor_candidate_groups(
            unit,
            deployment_zone,
            already_deployed=list(already_deployed or []),
            player=player,
        )
        candidate_limit = max(1, int(max_candidates))
        seen_anchor: set[tuple[float, float]] = set()
        seen_payload: set[tuple[tuple[str, float, float, float, float], ...]] = set()
        candidates: list[dict] = []

        for source, anchors in list(candidate_groups or []):
            for x, y in list(anchors or []):
                key = (round(float(x), 3), round(float(y), 3))
                if key in seen_anchor:
                    continue
                seen_anchor.add(key)
                payload = self._select_valid_deployment_payload(
                    unit,
                    player_id=str(player_id),
                    x=float(x),
                    y=float(y),
                    fast_validate_fn=validate_fn,
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
    ) -> list[tuple[str, list[tuple[float, float]]]]:
        groups: list[tuple[str, list[tuple[float, float]]]] = [
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
            ("lattice_exhaustive", self._candidate_positions_exhaustive(unit, deployment_zone)),
        ]
        if self._unit_has_infiltrate(unit):
            infiltrate_groups = self._infiltrate_candidate_groups(unit, already_deployed=already_deployed)
            for idx, anchors in enumerate(list(infiltrate_groups or [])):
                groups.append((f"infiltrate_{int(idx)}", list(anchors or [])))
        return groups

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

    def _select_valid_deployment_payload(
        self,
        unit: object,
        *,
        player_id: str,
        x: float,
        y: float,
        fast_validate_fn,
    ) -> list[dict]:
        if not bool(fast_validate_fn(unit, float(x), float(y), str(player_id))):
            return []
        unit_id = str(get_entity_id(unit) or "")
        if not unit_id:
            return []

        payload_variants = self._build_model_positions_variants(unit, x=float(x), y=float(y))
        for model_positions in payload_variants:
            allowed_model_ids = [str(entry.get("model_id", "") or "") for entry in list(model_positions or [])]
            if not all(allowed_model_ids):
                continue
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
                return list(model_positions)
        return []

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

    def _build_model_positions_variants(self, unit: object, *, x: float, y: float) -> list[list[dict]]:
        base_positions = self._build_model_positions(unit, x=float(x), y=float(y))
        if not base_positions:
            return []
        models = list(getattr(unit, "models", []) or [])
        if not models or len(models) != len(base_positions):
            return [list(base_positions)]

        per_model_surfaces: list[list[float]] = []
        for model, entry in zip(models, base_positions):
            pos = list(entry.get("position", []) or [])
            if len(pos) < 3:
                return [list(base_positions)]
            per_model_surfaces.append(
                self._ruins_surface_z_options_for_model(model, x=float(pos[0]), y=float(pos[1]), current_z=float(pos[2]))
            )

        variants: list[list[dict]] = []
        seen: set[tuple[tuple[str, float], ...]] = set()

        def _add_variant(positions: list[dict]) -> None:
            key: list[tuple[str, float]] = []
            for entry in list(positions or []):
                model_id = str(entry.get("model_id", "") or "")
                pos = list(entry.get("position", []) or [])
                if len(pos) < 3:
                    return
                key.append((model_id, round(float(pos[2]), 3)))
            key_tuple = tuple(key)
            if key_tuple in seen:
                return
            seen.add(key_tuple)
            variants.append(positions)

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
        return candidates

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

        payload_variants = self._build_model_positions_variants(unit, x=float(position[0]), y=float(position[1]))
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
