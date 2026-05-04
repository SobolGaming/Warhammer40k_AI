"""Fight-phase movement, geometry, and charge validation helpers for Unit positioning/runtime state."""

from ._common import *
import logging
logger = logging.getLogger(__name__)


class PositioningFightMovementMixin:
    def attached_unit_has_reanimation_protocols(self) -> bool:
        """Attached-unit RP rules require a surviving bodyguard model while a Leader remains attached."""
        root = self.get_attached_unit_root()
        attached_leaders = list(getattr(root, "attached_leaders", []) or []) if root is not None else []
        if attached_leaders:
            bodyguard_models = list(getattr(root, "models", []) or []) if root is not None else []
            bodyguard_alive = False
            for model in list(bodyguard_models or []):
                alive_attr = getattr(model, "is_alive", False)
                if bool(alive_attr() if callable(alive_attr) else alive_attr):
                    bodyguard_alive = True
                    break
            if not bodyguard_alive:
                return False
        for u in root.get_attached_unit_members():
            try:
                if u.has_reanimation_protocols():
                    return True
            except Exception:
                continue
        return False


    def get_choreographer_of_war_source(self) -> str:
        """Return the source name if a leading Choreographer of War ability is active."""
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        cache_key = "choreographer_of_war_source"
        try:
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict):
                stratagem_source = str(sr.get("stratagem_choreographer_of_war_source", "") or "").strip()
                if stratagem_source:
                    active = True
                    exp_phase = str(
                        sr.get("stratagem_choreographer_of_war_expires_phase", "")
                        or sr.get("carnival_violent_crescendo_expires_phase", "")
                        or ""
                    ).strip().upper()
                    owner_id = str(
                        sr.get("stratagem_choreographer_of_war_turn_owner", "")
                        or sr.get("carnival_violent_crescendo_owner", "")
                        or ""
                    )
                    effect_turn = int(
                        sr.get("stratagem_choreographer_of_war_turn", sr.get("carnival_violent_crescendo_turn", 0))
                        or 0
                    )
                    game = None
                    try:
                        army = root.get_parent_army()
                    except Exception:
                        army = None
                    try:
                        game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                    except Exception:
                        game = None
                    if game is not None:
                        cur_player = getattr(game, "get_current_player", lambda: None)()
                        cur_owner = str(getattr(cur_player, "id", "") or "")
                        cur_turn = int(getattr(game, "turn", 0) or 0)
                        cur_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                        if owner_id and cur_owner and owner_id != cur_owner:
                            active = False
                        if effect_turn and cur_turn and effect_turn != cur_turn:
                            active = False
                        if exp_phase and cur_phase and exp_phase != cur_phase:
                            active = False
                    if active:
                        if not hasattr(root, "_ability_cache"):
                            root._ability_cache = {}
                        root._ability_cache[cache_key] = stratagem_source
                        return str(stratagem_source or "")
        except Exception:
            pass
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict) and cache_key in cache:
            return str(cache.get(cache_key) or "")

        source = ""
        for ab, _leader in root._iter_attached_leader_leading_abilities():
            try:
                name = str(getattr(ab, "name", "") or "")
                desc = str(getattr(ab, "description", "") or "") or name
            except Exception:
                name = ""
                desc = ""
            name_norm = name.strip().lower()
            text = root._normalize_rules_text(desc or "")
            if not text:
                continue
            norm = text.replace("\u2019", "'").replace("\u0192?T", "'").lower()
            norm = re.sub(r"'s\b", " s", norm)
            norm = re.sub(r"[^a-z0-9]+", " ", norm)
            norm = re.sub(r"\s+", " ", norm).strip()
            if name_norm == "choreographer of war":
                source = name or "Choreographer of War"
                break
            if name_norm == "onslaught":
                if (
                    "pile in" in norm
                    and "consolidation move" in norm
                    and "move up to 6" in norm
                    and "instead of up to 3" in norm
                ):
                    source = name or "Onslaught"
                    break
            if (
                "pile in" in norm
                and "consolidation move" in norm
                and "move up to 6" in norm
                and "instead of up to 3" in norm
                and (
                    "as close as possible to the closest enemy unit" in norm
                    or "while this model is leading a unit" in norm
                )
            ):
                source = name or "Choreographer of War"
                break

        if not hasattr(root, "_ability_cache"):
            root._ability_cache = {}
        root._ability_cache[cache_key] = source
        return str(source or "")


    def _can_consolidate_end_in_engagement(self, max_distance: float) -> bool:
        """Return True if this unit can end a consolidate within Engagement Range this move."""
        try:
            distance_limit = float(max_distance)
        except (TypeError, ValueError):
            return False
        if distance_limit <= 0.0:
            return False

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self

        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        player = getattr(army, "player", None) if army is not None else None
        game = getattr(player, "game", None) if player is not None else None
        game_map = getattr(game, "map", None)
        if game_map is None:
            # Preserve existing behavior in contexts without a live map (e.g. isolated tests).
            return True

        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if callable(get_enemy_units):
            enemy_units = list(get_enemy_units(root) or [])
        else:
            enemy_units = [
                u
                for u in list(getattr(game_map, "units", []) or [])
                if u is not None and getattr(u, "faction", None) != getattr(root, "faction", None)
            ]
        if not enemy_units:
            return False

        alive_enemies = []
        for enemy in enemy_units:
            if enemy is None:
                continue
            alive_fn = getattr(enemy, "is_alive", None)
            if callable(alive_fn):
                if not alive_fn():
                    continue
            elif getattr(enemy, "is_alive", True) is False:
                continue
            if getattr(enemy, "deployed", True) is False:
                continue
            alive_enemies.append(enemy)
        if not alive_enemies:
            return False

        is_within_engagement = getattr(game_map, "is_within_engagement_range", None)
        if callable(is_within_engagement):
            for enemy in alive_enemies:
                if is_within_engagement(root, enemy):
                    return True

        get_distance_between_units = getattr(game_map, "get_distance_between_units", None)
        if not callable(get_distance_between_units):
            return False

        min_distance = None
        for enemy in alive_enemies:
            try:
                dist = float(get_distance_between_units(root, enemy))
            except (TypeError, ValueError):
                continue
            if min_distance is None or dist < min_distance:
                min_distance = dist
        if min_distance is None:
            return False

        from ...utility.constants import ENGAGEMENT_RANGE_HORIZONTAL

        return float(min_distance) <= float(distance_limit) + float(ENGAGEMENT_RANGE_HORIZONTAL or 1.0)


    def get_fight_phase_move_distance_override(self, movement_kind: str) -> Optional[float]:
        """
        Return a fight-phase move distance override (pile-in / consolidate) if a rule modifies it.
        movement_kind: 'pile_in' or 'consolidate'
        """
        kind = str(movement_kind).strip().lower()
        if kind not in ("pile_in", "consolidate"):
            return None

        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self

        override = None

        try:
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict):
                exp = str(sr.get("battle_focus_sudden_strike_expires_phase", "") or "").strip().upper()
                if exp:
                    pname = ""
                    try:
                        army = root.get_parent_army()
                        game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
                        phase = getattr(game, "phase", None) if game is not None else None
                        pname = str(getattr(phase, "name", "") or phase or "").strip().upper()
                    except Exception:
                        pname = ""
                    if not pname or pname == exp:
                        override = max(float(override or 0.0), 6.0)
        except Exception:
            pass

        try:
            if self.get_choreographer_of_war_source():
                override = max(float(override or 0.0), 6.0)
        except Exception:
            pass

        try:
            army = root.get_parent_army()
            mgr = getattr(army, "blessings_of_khorne", None) if army is not None else None
            game = army.player.game if (army is not None and getattr(army, "player", None) is not None) else None
            br = int(getattr(game, "turn", 0) or 0) if game is not None else 0
            if mgr is not None and br > 0:
                if root.attached_unit_has_blessings_of_khorne():
                    if mgr.is_blessing_active_for_unit("RAGE_FUELLED_INVIGORATION", root, battle_round=br):
                        override = max(float(override or 0.0), 6.0)
        except Exception:
            pass

        try:
            members = list(root.get_attached_unit_members() or []) if hasattr(root, "get_attached_unit_members") else [root]
            if not members:
                members = [root]
            for member in members:
                sr_member = getattr(member, "special_rules", None)
                if not isinstance(sr_member, dict):
                    continue
                if not bool(sr_member.get("enhancement_singular_will", False)):
                    continue
                bearer = None
                bearer_id = str(
                    sr_member.get("enhancement_singular_will_bearer_model_id", "")
                    or sr_member.get("enhancement_bearer_model_id", "")
                    or ""
                ).strip()
                if bearer_id:
                    for model in list(getattr(member, "models", []) or []):
                        model_entity_id = str(get_entity_id(model) or "").strip()
                        model_local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
                        if bearer_id != model_entity_id and bearer_id != model_local_id:
                            continue
                        bearer = model
                        break
                if bearer is None:
                    get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
                    if callable(get_bearer):
                        bearer = get_bearer()
                if bearer is None:
                    continue
                alive_attr = getattr(bearer, "is_alive", True)
                bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                if not bearer_alive:
                    continue
                if kind == "pile_in":
                    bonus = int(sr_member.get("enhancement_singular_will_pile_in_distance_bonus", 3) or 3)
                else:
                    bonus = int(sr_member.get("enhancement_singular_will_consolidate_distance_bonus", 3) or 3)
                if bonus <= 0:
                    continue
                override = max(float(override or 0.0), 3.0 + float(bonus))
        except Exception:
            pass

        try:
            members = list(root.get_attached_unit_members() or []) if hasattr(root, "get_attached_unit_members") else [root]
            if not members:
                members = [root]
            for member in members:
                sr_member = getattr(member, "special_rules", None)
                if not isinstance(sr_member, dict):
                    continue
                if not bool(sr_member.get("enhancement_adrenalised_onslaught", False)):
                    continue
                bearer = None
                bearer_id = str(
                    sr_member.get("enhancement_adrenalised_onslaught_bearer_model_id", "")
                    or sr_member.get("enhancement_bearer_model_id", "")
                    or ""
                ).strip()
                if bearer_id:
                    for model in list(getattr(member, "models", []) or []):
                        model_entity_id = str(get_entity_id(model) or "").strip()
                        model_local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
                        if bearer_id != model_entity_id and bearer_id != model_local_id:
                            continue
                        bearer = model
                        break
                if bearer is None:
                    get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
                    if callable(get_bearer):
                        bearer = get_bearer()
                if bearer is None:
                    continue
                alive_attr = getattr(bearer, "is_alive", True)
                bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                if not bearer_alive:
                    continue
                if kind == "pile_in":
                    bonus = int(sr_member.get("enhancement_adrenalised_onslaught_pile_in_distance_bonus", 3) or 3)
                else:
                    bonus = int(
                        sr_member.get("enhancement_adrenalised_onslaught_consolidate_distance_bonus", 3) or 3
                    )
                if bonus <= 0:
                    continue
                override = max(float(override or 0.0), 3.0 + float(bonus))
        except Exception:
            pass

        try:
            members = list(root.get_attached_unit_members() or []) if hasattr(root, "get_attached_unit_members") else [root]
            if not members:
                members = [root]
            for member in members:
                sr_member = getattr(member, "special_rules", None)
                if not isinstance(sr_member, dict):
                    continue
                if not bool(sr_member.get("enhancement_driven_by_duty", False)):
                    continue
                bearer = None
                bearer_id = str(
                    sr_member.get("enhancement_driven_by_duty_bearer_model_id", "")
                    or sr_member.get("enhancement_bearer_model_id", "")
                    or ""
                ).strip()
                if bearer_id:
                    for model in list(getattr(member, "models", []) or []):
                        model_entity_id = str(get_entity_id(model) or "").strip()
                        model_local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
                        if bearer_id != model_entity_id and bearer_id != model_local_id:
                            continue
                        bearer = model
                        break
                if bearer is None:
                    get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
                    if callable(get_bearer):
                        bearer = get_bearer()
                if bearer is None:
                    continue
                alive_attr = getattr(bearer, "is_alive", True)
                bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                if not bearer_alive:
                    continue
                if kind == "pile_in":
                    distance = int(
                        sr_member.get("enhancement_driven_by_duty_pile_in_distance_override", 6) or 6
                    )
                else:
                    distance = int(
                        sr_member.get("enhancement_driven_by_duty_consolidate_distance_override", 6) or 6
                    )
                if distance <= 0:
                    continue
                override = max(float(override or 0.0), float(distance))
        except Exception:
            pass

        if kind == "consolidate":
            try:
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict):
                    dist = sr.get("stratagem_consolidate_distance_override")
                    if dist is not None:
                        override = max(float(override or 0.0), float(dist))
                    dist = sr.get("bearer_unit_consolidate_distance_override")
                    if dist is not None:
                        dist_value = float(dist)
                        requires_engagement = bool(sr.get("bearer_unit_consolidate_requires_engagement", False))
                        if (not requires_engagement) or self._can_consolidate_end_in_engagement(dist_value):
                            override = max(float(override or 0.0), dist_value)
            except Exception:
                pass
        if kind == "pile_in":
            try:
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict):
                    dist = sr.get("stratagem_pile_in_distance_override")
                    if dist is not None:
                        override = max(float(override or 0.0), float(dist))
                    dist = sr.get("bearer_unit_pile_in_distance_override")
                    if dist is not None:
                        override = max(float(override or 0.0), float(dist))
            except Exception:
                pass

        return float(override) if override else None


    def maybe_resolve_pending_separation(self, game_map: Optional['Map'] = None) -> None:
        """Resolve pending separation only if no attack resolution window is active."""
        root = self._attack_resolution_root()
        try:
            depth = int(getattr(root, "_attack_resolution_depth", 0))
        except Exception:
            depth = 0
        if depth == 0:
            try:
                root.resolve_pending_leader_separation(game_map=game_map)
            except Exception:
                pass


    def get_closest_model_position_to_target(self, target_position: Tuple[float, float, float]) -> Optional[Tuple[float, float, float]]:
        """Get the position of the model closest to a target position.

        Args:
            target_position: (x, y, z) coordinates of the target

        Returns:
            Tuple[float, float, float]: Position of closest model or None if no alive models
        """
        closest_model = None
        closest_distance = float('inf')

        for model in self.models:
            if not model.is_alive:
                continue
            model_pos = model.get_location()
            if model_pos:
                distance = get_dist(
                    target_position[0] - model_pos[0],
                    target_position[1] - model_pos[1],
                    target_position[2] - model_pos[2] if len(model_pos) > 2 else 0
                )
                if distance < closest_distance:
                    closest_distance = distance
                    closest_model = model

        return closest_model.get_location() if closest_model else None


    def is_point_inside(self, x, y):
        # Check if point is within any model's base
        for model in self.models:
            if not model.is_alive:
                continue
            model_pos = model.get_location()
            if model_pos:
                # Check if point is within model's base radius
                model_radius = getattr(model.model_base, 'radius', 1.0)
                if isinstance(model_radius, (tuple, list)):
                    model_radius = max(model_radius)  # Use larger radius for elliptical bases
                distance = get_dist(x - model_pos[0], y - model_pos[1])
                if distance <= model_radius:
                    return True
        return False


    def score_position(self, x, y, z, facing, game_map, model, placed_positions):
        """
        Score a candidate position for model placement.
        Lower is better.
        You can enhance this to factor in more things: cover, distance to objective, edge, enemy, etc.
        """
        # Simple version: maximize coherency, avoid edge, avoid obstacles.
        battlefield_width, battlefield_height = game_map.width, game_map.height

        # Distance from board edge (prefer center)
        min_x_dist = min(x, battlefield_width - x)
        min_y_dist = min(y, battlefield_height - y)
        edge_penalty = max(0, 6.0 - min(min_x_dist, min_y_dist)) * 10  # penalize <6" from edge

        # Penalty if near obstacle/impassable (cover not scored in this heuristic).
        cover_bonus = 0

        # Coherency bonus (number of coherent neighbors)
        coherent_neighbors = 0
        for pos in placed_positions:
            other_x, other_y, other_z, other_facing = pos
            # Assume unit has .coherency_distance
            dist = get_dist(x - other_x, y - other_y, z - other_z)
            if dist <= self.coherency_distance:
                coherent_neighbors += 1
        # Encourage more neighbors
        coherency_bonus = -coherent_neighbors * 20

        return edge_penalty + cover_bonus + coherency_bonus


    def _get_reduced_boundary_repulsors(self, game_map: 'Map') -> List:
        """Get reduced boundary repulsors for formation finding during movement.

        These are smaller than the full battlefield edge repulsors to allow better
        formation finding in crowded areas while still preventing units from going
        off the battlefield.
        """
        from shapely.geometry import Polygon

        repulsors = []
        repulsor_thickness = 0.25  # Reduced from 0.5 to 0.25 inches

        # Left battlefield edge repulsor (reduced)
        left_edge = Polygon([
            (-repulsor_thickness, -repulsor_thickness),
            (0, -repulsor_thickness),
            (0, game_map.height + repulsor_thickness),
            (-repulsor_thickness, game_map.height + repulsor_thickness)
        ])
        repulsors.append(left_edge)

        # Right battlefield edge repulsor (reduced)
        right_edge = Polygon([
            (game_map.width, -repulsor_thickness),
            (game_map.width + repulsor_thickness, -repulsor_thickness),
            (game_map.width + repulsor_thickness, game_map.height + repulsor_thickness),
            (game_map.width, game_map.height + repulsor_thickness)
        ])
        repulsors.append(right_edge)

        # Bottom battlefield edge repulsor (reduced)
        bottom_edge = Polygon([
            (-repulsor_thickness, -repulsor_thickness),
            (game_map.width + repulsor_thickness, -repulsor_thickness),
            (game_map.width + repulsor_thickness, 0),
            (-repulsor_thickness, 0)
        ])
        repulsors.append(bottom_edge)

        # Top battlefield edge repulsor (reduced)
        top_edge = Polygon([
            (-repulsor_thickness, game_map.height),
            (game_map.width + repulsor_thickness, game_map.height),
            (game_map.width + repulsor_thickness, game_map.height + repulsor_thickness),
            (-repulsor_thickness, game_map.height + repulsor_thickness)
        ])
        repulsors.append(top_edge)

        logger.debug(f"DEBUG: _get_reduced_boundary_repulsors returning {len(repulsors)} repulsors for map size {game_map.width}x{game_map.height}")

        return repulsors


    def calculate_strategic_facing(self, x: float, y: float, game_map: 'Map') -> float:
        """Calculate strategic facing direction towards enemies or objectives"""

        # Get our army to determine enemies
        army = self.get_parent_army()
        if not army:
            return 0.0  # Default facing if no army context

        best_target = None
        min_distance = float('inf')

        # Priority 1: Face nearest visible enemy unit
        for unit in game_map.units:
            if unit != self and unit.get_parent_army() != army and unit.is_alive():
                # Find the closest model in the enemy unit to our position
                closest_enemy_distance = float('inf')
                closest_enemy_pos = None

                for model in unit.models:
                    if model.is_alive:
                        enemy_pos = model.get_location()
                        distance = get_dist(x - enemy_pos[0], y - enemy_pos[1])
                        if distance < closest_enemy_distance:
                            closest_enemy_distance = distance
                            closest_enemy_pos = enemy_pos

                if closest_enemy_pos and closest_enemy_distance < min_distance:
                    min_distance = closest_enemy_distance
                    best_target = closest_enemy_pos

        # Priority 2: If no enemies, face towards objectives
        if not best_target and hasattr(game_map, 'objectives'):
            for objective in game_map.objectives:
                obj_pos = (objective.location.x, objective.location.y)
                distance = get_dist(x - obj_pos[0], y - obj_pos[1])
                if distance < min_distance:
                    min_distance = distance
                    best_target = obj_pos

        # Priority 3: Face towards center of battlefield
        if not best_target:
            center_x = game_map.width / 2
            center_y = game_map.height / 2
            best_target = (center_x, center_y)

        # Calculate angle to target
        dx = best_target[0] - x
        dy = best_target[1] - y
        return get_angle(dy, dx)


    def calculate_model_positions(self,
                                start_x: float,
                                start_y: float,
                                game_map: 'Map',
                                grid_step=0.5,
                                relax_iters=5,
                                avoid_friendly_units=True,
                                boundary_repulsors=None,
                                search_context=None,
                                calculate_facing: bool = True,
                                resolve_surface_height: bool = True):
        """
        Computes (x, y, z, facing) for each model in self.models.
        Tries formation templates (block, wedge, circle, column) built
        with safe spacing based on base size; falls back to per-model A*.

        Args:
            start_x: Target X coordinate for unit placement
            start_y: Target Y coordinate for unit placement
            game_map: The game map
            grid_step: Step size for pathfinding grid (default 0.5)
            relax_iters: Number of relaxation iterations (default 5)
            avoid_friendly_units: Whether to avoid collisions with friendly units
            boundary_repulsors: Optional list of boundary repulsor polygons to avoid

        Returns:
            List of (x, y, z, facing) tuples for each model, or None if failed
        """
        from ...utility.placement_search import (
            build_placement_search_context,
            cached_formation_templates,
            estimated_unit_pack_spacing,
        )

        if not self.models:
            return []

        if boundary_repulsors is None:
            boundary_repulsors = []

        logger.debug(f"DEBUG: calculate_model_positions for {self.name} ({len(self.models)} models)")
        logger.debug(f"DEBUG: start position: ({start_x:.1f}, {start_y:.1f})")
        logger.debug(f"DEBUG: avoid_friendly_units: {avoid_friendly_units}")
        logger.debug(f"DEBUG: boundary_repulsors: {len(boundary_repulsors) if boundary_repulsors else 0}")

        if len(self.models) == 1:
            # Exact-placement callers expect the requested anchor itself; later validation
            # decides whether that anchor is legal for deployment/reserves/scout flows.
            z = game_map.get_surface_height_for_model(self.models[0], start_x, start_y) if bool(resolve_surface_height) else 0.0
            f = self.calculate_strategic_facing(start_x, start_y, game_map) if bool(calculate_facing) else 0.0
            self.models[0].set_location(float(start_x), float(start_y), float(z), float(f))
            return [(float(start_x), float(start_y), float(z), float(f))]

        if search_context is None:
            search_context = build_placement_search_context(
                self,
                game_map,
                avoid_friendly_units=bool(avoid_friendly_units),
                boundary_repulsors=boundary_repulsors,
            )

        # Debug boundary repulsors
        if len(boundary_repulsors) == 0:
            logger.debug(f"DEBUG: No boundary repulsors provided - this might cause formation finding issues")
        else:
            logger.debug(f"DEBUG: Boundary repulsors provided: {[type(br).__name__ for br in boundary_repulsors]}")

        logger.debug(f"DEBUG: Using multi-model formation templates")
        # SLOW PATH FOR MULTI-MODEL UNITS
        logger.debug(
            "DEBUG: Search context blockers: enemies=%d friendlies=%d terrain=%d boundary=%d",
            int(getattr(search_context, "enemy_blocking_count", 0)),
            int(getattr(search_context, "friendly_blocking_count", 0)),
            int(len(getattr(search_context, "terrain_polygons", ()) or ())),
            int(len(getattr(search_context, "boundary_repulsors", ()) or ())),
        )
        tree = search_context.tree

        # 4) Compute safe spacing from the model base shape
        # Use tighter spacing for deployment to allow formations to fit in crowded areas
        # Models can be in base-to-base contact (spacing = 2 * radius) but we allow slightly tighter
        spacing = float(estimated_unit_pack_spacing(self))
        logger.debug("DEBUG: Computed spacing: %.2f inches", float(spacing))

        # 5) Build formation templates
        templates = cached_formation_templates(len(self.models), spacing)
        logger.debug(f"DEBUG: Generated {len(templates)} formation templates: {list(templates.keys())}")

        origin_2d = np.array((start_x, start_y), float)

        # 6) Try each template
        for template_name, offsets in templates.items():
            logger.debug(f"DEBUG: Trying template '{template_name}' with {len(offsets)} positions")

            # world positions in 2D & then lift to 3D + facing
            world = []
            pts2d = offsets + origin_2d
            for x, y in pts2d:
                z = (
                    game_map.get_surface_height_for_model(self.models[len(world)], x, y)
                    if bool(resolve_surface_height)
                    else 0.0
                )
                f = self.calculate_strategic_facing(x, y, game_map) if bool(calculate_facing) else 0.0
                world.append([x, y, z, f])

            # Check individual model base collisions instead of unit footprint
            # This allows unit footprints to overlap as long as individual model bases don't overlap
            model_collision_detected = False
            for i, (dx, dy) in enumerate(offsets):
                model_x = origin_2d[0] + dx
                model_y = origin_2d[1] + dy

                # Create temporary model base at this position
                temp_model = self.models[i] if i < len(self.models) else self.models[0]
                temp_base = temp_model.model_base.get_base_shape()
                temp_base_positioned = translate(temp_base,
                                               model_x - temp_base.centroid.x,
                                               model_y - temp_base.centroid.y)

                # Check collision with obstacles and enemy models only
                # (friendly unit avoidance is handled by the avoid_friendly_units parameter)
                base_hits = query_spatial_index(tree, temp_base_positioned)
                if len(base_hits) > 0:
                    # Check if any hits are actual overlaps (not just touching)
                    for hit in base_hits:
                        if temp_base_positioned.overlaps(hit):
                            model_collision_detected = True
                            break
                    if model_collision_detected:
                        break

            if model_collision_detected:
                logger.debug(f"DEBUG: Template '{template_name}' rejected - model base overlap detected")
                continue

            # Debug: Check if any models are outside battlefield bounds
            models_outside_bounds = 0
            for i, pos in enumerate(world):
                if pos[0] < 0 or pos[0] > game_map.width or pos[1] < 0 or pos[1] > game_map.height:
                    models_outside_bounds += 1

            if models_outside_bounds > 0:
                logger.debug(f"DEBUG: Template '{template_name}' rejected - {models_outside_bounds} models outside battlefield bounds (map: {game_map.width}x{game_map.height})")
                continue

            logger.debug(f"DEBUG: Template '{template_name}' passed footprint check, starting relaxation")

            # Relaxation loop (terrain + self-collisions)
            for relax_iter in range(relax_iters):
                collided = False

                # precompute friendly polys at current trial positions
                friendly = []
                for idx, pos in enumerate(world):
                    base = self.models[idx].model_base.get_base_shape()
                    friendly.append(
                        translate(base,
                                pos[0] - base.centroid.x,
                                pos[1] - base.centroid.y)
                    )

                for i, pos in enumerate(world):
                    poly_i = friendly[i]
                    # gather blockers as a pure Python list
                    hits = query_spatial_index(tree, poly_i) \
                        + [p for j,p in enumerate(friendly) if j != i]

                    # DEBUG: Add defensive programming to catch geometry type errors
                    try:
                        intersects_any = any(poly_i.intersects(b) for b in hits)
                    except TypeError as e:
                        logger.debug(f"DEBUG: TypeError in multi-model intersects check: {e}")
                        logger.debug(f"DEBUG: poly_i type: {type(poly_i)}")
                        logger.debug(f"DEBUG: hits count: {len(hits)}")
                        for idx, hit in enumerate(hits):
                            logger.debug(f"DEBUG: hit {idx}: {type(hit)} - {hit}")
                            if hasattr(hit, 'geom_type'):
                                logger.debug(f"DEBUG:   geom_type: {hit.geom_type}")
                            if hasattr(hit, 'is_valid'):
                                logger.debug(f"DEBUG:   is_valid: {hit.is_valid}")
                        raise

                    if intersects_any:
                        # repel along the vector between centroids
                        b = next(b for b in hits if poly_i.intersects(b))
                        vx = poly_i.centroid.x - b.centroid.x
                        vy = poly_i.centroid.y - b.centroid.y
                        norm = get_dist(vx, vy) or 1.0
                        pos[0] += (vx / norm) * grid_step
                        pos[1] += (vy / norm) * grid_step
                        pos[2] = (
                            game_map.get_surface_height_for_model(self.models[i], pos[0], pos[1])
                            if bool(resolve_surface_height)
                            else 0.0
                        )
                        collided = True

                if not collided:
                    logger.debug(f"DEBUG: Template '{template_name}' completed relaxation after {relax_iter + 1} iterations")
                    break
                elif relax_iter == relax_iters - 1:
                    logger.debug(f"DEBUG: Template '{template_name}' still had collisions after {relax_iters} relaxation iterations")

            # after you've cleared collisions...
            attract_iters = 5
            attract_step = 0.2
            target_min = 0.25
            for _ in range(attract_iters):
                moved = False
                for i, m1 in enumerate(self.models):
                    for j, m2 in enumerate(self.models[i+1:], start=i+1):
                        d = m1.model_base.edge_to_edge_distance(m2.model_base)
                        if d > target_min + 1e-6:
                            # move each halfway toward the other
                            dx = (m2.x - m1.x)
                            dy = (m2.y - m1.y)
                            norm = get_dist(dx, dy)
                            shift = min(attract_step, d/2) / norm
                            m1.model_base.x += dx * shift
                            m1.model_base.y += dy * shift
                            m2.model_base.x -= dx * shift
                            m2.model_base.y -= dy * shift
                            moved = True
                if not moved:
                    break

            # Final overlap catcher
            final_polys = []
            for idx, pos in enumerate(world):
                base = self.models[idx].model_base.get_base_shape()
                final_polys.append(
                    translate(base,
                            pos[0] - base.centroid.x,
                            pos[1] - base.centroid.y)
                )

            # if any true-area overlap, reject this template
            ok = True
            for i in range(len(final_polys)):
                for j in range(i+1, len(final_polys)):
                    if final_polys[i].overlaps(final_polys[j]):
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                logger.debug(f"DEBUG: Template '{template_name}' rejected - final overlap check failed")
                continue

            # Commit & coherency-graph check
            for m, pos in zip(self.models, world):
                m.set_location(*pos)

            coherency_ok = self.check_coherency_graph()
            logger.debug(f"DEBUG: Template '{template_name}' coherency check: {' PASSED' if coherency_ok else ' FAILED'}")

            if coherency_ok:
                logger.debug(f"DEBUG: Successfully found formation using template '{template_name}'")
                return [(x, y, z, f) for x, y, z, f in world]
            else:
                logger.debug(f"DEBUG: Template '{template_name}' rejected - coherency check failed")

        # 7) If none fit, raise or fallback
        logger.debug(f"DEBUG: All {len(templates)} templates failed - no valid formation found")
        # No valid formation found - return None instead of raising exception
        # This allows auto-deployment to try other positions
        return None


    def _create_potential_base(self, x: float, y: float, z: float, facing: float, model: Model = None):
        # Create a new base with the same properties as the specified model's base
        if model is None:
            model = self.models[0]  # Default to first model
        new_base = clone_base(model.model_base)
        new_base.set_position(float(x), float(y), float(z))
        new_base.set_facing(facing)
        return new_base


    def _collides_with_unit_models(self, x: float, y: float, z: float, facing: float, positions: List[Tuple[float, float, float, float]], model: Model = None) -> bool:
        """Check if the model at the given position collides with any other model in the unit."""
        if not positions:
            return False

        if len(self.models) == 1:
            return False

        new_base = self._create_potential_base(x, y, z, facing, model)

        for i, pos in enumerate(positions):
            # Use the corresponding model for each position
            other_model = self.models[i] if i < len(self.models) else self.models[0]
            other_base = self._create_potential_base(pos[0], pos[1], pos[2], pos[3], other_model)
            if new_base.collides_with(other_base):
                logger.debug(f"Collision detected!")
                return True
        return False


    def _is_coherent_within_unit(self, x: float, y: float, z: float, facing: float, positions: List[Tuple[float, float, float, float]], model: Model = None) -> bool:
        """Check if the model at the given position is within coherency with the unit."""
        new_base = self._create_potential_base(x, y, z, facing, model)

        # Check against already placed models
        found_neighbors = 0
        current_neighbors_needed = 0 if len(positions) == 0 else 1 if len(positions) == 1 else self.required_neighbors

        if current_neighbors_needed == 0:
            return True

        for i, pos in enumerate(positions):
            # Use the corresponding model for each position
            other_model = self.models[i] if i < len(self.models) else self.models[0]
            other_base = self._create_potential_base(pos[0], pos[1], pos[2] if len(pos) > 2 else 0.0, pos[3] if len(pos) > 3 else facing, other_model)
            # 10th ed coherency: <=2" horizontal (base edge-to-edge) AND <=5" vertical (base-to-base)
            try:
                horizontal = new_base.get_base_shape().distance(other_base.get_base_shape())
                vertical = abs(float(getattr(new_base, 'z', 0.0)) - float(getattr(other_base, 'z', 0.0)))
            except Exception:
                horizontal = float('inf')
                vertical = float('inf')
            if horizontal <= self.coherency_distance + 1e-6 and vertical <= 5.0 + 1e-6:
                found_neighbors += 1
                if found_neighbors >= current_neighbors_needed:
                    return True
        return False


    def check_coherency_graph(self):
        """
        Returns True if every model in the unit
        has the required number of neighbors within edge-to-edge
        coherency_distance.

        - Units of 1\u20135 models: each model needs at least 1 neighbor.
        - Units of 6+ models: each model needs at least 2 neighbors.
        """
        models = self.models

        for i, m1 in enumerate(models):
            neighbors = 0
            for j, m2 in enumerate(models):
                if i == j:
                    continue
                # 10th ed coherency: <=2" horizontal (base edge-to-edge) AND <=5" vertical (base-to-base)
                try:
                    horizontal = m1.model_base.get_base_shape().distance(m2.model_base.get_base_shape())
                    vertical = abs(float(getattr(m1.model_base, 'z', 0.0)) - float(getattr(m2.model_base, 'z', 0.0)))
                except Exception:
                    horizontal = float('inf')
                    vertical = float('inf')
                if horizontal <= self.coherency_distance + 1e-6 and vertical <= 5.0 + 1e-6:
                    neighbors += 1
                if neighbors >= self.required_neighbors:
                    break

            if neighbors < self.required_neighbors:
                return False

        return True


    def _is_valid_position(self, x: float, y: float, z: float, facing: float, game_map: 'Map', placed_positions: List[Tuple[float, float, float, float]], model: Model = None) -> bool:
        if model is None:
            model = self.models[0]  # Use the first model as a reference
        if not game_map.is_within_boundary(model, (x, y)):
            return False
        if self._check_collision_with_obstacles_or_terrain(game_map, model, (x, y)):
            return False
        if game_map.check_collision_with_other_friendly_units(model, (x, y)):
            return False
        if game_map.check_collision_with_other_enemy_units(model, (x, y)):
            return False
        if self._collides_with_unit_models(x, y, z, facing, placed_positions, model):
            return False
        if not self._is_coherent_within_unit(x, y, z, facing, placed_positions, model):
            return False
        return True


    def maximum_range(self) -> int:
        """Maximum range of the unit."""
        if hasattr(self, 'max_shooting_range'):
            return self.max_shooting_range

        max_range = 0
        for model in self.models:
            max_range = max(max_range, model.maximum_range())
        self.max_shooting_range = max_range
        return max_range


    def print_unit(self) -> str:
        return f"{self.name} :: M: {self.movement}\", T: {self.toughness}, Sv: {self.save}, InvSv: {self.inv_save}, OC: {self.objective_control}"


    def __str__(self):
        return f"{self.name} ({len(self.models)} models)"


    def __repr__(self):
        return f"Unit(name='{self.name}', models={len(self.models)})"


    def __eq__(self, other) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return self._id == other._id


    def __hash__(self) -> int:
        return hash(self._id)


    def can_declare_charge_against(self, target_unit: 'Unit', game: 'Game', *, out_of_turn: bool = False) -> bool:
        """Check if this unit can declare a charge against the target unit."""
        if not self.is_alive() or not target_unit.is_alive():
            return False

        if not self._can_declare_charge_base(game, out_of_turn=out_of_turn):
            return False

        # Only FLY units can charge AIRCRAFT.
        try:
            if bool(getattr(target_unit, "is_aircraft", False)) and not bool(getattr(self, "is_flying", False)):
                return False
        except Exception:
            pass
        try:
            army = self.get_parent_army() if hasattr(self, "get_parent_army") else None
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            target_ok_fn = getattr(sm_mgr, "heresy_undone_target_is_legal", None) if sm_mgr is not None else None
            if callable(target_ok_fn) and not target_ok_fn(self, target_unit, game=game):
                return False
        except Exception:
            pass

        # Cabal of Sorcerers (Temporal Surge): cannot charge until end of turn.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("cabal_temporal_surge_no_charge_turn_owner"):
                owner = str(sr.get("cabal_temporal_surge_no_charge_turn_owner") or "")
                turn = int(sr.get("cabal_temporal_surge_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    try:
                        if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                            return False
                    except Exception:
                        return False
        except Exception:
            pass

        # Swooping Descent: arriving within 9" denies charges until end of turn.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("pain_swooping_descent_no_charge_turn_owner"):
                owner = str(sr.get("pain_swooping_descent_no_charge_turn_owner") or "")
                turn = int(sr.get("pain_swooping_descent_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Cloudstrider: cannot charge until end of turn after 6" deep strike option.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("cloudstrider_no_charge_turn_owner"):
                owner = str(sr.get("cloudstrider_no_charge_turn_owner") or "")
                turn = int(sr.get("cloudstrider_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Eternity Gate: cannot charge until end of turn after setup.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("eternity_gate_no_charge_turn_owner"):
                owner = str(sr.get("eternity_gate_no_charge_turn_owner") or "")
                turn = int(sr.get("eternity_gate_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    override_owner = str(sr.get("hypercrypt_dimensional_corridor_turn_owner", "") or "")
                    override_turn = int(sr.get("hypercrypt_dimensional_corridor_turn", 0) or 0)
                    has_override = bool(sr.get("hypercrypt_dimensional_corridor_active")) and override_owner == owner and override_turn == turn
                    if not has_override and game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Cosmic Precision: cannot charge until end of turn after 6" Deep Strike option.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("cosmic_precision_no_charge_turn_owner"):
                owner = str(sr.get("cosmic_precision_no_charge_turn_owner") or "")
                turn = int(sr.get("cosmic_precision_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Reletavistic Tether: arriving within 9" after the setup override denies charges until end of turn.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("reletavistic_tether_no_charge_turn_owner"):
                owner = str(sr.get("reletavistic_tether_no_charge_turn_owner") or "")
                turn = int(sr.get("reletavistic_tether_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Screaming Descent: cannot charge until end of turn after 6" setup.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("dread_talons_screaming_descent_no_charge_turn_owner"):
                owner = str(sr.get("dread_talons_screaming_descent_no_charge_turn_owner") or "")
                turn = int(sr.get("dread_talons_screaming_descent_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Rapid Manifestation: cannot charge until end of turn after 6" Deep Strike option.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("rapid_manifestation_no_charge_turn_owner"):
                owner = str(sr.get("rapid_manifestation_no_charge_turn_owner") or "")
                turn = int(sr.get("rapid_manifestation_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Combat Manifestation: cannot charge until end of turn after 6" Deep Strike option.
        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict) and sr.get("combat_manifestation_no_charge_turn_owner"):
            owner = str(sr.get("combat_manifestation_no_charge_turn_owner") or "")
            turn_raw = sr.get("combat_manifestation_no_charge_turn", 0)
            try:
                turn = int(turn_raw or 0)
            except (TypeError, ValueError):
                turn = 0
            if owner and game is not None:
                get_current_player = getattr(game, "get_current_player", None)
                current_player = get_current_player() if callable(get_current_player) else None
                current_owner = str(getattr(current_player, "id", "") or "")
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    current_turn = 0
                if current_owner == owner and current_turn == turn:
                    return False

        if isinstance(sr, dict) and sr.get("bridgehead_bellicosa_no_charge_turn_owner"):
            owner = str(sr.get("bridgehead_bellicosa_no_charge_turn_owner") or "")
            turn_raw = sr.get("bridgehead_bellicosa_no_charge_turn", 0)
            try:
                turn = int(turn_raw or 0)
            except (TypeError, ValueError):
                turn = 0
            if owner and game is not None:
                get_current_player = getattr(game, "get_current_player", None)
                current_player = get_current_player() if callable(get_current_player) else None
                current_owner = str(getattr(current_player, "id", "") or "")
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    current_turn = 0
                if current_owner == owner and current_turn == turn:
                    return False

        if isinstance(sr, dict) and sr.get("tau_shortened_blade_no_charge_turn_owner"):
            owner = str(sr.get("tau_shortened_blade_no_charge_turn_owner") or "")
            turn_raw = sr.get("tau_shortened_blade_no_charge_turn", 0)
            try:
                turn = int(turn_raw or 0)
            except (TypeError, ValueError):
                turn = 0
            if owner and game is not None:
                get_current_player = getattr(game, "get_current_player", None)
                current_player = get_current_player() if callable(get_current_player) else None
                current_owner = str(getattr(current_player, "id", "") or "")
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    current_turn = 0
                if current_owner == owner and current_turn == turn:
                    return False

        # Relic Teleportarium: cannot charge until end of turn after 6" Deep Strike option.
        if isinstance(sr, dict) and sr.get("space_marines_inner_circle_relic_teleportarium_no_charge_turn_owner"):
            owner = str(sr.get("space_marines_inner_circle_relic_teleportarium_no_charge_turn_owner") or "")
            turn_raw = sr.get("space_marines_inner_circle_relic_teleportarium_no_charge_turn", 0)
            try:
                turn = int(turn_raw or 0)
            except (TypeError, ValueError):
                turn = 0
            if owner and game is not None:
                get_current_player = getattr(game, "get_current_player", None)
                current_player = get_current_player() if callable(get_current_player) else None
                current_owner = str(getattr(current_player, "id", "") or "")
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    current_turn = 0
                if current_owner == owner and current_turn == turn:
                    return False

        # Cloudstrike: cannot charge until end of turn after 6" Deep Strike option.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("cloudstrike_no_charge_turn_owner"):
                owner = str(sr.get("cloudstrike_no_charge_turn_owner") or "")
                turn = int(sr.get("cloudstrike_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Tunnel Crawlers: cannot charge until end of turn after 6" Deep Strike option.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("tunnel_crawlers_no_charge_turn_owner"):
                owner = str(sr.get("tunnel_crawlers_no_charge_turn_owner") or "")
                turn = int(sr.get("tunnel_crawlers_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Twisted Mirage: cannot charge until end of turn after the setup override is used.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("thousand_sons_twisted_mirage_no_charge_turn_owner"):
                owner = str(sr.get("thousand_sons_twisted_mirage_no_charge_turn_owner") or "")
                turn = int(sr.get("thousand_sons_twisted_mirage_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Fire and Fade: cannot charge until end of turn.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("fire_and_fade_no_charge_turn_owner"):
                owner = str(sr.get("fire_and_fade_no_charge_turn_owner") or "")
                turn = int(sr.get("fire_and_fade_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Venomous Wrath: cannot charge until end of turn.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("serpents_brood_venomous_wrath_no_charge_turn_owner"):
                owner = str(sr.get("serpents_brood_venomous_wrath_no_charge_turn_owner") or "")
                turn = int(sr.get("serpents_brood_venomous_wrath_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # Tactical Acumen: cannot charge until end of turn after the reactive move.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("tactical_acumen_no_charge_turn_owner"):
                owner = str(sr.get("tactical_acumen_no_charge_turn_owner") or "")
                turn = int(sr.get("tactical_acumen_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        return False
        except Exception:
            pass

        # A Foot in the Future: cannot charge until end of turn after the reactive move.
        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict) and sr.get("a_foot_in_the_future_no_charge_turn_owner"):
            owner = str(sr.get("a_foot_in_the_future_no_charge_turn_owner") or "")
            turn_raw = sr.get("a_foot_in_the_future_no_charge_turn", 0)
            try:
                turn = int(turn_raw or 0)
            except (TypeError, ValueError):
                turn = 0
            if owner and game is not None:
                get_current_player = getattr(game, "get_current_player", None)
                current_player = get_current_player() if callable(get_current_player) else None
                current_owner = str(getattr(current_player, "id", "") or "")
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    current_turn = 0
                if current_owner == owner and current_turn == turn:
                    return False

        # The Ephemeral Tome: cannot charge until end of turn after the start-of-Shooting move.
        if isinstance(sr, dict) and sr.get("ephemeral_tome_no_charge_turn_owner"):
            owner = str(sr.get("ephemeral_tome_no_charge_turn_owner") or "")
            turn_raw = sr.get("ephemeral_tome_no_charge_turn", 0)
            try:
                turn = int(turn_raw or 0)
            except (TypeError, ValueError):
                turn = 0
            if owner and game is not None:
                get_current_player = getattr(game, "get_current_player", None)
                current_player = get_current_player() if callable(get_current_player) else None
                current_owner = str(getattr(current_player, "id", "") or "")
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    current_turn = 0
                if current_owner == owner and current_turn == turn:
                    return False

        # Flickerjump: cannot charge until end of turn.
        try:
            sr = getattr(self, "special_rules", None)
            if isinstance(sr, dict) and sr.get("flickerjump_no_charge_turn_owner"):
                owner = str(sr.get("flickerjump_no_charge_turn_owner") or "")
                turn = int(sr.get("flickerjump_no_charge_turn", 0) or 0)
                if owner and game is not None:
                    if game.get_current_player().id == owner and int(getattr(game, "turn", 0) or 0) == turn:
                        if not self.has_empyric_ambush():
                            return False
        except Exception:
            pass

        if self._thrill_seekers_restriction_reason(target_unit, game):
            return False

        # Charge declaration has a hard 12" target gate; charge-roll modifiers only
        # affect the later charge move distance after a legal declaration is made.
        distance = game.map.get_distance_between_units(self, target_unit)
        if float(distance) > 12.0 + 1e-6:
            return False

        return True


    def _can_declare_charge_base(self, game: 'Game', *, out_of_turn: bool = False) -> bool:
        from ...engine.combat_timing import disembark_charge_blocked

        if not self.is_alive():
            return False
        if bool(getattr(self, "is_aircraft", False)):
            return False
        if self.round_state.attempted_charge_this_round and not out_of_turn:
            return False
        try:
            army = self.get_parent_army()
            mgr = getattr(army, "orks_detachments", None) if army is not None else None
            blocks_fn = getattr(mgr, "speedwaaagh_turbo_boostas_blocks_charge", None) if mgr is not None else None
            if callable(blocks_fn) and bool(blocks_fn(self, game=game)):
                return False
        except Exception:
            pass
        if self.round_state.advanced_this_round and not self.can_charge_after_advance():
            return False
        if disembark_charge_blocked(self, game=game, out_of_turn=out_of_turn):
            return False
        if self.round_state.fell_back_this_round and not self.can_charge_after_fall_back():
            return False
        if getattr(self.round_state, 'action_locked_until_turn_end', False):
            return False
        if self.arrived_from_reserves_this_turn and not self.can_charge_after_arriving_from_reserves():
            return False

        # Units within Engagement Range of any enemy cannot declare charges.
        try:
            game_map = getattr(game, "map", None)
        except Exception:
            game_map = None
        if game_map is not None:
            try:
                enemy_units = list(game_map.get_enemy_units(self) or [])
            except Exception:
                enemy_units = []
            for enemy in enemy_units:
                if not getattr(enemy, "is_alive", False):
                    continue
                if game_map.is_within_engagement_range(self, enemy):
                    return False
        return True


    def can_declare_charge(self, game: 'Game', *, out_of_turn: bool = False) -> bool:
        """Check if this unit is eligible to declare any charge this phase."""
        if not self._can_declare_charge_base(game, out_of_turn=out_of_turn):
            return False
        try:
            game_map = getattr(game, "map", None)
        except Exception:
            game_map = None
        if game_map is None:
            return False
        enemy_units = [u for u in game_map.get_enemy_units(self) if u.is_alive()]
        if not enemy_units:
            return False
        sycophantic_active_fn = getattr(self, "_carnival_sycophantic_surge_active_for_charge", None)
        sycophantic_target_fn = getattr(self, "_carnival_sycophantic_target_condition_met", None)
        sycophantic_active = bool(callable(sycophantic_active_fn) and sycophantic_active_fn(game=game))
        if sycophantic_active and not callable(sycophantic_target_fn):
            return False
        for enemy in enemy_units:
            try:
                if float(game_map.get_distance_between_units(self, enemy)) > 12.0 + 1e-6:
                    continue
                if sycophantic_active and not bool(sycophantic_target_fn(enemy, game)):
                    continue
                return True
            except Exception:
                continue
        return False


    def validate_charge_end_state(self, target_units: list['Unit'], game_map: 'Map') -> tuple[bool, str]:
        """Validate charge end position against declared targets and non-targets."""
        if not target_units:
            return False, "Charge requires at least one target"
        target_ids = {get_entity_id(u) for u in list(target_units or []) if u is not None}
        missing = []
        for target in target_units:
            if target is None or not getattr(target, "is_alive", False):
                missing.append(getattr(target, "name", "Unknown"))
                continue
            if not game_map.is_within_engagement_range(self, target):
                missing.append(getattr(target, "name", "Unknown"))
        if missing:
            return False, f"Charge must end within Engagement Range of all targets (missing: {', '.join(missing)})"
        # Cannot end within Engagement Range of non-target enemy units.
        for enemy in list(game_map.get_enemy_units(self) or []):
            if enemy is None or not getattr(enemy, "is_alive", False):
                continue
            if get_entity_id(enemy) in target_ids:
                continue
            if game_map.is_within_engagement_range(self, enemy):
                return False, f"Charge cannot end within Engagement Range of non-target unit {enemy.name}"
        return True, ""
