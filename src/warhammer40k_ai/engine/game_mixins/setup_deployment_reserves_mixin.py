from __future__ import annotations

from ._shared import *  # noqa: F401,F403
from ..prospective_positions import calculate_prospective_model_positions
import logging
logger = logging.getLogger(__name__)


class GameSetupDeploymentReservesMixin:
    def _pending_reinforcements_select_unit_request(self):
        queue = getattr(self, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return None
        from ..decision_kinds import DECISION_SELECT_UNIT

        for request in list(queue.list() or []):
            if str(getattr(request, "decision_type", "") or "") != DECISION_SELECT_UNIT:
                continue
            ctx = dict(getattr(request, "context", {}) or {})
            if str(ctx.get("phase_name", "") or "").strip().upper() != "MOVEMENT_PHASE":
                continue
            if str(ctx.get("phase_step", "") or "").strip().upper() != "REINFORCEMENTS":
                continue
            return request
        return None

    def _reinforcements_step_skipped_unit_ids_set(self) -> set[str]:
        values = getattr(self, "_reinforcements_step_skipped_ids", set())
        return {str(value or "").strip() for value in list(values or []) if str(value or "").strip()}

    def _mark_reinforcements_step_unit_skipped(self, unit_id: str) -> None:
        text = str(unit_id or "").strip()
        if not text:
            return
        values = set(self._reinforcements_step_skipped_unit_ids_set())
        values.add(text)
        self._reinforcements_step_skipped_ids = values

    def _standard_reserves_arrival_excluded_unit_ids(self, player: Player) -> set[str]:
        excluded: set[str] = set()
        if player is None:
            return excluded
        army = player.get_army() if player is not None else None
        csm_mgr = getattr(army, "chaos_space_marines_detachments", None) if army is not None else None
        excludes_standard_arrival = (
            getattr(csm_mgr, "deceptors_falsehood_excludes_standard_reserves_arrival", None)
            if csm_mgr is not None
            else None
        )
        if not callable(excludes_standard_arrival):
            return excluded
        for unit in list(self.get_units_in_reserves(player) or []):
            try:
                if not bool(excludes_standard_arrival(unit, game=self, player=player)):
                    continue
            except Exception:
                continue
            try:
                unit_id = str(get_entity_id(unit) or "").strip()
            except Exception:
                unit_id = ""
            if unit_id:
                excluded.add(unit_id)
        return excluded

    def _reserve_entry_kind_for_unit(self, unit: Unit) -> str:
        if unit is None:
            return "other"
        try:
            if bool(getattr(unit, "has_deep_strike", lambda: False)()):
                return "deep_strike"
        except Exception:
            pass
        try:
            if bool(getattr(unit, "is_in_strategic_reserves", lambda: False)()):
                return "strategic_reserve"
        except Exception:
            pass
        return "other"

    def _reinforcements_step_selection_state(self, player: Player) -> tuple[list[Unit], bool, set[str]]:
        if player is None:
            return ([], True, set())
        excluded_ids = self._standard_reserves_arrival_excluded_unit_ids(player)
        skipped_ids = self._reinforcements_step_skipped_unit_ids_set()
        units_that_can_arrive = []
        for unit in list(self.get_units_that_can_arrive_from_reserves(player) or []):
            unit_id = str(get_entity_id(unit) or "").strip()
            if not unit_id or unit_id in excluded_ids or unit_id in skipped_ids:
                continue
            units_that_can_arrive.append(unit)
        units_that_must_arrive = []
        for unit in list(self.get_units_that_must_arrive_from_reserves(player) or []):
            unit_id = str(get_entity_id(unit) or "").strip()
            if not unit_id or unit_id in excluded_ids or unit_id in skipped_ids:
                continue
            units_that_must_arrive.append(unit)
        selectable = units_that_must_arrive or units_that_can_arrive
        selectable.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        must_ids = {
            str(get_entity_id(unit) or "").strip()
            for unit in list(units_that_must_arrive or [])
            if str(get_entity_id(unit) or "").strip()
        }
        allow_pass = not bool(must_ids)
        return (selectable, allow_pass, must_ids)

    def _queue_movement_phase_reinforcements_selection(self, player=None):
        if not bool(getattr(self, "is_authoritative", True)):
            return None
        if str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return None
        active_player = player if player is not None else self.get_current_player()
        if active_player is None or active_player is not self.get_current_player():
            return None
        pending_request = self._pending_reinforcements_select_unit_request()
        if pending_request is not None:
            return pending_request
        selectable, allow_pass, must_ids = self._reinforcements_step_selection_state(active_player)
        if not selectable:
            return None
        from ..decision_requests import queue_select_unit_request

        reserve_entry_kinds_by_unit_id = {
            str(get_entity_id(unit) or ""): self._reserve_entry_kind_for_unit(unit)
            for unit in list(selectable or [])
            if str(get_entity_id(unit) or "")
        }
        return queue_select_unit_request(
            self,
            selectable,
            player_id=getattr(active_player, "id", None),
            phase_name="MOVEMENT_PHASE",
            phase_step="REINFORCEMENTS",
            selection_purpose="ACTIVATE_REINFORCEMENT_UNIT",
            allow_pass=allow_pass,
            context={
                "battle_round": int(getattr(self, "turn", 0) or 0),
                "pending_must_arrival_unit_ids": sorted(must_ids),
                "reserve_entry_kinds_by_unit_id": reserve_entry_kinds_by_unit_id,
            },
        )

    def _reinforcements_step_has_pending_decisions(self) -> bool:
        if not bool(getattr(self, "reinforcements_step_active", False)):
            return False
        queue = getattr(self, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        return bool(list(queue.list() or []))

    def _maybe_queue_movement_phase_reinforcements_followup(self, request: DecisionRequest, result: DecisionResult) -> None:
        if request is None or result is None:
            return
        if str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        if not bool(getattr(self, "reinforcements_step_active", False)):
            return
        if str(getattr(request, "decision_type", "") or "").strip() != DECISION_MOVE_UNIT:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("placement_kind", "") or "").strip() != "reserves_arrival":
            return
        unit_id = str(ctx.get("unit_id", "") or "").strip()
        if bool(getattr(result, "payload", {}).get("skipped", False)):
            self._mark_reinforcements_step_unit_skipped(unit_id)
        self._queue_movement_phase_reinforcements_selection(player=self.get_current_player())

    def on_select_unit_resolved(
        self,
        *,
        request: DecisionRequest,
        selected_unit_id: str | None,
        selected_unit=None,
        payload: dict | None = None,
        pass_selected: bool = False,
    ):
        ctx = dict(getattr(request, "context", {}) or {})
        if (
            str(ctx.get("phase_name", "") or "").strip().upper() == "MOVEMENT_PHASE"
            and str(ctx.get("phase_step", "") or "").strip().upper() == "REINFORCEMENTS"
        ):
            if bool(pass_selected) or selected_unit is None or not selected_unit_id:
                return {
                    "selected_unit_id": selected_unit_id,
                    "pass_selected": bool(pass_selected),
                    "payload": dict(payload or {}),
                }
            must_ids = {
                str(value or "").strip()
                for value in list(ctx.get("pending_must_arrival_unit_ids", []) or [])
                if str(value or "").strip()
            }
            allow_skip = str(selected_unit_id or "") not in must_ids
            request_obj = self._build_reserves_arrival_request(selected_unit, allow_skip=allow_skip)
            if request_obj is not None:
                self.request_decision(request_obj)
            return {
                "selected_unit_id": selected_unit_id,
                "pass_selected": False,
                "payload": dict(payload or {}),
            }
        handler = getattr(super(), "on_select_unit_resolved", None)
        if callable(handler):
            return handler(
                request=request,
                selected_unit_id=selected_unit_id,
                selected_unit=selected_unit,
                payload=dict(payload or {}),
                pass_selected=pass_selected,
            )
        return None

    def add_player(self, player: Player) -> None:
        """Add a player to the game."""
        self.players.append(player)
        player.set_game(self)
        player.assign_default_ui_color(len(self.players) - 1)
        self.refresh_rule_subscribers()

    def add_objective(self, objective: Objective) -> None:
        """Add an objective to the game."""
        self.objectives.append(objective)

    def get_battlefield_size(self) -> tuple[int, int]:
        return self.battlefield.width, self.battlefield.height

    def set_attacker_defender(self, attacker_index: int, defender_index: int) -> None:
        """DEPRECATED: Set which player is the attacker and which is the defender.
        
        This method should not be used - attacker/defender roles are determined
        during the DETERMINE_ATTACKER_AND_DEFENDER setup phase only.
        """
        import warnings
        warnings.warn("set_attacker_defender is deprecated. Roles are determined during setup phase.", 
                     DeprecationWarning, stacklevel=2)
        self.attacker_index = attacker_index
        self.defender_index = defender_index
        # Defender always starts deployment
        self.deployment_turn_index = self.defender_index

    def get_current_deployment_player(self) -> Player:
        """Get the player whose turn it is to deploy."""
        return self.players[self.deployment_turn_index]

    def get_attacker(self) -> Player:
        """Get the attacking player."""
        return self.players[self.attacker_index]

    def get_defender(self) -> Player:
        """Get the defending player."""
        return self.players[self.defender_index]

    def is_deployment_phase(self) -> bool:
        """Check if we're in the deployment phase."""
        # We're in deployment phase if any units are not deployed and it's turn 1
        if self.turn != 1:
            return False
        
        for player in self.players:
            army = player.get_army()
            if army:
                undeployed_units = [u for u in army.units if not u.deployed]
                if undeployed_units:
                    return True
        return False

    def can_player_deploy_unit(self, player: Player) -> bool:
        """Check if the given player can deploy a unit (i.e., it's their deployment turn)."""
        if not self.is_deployment_phase():
            return False
        return player == self.get_current_deployment_player()

    def get_deployable_units(self, player: Player) -> List['Unit']:
        """Get units that the player can deploy during the deployment phase."""
        if not player.get_army():
            return []
        # Units with deployed=False still need to be placed on the battlefield.
        # Units with deployed=True have been handled (battlefield placement already done OR start in reserves OR start embarked/attached).
        deployable: List['Unit'] = []
        for u in list(player.get_army().units or []):
            if u is None:
                continue
            if getattr(u, "deployed", False):
                continue

            # Attached leaders deploy with their bodyguard
            if u.is_attached_leader:
                continue
            # Joined support artillery models deploy with their bodyguard
            if bool(getattr(u, "is_joined_support", False)):
                continue

            # Embarked units deploy with their transport
            if u.is_embarked or getattr(u, "embarked_in", None) is not None:
                continue

            # Units allocated to any reserves are not deployed now
            if u.reserve_status in ("reserves", "strategic_reserves"):
                continue

            deployable.append(u)

        return deployable

    def record_deployment_action(self, player: Player, unit: 'Unit', action: str, location: tuple = None) -> None:
        """Record a deployment action for display in the InfoPane."""
        if action == 'deployed' and location:
            # Accept both 2D (x,y) and 3D (x,y,z) tuples; ignore extra fields (e.g. facing)
            if not isinstance(location, (list, tuple)) or len(location) < 2:
                raise RuntimeError("Deployment location must provide at least x and y coordinates.")
            x = float(location[0])
            y = float(location[1])
            z = float(location[2]) if len(location) > 2 else 0.0

            if x is not None and y is not None:
                if abs(z) > 1e-6:
                    action_text = f"{unit.name} deployed at ({x:.1f}, {y:.1f}, {z:.1f})"
                else:
                    action_text = f"{unit.name} deployed at ({x:.1f}, {y:.1f})"
            else:
                action_text = f"{unit.name} deployed"
        elif action == 'reserves':
            action_text = f"{unit.name} placed in Reserves"
        elif action == 'strategic_reserves':
            action_text = f"{unit.name} placed in Strategic Reserves"
        else:
            action_text = f"{unit.name} - {action}"
        
        self.deployment_actions[player.id] = action_text

    def clear_deployment_actions(self) -> None:
        """Clear deployment action history after deployment phase ends."""
        self.deployment_actions = {}
        self.deployment_notice = None
        self.deployment_skip_turns = {}

    def _has_any_other_deployable_units(self, player_index: int) -> bool:
        """Return True if any other player (besides player_index) has deployable units."""
        for i, p in enumerate(self.players):
            if i == player_index:
                continue
            if self.get_deployable_units(p):
                return True
        return False

    def advance_deployment_turn(self, last_deployed_unit: Optional['Unit'] = None) -> None:
        """Advance to the next player's deployment turn.

        Special rule: If the current player deploys a TITANIC unit, they skip their next deployment turn.
        """
        if not self.is_deployment_phase():
            return

        n = len(self.players)
        if n <= 0:
            return

        # If a TITANIC unit was just deployed, the current player skips their next deployment turn.
        if last_deployed_unit is not None and last_deployed_unit.is_titanic:
            cur_idx = int(self.deployment_turn_index)
            self.deployment_skip_turns[cur_idx] = int(self.deployment_skip_turns.get(cur_idx, 0)) + 1
            deploying_player = self.players[cur_idx]
            opponent_idx = (cur_idx + 1) % n
            opponent_player = self.players[opponent_idx]
            if self.get_deployable_units(opponent_player):
                self.deployment_notice = (
                    f"{deploying_player.name} deployed a TITANIC unit; they will skip their next deployment turn. "
                    f"{opponent_player.name} will deploy again."
                )
            else:
                self.deployment_notice = (
                    f"{deploying_player.name} deployed a TITANIC unit; they would skip their next deployment turn "
                    f"(no opponent units left to benefit)."
                )

        # Find the next eligible player:
        # - Skip players with no deployable units
        # - Apply "skip next deployment turn" unless there are no other deployable units remaining
        next_idx = (int(self.deployment_turn_index) + 1) % n
        attempts = 0
        while attempts < n:
            skip_cnt = int(self.deployment_skip_turns.get(next_idx, 0) or 0)
            if skip_cnt > 0 and self._has_any_other_deployable_units(next_idx):
                # Consume one skip and move to the next player.
                self.deployment_skip_turns[next_idx] = skip_cnt - 1
                skipped_player = self.players[next_idx]
                other_player = self.players[(next_idx + 1) % n]
                self.deployment_notice = (
                    f"{skipped_player.name} skips this deployment turn (TITANIC rule). "
                    f"{other_player.name} deploys again."
                )
                next_idx = (next_idx + 1) % n
                attempts += 1
                continue

            candidate_player = self.players[next_idx]
            if self.get_deployable_units(candidate_player):
                self.deployment_turn_index = next_idx
                return

            next_idx = (next_idx + 1) % n
            attempts += 1

        # Fallback: leave turn index unchanged if nobody is deployable (deployment is effectively done).
        return

    def complete_deployment_phase(self, manual_phases: bool = False) -> None:
        """Auto-deployment disabled; units must be deployed via UI/controller."""
        logger.warning("WARN: Auto-deployment disabled; deploy units via UI/controller.")
        self.waiting_for_deployment_input = True
        return

    def auto_deploy_unit(self, unit: 'Unit') -> bool:
        """Auto-deployment disabled; units must be deployed via UI/controller."""
        name = getattr(unit, "name", "Unit")
        logger.warning("WARN: auto_deploy_unit called for %s; manual placement required.", name)
        return False

    def _is_position_too_crowded(self, x: float, y: float, unit: 'Unit', player_id: str) -> bool:
        """Quick check if a position is too close to existing units to likely succeed."""
        # Much more reasonable minimum distance - just need to avoid immediate overlap
        min_distance = max(2.0, len(unit.models) * 0.4)  # Reduced from 4.0 and 0.8
        
        # Check distance to all deployed units
        for player in self.players:
            if not player.get_army():
                continue
            for existing_unit in player.get_army().units:
                if not existing_unit.deployed or existing_unit.reserve_status != 'deployed':
                    continue
                
                # Check distance to closest model in existing unit
                closest_distance = float('inf')
                for model in existing_unit.models:
                    if model.is_alive:
                        model_pos = model.get_location()
                        if model_pos:
                            distance = ((x - model_pos[0]) ** 2 + (y - model_pos[1]) ** 2) ** 0.5
                            closest_distance = min(closest_distance, distance)

                if closest_distance < min_distance:
                    return True
        
        return False

    def _get_infiltrate_search_zones(self, player_id: str, battlefield_width: float, battlefield_height: float) -> list:
        """Get valid search zones for infiltrate units (avoiding enemy deployment zones and 9\" buffer)."""
        # We intentionally do NOT derive "safe" search rectangles from deployment-zone bounding boxes.
        # Infiltrate legality is enforced by the validation logic itself (enemy zone + 9" buffer + enemy models).
        margin = 3.0
        return [(margin, battlefield_width - margin, margin, battlefield_height - margin)]

    def _deploy_unit_at_position(self, unit: 'Unit', x: float, y: float, z: float) -> bool:
        """Deploy a unit at the specified position using the same flow as manual deployment."""
        # Use the exact same approach as manual deployment in GameView.on_mouse_press
        # Calculate model positions (this also sets the positions internally)
        # CRITICAL: Use deployment-specific boundary repulsors to ensure models stay within deployment zones
        # This must match the repulsors used in is_valid_deployment_position for consistency
        deployment_repulsors = self.get_boundary_repulsors(unit, context='deployment')
        model_positions = unit.calculate_model_positions(
            x, y, self.map, avoid_friendly_units=False, boundary_repulsors=deployment_repulsors
        )

        if not model_positions:
            logger.debug(f"DEBUG: Infiltrate - no model positions found for {unit.name} at candidate ({x:.1f}, {y:.1f})")
            return False

        # CRITICAL: Validate that all models are actually within deployment zone after positioning
        # This is a final safety check to catch any edge cases where models extend outside zones
        # EXCEPTION: Skip this check for Infiltrate units as they can deploy outside deployment zones
        parent_army = unit.get_parent_army()
        player_id = parent_army.player.id if parent_army and parent_army.player else None
        if player_id and not unit.has_infiltrate():
            for model, position in zip(unit.models, model_positions):
                model_x, model_y = position[0], position[1]
                if not self.is_position_wholly_in_deployment_zone(model_x, model_y, model.model_base, player_id):
                    logger.error("CRITICAL: Auto-deployment validation failed - "
                        f"{unit.name} {model.name} at ({model_x:.1f}, {model_y:.1f}) extends outside deployment zone")
                    return False

        # Unit position is now determined by model positions

        # Place unit on map (same as manual)
        if self.map and self.map.place_unit(unit):
            # Don't set unit.deployed here - let the calling function handle it
            return True
        return False

    def _auto_position_models(self, unit: 'Unit', center_x: float, center_y: float, center_z: float) -> None:
        """Simple model positioning for auto-deployment without complex validation."""
        import math
        
        if len(unit.models) == 1:
            # Single model - place at center
            unit.models[0].set_location(center_x, center_y, center_z, 0.0)
        else:
            # Multiple models - arrange in a simple circle or line
            coherency_distance = unit.coherency_distance
            models_per_row = min(len(unit.models), 5)  # Max 5 models per row
            
            for i, model in enumerate(unit.models):
                if len(unit.models) <= 5:
                    # Small unit - arrange in a line
                    offset_x = (i - (len(unit.models) - 1) / 2) * (coherency_distance * 0.8)
                    model_x = center_x + offset_x
                    model_y = center_y
                else:
                    # Larger unit - arrange in rows
                    row = i // models_per_row
                    col = i % models_per_row
                    offset_x = (col - (models_per_row - 1) / 2) * (coherency_distance * 0.8)
                    offset_y = row * (coherency_distance * 0.8)
                    model_x = center_x + offset_x
                    model_y = center_y + offset_y
                
                model.set_location(model_x, model_y, center_z, 0.0)

    def is_position_in_deployment_zone(self, x: float, y: float, player_id: str) -> bool:
        """Check if a position is within a player's deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return False
        
        if player_id not in self.deployment_zones:
            return False
        
        zone = self.deployment_zones[player_id]
        
        # Only mission zones are supported
        if 'mission_zones' in zone and zone['mission_zones']:
            for mission_zone in zone['mission_zones']:
                if mission_zone.contains_point(x, y):
                    return True
        return False

    def is_model_wholly_in_deployment_zone(self, model: 'Model', player_id: str) -> bool:
        """Check if a model's entire base is wholly within a player's deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            raise RuntimeError("Deployment zones not configured (invalid configuration).")
        
        if player_id not in self.deployment_zones:
            return False
        
        zone = self.deployment_zones[player_id]
        
        # Get model position and base size
        model_x, model_y = model.get_location()[:2]
        base = model.model_base
        base_radius = base.get_radius()
        
        # Require mission_zones polygons
        if 'mission_zones' not in zone or not zone['mission_zones']:
            raise RuntimeError("Deployment zone missing mission_zones polygons (invalid configuration).")

        for mission_zone in zone['mission_zones']:
            if base.base_type.name == 'CIRCULAR':
                if mission_zone.contains_circular_base(model_x, model_y, base_radius):
                    return True
            else:
                base_vertices = base.get_vertices_at_position(model_x, model_y)
                if mission_zone.contains_polygon_base(base_vertices):
                    return True
        return False

    def is_position_wholly_in_deployment_zone(self, x: float, y: float, model_base, player_id: str) -> bool:
        """Check if a model base at (x,y) is wholly within the player's deployment zone,
        using mission zones with cutout-aware Shapely checks when available."""
        # Require configured zones
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return False

        # Player must have a zone
        if player_id not in self.deployment_zones:
            return False

        zone_info = self.deployment_zones[player_id]

        # Only support mission_zones from missions.py with cutouts
        if 'mission_zones' in zone_info and zone_info['mission_zones']:
            for mission_zone in zone_info['mission_zones']:
                if model_base.base_type.name == 'CIRCULAR':
                    # Coerce radius to scalar
                    radius_val = getattr(model_base, 'radius', None)
                    if radius_val is None:
                        radius_val = model_base.get_radius() if hasattr(model_base, 'get_radius') else 0.5
                    if isinstance(radius_val, (list, tuple)):
                        radius_val = float(max(radius_val)) if radius_val else 0.5
                    else:
                        radius_val = float(radius_val)
                    if mission_zone.contains_circular_base(x, y, radius_val):
                        return True
                else:
                    # Use provided Shapely geometry from the base itself.
                    if not hasattr(model_base, 'get_base_shape_at'):
                        return False
                    base_geom = model_base.get_base_shape_at(x, y, getattr(model_base, 'facing', 0.0))
                    if mission_zone.contains_base_geometry(base_geom):
                        return True
            return False
        return False

    def is_position_in_enemy_deployment_zone(self, x: float, y: float, player_id: str) -> bool:
        """Check if a position is within any enemy deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return False
        
        for zone_player_id, zone in self.deployment_zones.items():
            if zone_player_id != player_id:
                # Deployment zones are polygons (mission_zones); rectangular zones are not supported.
                if 'mission_zones' not in zone or not zone['mission_zones']:
                    raise RuntimeError("Deployment zone missing mission_zones polygons (invalid configuration).")
                for mission_zone in zone['mission_zones']:
                    if mission_zone.contains_point(x, y):
                        return True
        return False

    def get_distance_to_enemy_deployment_zone(self, x: float, y: float, player_id: str) -> float:
        """Get the minimum distance from a position to any enemy deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return float('inf')
        
        min_distance = float('inf')
        
        for zone_player_id, zone in self.deployment_zones.items():
            if zone_player_id != player_id and 'mission_zones' in zone and zone['mission_zones']:
                from shapely.geometry import Point as _ShPoint
                from shapely.geometry import Polygon as _ShPoly
                pt = _ShPoint(x, y)
                for mission_zone in zone['mission_zones']:
                    poly = _ShPoly(mission_zone.vertices)
                    d = pt.distance(poly)
                    if d < min_distance:
                        min_distance = d
        
        return min_distance

    def get_distance_to_enemy_models(self, x: float, y: float, player_id: str) -> float:
        """Get the minimum distance from a position to any enemy model."""
        min_distance = float('inf')
        
        for player in self.players:
            if player.id != player_id and player.get_army():
                for unit in player.get_army().units:
                    if unit.deployed and unit.reserve_status == 'deployed':
                        for model in unit.models:
                            model_x, model_y = model.get_location()[:2]
                            distance = ((x - model_x) ** 2 + (y - model_y) ** 2) ** 0.5
                            min_distance = min(min_distance, distance)
        
        return min_distance

    def get_boundary_repulsors(self, unit: 'Unit', context: str = 'deployment') -> List:
        """Generate boundary repulsors for spatial collision detection.
        
        Args:
            unit: The unit being positioned
            context: 'deployment' or 'movement' - determines which boundaries to include
            
        Returns:
            List of Shapely polygons representing boundary repulsors
        """
        from shapely.geometry import Polygon, Point
        from shapely.affinity import scale
        
        repulsors = []
        battlefield_width, battlefield_height = self.get_battlefield_size()
        player_id = unit.get_parent_army().player.id if unit.get_parent_army() and unit.get_parent_army().player else None
        
        if context == 'deployment':
            # For deployment, add deployment zone boundaries (mission-aware) and cutouts as repulsors
            if hasattr(self, 'deployment_zones') and self.deployment_zones and player_id:
                if player_id in self.deployment_zones:
                    zone = self.deployment_zones[player_id]
                    repulsor_thickness = 0.5  # 0.5 inch thick edge repulsor ring

                    # New mission system: polygon zones + cutouts
                    if 'mission_zones' in zone and zone['mission_zones']:
                        from shapely.geometry import Polygon as _ShPoly
                        for mz in zone['mission_zones']:
                            poly = _ShPoly(mz.vertices)
                            # Outer ring to repel from edges (outside only)
                            ring = poly.buffer(repulsor_thickness).difference(poly)
                            if not ring.is_empty:
                                repulsors.append(ring)
                            # Cutouts act as hard blockers
                            if getattr(mz, 'cutouts', None):
                                for c in mz.cutouts:
                                    cg = c.get_shapely_geometry()
                                    if cg is not None and not cg.is_empty:
                                        repulsors.append(cg)
                    else:
                        raise RuntimeError("Deployment zone missing mission_zones polygons (invalid configuration).")
        
        elif context == 'movement':
            # For movement, add battlefield edge boundaries as repulsors
            # This prevents units from moving off the battlefield
            repulsor_thickness = 0.5  # 0.5 inch thick repulsor zones
            
            # Left battlefield edge repulsor
            left_edge = Polygon([
                (-repulsor_thickness, -repulsor_thickness),
                (0, -repulsor_thickness),
                (0, battlefield_height + repulsor_thickness),
                (-repulsor_thickness, battlefield_height + repulsor_thickness)
            ])
            repulsors.append(left_edge)
            
            # Right battlefield edge repulsor
            right_edge = Polygon([
                (battlefield_width, -repulsor_thickness),
                (battlefield_width + repulsor_thickness, -repulsor_thickness),
                (battlefield_width + repulsor_thickness, battlefield_height + repulsor_thickness),
                (battlefield_width, battlefield_height + repulsor_thickness)
            ])
            repulsors.append(right_edge)
            
            # Bottom battlefield edge repulsor
            bottom_edge = Polygon([
                (-repulsor_thickness, -repulsor_thickness),
                (battlefield_width + repulsor_thickness, -repulsor_thickness),
                (battlefield_width + repulsor_thickness, 0),
                (-repulsor_thickness, 0)
            ])
            repulsors.append(bottom_edge)
            
            # Top battlefield edge repulsor
            top_edge = Polygon([
                (-repulsor_thickness, battlefield_height),
                (battlefield_width + repulsor_thickness, battlefield_height),
                (battlefield_width + repulsor_thickness, battlefield_height + repulsor_thickness),
                (-repulsor_thickness, battlefield_height + repulsor_thickness)
            ])
            repulsors.append(top_edge)
        
        return repulsors

    def is_valid_deployment_position(self, unit: 'Unit', x: float, y: float, player_id: str) -> bool:
        """Check if a position is valid for deploying a unit during deployment phase."""
        # Units in reserves don't need position validation
        if unit.reserve_status in ['reserves', 'strategic_reserves']:
            return True

        from ...utility.deployment_special_rules import (
            is_aegis_defence_line_deployment_unit,
            validate_aegis_defence_line_deployment,
        )

        def _validate_datasheet_deployment_rules(model_positions: list[tuple]) -> bool:
            if not is_aegis_defence_line_deployment_unit(unit):
                return True
            base_entries: list[tuple[str, object]] = []
            create_potential_base = getattr(unit, "_create_potential_base", None)
            for idx, (model, position) in enumerate(zip(unit.models, model_positions)):
                model_x = float(position[0])
                model_y = float(position[1])
                model_z = float(position[2]) if len(position) > 2 else 0.0
                model_facing = float(position[3]) if len(position) > 3 else float(getattr(model.model_base, "facing", 0.0))
                candidate_base = model.model_base
                if callable(create_potential_base):
                    maybe_base = create_potential_base(model_x, model_y, model_z, model_facing, model=model)
                    if maybe_base is not None:
                        candidate_base = maybe_base
                model_name = str(getattr(model, "name", "") or f"Model #{idx + 1}")
                base_entries.append((model_name, candidate_base))

            valid, reason = validate_aegis_defence_line_deployment(base_entries)
            if not valid:
                logger.debug(
                    "DEBUG: Datasheet deployment validation failed for %s: %s",
                    unit.name,
                    reason,
                )
            return bool(valid)

        # Check if unit has Infiltrate ability
        if unit.has_infiltrate():
            # Infiltrate units can deploy anywhere except:
            # 1. Inside enemy deployment zone
            # 2. Within 9" of enemy deployment zone
            # 3. Within 9" of enemy models

            # For infiltrate units, we need to check each model's base at the proposed position
            # Calculate model positions using the same logic as unit deployment
            # NOTE: Don't use boundary_repulsors for validation - they make formation finding too restrictive
            # During deployment, use relaxed friendly unit avoidance to allow tighter formations
            # Use deployment boundary repulsors (mission-zone aware) to guide formation inside zone
            deployment_repulsors = self.get_boundary_repulsors(unit, context='deployment')
            model_positions = calculate_prospective_model_positions(
                unit,
                x,
                y,
                self.map,
                avoid_friendly_units=False,
                boundary_repulsors=deployment_repulsors,
            )

            if not model_positions:
                return False

            if not _validate_datasheet_deployment_rules(model_positions):
                return False

            from ...battlefield.map import validate_ruins_placement
            for model, position in zip(unit.models, model_positions):
                model_x, model_y = position[0], position[1]

                # Check if any part of the model is in enemy deployment zone
                if self.is_position_in_enemy_deployment_zone(model_x, model_y, player_id):
                    model_name = getattr(model, 'name', 'model')
                    logger.debug(f"DEBUG: Infiltrate - {unit.name} {model_name} at ({model_x:.1f}, {model_y:.1f}) "
                        "is inside enemy deployment zone")
                    return False

                # Check 9" distance to enemy deployment zone (from model edge)
                base_radius = model.model_base.get_radius()
                distance_to_enemy_zone = self.get_distance_to_enemy_deployment_zone(model_x, model_y, player_id)
                if distance_to_enemy_zone - base_radius < 9.0:
                    model_name = getattr(model, 'name', 'model')
                    logger.debug(f"DEBUG: Infiltrate - {unit.name} {model_name} too close to enemy zone: "
                        f"edge_distance={distance_to_enemy_zone:.2f}\" base_radius={base_radius:.2f}\" < 9\"")
                    return False

                # Check 9" distance to enemy models (from model edge)
                distance_to_enemy_models = self.get_distance_to_enemy_models(model_x, model_y, player_id)
                if distance_to_enemy_models - base_radius < 9.0:
                    model_name = getattr(model, 'name', 'model')
                    logger.debug(f"DEBUG: Infiltrate - {unit.name} {model_name} too close to enemy models: "
                        f"edge_distance={distance_to_enemy_models:.2f}\" base_radius={base_radius:.2f}\" < 9\"")
                    return False
                # RUINS validation: cannot start/end overlapping walls/floors
                model_z = position[2] if len(position) > 2 else 0.0
                ruins_validation = validate_ruins_placement(
                    unit, (model_x, model_y, model_z), self.map.terrain_features, moving_model=model
                )
                if not ruins_validation['valid']:
                    model_name = getattr(model, 'name', 'model')
                    reason = ruins_validation.get('reason', 'unknown')
                    floor_level = ruins_validation.get('floor_level', '?')
                    logger.debug(f"DEBUG: Infiltrate - RUINS validation failed for {unit.name} {model_name}: "
                        f"{reason} (floor {floor_level})")
                    return False

            return True
        else:
            # Normal units must be WHOLLY within their own deployment zone
            # Check that every model's entire base would be within the deployment zone at the proposed position
            # Calculate model positions using the same logic as unit deployment
            # NOTE: Don't use boundary_repulsors for validation - they make formation finding too restrictive
            # During deployment, use relaxed friendly unit avoidance to allow tighter formations
            deployment_repulsors = self.get_boundary_repulsors(unit, context='deployment')
            model_positions = calculate_prospective_model_positions(
                unit,
                x,
                y,
                self.map,
                avoid_friendly_units=False,
                boundary_repulsors=deployment_repulsors,
            )

            if not model_positions:
                return False

            if not _validate_datasheet_deployment_rules(model_positions):
                return False

            from ...battlefield.map import validate_ruins_placement
            for model, position in zip(unit.models, model_positions):
                model_x, model_y, model_z = position[0], position[1], position[2]

                # Check if this model would be wholly within the deployment zone
                if not self.is_position_wholly_in_deployment_zone(model_x, model_y, model.model_base, player_id):
                    model_name = getattr(model, 'name', 'model')
                    logger.debug(f"DEBUG: Zone check failed for {unit.name} {model_name} at "
                        f"({model_x:.1f}, {model_y:.1f}) in player '{player_id}' zone")
                    return False

                # Check RUINS terrain placement rules
                ruins_validation = validate_ruins_placement(
                    unit, (model_x, model_y, model_z), self.map.terrain_features, moving_model=model
                )
                if not ruins_validation['valid']:
                    model_name = getattr(model, 'name', 'model')
                    logger.debug(f"DEBUG: RUINS validation failed for {unit.name} {model_name}: "
                        f"{ruins_validation['reason']}")
                    return False
            return True

    def is_valid_single_model_deployment(self, model: 'Model', x: float, y: float, z: float, player_id: str) -> dict:
        """Validate deploying a single model at (x,y,z) during deployment.

        Applies deployment-zone rules (infiltrate vs normal) and RUINS placement rules for the model only.

        Returns a dict: { 'valid': bool, 'reason': str }
        """
        unit = model.parent_unit
        # Units destined for reserves are not placed on battlefield
        if unit.reserve_status in ['reserves', 'strategic_reserves']:
            return {'valid': False, 'reason': 'Unit is in reserves'}

        # Infiltrate logic: anywhere except inside enemy zone or within 9" from enemy zone/models (edge of base)
        if unit.has_infiltrate():
            # Inside enemy zone
            if self.is_position_in_enemy_deployment_zone(x, y, player_id):
                return {'valid': False, 'reason': 'Inside enemy deployment zone'}
            # 9" from enemy zone (from model edge)
            base_radius = model.model_base.get_radius()
            distance_to_enemy_zone = self.get_distance_to_enemy_deployment_zone(x, y, player_id)
            if distance_to_enemy_zone - base_radius < 9.0:
                return {'valid': False, 'reason': 'Too close to enemy deployment zone (<9\")'}
            # 9" from enemy models (from model edge)
            distance_to_enemy_models = self.get_distance_to_enemy_models(x, y, player_id)
            if distance_to_enemy_models - base_radius < 9.0:
                return {'valid': False, 'reason': 'Too close to enemy models (<9\")'}
        else:
            # Normal deployment: wholly within own zone
            if not self.is_position_wholly_in_deployment_zone(x, y, model.model_base, player_id):
                return {'valid': False, 'reason': 'Model base not wholly within deployment zone'}

        from ...utility.deployment_special_rules import (
            is_aegis_defence_line_deployment_unit,
            validate_aegis_defence_line_deployment_base,
        )
        if is_aegis_defence_line_deployment_unit(unit):
            candidate_base = model.model_base
            create_potential_base = getattr(unit, "_create_potential_base", None)
            if callable(create_potential_base):
                facing = float(getattr(model.model_base, "facing", 0.0))
                maybe_base = create_potential_base(x, y, z, facing, model=model)
                if maybe_base is not None:
                    candidate_base = maybe_base
            aegis_valid, aegis_reason = validate_aegis_defence_line_deployment_base(candidate_base)
            if not aegis_valid:
                return {'valid': False, 'reason': aegis_reason}

        # RUINS placement validation for this single model
        from ...battlefield.map import validate_ruins_placement
        ruins_validation = validate_ruins_placement(unit, (x, y, z), self.map.terrain_features, moving_model=model)
        if not ruins_validation['valid']:
            return {'valid': False, 'reason': f"RUINS: {ruins_validation.get('reason', 'invalid placement')}"}
        surface_validation = self.map.validate_model_surface_placement(model, (x, y, z))
        if not surface_validation.get('valid', False):
            return {'valid': False, 'reason': str(surface_validation.get('reason', 'invalid placement'))}

        return {'valid': True, 'reason': 'Valid single-model deployment'}

    def get_units_in_reserves(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that are currently in reserves."""
        return [unit for unit in player.get_army().units if unit.is_in_reserves()]

    def get_units_that_can_arrive_from_reserves(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that can arrive from reserves this turn."""
        return [unit for unit in self.get_units_in_reserves(player) 
                if unit.can_arrive_from_reserves(self.turn)]

    def get_units_that_must_arrive_from_reserves(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that must arrive from reserves this turn or be destroyed."""
        return [unit for unit in self.get_units_in_reserves(player) 
                if unit.must_arrive_from_reserves(self.turn)]

    def _normalize_ability_text(self, text: str) -> str:
        raw = re.sub(r"<[^>]+>", " ", str(text or ""))
        raw = html.unescape(raw)
        raw = re.sub(r"\s+", " ", raw).strip().lower()
        return raw

    def _reserves_denial_ranges_for_unit(self, unit) -> list[dict]:
        ranges: list[dict] = []
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = []
        if not members:
            members = [root]
        resolved_members = [member for member in list(members or []) if member is not None]

        def _member_sort_key(member: object) -> str:
            member_id = getattr(member, "id", None)
            if member_id:
                return str(member_id)
            member_id = getattr(member, "_id", None)
            if member_id:
                return str(member_id)
            for model in list(getattr(member, "models", []) or []):
                model_id = getattr(model, "id", None)
                if model_id:
                    return f"model:{model_id}"
                model_id = getattr(model, "_id", None)
                if model_id:
                    return f"model:{model_id}"
            member_name = str(getattr(member, "name", "") or "")
            member_type = type(member).__name__
            return f"{member_type}:{member_name}"

        members = sorted(resolved_members, key=_member_sort_key)

        for member in members:
            for ab in list(getattr(member, "possible_abilities", []) or []):
                name = str(getattr(ab, "name", "") or "")
                desc = str(getattr(ab, "description", "") or "")
                text = self._normalize_ability_text(f"{name} {desc}")
                if not text:
                    continue
                flat = re.sub(r"[^a-z0-9.]+", " ", text).strip()
                if "enemy" not in flat:
                    continue
                if ("cannot be set up" not in flat) and ("cannot set up" not in flat):
                    continue
                horizontal_only = ("horizontally" in flat) or ("horizontal" in flat)
                requires_controlled_objective = (
                    "while this model is within range of an objective marker you control" in flat
                    or "while this unit is within range of an objective marker you control" in flat
                )
                distances = []
                for match in re.finditer(r"within\s+(\d+(?:\.\d+)?)\b", flat):
                    distances.append(float(match.group(1)))
                if not distances:
                    continue
                source_model_id = ""
                if "this model" in flat:
                    for model in list(getattr(member, "models", []) or []):
                        alive_attr = getattr(model, "is_alive", True)
                        is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                        if not is_alive:
                            continue
                        source_model_id = str(get_entity_id(model) or "").strip()
                        if source_model_id:
                            break
                ranges.append(
                    {
                        "range": max(distances),
                        "horizontal_only": horizontal_only,
                        "requires_controlled_objective": bool(requires_controlled_objective),
                        "source_model_id": source_model_id,
                    }
                )

        for member in members:
            sr = getattr(member, "special_rules", None)
            if not (isinstance(sr, dict) and bool(sr.get("enhancement_sanctified_amulet", False))):
                continue
            try:
                min_enemy_distance = float(sr.get("enhancement_sanctified_amulet_min_enemy_distance", 12.0) or 12.0)
            except (TypeError, ValueError):
                min_enemy_distance = 12.0
            if min_enemy_distance <= 0.0:
                continue
            horizontal_only = bool(sr.get("enhancement_sanctified_amulet_horizontal_only", False))
            source_name = str(sr.get("enhancement_sanctified_amulet_source", "") or "Sanctified Amulet").strip()
            if not source_name:
                source_name = "Sanctified Amulet"

            bearer_id = str(
                sr.get("enhancement_sanctified_amulet_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            bearer_model = None
            for model in list(getattr(member, "models", []) or []):
                if bearer_id and str(get_entity_id(model) or "") != bearer_id:
                    continue
                alive_attr = getattr(model, "is_alive", True)
                is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                if not is_alive:
                    continue
                bearer_model = model
                break
            if bearer_model is None:
                get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
                candidate = get_bearer() if callable(get_bearer) else None
                if candidate is not None and bearer_id and str(get_entity_id(candidate) or "") != bearer_id:
                    candidate = None
                if candidate is not None:
                    alive_attr = getattr(candidate, "is_alive", True)
                    is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                    if is_alive:
                        bearer_model = candidate
            if bearer_model is None:
                continue
            resolved_bearer_id = str(get_entity_id(bearer_model) or "").strip()
            ranges.append(
                {
                    "range": float(min_enemy_distance),
                    "horizontal_only": bool(horizontal_only),
                    "source": source_name,
                    "source_model_id": resolved_bearer_id,
                }
            )
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not (isinstance(sr, dict) and bool(sr.get("enhancement_helm_of_all_seeing", False))):
                continue
            try:
                min_enemy_distance = float(sr.get("enhancement_helm_of_all_seeing_min_enemy_distance", 12.0) or 12.0)
            except (TypeError, ValueError):
                min_enemy_distance = 12.0
            if min_enemy_distance <= 0.0:
                continue
            horizontal_only = bool(sr.get("enhancement_helm_of_all_seeing_horizontal_only", False))
            source_name = str(sr.get("enhancement_helm_of_all_seeing_source", "") or "Helm of All-seeing").strip()
            if not source_name:
                source_name = "Helm of All-seeing"

            bearer_id = str(
                sr.get("enhancement_helm_of_all_seeing_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            bearer_model = None
            for model in list(getattr(member, "models", []) or []):
                if bearer_id and str(get_entity_id(model) or "") != bearer_id:
                    continue
                alive_attr = getattr(model, "is_alive", True)
                is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                if not is_alive:
                    continue
                bearer_model = model
                break
            if bearer_model is None:
                get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
                candidate = get_bearer() if callable(get_bearer) else None
                if candidate is not None and bearer_id and str(get_entity_id(candidate) or "") != bearer_id:
                    candidate = None
                if candidate is not None:
                    alive_attr = getattr(candidate, "is_alive", True)
                    is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                    if is_alive:
                        bearer_model = candidate
            if bearer_model is None:
                continue
            resolved_bearer_id = str(get_entity_id(bearer_model) or "").strip()
            ranges.append(
                {
                    "range": float(min_enemy_distance),
                    "horizontal_only": bool(horizontal_only),
                    "source": source_name,
                    "source_model_id": resolved_bearer_id,
                }
            )
        get_parent_army = getattr(root, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else None
        csm_mgr = getattr(army, "chaos_space_marines_detachments", None) if army is not None else None
        deceptors_denial_fn = (
            getattr(csm_mgr, "deceptors_scrambled_coordinates_reserves_denial", None)
            if csm_mgr is not None
            else None
        )
        if callable(deceptors_denial_fn):
            entry = deceptors_denial_fn(root, game=self)
            if isinstance(entry, dict):
                try:
                    denial_range = float(entry.get("range", 0.0) or 0.0)
                except (TypeError, ValueError):
                    denial_range = 0.0
                if denial_range > 0.0:
                    ranges.append(dict(entry))
        tau_mgr = getattr(army, "tau_empire_detachments", None) if army is not None else None
        kroothawk_denial_fn = (
            getattr(tau_mgr, "kroot_hunting_pack_kroothawk_flock_reserves_denial", None)
            if tau_mgr is not None
            else None
        )
        if callable(kroothawk_denial_fn):
            entry = kroothawk_denial_fn(root, game=self)
            if isinstance(entry, dict):
                try:
                    denial_range = float(entry.get("range", 0.0) or 0.0)
                except (TypeError, ValueError):
                    denial_range = 0.0
                if denial_range > 0.0:
                    ranges.append(dict(entry))
        return ranges

    def _reserves_denial_violated(self, unit, prospective: list[Tuple[float, float, float, float]]) -> bool:
        if unit is None or not prospective:
            return False
        parent_army = unit.get_parent_army()
        player = parent_army.player if parent_army is not None else None
        if player is None:
            return False
        enemy_units = self.get_enemy_units(player)
        if not enemy_units:
            return False

        from ...utility.aura_utils import (
            distance_between_bases_3d,
            horizontal_distance_between_bases_2d,
        )

        objectives = list(getattr(getattr(self, "map", None), "objectives", []) or [])

        def _source_model_within_controlled_objective(source_model, owner_player) -> bool:
            if source_model is None or owner_player is None:
                return False
            for objective in objectives:
                location = getattr(objective, "location", None)
                if location is None or bool(getattr(location, "removed", False)):
                    continue
                update_fn = getattr(location, "update_control", None)
                if callable(update_fn):
                    update_fn(self)
                if getattr(location, "controlling_player", None) is not owner_player:
                    continue
                within_fn = getattr(self, "_model_within_objective_marker", None)
                if callable(within_fn):
                    if bool(within_fn(source_model, location)):
                        return True
                    continue
                unit = getattr(source_model, "parent_unit", None)
                if unit is None or not hasattr(unit, "is_within_objective_range"):
                    continue
                if bool(unit.is_within_objective_range(location)):
                    return True
            return False

        for enemy in enemy_units:
            if callable(getattr(enemy, "is_alive", None)):
                if not enemy.is_alive():
                    continue
            elif not getattr(enemy, "is_alive", True):
                continue
            if not bool(getattr(enemy, "deployed", False)):
                continue
            if str(getattr(enemy, "reserve_status", "deployed")) != "deployed":
                continue
            if getattr(enemy, "embarked_in", None) is not None:
                continue
            if bool(getattr(enemy, "is_embarked", False)):
                continue
            enemy_player = None
            get_enemy_army = getattr(enemy, "get_parent_army", None)
            enemy_army = get_enemy_army() if callable(get_enemy_army) else getattr(enemy, "parent_army", None)
            if enemy_army is not None:
                enemy_player = getattr(enemy_army, "player", None)

            ranges = self._reserves_denial_ranges_for_unit(enemy)
            if not ranges:
                continue
            get_attached_models = getattr(enemy, "get_attached_unit_models", None)
            if callable(get_attached_models):
                enemy_models_raw = list(get_attached_models() or [])
            else:
                enemy_models_raw = list(getattr(enemy, "models", []) or [])
            enemy_models = []
            for model in list(enemy_models_raw or []):
                if model is None:
                    continue
                alive_attr = getattr(model, "is_alive", True)
                is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                if not is_alive:
                    continue
                enemy_models.append(model)
            if not enemy_models:
                continue
            for idx, (x, y, z, facing) in enumerate(prospective):
                if idx >= len(getattr(unit, "models", []) or []):
                    break
                base = unit._create_potential_base(x, y, z, facing, model=unit.models[idx])
                for em in enemy_models:
                    for rinfo in ranges:
                        source_model_id = ""
                        horizontal_only = False
                        requires_controlled_objective = False
                        if isinstance(rinfo, dict):
                            r = float(rinfo.get("range", 0) or 0)
                            horizontal_only = bool(rinfo.get("horizontal_only", False))
                            source_model_id = str(rinfo.get("source_model_id", "") or "").strip()
                            requires_controlled_objective = bool(rinfo.get("requires_controlled_objective", False))
                        elif isinstance(rinfo, (list, tuple)) and rinfo:
                            r = float(rinfo[0])
                            if len(rinfo) > 1:
                                horizontal_only = bool(rinfo[1])
                        else:
                            r = float(rinfo)
                        if r <= 0:
                            continue
                        if source_model_id and str(get_entity_id(em) or "") != source_model_id:
                            continue
                        if requires_controlled_objective and not _source_model_within_controlled_objective(em, enemy_player):
                            continue
                        if horizontal_only:
                            dist = float(horizontal_distance_between_bases_2d(base, em.model_base))
                        else:
                            dist = float(distance_between_bases_3d(base, em.model_base))
                        if dist < r:
                            return True
        return False

    def _masters_of_the_void_enemy_dz_override_active(self, unit: 'Unit') -> bool:
        if unit is None:
            return False
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get("imperial_agents_masters_of_the_void_enemy_dz_override_active")):
            return False

        owner_id = str(sr.get("imperial_agents_masters_of_the_void_enemy_dz_override_turn_owner", "") or "")
        turn_value = sr.get("imperial_agents_masters_of_the_void_enemy_dz_override_turn", 0)
        try:
            effect_turn = int(turn_value or 0)
        except (TypeError, ValueError):
            effect_turn = 0
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        if effect_turn and current_turn and effect_turn != current_turn:
            return False

        current_player = self.get_current_player() if hasattr(self, "get_current_player") else None
        current_owner_id = str(getattr(current_player, "id", "") or "")
        if owner_id and current_owner_id and owner_id != current_owner_id:
            return False

        expires_phase = str(
            sr.get("imperial_agents_masters_of_the_void_enemy_dz_override_expires_phase", "") or ""
        ).strip().upper()
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if expires_phase and phase_name and expires_phase != phase_name:
            return False
        return True

    def _transponder_lock_module_turn_one_spotter_requirement_satisfied(
        self,
        unit: 'Unit',
        prospective: list[tuple[float, float, float, float]],
        *,
        pending_deep_strike: bool,
    ) -> bool:
        if unit is None or not bool(pending_deep_strike):
            return True
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            return True
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("enhancement_transponder_lock_module")):
            return True
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        if current_turn != 1:
            return True

        try:
            max_range = float(sr.get("enhancement_transponder_lock_module_turn_one_spotter_range", 12.0) or 12.0)
        except (TypeError, ValueError):
            max_range = 12.0
        if max_range <= 0.0:
            return False
        required_keywords = [
            str(v or "").strip().upper()
            for v in list(
                sr.get(
                    "enhancement_transponder_lock_module_turn_one_spotter_keywords_any",
                    ("KROOT", "VESPID STINGWINGS"),
                )
                or ()
            )
            if str(v or "").strip()
        ]
        if not required_keywords:
            required_keywords = ["KROOT", "VESPID STINGWINGS"]

        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        game_map = getattr(self, "map", None)
        if army is None or game_map is None:
            return False

        from ...utility.aura_utils import distance_between_bases_3d

        def _unit_has_required_keyword(candidate_unit: object) -> bool:
            if candidate_unit is None:
                return False
            has_any_keyword = getattr(candidate_unit, "has_any_keyword", None)
            if callable(has_any_keyword):
                for keyword in required_keywords:
                    if bool(has_any_keyword(keyword)):
                        return True
            pool: list[str] = []
            pool.extend([str(v or "").strip().upper() for v in list(getattr(candidate_unit, "keywords", []) or [])])
            pool.extend(
                [str(v or "").strip().upper() for v in list(getattr(candidate_unit, "faction_keywords", []) or [])]
            )
            return any(keyword in pool for keyword in required_keywords)

        friendly_units: list[object] = []
        seen_ids: set[str] = set()
        for candidate in list(getattr(game_map, "units", []) or []):
            if candidate is None:
                continue
            get_candidate_root = getattr(candidate, "get_attached_unit_root", None)
            candidate_root = get_candidate_root() if callable(get_candidate_root) else candidate
            if candidate_root is None:
                continue
            candidate_id = str(get_entity_id(candidate_root) or "")
            if candidate_id and candidate_id in seen_ids:
                continue
            if candidate_id:
                seen_ids.add(candidate_id)
            if candidate_root is root:
                continue
            candidate_army = (
                candidate_root.get_parent_army() if hasattr(candidate_root, "get_parent_army") else None
            )
            if candidate_army is not army:
                continue
            is_alive_fn = getattr(candidate_root, "is_alive", None)
            alive = bool(is_alive_fn()) if callable(is_alive_fn) else bool(getattr(candidate_root, "is_alive", True))
            if not alive:
                continue
            if not bool(getattr(candidate_root, "deployed", False)):
                continue
            if str(getattr(candidate_root, "reserve_status", "deployed") or "deployed") != "deployed":
                continue
            if bool(getattr(candidate_root, "is_embarked", False)) or getattr(candidate_root, "embarked_in", None) is not None:
                continue
            if not _unit_has_required_keyword(candidate_root):
                continue
            friendly_units.append(candidate_root)

        if not friendly_units:
            return False

        for idx, (x, y, z, facing) in enumerate(prospective):
            if idx >= len(getattr(root, "models", []) or []):
                break
            base = root._create_potential_base(x, y, z, facing, model=root.models[idx])
            for spotter in list(friendly_units or []):
                for model in list(getattr(spotter, "models", []) or []):
                    model_alive_attr = getattr(model, "is_alive", True)
                    model_alive = bool(model_alive_attr() if callable(model_alive_attr) else model_alive_attr)
                    if not model_alive:
                        continue
                    if float(distance_between_bases_3d(base, model.model_base)) <= float(max_range) + 1e-6:
                        return True
        return False

    def can_place_unit_arriving_from_reserves(self, unit: 'Unit', position: Tuple[float, float, float],
                                              battlefield_edge: str = None) -> bool:
        """Check if a unit can be legally placed when arriving from reserves.

        Args:
            unit: The unit arriving from reserves
            position: (x, y, z) position where the unit would be placed
            battlefield_edge: For strategic reserves, which edge they're arriving from
                             ('own', 'left', 'right', 'enemy')

        Returns:
            bool: True if the placement is legal
        """
        # Check if position is within battlefield bounds
        if (position[0] < 0 or position[0] >= self.battlefield.width or
            position[1] < 0 or position[1] >= self.battlefield.height):
            return False

        # Strategic Reserves vs Deep Strike choice:
        # If a unit with Deep Strike arrives from Strategic Reserves, it may be set up using either:
        # - Strategic Reserves rules (edge within 6", plus turn-based allowed edges), OR
        # - Deep Strike rules (anywhere, still respecting the 9" from enemies restriction).
        # Clear any prior pending edge-touch marker for this unit.
        if hasattr(unit, "_pending_reserves_edge_touch"):
            delattr(unit, "_pending_reserves_edge_touch")

        strategic_ok = True
        strategic_used_edge_touch = False
        if unit.is_in_strategic_reserves():
            strategic_ok = False
            try:
                if hasattr(unit, "get_strategic_reserves_setup_turn"):
                    effective_turn = int(unit.get_strategic_reserves_setup_turn(game=self, current_turn=self.turn))
                else:
                    effective_turn = int(getattr(self, "turn", 0) or 0)
            except Exception:
                effective_turn = int(getattr(self, "turn", 0) or 0)
            # Determine which edge(s) to validate
            if battlefield_edge:
                candidate_edges = [battlefield_edge]
            else:
                candidate_edges = ["own", "left", "right", "enemy"]

            def _model_radius(m) -> float:
                mb = getattr(m, "model_base", None)
                if mb is None:
                    return 1.0
                if hasattr(mb, "get_longest_radius"):
                    return float(mb.get_longest_radius())
                if hasattr(mb, "get_radius"):
                    return float(mb.get_radius())
                r = getattr(mb, "radius", None)
                if isinstance(r, (list, tuple)) and r:
                    return float(r[0])
                return float(r) if r is not None else 1.0

            def _center_dist_to_edge(x: float, y: float, edge: str) -> float:
                # Uses existing coordinate conventions: own=y0, enemy=yH, left=x0, right=xW
                if edge == "own":
                    return float(y)
                if edge == "enemy":
                    return float(self.battlefield.height - y)
                if edge == "left":
                    return float(x)
                if edge == "right":
                    return float(self.battlefield.width - x)
                return float("inf")

            # We validate against the unit's *actual* prospective formation at this position.
            snapshot = [m.get_location() for m in unit.models]
            boundary_repulsors = self.map.get_battlefield_edge_repulsors() if self.map else []
            prospective = unit.calculate_model_positions(
                position[0],
                position[1],
                self.map,
                boundary_repulsors=boundary_repulsors,
                avoid_friendly_units=True,
            )
            for m, loc in zip(unit.models, snapshot):
                if loc:
                    m.set_location(*loc)

            if not prospective:
                return False

            # Round 2 Strategic Reserves restriction: cannot be set up within the enemy deployment zone
            # (applies only when using Strategic Reserves edge placement, not Deep Strike alternative).
            parent_army = unit.get_parent_army()
            player_id = parent_army.player.id if parent_army and parent_army.player else None

            for edge in candidate_edges:
                if not self.is_valid_strategic_reserves_edge(edge, turn=effective_turn):
                    continue

                # Turn-based enemy deployment zone restriction (turn 2 only),
                # unless enabled by Masters of the Void for this unit.
                if (
                    effective_turn == 2
                    and player_id
                    and not self._masters_of_the_void_enemy_dz_override_active(unit)
                ):
                    any_in_enemy_dz = False
                    for (mx, my, _mz, _f) in prospective:
                        if self.is_position_in_enemy_deployment_zone(float(mx), float(my), player_id):
                            any_in_enemy_dz = True
                            break
                    if any_in_enemy_dz:
                        continue

                # Strategic Reserves must be set up wholly within 6" of a single battlefield edge.
                # If a model is too large to fit wholly within 6", allow the base to touch the edge instead.
                used_touch = False
                ok_all = True
                for idx, (mx, my, mz, mf) in enumerate(prospective):
                    if idx >= len(unit.models):
                        break
                    r = _model_radius(unit.models[idx])
                    d = _center_dist_to_edge(float(mx), float(my), edge)

                    # "Wholly within 6" from that edge" means (center distance) <= 6 - radius.
                    max_center = 6.0 - float(r)
                    if max_center >= 0.0:
                        if d > max_center + 1e-6:
                            ok_all = False
                            break
                    else:
                        # Too big to fit wholly within 6": require base touches the edge.
                        # For circular approximation: center distance ~= radius.
                        if abs(d - float(r)) > 0.25:  # 1/4" tolerance
                            ok_all = False
                            break
                        used_touch = True

                if ok_all:
                    strategic_ok = True
                    strategic_used_edge_touch = bool(used_touch)
                    break

        # Check 9" restriction from enemy models using base-to-base closest-point distance.
        # We validate against the unit's *actual* prospective formation at this position.
        snapshot = [m.get_location() for m in unit.models]
        boundary_repulsors = self.map.get_battlefield_edge_repulsors() if self.map else []
        prospective = unit.calculate_model_positions(
            position[0],
            position[1],
            self.map,
            boundary_repulsors=boundary_repulsors,
            avoid_friendly_units=True,
        )
        if not prospective:
            return False

        tunnel_marker = None
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        tyr_mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
        marker_fn = getattr(tyr_mgr, "subterranean_assault_arrival_marker_for_positions", None) if tyr_mgr is not None else None
        if callable(marker_fn):
            tunnel_marker = marker_fn(unit, list(prospective), game=self)

        for m, loc in zip(unit.models, prospective):
            if loc:
                m.set_location(*loc)

        # HALLOWED BEACON: unit must be set up wholly within Hallowed Ground.
        try:
            root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        except Exception:
            root = unit
        sr = getattr(root, "special_rules", None)
        requires_hallowed_ground = False
        if isinstance(sr, dict) and bool(sr.get("hallowed_beacon_requires_hallowed_ground")):
            owner_id = str(sr.get("hallowed_beacon_turn_owner", "") or "")
            effect_turn = int(sr.get("hallowed_beacon_turn", 0) or 0)
            expires_phase = str(sr.get("hallowed_beacon_expires_phase", "") or "").strip().upper()
            current_turn = int(getattr(self, "turn", 0) or 0)
            current_owner = str(getattr(getattr(self, "get_current_player", lambda: None)(), "id", "") or "")
            phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
            requires_hallowed_ground = True
            if owner_id and current_owner and owner_id != current_owner:
                requires_hallowed_ground = False
            if requires_hallowed_ground and effect_turn and current_turn and effect_turn != current_turn:
                requires_hallowed_ground = False
            if requires_hallowed_ground and expires_phase and phase_name and expires_phase != phase_name:
                requires_hallowed_ground = False
        if requires_hallowed_ground:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            gk_mgr = getattr(army, "grey_knights_detachments", None) if army is not None else None
            if gk_mgr is None or not bool(
                getattr(gk_mgr, "unit_wholly_within_hallowed_ground", lambda *_a, **_k: False)(root, game=self)
            ):
                for m, loc in zip(unit.models, snapshot):
                    if loc:
                        m.set_location(*loc)
                return False
        if battlefield_edge is None and tunnel_marker is None:
            valid_dark_apparitions = True
            try:
                checker = getattr(unit, "is_dark_apparitions_arrival_valid", None)
                if callable(checker):
                    valid_dark_apparitions = bool(
                        checker(
                            prospective,
                            game=self,
                            game_map=self.map,
                        )
                    )
            except Exception:
                valid_dark_apparitions = False
            if not valid_dark_apparitions:
                for m, loc in zip(unit.models, snapshot):
                    if loc:
                        m.set_location(*loc)
                return False

        min_enemy_distance = float(self._warp_rifts_min_distance(unit) or 9.0)
        for m, loc in zip(unit.models, snapshot):
            if loc:
                m.set_location(*loc)

        if tunnel_marker is not None:
            min_enemy_distance = float(6.0)
        if battlefield_edge is None and tunnel_marker is None:
            try:
                if hasattr(unit, "get_deep_strike_min_distance_override"):
                    override = unit.get_deep_strike_min_distance_override()
                else:
                    override = None
            except Exception:
                override = None
            if override:
                min_enemy_distance = min(float(min_enemy_distance), float(override))
            try:
                army = unit.get_parent_army()
            except Exception:
                army = None
            dg_mgr = getattr(army, "death_guard_detachments", None) if army is not None else None
            beckoning_fn = (
                getattr(dg_mgr, "tallyband_beckoning_blight_deep_strike_min_enemy_distance", None)
                if dg_mgr is not None
                else None
            )
            if callable(beckoning_fn):
                try:
                    beckoning_distance, _beckoning_source = beckoning_fn(
                        unit,
                        prospective_positions=list(prospective),
                        game=self,
                        game_map=self.map,
                    )
                except Exception:
                    beckoning_distance = 0.0
                if float(beckoning_distance or 0.0) > 0.0:
                    min_enemy_distance = min(float(min_enemy_distance), float(beckoning_distance))

        from ...utility.aura_utils import horizontal_distance_between_bases_2d
        enemy_units = self.get_enemy_units(unit.get_parent_army().player)
        enemy_models: list[tuple[object, object]] = []
        for eu in list(enemy_units or []):
            if eu is None:
                continue
            try:
                enemy_root = eu.get_attached_unit_root() if hasattr(eu, "get_attached_unit_root") else eu
            except Exception:
                enemy_root = eu
            if enemy_root is None:
                continue
            try:
                if not enemy_root.is_alive():
                    continue
            except Exception:
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            for em in list(getattr(enemy_root, "models", []) or []):
                if not getattr(em, "is_alive", True):
                    continue
                enemy_models.append((enemy_root, em))

        for idx, (x, y, z, facing) in enumerate(prospective):
            if idx >= len(unit.models):
                break
            mb = unit._create_potential_base(x, y, z, facing, model=unit.models[idx])
            for enemy_root, em in list(enemy_models or []):
                required_distance = float(min_enemy_distance)
                if battlefield_edge is None and tunnel_marker is None:
                    try:
                        per_enemy = None
                        if hasattr(unit, "get_deep_strike_min_distance_vs_enemy"):
                            per_enemy = unit.get_deep_strike_min_distance_vs_enemy(
                                enemy_root,
                                game=self,
                                game_map=self.map,
                            )
                    except Exception:
                        per_enemy = None
                    if per_enemy:
                        required_distance = float(per_enemy)
                if float(horizontal_distance_between_bases_2d(mb, em.model_base)) < float(required_distance):
                    return False

        if self._reserves_denial_violated(unit, prospective):
            return False

        if unit.is_in_strategic_reserves():
            deep_strike_ok = bool(unit.has_deep_strike())
            tunnel_ok = bool(tunnel_marker is not None)
            ok = bool(strategic_ok or deep_strike_ok or tunnel_ok)
            # If we are validating Strategic edge placement and it required the edge-touch exception,
            # mark it on the unit so `arrive_from_reserves` can apply additional restrictions this turn.
            if ok and strategic_ok and strategic_used_edge_touch:
                setattr(unit, "_pending_reserves_edge_touch", True)
            if ok:
                if battlefield_edge is None:
                    pending_deep_strike = bool(deep_strike_ok and not tunnel_ok)
                else:
                    pending_deep_strike = bool(deep_strike_ok and not strategic_ok)
                if not self._transponder_lock_module_turn_one_spotter_requirement_satisfied(
                    unit,
                    list(prospective),
                    pending_deep_strike=pending_deep_strike,
                ):
                    return False
                setattr(unit, "_pending_reserves_deep_strike", pending_deep_strike)
                if tunnel_ok:
                    setattr(unit, "_pending_reserves_tunnel_marker_id", str(getattr(tunnel_marker, "marker_id", "") or ""))
                elif hasattr(unit, "_pending_reserves_tunnel_marker_id"):
                    delattr(unit, "_pending_reserves_tunnel_marker_id")
            return ok

        pending_deep_strike = bool(tunnel_marker is None)
        if not self._transponder_lock_module_turn_one_spotter_requirement_satisfied(
            unit,
            list(prospective),
            pending_deep_strike=pending_deep_strike,
        ):
            return False
        setattr(unit, "_pending_reserves_deep_strike", pending_deep_strike)
        if tunnel_marker is not None:
            setattr(unit, "_pending_reserves_tunnel_marker_id", str(getattr(tunnel_marker, "marker_id", "") or ""))
        elif hasattr(unit, "_pending_reserves_tunnel_marker_id"):
            delattr(unit, "_pending_reserves_tunnel_marker_id")
        return True

    def is_valid_strategic_reserves_edge(self, battlefield_edge: str, *, turn: Optional[int] = None) -> bool:
        """Check if the specified battlefield edge is valid for strategic reserves arrival.
        
        Args:
            battlefield_edge: 'own', 'left', 'right', 'enemy'
        
        Returns:
            bool: True if the edge is valid for the current turn
        """
        # Chapter Approved: Strategic Reserves can arrive from ANY battlefield edge starting in battle round 2.
        use_turn = self.turn
        if turn is not None:
            try:
                use_turn = int(turn)
            except Exception:
                use_turn = self.turn
        if use_turn < 2:
            return False
        return battlefield_edge in ['own', 'left', 'right', 'enemy']

    def get_distance_to_battlefield_edge(self, position: Tuple[float, float, float], 
                                       battlefield_edge: str) -> float:
        """Calculate distance from a position to the specified battlefield edge.
        
        Args:
            position: (x, y, z) position
            battlefield_edge: 'own', 'left', 'right', 'enemy'
        
        Returns:
            float: Distance to the edge in inches
        """
        x, y, z = position
        
        if battlefield_edge == 'own':
            # Assuming own edge is at y=0 (bottom)
            return y
        elif battlefield_edge == 'enemy':
            # Assuming enemy edge is at y=battlefield.height (top)
            return self.battlefield.height - y
        elif battlefield_edge == 'left':
            # Left edge at x=0
            return x
        elif battlefield_edge == 'right':
            # Right edge at x=battlefield.width
            return self.battlefield.width - x
        else:
            return float('inf')  # Invalid edge

    def handle_reserves_arrival_phase(self) -> Dict[str, List['Unit']]:
        """Handle the reserves arrival phase at the end of movement phase.

        This should be called at the end of each player's movement phase.

        Returns:
            Dict mapping player ids to lists of units that arrived from reserves
        """
        arrival_results = {}
        current_player = self.get_current_player()
        if current_player is None:
            self.end_reinforcements_step()
            return arrival_results
        self.begin_reinforcements_step(current_player)

        current_army = current_player.get_army()
        current_mgr = getattr(current_army, "chaos_space_marines_detachments", None) if current_army is not None else None
        queue_falsehood = (
            getattr(current_mgr, "queue_deceptors_falsehood_reinforcements_request", None)
            if current_mgr is not None
            else None
        )
        if callable(queue_falsehood):
            queue_falsehood(game=self, player=current_player)
        for player in list(getattr(self, "players", []) or []):
            if player is None or player is current_player:
                continue
            stratagem_mgr = getattr(player, "stratagems", None)
            queue_reaction = (
                getattr(stratagem_mgr, "_queue_deceptors_reinforcements_step_reactions", None)
                if stratagem_mgr is not None
                else None
            )
            if callable(queue_reaction):
                queue_reaction(current_player=current_player)

        current_stratagems = getattr(current_player, "stratagems", None)
        queue_dread_talons = (
            getattr(current_stratagems, "_queue_dread_talons_reinforcements_step_reactions", None)
            if current_stratagems is not None
            else None
        )
        if callable(queue_dread_talons):
            queue_dread_talons(current_player=current_player)

        # Handle reserves arrivals for the current player
        units_arrived = self.process_player_reserves_arrivals(current_player)
        arrival_results[current_player.id] = units_arrived

        # Cult Ambush: opponent's reinforcements step (end of this player's Movement phase)
        self._handle_cult_ambush_reinforcements(current_player)

        # Chapter Approved "destroy after battle round 3" is enforced at end-of-battle-round.

        return arrival_results

    def begin_reinforcements_step(self, player=None) -> None:
        active_player = player if player is not None else self.get_current_player()
        self.reinforcements_step_active = active_player is not None
        self.reinforcements_step_player_id = str(getattr(active_player, "id", "") or "") if active_player is not None else ""
        self._reinforcements_step_skipped_ids = set()
        try:
            self.reinforcements_step_turn = int(getattr(self, "turn", 0) or 0)
        except (TypeError, ValueError):
            self.reinforcements_step_turn = 0

    def end_reinforcements_step(self) -> None:
        self.reinforcements_step_active = False
        self.reinforcements_step_player_id = ""
        self.reinforcements_step_turn = 0
        self._reinforcements_step_skipped_ids = set()

    def _handle_cult_ambush_reinforcements(self, current_player) -> None:
        players = list(getattr(self, "players", []) or [])
        for p in players:
            if p is None or p is current_player:
                continue
            army = p.get_army()
            mgr = getattr(army, "cult_ambush", None) if army is not None else None
            if mgr is None:
                continue
            mgr.handle_reinforcements(game=self, player=p)

    def process_player_reserves_arrivals(self, player: Player) -> List['Unit']:
        """Process reserves arrivals for a specific player.

        This method requires explicit placement decisions from a controller.

        Args:
            player: The player whose reserves arrivals to process

        Returns:
            List of units that arrived from reserves
        """
        units_arrived: list['Unit'] = []
        units_that_can_arrive = self.get_units_that_can_arrive_from_reserves(player)
        units_that_must_arrive = self.get_units_that_must_arrive_from_reserves(player)
        army = player.get_army() if player is not None else None
        csm_mgr = getattr(army, "chaos_space_marines_detachments", None) if army is not None else None
        excludes_standard_arrival = (
            getattr(csm_mgr, "deceptors_falsehood_excludes_standard_reserves_arrival", None)
            if csm_mgr is not None
            else None
        )
        if callable(excludes_standard_arrival):
            units_that_can_arrive = [
                unit
                for unit in list(units_that_can_arrive or [])
                if not bool(excludes_standard_arrival(unit, game=self, player=player))
            ]
            units_that_must_arrive = [
                unit
                for unit in list(units_that_must_arrive or [])
                if not bool(excludes_standard_arrival(unit, game=self, player=player))
            ]

        self._queue_necrons_eternity_gate_requests(player)

        player_name = getattr(player, "name", "Player")
        logger.info("INFO: %s has %d units that can arrive from reserves", player_name, len(units_that_can_arrive))
        if units_that_must_arrive:
            hub = getattr(self, "decision_controller_hub", None)
            controllers = list(getattr(hub, "_controllers", []) or [])
            player_id = str(getattr(player, "id", "") or "")
            handled = [
                controller
                for controller in controllers
                if bool(getattr(controller, "handles_player", lambda _player_id: False)(player_id))
            ]
            if handled:
                logger.info(
                    "INFO: %s has %d units that must arrive from reserves; placement decisions will be queued "
                    "for %d controller(s).",
                    player_name,
                    len(units_that_must_arrive),
                    len(handled),
                )
            else:
                logger.warning(
                    "WARN: %s has %d units that must arrive from reserves, but no decision controller is registered "
                    "for player_id=%s.",
                    player_name,
                    len(units_that_must_arrive),
                    player_id or "<unknown>",
                )

        for unit in list(units_that_can_arrive or []):
            try:
                unit_id = str(get_entity_id(unit))
            except Exception:
                unit_id = ""
            source = ""
            deep_strike_min_distance = 6.0
            try:
                rule = None
                if unit is not None and hasattr(unit, "get_cloudstrider_deep_strike_rule"):
                    rule = unit.get_cloudstrider_deep_strike_rule()
                if isinstance(rule, dict):
                    source = str(rule.get("source", "") or "").strip()
                    try:
                        deep_strike_min_distance = float(rule.get("deep_strike_min_distance", 6.0) or 6.0)
                    except (TypeError, ValueError):
                        deep_strike_min_distance = 6.0
                elif unit is not None and hasattr(unit, "get_cloudstrider_deep_strike_source"):
                    source = str(unit.get_cloudstrider_deep_strike_source() or "")
            except Exception:
                source = ""
                deep_strike_min_distance = 6.0
            if deep_strike_min_distance <= 0.0:
                deep_strike_min_distance = 6.0
            try:
                can_deep_strike = bool(getattr(unit, "has_deep_strike", lambda: False)())
            except Exception:
                can_deep_strike = False
            if source and can_deep_strike:
                try:
                    sr = getattr(unit, "special_rules", None)
                    if not isinstance(sr, dict):
                        sr = {}
                    owner_id = str(getattr(player, "id", "") or "")
                    current_turn = int(getattr(self, "turn", 0) or 0)
                    active = (
                        str(sr.get("cloudstrider_choice_turn_owner", "") or "") == owner_id
                        and int(sr.get("cloudstrider_choice_turn", 0) or 0) == current_turn
                    )
                except Exception:
                    active = False
                if not active:
                    ctx = {
                        "unit_id": unit_id,
                        "ability_name": source or "Cloudstrider",
                        "deep_strike_min_distance": float(deep_strike_min_distance),
                        "phase": "Movement phase",
                    }
                    distance_label = f"{float(deep_strike_min_distance):.1f}".rstrip("0").rstrip(".")
                    message = (
                        f"{source or 'Cloudstrider'}: use {distance_label}\" Deep Strike placement "
                        f"(no charge this turn)?"
                    )
                    self._queue_optional_ability_confirmation(
                        player=player,
                        ability_key="cloudstrider",
                        ability_name=source or "Cloudstrider",
                        message=message,
                        context=ctx,
                        payload={"unit_id": unit_id},
                        instance_key=f"{unit_id}:{getattr(self, 'turn', 0)}:cloudstrider",
                    )
        self._queue_movement_phase_reinforcements_selection(player)

        return units_arrived

    def _pending_choose_quarry_request(
        self,
        *,
        ability: str,
        player_id: str = "",
        source_unit_id: str = "",
    ) -> bool:
        queue = getattr(self, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        ability_key = str(ability or "").strip().lower()
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            req_player_id = str(getattr(req, "player_id", "") or "")
            if player_id and req_player_id and req_player_id != str(player_id):
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != ability_key:
                continue
            if source_unit_id and str(ctx.get("source_unit_id", "") or "") != str(source_unit_id):
                continue
            return True
        return False

    def _queue_necrons_eternity_gate_requests(self, player: Player) -> None:
        if player is None:
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        if player is not self.get_current_player():
            return

        army = player.get_army()
        if army is None:
            return

        owner_id = str(getattr(player, "id", "") or "")
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0

        def _unit_sort_key(unit_obj):
            return str(get_entity_id(unit_obj) or "")

        def _root_from_unit(unit_obj):
            if unit_obj is None:
                return None
            get_root = getattr(unit_obj, "get_attached_unit_root", None)
            return get_root() if callable(get_root) else unit_obj

        def _on_battlefield(root) -> bool:
            if root is None:
                return False
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive):
                if not bool(is_alive()):
                    return False
            elif getattr(root, "is_alive", True) is False:
                return False
            if not bool(getattr(root, "deployed", True)):
                return False
            if str(getattr(root, "reserve_status", "deployed") or "deployed") != "deployed":
                return False
            if bool(getattr(root, "embarked_in", None)) or bool(getattr(root, "is_embarked", False)):
                return False
            is_in_reserves = getattr(root, "is_in_reserves", None)
            if callable(is_in_reserves) and bool(is_in_reserves()):
                return False
            return True

        def _is_in_reserves(root) -> bool:
            if root is None:
                return False
            is_in_reserves = getattr(root, "is_in_reserves", None)
            if callable(is_in_reserves):
                return bool(is_in_reserves())
            status = str(getattr(root, "reserve_status", "") or "")
            return status in {"reserves", "strategic_reserves"}

        def _has_keywords(root, *keywords: str) -> bool:
            has_any_keyword = getattr(root, "has_any_keyword", None)
            if callable(has_any_keyword):
                for keyword in keywords:
                    if not bool(has_any_keyword(keyword)):
                        return False
                return True
            values = [str(v or "").strip().upper() for v in list(getattr(root, "keywords", []) or []) if str(v or "").strip()]
            values.extend(
                str(v or "").strip().upper()
                for v in list(getattr(root, "faction_keywords", []) or [])
                if str(v or "").strip()
            )
            pool = set(values)
            return all(str(keyword or "").strip().upper() in pool for keyword in keywords)

        source_roots: list[tuple[object, dict]] = []
        seen_sources: set[str] = set()
        for unit in sorted(list(getattr(army, "units", []) or []), key=_unit_sort_key):
            root = _root_from_unit(unit)
            if root is None:
                continue
            source_id = str(get_entity_id(root) or "")
            if not source_id or source_id in seen_sources:
                continue
            seen_sources.add(source_id)
            if not _on_battlefield(root):
                continue
            get_specs = getattr(root, "unit_eternity_gate_specs", None)
            specs = list(get_specs() or []) if callable(get_specs) else []
            if not specs:
                continue
            source_roots.append((root, dict(specs[0] or {})))

        if not source_roots:
            return

        candidate_roots: list[object] = []
        seen_candidates: set[str] = set()
        for unit in sorted(list(getattr(army, "units", []) or []), key=_unit_sort_key):
            root = _root_from_unit(unit)
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "")
            if not root_id or root_id in seen_candidates:
                continue
            seen_candidates.add(root_id)
            if not _has_keywords(root, "NECRONS", "INFANTRY"):
                continue
            if bool(getattr(root, "embarked_in", None)) or bool(getattr(root, "is_embarked", False)):
                continue
            candidate_roots.append(root)

        if not candidate_roots:
            return

        for source_root, spec in source_roots:
            source_id = str(get_entity_id(source_root) or "")
            if not source_id:
                continue
            if self._pending_choose_quarry_request(
                ability="eternity_gate_target",
                player_id=owner_id,
                source_unit_id=source_id,
            ):
                continue

            try:
                selection_range = float(spec.get("range", 6) or 6)
            except (TypeError, ValueError):
                selection_range = 6.0
            if selection_range <= 0.0:
                selection_range = 6.0
            allow_target_in_reserves = bool(spec.get("allow_target_in_reserves", True))
            allow_target_on_battlefield = bool(spec.get("allow_target_on_battlefield", True))
            ability_name = str(spec.get("source", "") or "Eternity Gate").strip() or "Eternity Gate"
            no_charge_this_turn = bool(spec.get("no_charge_this_turn", True))

            options = [DecisionOption.create("None", payload={"action": "skip"})]
            candidate_ids: list[str] = []
            for target_root in list(candidate_roots or []):
                target_id = str(get_entity_id(target_root) or "")
                if not target_id or target_id == source_id:
                    continue
                target_in_reserves = _is_in_reserves(target_root)
                target_on_battlefield = _on_battlefield(target_root)
                if target_in_reserves:
                    if not allow_target_in_reserves:
                        continue
                    can_arrive = getattr(target_root, "can_arrive_from_reserves", None)
                    if callable(can_arrive) and not bool(can_arrive(current_turn)):
                        continue
                elif target_on_battlefield:
                    if not allow_target_on_battlefield:
                        continue
                else:
                    continue

                candidate_ids.append(target_id)
                options.append(
                    DecisionOption.create(
                        str(getattr(target_root, "name", "Unit") or "Unit"),
                        payload={
                            "source_unit_id": source_id,
                            "target_unit_id": target_id,
                        },
                    )
                )

            if not candidate_ids:
                continue

            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select one friendly NECRONS INFANTRY unit (or None).",
                player_id=getattr(player, "id", None),
                options=options,
                context={
                    "ability": "eternity_gate_target",
                    "ability_name": ability_name,
                    "phase": "Reinforcements step (Movement phase)",
                    "source_unit_id": source_id,
                    "unit_id": source_id,
                    "candidate_unit_ids": sorted(set(candidate_ids)),
                    "range": float(selection_range),
                    "allow_target_in_reserves": bool(allow_target_in_reserves),
                    "allow_target_on_battlefield": bool(allow_target_on_battlefield),
                    "no_charge_this_turn": bool(no_charge_this_turn),
                    "turn_owner_id": owner_id,
                    "turn": int(current_turn),
                    "optional": True,
                },
            )
            self.request_decision(request)

    def find_valid_reserves_position(self, unit: 'Unit') -> Optional[Tuple[float, float, float]]:
        """Return None unless a controller provides an explicit placement."""
        return None

    def _build_reserves_arrival_request(self, unit: 'Unit', *, allow_skip: bool) -> Optional["DecisionRequest"]:
        if unit is None:
            return None
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id
        unit_id = get_entity_id(unit)
        options = [
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": unit_id, "movement_type": "deploy", "action": "confirm"},
            )
        ]
        if allow_skip:
            options.append(
                DecisionOption.create(
                    "Skip",
                    payload={"unit_id": unit_id, "movement_type": "deploy", "action": "skip"},
                )
            )
        player_id = None
        try:
            army = unit.get_parent_army()
        except Exception:
            army = getattr(unit, "parent_army", None)
        if army is not None:
            player = getattr(army, "player", None)
            player_id = getattr(player, "id", None) if player is not None else None
        allowed_model_ids = [get_entity_id(m) for m in list(getattr(unit, "models", []) or []) if m is not None]
        context = {
            "unit_id": unit_id,
            "movement_type": "deploy",
            "placement_kind": "reserves_arrival",
            "allowed_model_ids": allowed_model_ids,
            "allow_skip": bool(allow_skip),
            "phase_name": "MOVEMENT_PHASE",
            "phase_step": "REINFORCEMENTS",
            "battle_round": int(getattr(self, "turn", 0) or 0),
            "reserve_status": str(getattr(unit, "reserve_status", "") or ""),
            "reserve_entry_kind": self._reserve_entry_kind_for_unit(unit),
        }
        return DecisionRequest.create(
            DECISION_MOVE_UNIT,
            f"Arrive from Reserves: {getattr(unit, 'name', 'Unit')}",
            player_id=player_id,
            options=options,
            context=context,
        )

    def get_first_turn_player_index(self) -> int:
        """Get the index of player who goes first (will be set during DETERMINE_FIRST_TURN_ORDER)"""
        return self.first_turn_player_index

    def is_in_setup_phase(self) -> bool:
        """Check if we're still in the setup phase."""
        return not self.setup_complete

    def get_current_setup_phase(self) -> SetupPhase:
        """Get the current setup phase."""
        return self.setup_phase

    def _advance_setup_phase_impl(self) -> bool:
        """Advance to the next setup phase. Returns True if setup is complete."""
        if self.setup_complete:
            return True
        
        current_phase_value = self.setup_phase.value
        next_phase_value = current_phase_value + 1
        
        if next_phase_value >= len(SetupPhase):
            # Setup is complete, start battle rounds
            self.setup_complete = True
            # AIRCRAFT are treated as Strategic Reserves once the battle starts.
            for player in list(self.players or []):
                if player is None:
                    raise RuntimeError("Missing player when applying aircraft reserve updates.")
                army = player.get_army()
                if army is None:
                    raise RuntimeError(f"Missing army for {player.name} when applying aircraft reserve updates.")
                for unit in list(army.units):
                    if unit is None:
                        continue
                    if not bool(getattr(unit, "is_aircraft", False)):
                        continue
                    if bool(getattr(unit, "hover_mode", False)):
                        continue
                    if str(getattr(unit, "reserve_status", "deployed")) != "reserves":
                        continue
                    unit.set_reserve_status("strategic_reserves")
            # Set current player to first turn player
            if self.first_turn_player_index is not None:
                self.current_player_index = self.first_turn_player_index
            else:
                # Default: attacker goes first
                self.current_player_index = self.attacker_index if self.attacker_index is not None else 0
            
            # Set the battle round starting player to whoever goes first
            self.battle_round_starting_player_index = self.current_player_index
            self.phase = BattleRoundPhases.COMMAND_PHASE

            # BR1 start-of-battle-round hook:
            # At game start we haven't completed a full round cycle yet, so the normal
            # next_phase() logic won't publish battle_round_started until BR2.
            # Publish it now so "start of the first battle round" abilities trigger (e.g. Shalaxi quarry).
            for player in list(self.players or []):
                if player is None:
                    raise RuntimeError("Missing player when starting battle round.")
                army = player.get_army()
                if army is None:
                    raise RuntimeError(f"Missing army for {player.name} when starting battle round.")
                for unit in list(army.units):
                    unit.initialize_round()
                # Army-level battle round start hook (faction rules/buffs)
                army.on_battle_round_start(self.turn)
            self.event_system.publish("battle_round_started", game=self, battle_round=self.turn)

            # Start of Command phase for the first battle round.
            self.start_command_phase()

            # Show detailed first turn information
            first_turn_player = self.get_current_player()
            if self.first_turn_player_index == self.attacker_index:
                role = "Attacker"
            elif self.first_turn_player_index == self.defender_index:
                role = "Defender"
            else:
                role = "Player"

            logger.info(f"Setup complete! {first_turn_player.name} ({role}) goes first")
            return True
        else:
            self.setup_phase = SetupPhase(next_phase_value)
            if self.setup_phase == SetupPhase.SELECT_MISSION_OBJECTIVES:
                if bool(getattr(self, "is_authoritative", True)):
                    self.request_mission_selection()
            if self.setup_phase == SetupPhase.RESOLVE_PREBATTLE_RULES:
                self._queue_prebattle_rules_start_requests()
            logger.info(f"Advanced to setup phase: {self.setup_phase.name}")
            return False

    def advance_setup_phase(self) -> bool:
        """Advance to the next setup phase. Returns True if setup is complete."""
        if self.in_command_context():
            return self._advance_setup_phase_impl()
        player_id = None
        try:
            player_id = self.get_current_player().id
        except Exception:
            player_id = None
        cmd = GameCommand.create(CMD_ADVANCE_SETUP_PHASE, player_id=player_id)
        result = self.apply_command(cmd)
        if getattr(result, "ok", False):
            return bool(getattr(result, "value", False))
        return bool(self.setup_complete)

    def execute_muster_armies_phase(
        self,
        player1_army_file: str = None,
        player2_army_file: str = None,
        player1_muster: "ArmyMusterRequest" = None,
        player2_muster: "ArmyMusterRequest" = None,
    ) -> None:
        """Phase 1: Muster Armies - Load army lists for both players."""
        logger.info("MUSTER ARMIES: Loading army lists...")
        
        if player1_muster is None or player2_muster is None:
            stored = getattr(self, "army_muster_requests", {}) or {}
            if player1_muster is None:
                player1_muster = stored.get("player1")
            if player2_muster is None:
                player2_muster = stored.get("player2")

        # Use army files from game.army_files if not provided as parameters
        if player1_army_file is None:
            player1_army_file = getattr(self, 'army_files', {}).get('player1', 'army_lists/warhammer_app_dump.txt')
        if player2_army_file is None:
            player2_army_file = getattr(self, 'army_files', {}).get('player2', 'army_lists/chaos_daemons_GT2023.txt')
        
        # Validate army files exist
        import os
        if player1_muster is None and not os.path.exists(player1_army_file):
            raise FileNotFoundError(f"Player 1 army file not found: {player1_army_file}")
        if player2_muster is None and not os.path.exists(player2_army_file):
            raise FileNotFoundError(f"Player 2 army file not found: {player2_army_file}")
        
        # Load armies for both players
        from ...roster.army import parse_army_list
        from ...roster.army_muster import ArmyMusterer
        from ...waha_helper import WahaHelper

        waha_helper = WahaHelper()
        muster = ArmyMusterer(waha_helper)
        
        if len(self.players) >= 2:
            # Load army for Player 1
            if player1_muster is not None:
                player1_army = muster.muster_army(player1_muster)
            else:
                player1_army = parse_army_list(player1_army_file, waha_helper)
            self.players[0].set_army(player1_army)
            
            # Load army for Player 2  
            if player2_muster is not None:
                player2_army = muster.muster_army(player2_muster)
            else:
                player2_army = parse_army_list(player2_army_file, waha_helper)
            self.players[1].set_army(player2_army)
            
            player1_units = len(self.players[0].get_army().units)
            player2_units = len(self.players[1].get_army().units)
            logger.info(f"{self.players[0].name}: {player1_units} units loaded from {player1_army_file}")
            logger.info(f"{self.players[1].name}: {player2_units} units loaded from {player2_army_file}")
            for player in list(self.players[:2]):
                if player is None:
                    raise RuntimeError("Missing player during mustering.")
                army = player.get_army()
                if army is None:
                    raise RuntimeError(f"Missing army for {player.name} during mustering.")
                if not bool(getattr(self, "is_authoritative", True)):
                    continue
                pending = list(army.get_pending_daemonic_allegiance_units() or [])
                if pending:
                    army.resolve_daemonic_allegiances(player=player, game=self)
                tyr_mgr = getattr(army, "tyranids_detachments", None)
                queue_trygon_fn = getattr(
                    tyr_mgr,
                    "queue_subterranean_assault_trygon_character_selection_request",
                    None,
                ) if tyr_mgr is not None else None
                if callable(queue_trygon_fn):
                    queue_trygon_fn(game=self, player=player)
                ac_mgr = getattr(army, "adeptus_custodes_detachments", None)
                queue_walker_fn = getattr(
                    ac_mgr,
                    "queue_solar_spearhead_walker_character_selection_request",
                    None,
                ) if ac_mgr is not None else None
                if callable(queue_walker_fn):
                    queue_walker_fn(game=self, player=player)
                ck_mgr = getattr(army, "chaos_knights_detachments", None)
                queue_houndpack_fn = getattr(
                    ck_mgr,
                    "queue_houndpack_lance_character_selection_request",
                    None,
                ) if ck_mgr is not None else None
                if callable(queue_houndpack_fn):
                    queue_houndpack_fn(game=self, player=player)
        else:
            logger.info("Not enough players loaded")

        # Armies and units are now populated; rebuild the entity registry for decision resolution.
        self.rebuild_entity_registry()

    def execute_select_mission_objectives_phase(self) -> None:
        """Phase 2: Select Mission Objectives - Choose mission and objectives."""
        logger.info("SELECT MISSION OBJECTIVES: Setting up mission...")
        
        # Set up available commands for high-level strategy
        self.commands = ["attack", "defend", "move"]
        logger.info(f"Commands configured: {self.commands}")
        
        # Store selected mission info for use in CREATE_BATTLEFIELD phase
        # This will be set by the UI when the mission selection dialog is used
        if not hasattr(self, 'selected_mission_info'):
            # Use a valid default combination - M: Purge the Foe / Crucible of Battle / Layout 1
            self.selected_mission_info = {
                "combination_id": "M",
                "primary": "Purge the Foe",  # Valid with Crucible of Battle
                "deployment": "Crucible of Battle",   
                "layout": 1  # Valid layout for this combination
            }
            logger.info(f"Using default mission: {self.selected_mission_info}")
        else:
            logger.info(f"Mission selected: {self.selected_mission_info}")
        
        # Mission objectives will be placed during CREATE_BATTLEFIELD phase
        logger.info("Mission framework configured")

        # Imperial Knights: Code Chivalric selection (end of Read Mission Objectives step).
        for player in list(self.players or []):
            if player is None:
                raise RuntimeError("Missing player during mission objective selection.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Missing army for {player.name} during mission objective selection.")
            mgr = getattr(army, "code_chivalric", None)
            if mgr is None:
                continue
            if not mgr._army_has_code_chivalric():
                continue
            mgr.on_read_mission_objectives(game=self, player=player)

    def execute_create_battlefield_phase(self, mission_name: str = None) -> None:
        """Phase 3: Create Battlefield - Set up map, terrain, deployment zones, and objectives."""
        logger.info("CREATE BATTLEFIELD: Setting up battlefield...")
        
        # Use selected mission info if available, otherwise use provided mission_name or default
        if hasattr(self, 'selected_mission_info'):
            deployment_mission = self.selected_mission_info["deployment"]
            terrain_layout = self.selected_mission_info["layout"]
            primary_mission = self.selected_mission_info["primary"]
        else:
            deployment_mission = mission_name or "Crucible of Battle"
            terrain_layout = 1
            primary_mission = "Take and Hold"
        
        # 1. Create the Map (already done in __init__)
        battlefield_width, battlefield_height = self.get_battlefield_size()
        logger.info(f"Map created: {battlefield_width}\" x {battlefield_height}\"")
        
        # 2. Terrain features based on selected terrain layout
        from ...battlefield.terrain_layouts import instantiate_layout
        terrain_features = instantiate_layout(terrain_layout)
        if terrain_features:
            self.map.add_terrain_features(terrain_features)
            logger.info(f"Terrain layout {terrain_layout} placed: {len(terrain_features)} features")
            # Debug: print RUINS footprints for verification
            from ...battlefield.map import TerrainType
            from ...utility.constants import RUINS_FLOOR_HEIGHT
            for idx, tf in enumerate(terrain_features):
                if getattr(tf, 'terrain_type', None) == TerrainType.RUINS:
                    coords = list(tf.footprint.exterior.coords)[:-1]
                    pairs = [(round(float(x), 2), round(float(y), 2)) for (x, y) in coords]
                    logger.info(f"   - RUINS #{idx+1} footprint: {pairs}")
                    # Floors detail (ground=0, first=1, second=2)
                    floors = getattr(tf, 'floors', []) or []
                    for fl in floors:
                        poly = fl.get('polygon')
                        elev = float(fl.get('elevation', 0.0))
                        level = int(round(elev / float(RUINS_FLOOR_HEIGHT)))
                        if hasattr(poly, 'exterior'):
                            fcoords = list(poly.exterior.coords)[:-1]
                            fpairs = [(round(float(x), 2), round(float(y), 2)) for (x, y) in fcoords]
                            logger.info(f"      - Floor L{level} (elev {elev:.1f}\"): {fpairs}")
        else:
            logger.info(f"Terrain layout {terrain_layout} has no registered features")
        
        # 3. Set up mission-based deployment zones and objectives
        from ..deployment import DeploymentManager
        deployment_manager = DeploymentManager(self, deployment_mission)
        
        # Set up deployment zones for the mission
        mission_zones = deployment_manager.create_deployment_zones()
        
        # Convert to the format expected by the game for visualization
        self.deployment_zones = {}
        for zone in mission_zones:
            if zone['zone_type'] == 'defender':
                # Assign to first player as defender (will be properly assigned later)
                self.deployment_zones[self.players[0].id] = zone
            elif zone['zone_type'] == 'attacker':
                # Assign to second player as attacker
                self.deployment_zones[self.players[1].id] = zone
        
        logger.info(f"Mission deployment zones created: {deployment_mission}")
        
        # 4. Set up mission objectives
        deployment_manager.setup_mission_objectives()
        logger.info(f"Mission objectives placed: {len(self.objectives)} objectives")
        logger.info(f"Primary Mission: {primary_mission}")

        # Apply primary-mission setup rules that modify objective markers (Chapter Approved 2025/26).
        self._apply_primary_mission_setup_rules()

    def sync_deployment_zones_to_attacker_defender(self) -> None:
        """Ensure deployment zones are keyed by current attacker/defender player ids."""
        zones = getattr(self, "deployment_zones", None)
        if not isinstance(zones, dict) or not zones:
            return
        attacker_idx = getattr(self, "attacker_index", None)
        defender_idx = getattr(self, "defender_index", None)
        if attacker_idx is None or defender_idx is None:
            return
        if not (0 <= int(attacker_idx) < len(self.players)):
            return
        if not (0 <= int(defender_idx) < len(self.players)):
            return
        attacker_player = self.players[int(attacker_idx)]
        defender_player = self.players[int(defender_idx)]
        attacker_zone = None
        defender_zone = None
        for zone in list(zones.values()):
            if not isinstance(zone, dict):
                continue
            zone_type = str(zone.get("zone_type", "") or "").strip().lower()
            if zone_type == "attacker" and attacker_zone is None:
                attacker_zone = zone
            elif zone_type == "defender" and defender_zone is None:
                defender_zone = zone
        if attacker_zone is None or defender_zone is None:
            return
        self.deployment_zones = {
            str(getattr(defender_player, "id", "")): defender_zone,
            str(getattr(attacker_player, "id", "")): attacker_zone,
        }

    def execute_determine_attacker_defender_phase(self) -> None:
        """Phase 4: Determine Attacker and Defender - Roll off to determine roles."""
        logger.info("DETERMINE ATTACKER AND DEFENDER: Rolling off...")
        
        from ...utility.dice import get_roll
        from ...utility.event_bus import append_dice
        
        p1 = self.players[0]
        p2 = self.players[1]
        
        player1_roll = get_roll(
            "1D6",
            game=self,
            player=p1,
            reason=f"Determine attacker and defender: {p1.name}",
            roll_type="determine_attacker_defender",
        )
        player2_roll = get_roll(
            "1D6",
            game=self,
            player=p2,
            reason=f"Determine attacker and defender: {p2.name}",
            roll_type="determine_attacker_defender",
        )
        append_dice(p1, f"First turn roll: {player1_roll}")
        append_dice(p2, f"First turn roll: {player2_roll}")
        
        logger.info(f"{p1.name} rolled: {player1_roll}")
        logger.info(f"{p2.name} rolled: {player2_roll}")
        
        if player1_roll > player2_roll:
            self.attacker_index = 0
            self.defender_index = 1
            logger.info(f"{p1.name} is the Attacker")
            logger.info(f"{p2.name} is the Defender")
        elif player2_roll > player1_roll:
            self.attacker_index = 1
            self.defender_index = 0
            logger.info(f"{p2.name} is the Attacker")
            logger.info(f"{p1.name} is the Defender")
        else:
            # Tie - re-roll
            logger.info("Tie! Re-rolling...")
            return self.execute_determine_attacker_defender_phase()
        
        # Set deployment turn to defender (defender deploys first)
        self.deployment_turn_index = self.defender_index
        self.sync_deployment_zones_to_attacker_defender()
        # Reset deployment special-rule trackers for a fresh setup sequence
        self.deployment_skip_turns = {}

    def _apply_hover_declarations(self) -> None:
        """Declare Hover mode choices before Battle Formations steps."""
        players = list(self.players or [])
        if not players:
            return
        pending_unit_ids: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "hover_mode":
                    continue
                unit_id = str(ctx.get("unit_id", "") or "")
                if unit_id:
                    pending_unit_ids.add(unit_id)

        from ..decision_requests import build_hover_mode_requests

        for player in players:
            if player is None:
                raise RuntimeError("Hover declarations require players.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Hover declarations require an army for {player.name}.")
            units = list(getattr(army, "units", []) or [])
            requests = build_hover_mode_requests(self, units, queue_requests=False)
            for req in list(requests or []):
                unit_id = str(getattr(req, "context", {}).get("unit_id", "") or "")
                if unit_id and unit_id in pending_unit_ids:
                    continue
                self.request_decision(req)

    def _apply_player_color_declarations(self) -> None:
        """Queue player color selection decisions before deployment interactions begin."""
        players = list(self.players or [])
        if not players:
            return
        from ..decision_requests import build_player_color_selection_requests

        build_player_color_selection_requests(self, players, queue_requests=True)

    def _apply_patrol_squad_declarations(self) -> None:
        """Queue two-into-five split choices at the start of Declare Battle Formations."""
        players = list(self.players or [])
        if not players:
            return
        pending_unit_ids: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") not in {"patrol_squad", "combat_squads"}:
                    continue
                unit_id = str(ctx.get("unit_id", "") or "")
                if unit_id:
                    pending_unit_ids.add(unit_id)

        from ..decision_requests import build_patrol_squad_requests

        for player in players:
            if player is None:
                raise RuntimeError("Split-unit declarations require players.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Split-unit declarations require an army for {player.name}.")
            units = list(getattr(army, "units", []) or [])
            requests = build_patrol_squad_requests(self, units, queue_requests=False)
            for req in list(requests or []):
                unit_id = str(getattr(req, "context", {}).get("unit_id", "") or "")
                if unit_id and unit_id in pending_unit_ids:
                    continue
                self.request_decision(req)
                if unit_id:
                    pending_unit_ids.add(unit_id)

    def _apply_wolf_guard_headtakers_split_declarations(self) -> None:
        """Apply mandatory Wolf Guard Headtakers model-group splits at the start of Declare Battle Formations."""
        players = list(self.players or [])
        if not players:
            return

        from ...utility.unit_split import split_unit_into_wolf_guard_headtakers_units

        def _has_let_loose_the_wolves_rule(unit) -> bool:
            iter_entries = getattr(unit, "_iter_ability_entries_for_rules", None)
            if not callable(iter_entries):
                return False
            for ability_name, _desc in list(iter_entries(model=None) or []):
                if str(ability_name or "").strip().lower() == "let loose the wolves":
                    return True
            return False

        for player in players:
            if player is None:
                raise RuntimeError("Wolf Guard Headtakers split declarations require players.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Wolf Guard Headtakers split declarations require an army for {player.name}.")
            seen_root_ids: set[str] = set()
            units = sorted(
                [unit for unit in list(getattr(army, "units", []) or []) if unit is not None],
                key=lambda unit: str(
                    maybe_entity_id(
                        unit.get_attached_unit_root()
                        if callable(getattr(unit, "get_attached_unit_root", None))
                        else unit
                    )
                    or ""
                ),
            )
            for unit in units:
                root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
                if root is None:
                    continue
                root_id = str(maybe_entity_id(root) or "")
                if not root_id or root_id in seen_root_ids:
                    continue
                seen_root_ids.add(root_id)
                if not bool(getattr(root, "is_alive", lambda: True)()):
                    continue
                special_rules = getattr(root, "special_rules", None)
                if isinstance(special_rules, dict) and bool(special_rules.get("let_loose_the_wolves_split_applied", False)):
                    continue
                if not _has_let_loose_the_wolves_rule(root):
                    continue
                split_unit_into_wolf_guard_headtakers_units(
                    root,
                    game=self,
                    game_map=getattr(self, "map", None),
                )

    def _apply_shadow_assignment_declarations(self) -> None:
        """Queue SHADOW ASSIGNMENT choices for eligible Imperial Agents units."""
        players = list(self.players or [])
        if not players:
            return
        pending_unit_ids: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            from ..decision_kinds import DECISION_SHADOW_ASSIGNMENT

            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_SHADOW_ASSIGNMENT:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                unit_id = str(ctx.get("unit_id", "") or "")
                if unit_id:
                    pending_unit_ids.add(unit_id)

        from ..decision_requests import build_shadow_assignment_requests

        for player in players:
            if player is None:
                raise RuntimeError("Shadow Assignment declarations require players.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Shadow Assignment declarations require an army for {player.name}.")
            units = list(getattr(army, "units", []) or [])
            requests = build_shadow_assignment_requests(self, units, queue_requests=False)
            for req in list(requests or []):
                unit_id = str(getattr(req, "context", {}).get("unit_id", "") or "")
                if unit_id and unit_id in pending_unit_ids:
                    continue
                self.request_decision(req)
                if unit_id:
                    pending_unit_ids.add(unit_id)

    def _apply_selected_leading_infiltrators_declarations(self) -> None:
        """Queue Declare Battle Formations selection requests for selected-unit leading Infiltrators abilities."""
        players = list(self.players or [])
        if not players:
            return

        pending_army_ids: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "").strip().lower() != "army_selected_leading_infiltrators_declare":
                    continue
                army_id = str(ctx.get("army_id", "") or "")
                if army_id:
                    pending_army_ids.add(army_id)

        from ..decision_requests import build_army_selected_leading_infiltrators_requests

        for player in players:
            if player is None:
                raise RuntimeError("Selected leading Infiltrators declarations require players.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Selected leading Infiltrators declarations require an army for {player.name}.")
            units = list(getattr(army, "units", []) or [])
            requests = build_army_selected_leading_infiltrators_requests(self, units, queue_requests=False)
            for req in list(requests or []):
                army_id = str(getattr(req, "context", {}).get("army_id", "") or "")
                if army_id and army_id in pending_army_ids:
                    continue
                self.request_decision(req)
                if army_id:
                    pending_army_ids.add(army_id)

    def _apply_selected_unit_gain_scouts_declarations(self) -> None:
        """Queue Declare Battle Formations selection requests for unit abilities that grant Scouts to a selected unit."""
        players = list(self.players or [])
        if not players:
            return

        pending_source_ids: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "").strip().lower() != "declare_selected_unit_gain_scouts":
                    continue
                source_id = str(ctx.get("source_unit_id", "") or "")
                if source_id:
                    pending_source_ids.add(source_id)

        from ..decision_requests import build_declare_selected_units_gain_scouts_requests

        for player in players:
            if player is None:
                raise RuntimeError("Selected Scouts declarations require players.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Selected Scouts declarations require an army for {player.name}.")
            units = list(getattr(army, "units", []) or [])
            requests = build_declare_selected_units_gain_scouts_requests(self, units, queue_requests=False)
            for req in list(requests or []):
                source_id = str(getattr(req, "context", {}).get("source_unit_id", "") or "")
                if source_id and source_id in pending_source_ids:
                    continue
                self.request_decision(req)
                if source_id:
                    pending_source_ids.add(source_id)

    def _apply_selected_unit_gain_deep_strike_declarations(self) -> None:
        """Queue Declare Battle Formations selection requests for unit abilities that grant Deep Strike to a selected unit."""
        players = list(self.players or [])
        if not players:
            return

        pending_source_ids: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "").strip().lower() != "declare_selected_unit_gain_deep_strike":
                    continue
                source_id = str(ctx.get("source_unit_id", "") or "")
                if source_id:
                    pending_source_ids.add(source_id)

        from ..decision_requests import build_declare_selected_units_gain_deep_strike_requests

        for player in players:
            if player is None:
                raise RuntimeError("Selected Deep Strike declarations require players.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Selected Deep Strike declarations require an army for {player.name}.")
            units = list(getattr(army, "units", []) or [])
            requests = build_declare_selected_units_gain_deep_strike_requests(self, units, queue_requests=False)
            for req in list(requests or []):
                source_id = str(getattr(req, "context", {}).get("source_unit_id", "") or "")
                if source_id and source_id in pending_source_ids:
                    continue
                self.request_decision(req)
                if source_id:
                    pending_source_ids.add(source_id)

    def _apply_leader_attachment_declarations(self) -> None:
        players = list(self.players or [])
        if not players:
            return

        pending_leader_ids: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            from ..decision_kinds import DECISION_ATTACH_LEADER

            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_ATTACH_LEADER:
                    continue
                leader_id = str(getattr(req, "context", {}).get("leader_id", "") or "")
                if leader_id:
                    pending_leader_ids.add(leader_id)

        from ..decision_requests import build_leader_attachment_requests

        for player in players:
            if player is None:
                raise RuntimeError("Leader attachment declarations require players.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Leader attachment declarations require an army for {player.name}.")
            units = list(getattr(army, "units", []) or [])
            requests = build_leader_attachment_requests(self, units, queue_requests=False)
            for req in list(requests or []):
                leader_id = str(getattr(req, "context", {}).get("leader_id", "") or "")
                if leader_id and leader_id in pending_leader_ids:
                    continue
                self.request_decision(req)
                if leader_id:
                    pending_leader_ids.add(leader_id)

    def _apply_support_artillery_attachment_declarations(self) -> None:
        players = list(self.players or [])
        if not players:
            return

        pending_support_ids: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            from ..decision_kinds import DECISION_ATTACH_SUPPORT_ARTILLERY

            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_ATTACH_SUPPORT_ARTILLERY:
                    continue
                support_id = str(getattr(req, "context", {}).get("support_unit_id", "") or "")
                if support_id:
                    pending_support_ids.add(support_id)

        from ..decision_requests import build_support_artillery_attachment_requests

        for player in players:
            if player is None:
                raise RuntimeError("Support attachment declarations require players.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Support attachment declarations require an army for {player.name}.")
            units = list(getattr(army, "units", []) or [])
            requests = build_support_artillery_attachment_requests(self, units, queue_requests=False)
            for req in list(requests or []):
                support_id = str(getattr(req, "context", {}).get("support_unit_id", "") or "")
                if support_id and support_id in pending_support_ids:
                    continue
                self.request_decision(req)
                if support_id:
                    pending_support_ids.add(support_id)

    def _apply_transport_assignment_declarations(self) -> None:
        players = list(self.players or [])
        if not players:
            return

        pending_unit_ids: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            from ..decision_kinds import DECISION_ASSIGN_TRANSPORT

            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_ASSIGN_TRANSPORT:
                    continue
                unit_id = str(getattr(req, "context", {}).get("unit_id", "") or "")
                if unit_id:
                    pending_unit_ids.add(unit_id)

        from ..decision_requests import build_transport_assignment_requests

        for player in players:
            if player is None:
                raise RuntimeError("Transport declarations require players.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Transport declarations require an army for {player.name}.")
            units = list(getattr(army, "units", []) or [])
            requests = build_transport_assignment_requests(self, units, queue_requests=False)
            for req in list(requests or []):
                unit_id = str(getattr(req, "context", {}).get("unit_id", "") or "")
                if unit_id and unit_id in pending_unit_ids:
                    continue
                self.request_decision(req)
                if unit_id:
                    pending_unit_ids.add(unit_id)

    def _apply_reserves_allocation_declarations(self) -> None:
        players = list(self.players or [])
        if not players:
            return

        pending_player_ids: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            from ..decision_kinds import DECISION_DECLARE_RESERVES

            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_DECLARE_RESERVES:
                    continue
                player_id = str(getattr(req, "player_id", "") or "")
                if player_id:
                    pending_player_ids.add(player_id)

        from ..decision_requests import build_reserves_allocation_request

        for player in players:
            if player is None:
                raise RuntimeError("Reserves declarations require players.")
            player_id = str(getattr(player, "id", "") or "")
            if player_id and player_id in pending_player_ids:
                continue
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Reserves declarations require an army for {player.name}.")
            req = build_reserves_allocation_request(self, army, queue_requests=False)
            if req is None:
                continue
            self.request_decision(req)
            if player_id:
                pending_player_ids.add(player_id)

    def _apply_rapid_drop_deployment_declarations(self) -> None:
        """Queue Rapid-drop Deployment selections for Orbital Assault Force armies."""
        players = list(self.players or [])
        if not players:
            return

        from ..decision_requests import build_rapid_drop_deployment_requests

        for player in players:
            if player is None:
                raise RuntimeError("Rapid-drop Deployment declarations require players.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Rapid-drop Deployment declarations require an army for {player.name}.")
            units = list(getattr(army, "units", []) or [])
            build_rapid_drop_deployment_requests(self, units, queue_requests=True)

    def _apply_teleport_homer_declarations(self) -> None:
        """Queue Teleport Homer marker placement decisions at the start of the battle."""
        players = list(self.players or [])
        if not players:
            return

        from ..decision_kinds import DECISION_PICK_POINT
        from ..decisions import DecisionOption as _DecisionOption
        from ..decisions import DecisionRequest as _DecisionRequest

        pending_unit_ids: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_PICK_POINT:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "").strip().lower() != "teleport_homer_marker_placement":
                    continue
                unit_id = str(ctx.get("unit_id", "") or "")
                if unit_id:
                    pending_unit_ids.add(unit_id)

        for player in players:
            if player is None:
                raise RuntimeError("Teleport Homer declarations require players.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Teleport Homer declarations require an army for {player.name}.")

            opponent_player_id = ""
            for candidate in list(self.players or []):
                if candidate is None or candidate is player:
                    continue
                candidate_id = str(getattr(candidate, "id", "") or "")
                if candidate_id:
                    opponent_player_id = candidate_id
                    break

            seen_root_ids: set[str] = set()
            units = sorted(
                [u for u in list(getattr(army, "units", []) or []) if u is not None],
                key=lambda u: str(maybe_entity_id(getattr(u, "get_attached_unit_root", lambda: u)() if callable(getattr(u, "get_attached_unit_root", None)) else u) or ""),
            )
            for unit in units:
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None:
                    continue
                unit_id = str(maybe_entity_id(root) or "")
                if not unit_id:
                    continue
                if unit_id in seen_root_ids:
                    continue
                seen_root_ids.add(unit_id)
                if unit_id in pending_unit_ids:
                    continue
                can_place = getattr(root, "can_place_teleport_homer_marker", None)
                if not callable(can_place) or not bool(can_place(self)):
                    continue
                get_rule = getattr(root, "get_teleport_homer_rapid_ingress_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if not isinstance(rule, dict):
                    continue
                ability_name = str(rule.get("source", "") or "Teleport Homer").strip() or "Teleport Homer"
                marker_name = str(rule.get("marker_name", "") or "Teleport Homer").strip() or "Teleport Homer"
                request = _DecisionRequest.create(
                    DECISION_PICK_POINT,
                    f"{ability_name}: place {marker_name} token (or Skip).",
                    player_id=getattr(player, "id", None),
                    options=[
                        _DecisionOption.create("Confirm", payload={"action": "confirm"}),
                        _DecisionOption.create("Skip", payload={"action": "skip"}),
                    ],
                    context={
                        "ability": "teleport_homer_marker_placement",
                        "ability_name": ability_name,
                        "marker_name": marker_name,
                        "phase": "Start of battle",
                        "unit": getattr(root, "name", "") or "Unit",
                        "unit_id": unit_id,
                        "source_unit_id": unit_id,
                        "forbidden_deployment_zone_player_id": opponent_player_id,
                        "optional": True,
                        "instruction": "Select a Teleport Homer token point outside your opponent's deployment zone, or Skip.",
                    },
                )
                self.request_decision(request)
                pending_unit_ids.add(unit_id)

    def execute_declare_battle_formations_phase(self) -> None:
        """Phase 5: Declare Battle Formations - Attach leaders, embark in transports, allocate reserves."""
        logger.info("DECLARE BATTLE FORMATIONS: Validating formations...")

        # Player color selections are chosen before deployment interaction begins.
        self._apply_player_color_declarations()

        # Hover mode declarations must happen before any other formation steps.
        self._apply_hover_declarations()
        self._apply_wolf_guard_headtakers_split_declarations()
        self._apply_patrol_squad_declarations()
        self._apply_shadow_assignment_declarations()
        self._apply_rapid_drop_deployment_declarations()
        self._apply_teleport_homer_declarations()
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Missing player during Declare Battle Formations.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Missing army for {p.name} during Declare Battle Formations.")
            apply_fn = getattr(army, "apply_declare_battle_formations_restrictions", None)
            if callable(apply_fn):
                apply_fn()

        # Thousand Sons: Risen Rubricae selections are made at the start of this step.
        from ..decision_requests import build_risen_rubricae_requests

        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Missing player during Declare Battle Formations.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Missing army for {p.name} during Declare Battle Formations.")
            units = list(getattr(army, "units", []) or [])
            build_risen_rubricae_requests(self, units, queue_requests=True)

        self._apply_selected_leading_infiltrators_declarations()
        self._apply_selected_unit_gain_scouts_declarations()
        self._apply_selected_unit_gain_deep_strike_declarations()
        self._apply_leader_attachment_declarations()
        self._apply_support_artillery_attachment_declarations()
        self._apply_transport_assignment_declarations()
        self._apply_reserves_allocation_declarations()

        # Chaos Space Marines Deceptors: select Masters of Misdirection units.
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Missing player during Declare Battle Formations.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Missing army for {p.name} during Declare Battle Formations.")
            mgr = getattr(army, "chaos_space_marines_detachments", None)
            queue_fn = getattr(mgr, "queue_masters_of_misdirection_selection_request", None) if mgr is not None else None
            if callable(queue_fn):
                queue_fn(game=self, player=p)
            falsehood_fn = getattr(mgr, "queue_deceptors_falsehood_declare_request", None) if mgr is not None else None
            if callable(falsehood_fn):
                falsehood_fn(game=self, player=p)

        # Chaos Knights Iconoclast Fiefdom: Pave the Way enhancement unit selection.
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Missing player during Declare Battle Formations.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Missing army for {p.name} during Declare Battle Formations.")
            mgr = getattr(army, "chaos_knights_detachments", None)
            queue_fn = getattr(mgr, "queue_iconoclast_pave_the_way_selection_request", None) if mgr is not None else None
            if callable(queue_fn):
                queue_fn(game=self, player=p)

        # Drukhari Kabalite Cartel: Informant Network enhancement unit selection.
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Missing player during Declare Battle Formations.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Missing army for {p.name} during Declare Battle Formations.")
            mgr = getattr(army, "drukhari_detachments", None)
            queue_fn = getattr(mgr, "queue_informant_network_selection_request", None) if mgr is not None else None
            if callable(queue_fn):
                queue_fn(game=self, player=p)

        # Validate leader attachment limits per army
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Missing player during Declare Battle Formations.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Missing army for {p.name} during Declare Battle Formations.")
            army.validate_leaders()
            try:
                army.validate_support_artillery()
            except AttributeError:
                pass

        # Nurgle's Gift (Aura): select a Plague during Declare Battle Formations.
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Missing player during Declare Battle Formations.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Missing army for {p.name} during Declare Battle Formations.")
            mgr = getattr(army, "nurgles_gift", None)
            if mgr is None:
                continue
            mgr.on_declare_battle_formations_start(game=self)

        # Death Guard Champions of Contagion: Cornucophagus pre-battle Plague selection.
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Missing player during Declare Battle Formations.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Missing army for {p.name} during Declare Battle Formations.")
            mgr = getattr(army, "death_guard_detachments", None)
            queue_fn = getattr(mgr, "queue_cornucophagus_declare_requests", None) if mgr is not None else None
            if callable(queue_fn):
                queue_fn(game=self, player=p)

        logger.info("INFO: Battle formations declared")

    def _apply_ethereal_pathway_declarations(self) -> None:
        """Queue Ethereal Pathway unit selections at the start of Deploy Armies."""
        players = list(self.players or [])
        if not players:
            return
        pending_source_ids: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            from ..decision_kinds import DECISION_CHOOSE_QUARRY

            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "ethereal_pathway":
                    continue
                source_id = str(ctx.get("source_unit_id", "") or "")
                if source_id:
                    pending_source_ids.add(source_id)

        from ..decision_requests import build_ethereal_pathway_requests

        for player in players:
            if player is None:
                raise RuntimeError("Ethereal Pathway declarations require players.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Ethereal Pathway declarations require an army for {player.name}.")
            units = list(getattr(army, "units", []) or [])
            requests = build_ethereal_pathway_requests(self, units, queue_requests=False)
            for req in list(requests or []):
                source_id = str(getattr(req, "context", {}).get("source_unit_id", "") or "")
                if source_id and source_id in pending_source_ids:
                    continue
                self.request_decision(req)
                if source_id:
                    pending_source_ids.add(source_id)

    def execute_deploy_armies_phase(self, manual_phases: bool = False, decision_makers: dict = None) -> None:
        """Phase 6: Deploy Armies - Execute the deployment phase."""
        logger.info("DEPLOY ARMIES: Starting deployment sequence...")

        # Aeldari: Ethereal Pathway selections are made at the start of this step.
        self._apply_ethereal_pathway_declarations()
        
        # Check if we have local players that need UI-based deployment
        has_local_players = any(getattr(player, "has_control", lambda: False)() for player in self.players)
        
        if has_local_players and manual_phases:
            # For local players in manual mode, set up deployment state but don't auto-deploy
            # The UI will handle the actual deployment decisions
            logger.info("INFO: Local deployment mode - use UI to deploy units")
            self.sync_deployment_zones_to_attacker_defender()
            
            # Set up deployment zones if not already done
            if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
                # Always use mission polygon deployment zones (rectangular zones are not supported).
                mission_name = (getattr(self, "selected_mission_info", None) or {}).get("deployment")
                if not mission_name:
                    raise RuntimeError("Missing deployment name in selected_mission_info.")

                from ..deployment import DeploymentManager
                deployment_manager = DeploymentManager(self, mission_name=mission_name)
                zones = deployment_manager.create_deployment_zones()
                defender_zone = next(z for z in zones if z.get("zone_type") == "defender")
                attacker_zone = next(z for z in zones if z.get("zone_type") == "attacker")

                defender_idx = self.defender_index
                attacker_idx = self.attacker_index
                if defender_idx is None or attacker_idx is None:
                    raise RuntimeError("Attacker/defender indices not set before deployment.")

                self.deployment_zones = {
                    self.players[defender_idx].id: defender_zone,
                    self.players[attacker_idx].id: attacker_zone,
                }
            
            # Initialize deployment tracking
            if not hasattr(self, 'deployment_turn_index'):
                if self.defender_index is None:
                    raise RuntimeError("Defender index not set before deployment.")
                self.deployment_turn_index = self.defender_index
            # Reset / initialize TITANIC skip-turn tracker (safe for checkpoint-loaded games)
            self.deployment_skip_turns = {}
            
            # Mark that we're in deployment phase
            self.waiting_for_deployment_input = False
            logger.info("INFO: Deployment phase initialized - deploy units through UI")
        
        elif decision_makers:
            # Use the proper deployment manager with decision makers for controller-driven
            from ..deployment import DeploymentManager
            deployment_manager = DeploymentManager(self)
            deployment_results = deployment_manager.execute_deployment_sequence(decision_makers)
            
            # Store deployment results for reference
            self.deployment_results = deployment_results
            logger.info("INFO: Army deployment complete")
        else:
            raise RuntimeError("Deployment requires manual UI or explicit decision_makers.")

    def _unit_is_deployed_on_battlefield_for_redeploy(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if not bool(getattr(unit, "deployed", False)):
                return False
            if str(getattr(unit, "reserve_status", "deployed") or "deployed") != "deployed":
                return False
            if bool(getattr(unit, "is_embarked", False)) or getattr(unit, "embarked_in", None) is not None:
                return False
            return True
        except Exception:
            return False

    def _redeploy_source_meets_battlefield_requirement(self, source_unit, *, allow_embarked_transport: bool) -> bool:
        if source_unit is None:
            return False
        try:
            source_root = source_unit.get_attached_unit_root()
        except Exception:
            source_root = source_unit
        if source_root is None:
            return False
        if self._unit_is_deployed_on_battlefield_for_redeploy(source_root):
            return True
        if not bool(allow_embarked_transport):
            return False
        try:
            transport = getattr(source_root, "embarked_in", None)
        except Exception:
            transport = None
        if transport is None:
            return False
        try:
            transport_root = transport.get_attached_unit_root()
        except Exception:
            transport_root = transport
        return self._unit_is_deployed_on_battlefield_for_redeploy(transport_root)

    def execute_redeploy_units_phase(self) -> None:
        """Phase: Redeploy Units - Alternate resolving redeploy rules, Attacker first.

        Rules:
        - Some rules allow redeploying certain units after both armies are deployed.
        - Players alternate resolving such rules, starting with the Attacker.
        - Redeploy allows selecting a new valid deployment location for eligible units.
        """
        logger.info("REDEPLOY UNITS: Resolving redeploy abilities...")
        if self.attacker_index is None or self.defender_index is None:
            logger.warning("WARN: Attacker/Defender not set; skipping Redeploy Units phase")
            return
        state = getattr(self, "_redeploy_state", None)
        if isinstance(state, dict) and state.get("active"):
            self._continue_redeploy_phase()
            return

        from ...utility.entity_ids import get_entity_id

        players_in_order = [self.players[self.attacker_index], self.players[self.defender_index]]
        redeploy_queues: dict[str, list[dict]] = {}
        army_once_seen_by_player: dict[str, set[str]] = {}

        for p in players_in_order:
            army = p.get_army()
            if not army:
                continue
            player_id = str(getattr(p, "id", "") or "")
            tokens: list[dict] = []
            for u in list(getattr(army, "units", []) or []):
                has_redeploy, count, can_place_in_reserves = u.has_redeploy()
                if not has_redeploy or int(count or 0) <= 0:
                    continue
                try:
                    cache = getattr(u, "_ability_cache", {}) or {}
                except Exception:
                    cache = {}
                requires_source_on_battlefield = bool(cache.get("redeploy_requires_source_on_battlefield", False))
                allow_embarked_transport_on_battlefield = bool(
                    cache.get("redeploy_allow_embarked_transport_on_battlefield", False)
                )
                if requires_source_on_battlefield and (
                    not self._redeploy_source_meets_battlefield_requirement(
                        u,
                        allow_embarked_transport=allow_embarked_transport_on_battlefield,
                    )
                ):
                    continue
                filters = list(cache.get("redeploy_filters") or [])
                excluded_keywords = list(cache.get("redeploy_excluded_keywords") or [])
                filter_any_groups = list(cache.get("redeploy_filter_any_groups") or [])
                exclude_source_unit = bool(cache.get("redeploy_exclude_source_unit", False))
                must_include_source_unit = bool(cache.get("redeploy_must_include_source_unit", False))
                require_exact_count = bool(cache.get("redeploy_require_exact_count", False))
                army_once_per_ability = bool(cache.get("redeploy_army_once_per_ability", False))
                ability_name = str(cache.get("redeploy_ability_name") or "")
                if not ability_name:
                    ability_name = str(getattr(getattr(u, "enhancement", None), "name", "") or "Redeploy")
                if army_once_per_ability:
                    army_once_key = str(ability_name or "").strip().lower()
                    if army_once_key:
                        seen = army_once_seen_by_player.setdefault(player_id, set())
                        if army_once_key in seen:
                            continue
                        seen.add(army_once_key)
                source_unit_id = get_entity_id(u)
                used_unit_ids = [source_unit_id] if exclude_source_unit and source_unit_id else []
                tokens.append(
                    {
                        "source_unit_id": source_unit_id,
                        "remaining": int(count or 0),
                        "can_place_in_reserves": bool(can_place_in_reserves),
                        "filters": list(filters),
                        "excluded_keywords": list(excluded_keywords),
                        "filter_any_groups": [list(group) for group in filter_any_groups],
                        "used_unit_ids": used_unit_ids,
                        "must_include_source_unit": bool(must_include_source_unit),
                        "require_exact_count": bool(require_exact_count),
                        "selections_made": 0,
                        "ability_name": ability_name,
                        "strategic_reserves_ignore_current_unit_count_limit": bool(
                            cache.get("redeploy_strategic_reserves_ignore_current_unit_count_limit", False)
                        ),
                        "strategic_reserves_ignored_unit_cap_root_ids": [],
                    }
                )
            if tokens:
                tokens.sort(key=lambda t: str(t.get("source_unit_id", "")))
                redeploy_queues[player_id] = tokens

        if not any(redeploy_queues.values()):
            logger.info("INFO: No units with Redeploy; skipping")
            return

        self._redeploy_state = {
            "active": True,
            "turn_index": 0,
            "player_order": [str(getattr(p, "id", "") or "") for p in players_in_order],
            "queues": redeploy_queues,
            "pending_move": False,
            "pending_move_unit_id": "",
        }
        self._queue_redeploy_selection()

    def _continue_redeploy_phase(self) -> None:
        state = getattr(self, "_redeploy_state", None)
        if not isinstance(state, dict) or not state.get("active"):
            return
        if state.get("pending_move"):
            return
        self._queue_redeploy_selection()

    def _redeploy_strategic_reserves_is_legal(
        self,
        army,
        unit,
        *,
        ignore_unit_cap_root_ids=None,
    ) -> bool:
        if army is None or unit is None:
            return False
        reserve_group_roots = getattr(army, "_reserve_group_roots", None)
        if callable(reserve_group_roots):
            for root in list(reserve_group_roots() or []):
                if not hasattr(root, "models_cost"):
                    return True
        validate_fn = getattr(army, "validate_redeploy_to_strategic_reserves", None)
        if not callable(validate_fn):
            return True
        ignored_ids = {
            str(value or "").strip()
            for value in list(ignore_unit_cap_root_ids or [])
            if str(value or "").strip()
        }
        outcome = dict(validate_fn(unit, ignore_unit_cap_root_ids=ignored_ids) or {})
        return bool(outcome.get("valid", False))

    def _queue_redeploy_selection(self) -> None:
        state = getattr(self, "_redeploy_state", None)
        if not isinstance(state, dict) or not state.get("active"):
            return
        if state.get("pending_move"):
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        queue = getattr(self, "decision_queue", None)
        last_decision_id = str(state.get("last_decision_id", "") or "")
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) == "aeldari_guileful_strategist":
                    if last_decision_id and str(getattr(req, "decision_id", "") or "") == last_decision_id:
                        continue
                    return
        order = list(state.get("player_order") or [])
        if not order:
            state["active"] = False
            return
        turn_idx = int(state.get("turn_index", 0) or 0)

        player_id = ""
        player_obj = None
        for _ in range(len(order)):
            pid = str(order[turn_idx % len(order)] or "")
            tokens = list(state.get("queues", {}).get(pid, []) or [])
            if tokens:
                player_id = pid
                player_obj = self.entity_registry.get(pid, kind="player") if self.entity_registry else None
                break
            turn_idx += 1

        if not player_id or player_obj is None:
            state["active"] = False
            logger.info("INFO: Redeploy phase complete")
            return

        state["turn_index"] = turn_idx
        tokens = list(state.get("queues", {}).get(player_id, []) or [])
        if not tokens:
            state["active"] = False
            logger.info("INFO: Redeploy phase complete")
            return
        token = tokens[0]

        army = player_obj.get_army()
        if army is None:
            state["active"] = False
            logger.info("INFO: Redeploy phase complete")
            return

        from ...utility.entity_ids import get_entity_id

        used = set(str(v) for v in list(token.get("used_unit_ids") or []) if v)
        filters = [str(f or "").strip().upper() for f in list(token.get("filters") or []) if str(f or "").strip()]
        excluded_keywords = [
            str(f or "").strip().upper() for f in list(token.get("excluded_keywords") or []) if str(f or "").strip()
        ]
        source_unit_id = str(token.get("source_unit_id", "") or "")
        must_include_source_unit = bool(token.get("must_include_source_unit", False))
        selections_made = int(token.get("selections_made", 0) or 0)
        strategic_reserves_ignore_current_unit_count_limit = bool(
            token.get("strategic_reserves_ignore_current_unit_count_limit", False)
        )
        strategic_reserves_ignored_unit_cap_root_ids = {
            str(value or "").strip()
            for value in list(token.get("strategic_reserves_ignored_unit_cap_root_ids", []) or [])
            if str(value or "").strip()
        }
        raw_any_groups = list(token.get("filter_any_groups") or [])
        filter_any_groups: list[list[str]] = []
        for raw_group in raw_any_groups:
            if isinstance(raw_group, str):
                group = [str(raw_group or "").strip().upper()]
            else:
                group = [str(v or "").strip().upper() for v in list(raw_group or []) if str(v or "").strip()]
            if group:
                filter_any_groups.append(group)

        candidates = []
        seen = set()
        for unit in list(getattr(army, "units", []) or []):
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            try:
                rid = str(get_entity_id(root))
            except Exception:
                continue
            if rid in seen:
                continue
            seen.add(rid)
            if rid in used:
                continue
            if must_include_source_unit and selections_made <= 0 and source_unit_id and rid != source_unit_id:
                continue
            try:
                if not bool(getattr(root, "deployed", False)):
                    continue
                if str(getattr(root, "reserve_status", "deployed") or "deployed") != "deployed":
                    continue
            except Exception:
                continue
            try:
                if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
                    continue
            except Exception:
                continue
            if filters:
                try:
                    if not all(root.has_any_keyword(f) for f in filters):
                        continue
                except Exception:
                    continue
            if excluded_keywords:
                try:
                    if any(root.has_any_keyword(keyword) for keyword in excluded_keywords):
                        continue
                except Exception:
                    continue
            if filter_any_groups:
                matched_any_group = False
                for group in filter_any_groups:
                    try:
                        if all(root.has_any_keyword(f) for f in group):
                            matched_any_group = True
                            break
                    except Exception:
                        continue
                if not matched_any_group:
                    continue
            candidates.append(root)

        if not candidates:
            tokens.pop(0)
            state.get("queues", {})[player_id] = tokens
            state["turn_index"] = turn_idx + 1
            self._queue_redeploy_selection()
            return

        def _cand_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        from ..decisions import DecisionOption, DecisionRequest

        allow_skip = True
        if bool(token.get("require_exact_count", False)) and selections_made > 0:
            allow_skip = False
        options = [DecisionOption.create("None", payload={"action": "skip"})] if allow_skip else []
        for cand in sorted(candidates, key=_cand_sort_key):
            cid = get_entity_id(cand)
            label = str(getattr(cand, "name", "Unit") or "Unit")
            if bool(token.get("can_place_in_reserves")):
                options.append(
                    DecisionOption.create(
                        f"{label} - Redeploy",
                        payload={"target_unit_id": cid, "redeploy_action": "battlefield"},
                    )
                )
                ignored_unit_cap_root_ids = set(strategic_reserves_ignored_unit_cap_root_ids)
                if strategic_reserves_ignore_current_unit_count_limit:
                    ignored_unit_cap_root_ids.add(str(cid))
                if self._redeploy_strategic_reserves_is_legal(
                    army,
                    cand,
                    ignore_unit_cap_root_ids=ignored_unit_cap_root_ids,
                ):
                    options.append(
                        DecisionOption.create(
                            f"{label} - Strategic Reserves",
                            payload={"target_unit_id": cid, "redeploy_action": "strategic_reserves"},
                        )
                    )
            else:
                options.append(
                    DecisionOption.create(
                        f"{label} - Redeploy",
                        payload={"target_unit_id": cid, "redeploy_action": "battlefield"},
                    )
                )

        ability_name = str(token.get("ability_name") or "Redeploy").strip()
        remaining = int(token.get("remaining", 0) or 0)
        ctx = {
            "ability": "aeldari_guileful_strategist",
            "ability_name": ability_name,
            "phase": "Redeploy Units",
            "remaining": remaining,
            "redeploy_player_id": player_id,
            "source_unit_id": token.get("source_unit_id"),
            "can_place_in_reserves": bool(token.get("can_place_in_reserves")),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a unit to redeploy ({remaining} remaining).",
            player_id=player_id,
            options=options,
            context=ctx,
        )
        self.request_decision(request)

    def _apply_redeploy_choice(self, request, result, *, skipped: bool = False) -> None:
        state = getattr(self, "_redeploy_state", None)
        if not isinstance(state, dict) or not state.get("active"):
            return
        ctx = dict(getattr(request, "context", {}) or {})
        player_id = str(ctx.get("redeploy_player_id") or getattr(request, "player_id", "") or "")
        if not player_id:
            return
        queues = state.get("queues", {}) or {}
        tokens = list(queues.get(player_id, []) or [])
        if not tokens:
            return
        token = tokens[0]
        if skipped:
            state["last_decision_id"] = str(getattr(request, "decision_id", "") or "")
            tokens.pop(0)
            queues[player_id] = tokens
            state["turn_index"] = int(state.get("turn_index", 0) or 0) + 1
            self._queue_redeploy_selection()
            return

        from ...utility.entity_ids import get_entity_id
        payload = dict(getattr(result, "payload", {}) or {})
        if not payload:
            try:
                opt = next((o for o in list(getattr(request, "options", []) or []) if o.option_id == result.option_id), None)
                if opt is not None:
                    payload = dict(getattr(opt, "payload", {}) or {})
            except Exception:
                payload = {}
        target_id = str(payload.get("target_unit_id", "") or "")
        action = str(payload.get("redeploy_action", "battlefield") or "battlefield").strip().lower()
        if not target_id:
            tokens.pop(0)
            queues[player_id] = tokens
            state["turn_index"] = int(state.get("turn_index", 0) or 0) + 1
            self._queue_redeploy_selection()
            return
        target = self.entity_registry.get(target_id, kind="unit") if self.entity_registry else None
        if target is None:
            tokens.pop(0)
            queues[player_id] = tokens
            state["turn_index"] = int(state.get("turn_index", 0) or 0) + 1
            self._queue_redeploy_selection()
            return
        try:
            root = target.get_attached_unit_root()
        except Exception:
            root = target
        root_id = get_entity_id(root)
        used = token.get("used_unit_ids")
        if isinstance(used, set):
            used.add(root_id)
        elif isinstance(used, list):
            if root_id not in used:
                used.append(root_id)
        token["selections_made"] = int(token.get("selections_made", 0) or 0) + 1
        token["remaining"] = max(int(token.get("remaining", 0) or 0) - 1, 0)
        if action == "strategic_reserves" and bool(
            token.get("strategic_reserves_ignore_current_unit_count_limit", False)
        ):
            ignored_root_ids = list(token.get("strategic_reserves_ignored_unit_cap_root_ids", []) or [])
            if root_id not in ignored_root_ids:
                ignored_root_ids.append(root_id)
            token["strategic_reserves_ignored_unit_cap_root_ids"] = ignored_root_ids
        if token["remaining"] <= 0:
            tokens.pop(0)
        queues[player_id] = tokens
        state["turn_index"] = int(state.get("turn_index", 0) or 0) + 1
        state["last_decision_id"] = str(getattr(request, "decision_id", "") or "")

        if action == "strategic_reserves":
            self._redeploy_unit_to_strategic_reserves(root)
            self._queue_redeploy_selection()
            return

        player = self.entity_registry.get(player_id, kind="player") if self.entity_registry else None
        ability_name = str(token.get("ability_name") or ctx.get("ability_name") or "Redeploy").strip()
        self._queue_redeploy_placement(player, root, ability_name=ability_name)

    def _queue_redeploy_placement(self, player, unit, *, ability_name: str) -> None:
        if unit is None or not bool(getattr(self, "is_authoritative", True)):
            return
        from ..decision_kinds import DECISION_MOVE_UNIT
        from ..decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_MOVE_UNIT:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if bool(ctx.get("redeploy_followup")) and str(ctx.get("unit_id", "")) == str(get_entity_id(unit)):
                    return

        unit_id = get_entity_id(unit)
        options = [
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": unit_id, "movement_type": "deploy", "action": "confirm"},
            )
        ]
        player_id = getattr(player, "id", None) if player is not None else None
        allowed_ids = [get_entity_id(m) for m in list(getattr(unit, "models", []) or [])]
        ctx = {
            "unit_id": unit_id,
            "movement_type": "deploy",
            "placement_kind": "deployment",
            "allowed_model_ids": allowed_ids,
            "allow_skip": False,
            "redeploy_followup": True,
            "redeploy_unit_id": unit_id,
            "ability_name": str(ability_name or "Redeploy"),
        }
        request = DecisionRequest.create(
            DECISION_MOVE_UNIT,
            f"{ability_name}: redeploy {getattr(unit, 'name', 'Unit')}",
            player_id=player_id,
            options=options,
            context=ctx,
        )
        self._redeploy_state["pending_move"] = True
        self._redeploy_state["pending_move_unit_id"] = str(unit_id)
        self.request_decision(request)

    def _on_redeploy_placement_resolved(self, unit_id: str) -> None:
        state = getattr(self, "_redeploy_state", None)
        if not isinstance(state, dict) or not state.get("active"):
            return
        if str(state.get("pending_move_unit_id") or "") != str(unit_id or ""):
            return
        state["pending_move"] = False
        state["pending_move_unit_id"] = ""
        self._queue_redeploy_selection()

    def _redeploy_unit_to_strategic_reserves(self, unit) -> None:
        if unit is None:
            return
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            return
        get_army = getattr(root, "get_parent_army", None)
        army = get_army() if callable(get_army) else getattr(root, "parent_army", None)
        reserve_group_members = getattr(army, "_reserve_group_members", None) if army is not None else None
        if callable(reserve_group_members):
            group_units = list(reserve_group_members(root) or [])
        else:
            get_members = getattr(root, "get_attached_unit_members", None)
            group_units = list(get_members() or []) if callable(get_members) else [root]
            if bool(getattr(root, "is_transport", False)):
                for passenger in list(getattr(root, "transport_passengers", []) or []):
                    if passenger not in group_units:
                        group_units.append(passenger)
                    for leader in list(getattr(passenger, "attached_leaders", []) or []):
                        if leader not in group_units:
                            group_units.append(leader)
        group_units.sort(key=lambda member: str(get_entity_id(member) or ""))
        game_map = getattr(self, "map", None)
        for member in group_units:
            set_reserve_status = getattr(member, "set_reserve_status", None)
            if callable(set_reserve_status):
                set_reserve_status("strategic_reserves")
            else:
                member.reserve_status = "strategic_reserves"
            member.deployed = True
            member.reserve_turn_deployed = None
            member.arrived_from_reserves_this_turn = False
            member._started_in_reserves = True
            if game_map is not None and hasattr(game_map, "units") and member in game_map.units:
                game_map.units.remove(member)

    def _find_valid_redeploy_position(self, player: 'Player', unit: 'Unit') -> tuple | None:
        """Return None unless a controller provides a redeploy position."""
        return None

    def execute_determine_first_turn_order_phase(self) -> None:
        """Phase 7: Determine First Turn Order - Attacker rolls to see who goes first."""
        logger.info("DETERMINE FIRST TURN ORDER: Rolling for first turn (roll-off)...")

        from ...utility.dice import get_roll
        from ...utility.event_bus import append_dice

        p1 = self.players[0]
        p2 = self.players[1]

        while True:
            roll1 = get_roll(
                "1D6",
                game=self,
                player=p1,
                reason=f"Determine first turn order: {p1.name}",
                roll_type="determine_first_turn_order",
            )
            roll2 = get_roll(
                "1D6",
                game=self,
                player=p2,
                reason=f"Determine first turn order: {p2.name}",
                roll_type="determine_first_turn_order",
            )
            append_dice(p1, f"First turn roll-off: {roll1}")
            append_dice(p2, f"First turn roll-off: {roll2}")
            logger.info(f"INFO: {p1.name} rolled: {roll1}")
            logger.info(f"INFO: {p2.name} rolled: {roll2}")
            if roll1 == roll2:
                logger.info("INFO: Tie on roll-off - re-rolling...")
                continue
            if roll1 > roll2:
                self.first_turn_player_index = 0
                logger.info(f"INFO: {p1.name} wins the roll-off and takes the first turn")
            else:
                self.first_turn_player_index = 1
                logger.info(f"INFO: {p2.name} wins the roll-off and takes the first turn")
            break

        # Clear deployment actions since deployment phase is now complete
        self.clear_deployment_actions()

    def execute_resolve_prebattle_rules_phase(self) -> None:
        """Phase 8: Resolve Pre-battle Rules - Resolve any pre-battle rules, abilities, or stratagems."""
        logger.info("RESOLVE PREBATTLE RULES: Resolving pre-battle rules...")

        self._queue_prebattle_rules_start_requests()

        # Handle Scout moves for all players
        self._handle_scout_moves()

        # TODO - other pre-battle rules (e.g., Detachment stuff like WE dice rolls, etc.)
        
        logger.info("INFO: Pre-battle rules resolved")

    def _queue_prebattle_rules_start_requests(self) -> None:
        """Queue pre-battle decision requests that must resolve before Scout moves."""
        for player in list(self.players or []):
            if player is None:
                continue
            army = player.get_army()
            if army is None:
                continue
            queue_hook = getattr(army, "on_prebattle_rules_start", None)
            if callable(queue_hook):
                queue_hook(game=self)

    def _handle_scout_moves(self) -> None:
        """Handle scout moves for all players during pre-battle rules phase."""
        logger.info("INFO: Processing Scout moves...")
        
        # Get all units with Scout ability from both players
        scout_units = []
        for player in self.players:
            if player.get_army():
                for unit in player.get_army().units:
                    has_scout, scout_distance = unit.has_scout()
                    if has_scout and unit.deployed and unit.reserve_status == 'deployed':
                        scout_units.append((player, unit, scout_distance))
        
        if not scout_units:
            logger.info("INFO: No units with Scout ability found")
            return
        
        logger.info(f"INFO: Found {len(scout_units)} units with Scout ability")
        
        # Sort units by player (first turn player goes first)
        # During setup phase, use first_turn_player_index instead of current_player_index
        if self.first_turn_player_index is not None:
            first_turn_player = self.players[self.first_turn_player_index]
        else:
            # Fallback to attacker if first turn not determined yet
            first_turn_player = self.get_attacker() if self.attacker_index is not None else self.players[0]
        
        scout_units_by_player = {}
        
        for player, unit, scout_distance in scout_units:
            if player not in scout_units_by_player:
                scout_units_by_player[player] = []
            scout_units_by_player[player].append((unit, scout_distance))
        
        # Process scout moves in turn order (first turn player first)
        players_in_order = [first_turn_player]
        for player in self.players:
            if player != first_turn_player:
                players_in_order.append(player)
        
        # Check if we have local players that need UI-based scout moves
        has_local_players = any(getattr(player, "has_control", lambda: False)() for player in self.players)
        
        if has_local_players:
            # For local players, let the UI handle scout moves
            # The PreBattlePhaseHandler will manage the scout move sequence
            logger.info("INFO: Local scout moves will be handled by UI")
            logger.info("INFO: Scout phase initialized - use UI to make scout moves")
        else:
            # For games without local control, queue explicit Scout decisions so
            # headless/network controllers resolve through DecisionRequest API.
            from ..decision_kinds import DECISION_SCOUT_MOVE
            from ..decision_requests import build_scout_move_request

            pending_unit_ids: set[str] = set()
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if getattr(req, "decision_type", None) != DECISION_SCOUT_MOVE:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    unit_id = str(ctx.get("unit_id", "") or "")
                    if unit_id:
                        pending_unit_ids.add(unit_id)

            queued_count = 0
            for player in players_in_order:
                if player in scout_units_by_player:
                    logger.info(f"INFO: {player.name}'s Scout moves:")
                    for unit, scout_distance in scout_units_by_player[player]:
                        unit_id = str(get_entity_id(unit) or "")
                        logger.info(f"  - {unit.name} (Scout {scout_distance}\")")
                        if not unit_id:
                            continue
                        if unit_id in pending_unit_ids:
                            logger.info("    Scout decision already pending")
                            continue
                        req = build_scout_move_request(self, unit)
                        if req is None:
                            continue
                        pending_unit_ids.add(unit_id)
                        queued_count += 1
                        logger.info("    Queued SCOUT_MOVE decision")

            if queued_count > 0:
                logger.info(f"INFO: Queued {queued_count} Scout move decision(s) for remote-only game")
            else:
                logger.info("INFO: Scout decisions already queued for remote-only game")

    def _execute_current_setup_phase_impl(self, **kwargs) -> None:
        """Execute the current setup phase with any necessary parameters."""
        if self.setup_phase == SetupPhase.MUSTER_ARMIES:
            self.execute_muster_armies_phase(
                kwargs.get('player1_army_file'), 
                kwargs.get('player2_army_file')
            )
        elif self.setup_phase == SetupPhase.SELECT_MISSION_OBJECTIVES:
            self.execute_select_mission_objectives_phase()
        elif self.setup_phase == SetupPhase.CREATE_BATTLEFIELD:
            self.execute_create_battlefield_phase()
        elif self.setup_phase == SetupPhase.DETERMINE_ATTACKER_AND_DEFENDER:
            self.execute_determine_attacker_defender_phase()
        elif self.setup_phase == SetupPhase.DECLARE_BATTLE_FORMATIONS:
            self.execute_declare_battle_formations_phase()
        elif self.setup_phase == SetupPhase.DEPLOY_ARMIES:
            decision_makers = kwargs.get('decision_makers')
            if decision_makers is None:
                decision_makers = getattr(self, "_pending_setup_decision_makers", None)
            self.execute_deploy_armies_phase(
                manual_phases=kwargs.get('manual_phases', False),
                decision_makers=decision_makers
            )
        elif self.setup_phase == SetupPhase.REDEPLOY_UNITS:
            self.execute_redeploy_units_phase()
        elif self.setup_phase == SetupPhase.DETERMINE_FIRST_TURN_ORDER:
            self.execute_determine_first_turn_order_phase()
        elif self.setup_phase == SetupPhase.RESOLVE_PREBATTLE_RULES:
            self.execute_resolve_prebattle_rules_phase()

    def execute_current_setup_phase(self, **kwargs) -> None:
        """Execute the current setup phase via command dispatch."""
        if self.in_command_context():
            self._execute_current_setup_phase_impl(**kwargs)
            return
        decision_makers = kwargs.get("decision_makers")
        if decision_makers is not None:
            # Store temporarily so command dispatch can stay serializable.
            self._pending_setup_decision_makers = decision_makers
        payload = {
            "player1_army_file": kwargs.get("player1_army_file"),
            "player2_army_file": kwargs.get("player2_army_file"),
            "manual_phases": bool(kwargs.get("manual_phases", False)),
        }
        player_id = None
        try:
            player_id = self.get_current_player().id
        except Exception:
            player_id = None
        cmd = GameCommand.create(CMD_EXECUTE_SETUP_PHASE, player_id=player_id, payload=payload)
        try:
            self.apply_command(cmd)
        finally:
            if decision_makers is not None:
                self._pending_setup_decision_makers = None

    def _apply_selected_mission(self, combination: dict, layout: object) -> None:
        self.selected_mission_info = {
            "combination_id": combination.get("id"),
            "primary": combination.get("primary"),
            "deployment": combination.get("deployment"),
            "layout": layout,
        }
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list") and hasattr(queue, "pop"):
            pending_ids = [
                str(getattr(req, "decision_id", "") or "")
                for req in list(queue.list() or [])
                if str(getattr(req, "decision_type", "")) == DECISION_CHOOSE_MISSION
            ]
            for decision_id in pending_ids:
                if decision_id:
                    queue.pop(decision_id)
        from ..mission_cards import create_primary_mission_card

        for player in list(self.players or []):
            player.set_primary_mission(create_primary_mission_card(combination.get("primary")))

    def set_selected_mission(self, combination: dict, layout: object) -> None:
        if self.in_command_context():
            self._apply_selected_mission(combination, layout)
            return
        player_id = None
        try:
            player_id = self.get_current_player().id
        except Exception:
            player_id = None
        cmd = GameCommand.create(
            CMD_SELECT_MISSION,
            player_id=player_id,
            payload={"combination": dict(combination or {}), "layout": layout},
        )
        self.apply_command(cmd)

    def set_waiting_for_deployment_input(self, value: bool) -> None:
        if self.in_command_context():
            self.waiting_for_deployment_input = bool(value)
            return
        player_id = None
        try:
            player_id = self.get_current_player().id
        except Exception:
            player_id = None
        cmd = GameCommand.create(
            CMD_SET_DEPLOYMENT_WAITING,
            player_id=player_id,
            payload={"value": bool(value)},
        )
        self.apply_command(cmd)
