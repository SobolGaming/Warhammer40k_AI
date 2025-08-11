from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import logging
from .event_system import EventSystem
from .map import Map, Objective
from .player import Player
from .unit import Unit
from .model import Model
from ..utility.calcs import get_dist, clear_enemy_model_cache
from ..utility.dice import DiceCollection
from ..utility.constants import TOTAL_ROUNDS

logger = logging.getLogger(__name__)

class SetupPhase(Enum):
    """
    The phases of the setup phase.
    """
    MUSTER_ARMIES = 0
    SELECT_MISSION_OBJECTIVES = 1
    CREATE_BATTLEFIELD = 2  # Place terrain, objectives, etc.
    DETERMINE_ATTACKER_AND_DEFENDER = 3
    DECLARE_BATTLE_FORMATIONS = 4  # Attach leaders to units if you want; declare reserve; declare embarked unts
    DEPLOY_ARMIES = 5
    DETERMINE_FIRST_TURN_ORDER = 6
    RESOLVE_PREBATTLE_RULES = 7  # Resolve any pre-battle rules, abilities, or stratagems


class BattleRoundPhases(Enum):
    """
    The phases of a battle round.
    """
    COMMAND_PHASE = 0
    MOVEMENT_PHASE = 1
    SHOOTING_PHASE = 2
    CHARGE_PHASE = 3
    FIGHT_PHASE = 4


class BattlefieldSize(Enum):
    COMBAT_PATROL = "Combat Patrol"
    INCURSION = "Incursion"
    STRIKE_FORCE = "Strike Force"
    ONSLAUGHT = "Onslaught"


class Battlefield:
    SIZES: Dict[BattlefieldSize, Dict[str, Any]] = {
        BattlefieldSize.COMBAT_PATROL: {
            "width": 44,
            "height": 30,
            "points": 500,
            "command_points": 3,
            "detachments": 1
        },
        BattlefieldSize.INCURSION: {
            "width": 44,
            "height": 30,
            "points": 1000,
            "command_points": 6,
            "detachments": 2
        },
        BattlefieldSize.STRIKE_FORCE: {
            "width": 60,
            "height": 44,
            "points": 2000,
            "command_points": 6,
            "detachments": 3
        },
        BattlefieldSize.ONSLAUGHT: {
            "width": 90,
            "height": 44,
            "points": 3000,
            "command_points": 8,
            "detachments": 4
        }
    }

    def __init__(self, size: BattlefieldSize = None, width: int = None, height: int = None):
        if size:
            self.size = size
            self.width = self.SIZES[size]["width"]
            self.height = self.SIZES[size]["height"]
            self.points = self.SIZES[size]["points"]
            self.command_points = self.SIZES[size]["command_points"]
            self.detachments = self.SIZES[size]["detachments"]
        else:
            self.size = None
            self.width = width
            self.height = height
            self.points = None
            self.command_points = None
            self.detachments = None

    def __str__(self):
        return f"Battlefield({self.width}\" x {self.height}\")"


class Game:
    def __init__(self, battlefield: Battlefield, players: List[Player] = []):
        self.battlefield = battlefield
        self.players = players
        self.turn = 1
        self.current_player_index = 0
        self.map = Map(battlefield.width, battlefield.height)
        self.event_system = EventSystem()
        self.objectives = []
        self.commands = []
        self.phase = BattleRoundPhases.COMMAND_PHASE  # Initialize phase to COMMAND_PHASE
        self.do_ai_action = False  # Initialize AI action flag
        
        # Setup phase tracking
        self.setup_phase = SetupPhase.MUSTER_ARMIES  # Start with first setup phase
        self.setup_complete = False  # Track when setup is finished
        
        # Deployment tracking
        self.deployment_turn_index = 0  # Track whose turn it is to deploy (0 = defender, 1 = attacker)
        self.attacker_index = None  # Index of the attacking player (will be set during DETERMINE_ATTACKER_AND_DEFENDER)
        self.defender_index = None  # Index of the defending player (will be set during DETERMINE_ATTACKER_AND_DEFENDER)
        self.deployment_zones = {}  # Store deployment zones for visualization {player_name: zone_dict}
        self.waiting_for_deployment_input = False  # Flag for manual phases during deployment
        self.deployment_actions = {}  # Track last deployment action for each player
        self.first_turn_player_index = None  # Index of player who goes first (will be set during DETERMINE_FIRST_TURN_ORDER)
        self.battle_round_starting_player_index = None  # Track who started the current battle round

    def add_player(self, player: Player) -> None:
        """Add a player to the game."""
        self.players.append(player)
        player.set_game(self)

    def add_objective(self, objective: Objective) -> None:
        """Add an objective to the game."""
        self.objectives.append(objective)

    def add_command(self, command: str) -> None:
        """Add a command to the game."""
        self.commands.append(command)

    def get_current_player(self) -> Player:
        """Get the current player."""
        return self.players[self.current_player_index]

    def get_opponent(self) -> Player:
        """Get the opponent of the current player."""
        return self.players[(self.current_player_index + 1) % len(self.players)]

    def get_enemy_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to the opponent of the given player."""
        # Get their opponent
        opponent = next((p for p in self.players if p != player), None)
        if not opponent:
            return []
        
        return opponent.get_army().units

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
        # Units with deployed=False still need deployment decisions made
        # Units with deployed=True have been assigned (battlefield, reserves, or strategic reserves)
        return [u for u in player.get_army().units if not u.deployed]
    
    def record_deployment_action(self, player: Player, unit: 'Unit', action: str, location: tuple = None) -> None:
        """Record a deployment action for display in the InfoPane."""
        if action == 'deployed' and location:
            x, y, z = location
            action_text = f"{unit.name} deployed at ({x:.1f}, {y:.1f})"
        elif action == 'reserves':
            action_text = f"{unit.name} placed in Reserves"
        elif action == 'strategic_reserves':
            action_text = f"{unit.name} placed in Strategic Reserves"
        else:
            action_text = f"{unit.name} - {action}"
        
        self.deployment_actions[player.name] = action_text

    def clear_deployment_actions(self) -> None:
        """Clear deployment action history after deployment phase ends."""
        self.deployment_actions = {}

    def advance_deployment_turn(self) -> None:
        """Advance to the next player's deployment turn."""
        if not self.is_deployment_phase():
            return
        
        # Get current and next player's deployable units
        current_player = self.get_current_deployment_player()
        current_deployable = self.get_deployable_units(current_player)
        
        # Switch to the other player
        self.deployment_turn_index = (self.deployment_turn_index + 1) % len(self.players)
        next_player = self.get_current_deployment_player()
        next_deployable = self.get_deployable_units(next_player)
        
        # If the next player has no units to deploy, keep switching until we find someone who does
        # or until everyone is done
        attempts = 0
        while not next_deployable and attempts < len(self.players):
            self.deployment_turn_index = (self.deployment_turn_index + 1) % len(self.players)
            next_player = self.get_current_deployment_player()
            next_deployable = self.get_deployable_units(next_player)
            attempts += 1
    
    def complete_deployment_phase(self, manual_phases: bool = False) -> None:
        """Force complete the deployment phase by auto-deploying remaining units one at a time."""
        print("🚀 Starting auto-deployment...")
        
        # Deploy units one at a time, respecting the deployment turn system
        max_attempts = 100  # Safety limit to prevent infinite loops
        attempts = 0
        
        while self.is_deployment_phase() and attempts < max_attempts:
            attempts += 1
            current_player = self.get_current_deployment_player()
            
            if not current_player:
                print("❌ No current deployment player found")
                break
            
            # Get units that need to be deployed for the current player
            undeployed_units = self.get_deployable_units(current_player)
            
            if not undeployed_units:
                # Current player has no more units to deploy, advance to next player
                print(f"Player {current_player.name} has no more units to deploy")
                self.advance_deployment_turn()
                continue
            
            # Auto-deploy the first undeployed unit for the current player
            unit = undeployed_units[0]
            print(f"Auto-deploying {unit.name} for {current_player.name}...")
            
            success = self.auto_deploy_unit(unit)
            if success:
                # Record deployment action
                if unit.position:
                    self.record_deployment_action(current_player, unit, 'deployed', unit.position)
                # Mark unit as deployed and advance to next player's turn
                unit.deployed = True
                self.advance_deployment_turn()
            else:
                print(f"❌ Failed to auto-deploy {unit.name}, advancing anyway")
                # Force deployment to prevent infinite loop
                unit.deployed = True
                unit.reserve_status = 'reserves'  # Mark as failed deployment
                # Record reserves action
                self.record_deployment_action(current_player, unit, 'reserves')
                self.advance_deployment_turn()
            
            # In manual phases mode, pause after each deployment action and require SPACE to continue
            if manual_phases and self.is_deployment_phase():  # Only pause if deployment isn't finished
                print(f"🔧 Deployment action {attempts} completed. Press SPACE to continue deployment...")
                # Set a flag to indicate we're waiting for manual input during deployment
                self.waiting_for_deployment_input = True
                return  # Exit and wait for manual input
        
        if attempts >= max_attempts:
            print(f"⚠️ Auto-deployment stopped after {max_attempts} attempts to prevent infinite loop")
        
        print(f"🎯 Auto-deployment complete after {attempts} deployment actions")
        self.waiting_for_deployment_input = False
    
    def auto_deploy_unit(self, unit: 'Unit') -> bool:
        """Auto-deploy a unit using systematic grid-based search to avoid crowded areas."""
        import random
        
        # Get the unit's player for deployment zone lookup
        player_name = unit.get_parent_army().player.name if unit.get_parent_army() and unit.get_parent_army().player else None
        
        if not player_name:
            logger.error(f"Cannot auto-deploy {unit.name}: No player found")
            return False
        
        # Get deployment constraints
        battlefield_width, battlefield_height = self.get_battlefield_size()
        
        # Determine search area based on unit type and deployment zones
        if unit.has_infiltrate():
            # Infiltrate units can deploy anywhere except restricted areas
            search_zones = self._get_infiltrate_search_zones(player_name, battlefield_width, battlefield_height)
        else:
            # Normal units must deploy within their deployment zone
            if hasattr(self, 'deployment_zones') and player_name in self.deployment_zones:
                zone = self.deployment_zones[player_name]

                # Helper: maximum model base radius approximation
                def _max_base_radius(u: 'Unit') -> float:
                    max_r = 0.5
                    for m in u.models:
                        r = getattr(m.model_base, 'radius', None)
                        if r is None and hasattr(m.model_base, 'get_radius'):
                            r = m.model_base.get_radius()
                        try:
                            r = float(r)
                        except Exception:
                            try:
                                r = float(max(r))
                            except Exception:
                                r = 0.5
                        max_r = max(max_r, r)
                    return max_r

                # Prepare effective mission polygons eroded by base radius to improve hit-rate
                mission_effective_zones = []

                # Check if this is the new mission zone system or old system
                if 'mission_zones' in zone and zone['mission_zones']:
                    from shapely.geometry import Point as _ShPoint, Polygon as _ShPoly
                    from shapely.ops import unary_union as _sh_union

                    # Compute erosion distance based on unit footprint
                    erosion = _max_base_radius(unit)
                    # Reasonable extra margin for formation spread
                    erosion += max(0.25, 0.1 * len(unit.models))

                    # Build effective (cutout-subtracted) polygons and erode
                    for mz in zone['mission_zones']:
                        poly = _ShPoly(mz.vertices)
                        # Subtract cutouts if any
                        if getattr(mz, 'cutouts', None):
                            for c in mz.cutouts:
                                cg = c.get_shapely_geometry()
                                if cg is not None:
                                    poly = poly.difference(cg)
                        # Erode polygon by erosion distance (buffer with negative value)
                        eff = poly.buffer(-erosion)
                        if not eff.is_empty:
                            mission_effective_zones.append(eff)

                    # If nothing usable after erosion, fall back to un-eroded zones
                    if not mission_effective_zones:
                        for mz in zone['mission_zones']:
                            mission_effective_zones.append(_ShPoly(mz.vertices))

                    # Construct an overall bbox to seed grid, but we will filter by polygon.contains
                    if mission_effective_zones:
                        union = _sh_union(mission_effective_zones)
                        min_x, min_y, max_x, max_y = union.bounds
                    else:
                        min_x = min_y = 0.0
                        max_x, max_y = battlefield_width, battlefield_height

                    search_zones = [(max(min_x, 0.0), min(max_x, battlefield_width),
                                     max(min_y, 0.0), min(max_y, battlefield_height))]
                else:
                    # No mission_zones present -> invalid configuration for deployment
                    return False
            else:
                logger.error(f"No deployment zone found for {player_name}")
                return False
        
        # Use systematic grid-based search instead of random
        for zone_idx, zone in enumerate(search_zones):
            x_min, x_max, y_min, y_max = zone
            
            if x_max <= x_min or y_max <= y_min:
                continue  # Skip invalid zones
            
            # Create a finer grid of potential positions
            grid_spacing = 1.0  # Reduced from 2.0 to 1.0 for finer search
            x_positions = []
            y_positions = []
            
            # Generate grid positions (adaptive to unit size)
            x = x_min
            # Use diameter-based spacing where possible to reduce futile tests
            base_step = 2.0 * max(0.5, len(unit.models) * 0.05)
            step = max(0.75, min(2.0, base_step))
            while x <= x_max:
                x_positions.append(x)
                x += step
            
            y = y_min
            while y <= y_max:
                y_positions.append(y)
                y += step
            
            # Shuffle the positions to avoid predictable patterns
            test_positions = [(x, y) for x in x_positions for y in y_positions]
            random.shuffle(test_positions)
            
            # Test positions systematically
            for x, y in test_positions:
                z = 0.0
                
                # If using mission polygons, skip points outside eroded zones early
                try:
                    if 'mission_effective_zones' not in locals():
                        pass
                    else:
                        inside_any = False
                        for eff in mission_effective_zones:
                            if eff.contains(_ShPoint(x, y)):
                                inside_any = True
                                break
                        if not inside_any:
                            continue
                except Exception:
                    # If Shapely not available or error, continue with regular checks
                    pass

                # Quick check: is this position too close to existing units?
                if self._is_position_too_crowded(x, y, unit, player_name):
                    continue
                
                # Check if this position would place all models wholly within the deployment zone
                try:
                    if self.is_valid_deployment_position(unit, x, y, player_name):
                        # Use the proper deployment flow
                        if self._deploy_unit_at_position(unit, x, y, z):
                            print(f"✅ Successfully auto-deployed {unit.name} at ({x:.1f}, {y:.1f})")
                            return True
                except Exception as e:
                    # If formation finding fails, continue to next position
                    continue
        
        print(f"❌ Failed to auto-deploy {unit.name} - no valid positions found")
        return False
    
    def _is_position_too_crowded(self, x: float, y: float, unit: 'Unit', player_name: str) -> bool:
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

    def _get_infiltrate_search_zones(self, player_name: str, battlefield_width: float, battlefield_height: float) -> list:
        """Get valid search zones for infiltrate units (avoiding enemy deployment zones and 9\" buffer)."""
        zones = []
        
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            # No deployment zones defined - use entire battlefield with buffer
            return [(3.0, battlefield_width - 3.0, 3.0, battlefield_height - 3.0)]
        
        # For infiltrate, we need to avoid enemy deployment zones + 9" buffer
        # Start with the entire battlefield and subtract restricted areas
        
        # Find enemy deployment zones
        enemy_zones = []
        for zone_player_name, zone in self.deployment_zones.items():
            if zone_player_name != player_name:
                enemy_zones.append(zone)
        
        if not enemy_zones:
            # No enemy zones - use entire battlefield
            return [(3.0, battlefield_width - 3.0, 3.0, battlefield_height - 3.0)]
        
        # Create zones that avoid enemy deployment zones + 9" buffer
        # For simplicity, create zones on either side of enemy zones
        for enemy_zone in enemy_zones:
            ex_min, ex_max = enemy_zone['x_range']
            ey_min, ey_max = enemy_zone['y_range']
            
            # Zone to the left of enemy zone (if space available)
            if ex_min - 9.0 > 3.0:
                zones.append((3.0, ex_min - 9.0, 3.0, battlefield_height - 3.0))
            
            # Zone to the right of enemy zone (if space available)
            if ex_max + 9.0 < battlefield_width - 3.0:
                zones.append((ex_max + 9.0, battlefield_width - 3.0, 3.0, battlefield_height - 3.0))
        
        # If no valid zones found, return a small safe zone in the center
        if not zones:
            center_x = battlefield_width / 2
            center_y = battlefield_height / 2
            zones.append((center_x - 5, center_x + 5, center_y - 5, center_y + 5))
        
        return zones

    def _deploy_unit_at_position(self, unit: 'Unit', x: float, y: float, z: float) -> bool:
        """Deploy a unit at the specified position using the same flow as manual deployment."""
        try:
            # Use the exact same approach as manual deployment in GameView.on_mouse_press
            # Calculate model positions (this also sets the positions internally)
            # Use boundary repulsors to prevent units from going off the battlefield
            # Deployment zone validation is handled separately by is_valid_deployment_position()
            # During deployment, use relaxed friendly unit avoidance to allow tighter formations
            boundary_repulsors = self.map.get_battlefield_edge_repulsors() if self.map else []
            model_positions = unit.calculate_model_positions(x, y, self.map, avoid_friendly_units=False, boundary_repulsors=boundary_repulsors)
            
            if not model_positions:
                return False
            
            # Unit position is now determined by model positions
            
            # Place unit on map (same as manual)
            if self.map and self.map.place_unit(unit):
                # Don't set unit.deployed here - let the calling function handle it
                return True
            else:
                return False
                
        except Exception as e:
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

    def is_position_in_deployment_zone(self, x: float, y: float, player_name: str) -> bool:
        """Check if a position is within a player's deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return False
        
        if player_name not in self.deployment_zones:
            return False
        
        zone = self.deployment_zones[player_name]
        
        # Only mission zones are supported
        if 'mission_zones' in zone and zone['mission_zones']:
            for mission_zone in zone['mission_zones']:
                if mission_zone.contains_point(x, y):
                    return True
        return False

    def is_model_wholly_in_deployment_zone(self, model: 'Model', player_name: str) -> bool:
        """Check if a model's entire base is wholly within a player's deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return True  # If no deployment zones defined, allow anywhere
        
        if player_name not in self.deployment_zones:
            return False
        
        zone = self.deployment_zones[player_name]
        
        # Get model position and base size
        model_x, model_y = model.get_location()[:2]
        base = model.model_base
        base_radius = base.get_radius()
        
        # Check if this zone has mission_zones (new system)
        if 'mission_zones' in zone:
            # Use the new base checking methods for accurate validation
            for mission_zone in zone['mission_zones']:
                # Check if the entire model base is wholly within this mission zone
                if base.base_type.name == 'CIRCULAR':
                    if mission_zone.contains_circular_base(model_x, model_y, base_radius):
                        return True  # Found a zone that contains the entire base
                else:
                    # For non-circular bases, get the base vertices
                    base_vertices = base.get_vertices_at_position(model_x, model_y)
                    if mission_zone.contains_polygon_base(base_vertices):
                        return True  # Found a zone that contains the entire base
            
            # If no mission zone contains the entire base, placement is invalid
            return False
        else:
            # Fall back to old system for compatibility
            x_min, x_max = zone['x_range']
            y_min, y_max = zone['y_range']
            
            # For circular bases, check that center +/- radius is within zone
            if base.base_type.name == 'CIRCULAR':
                return (x_min <= model_x - base_radius and 
                        model_x + base_radius <= x_max and
                        y_min <= model_y - base_radius and 
                        model_y + base_radius <= y_max)
            
            # For elliptical bases, use the major axis as the effective radius
            elif base.base_type.name == 'ELLIPTICAL':
                major_radius = max(base.radius) if isinstance(base.radius, tuple) else base.radius
                return (x_min <= model_x - major_radius and 
                        model_x + major_radius <= x_max and
                        y_min <= model_y - major_radius and 
                        model_y + major_radius <= y_max)
            
            # For hull bases, use a rectangular approximation
            elif base.base_type.name == 'HULL':
                length, width = base.radius if isinstance(base.radius, tuple) else (base.radius, base.radius)
                return (x_min <= model_x - length and 
                        model_x + length <= x_max and
                        y_min <= model_y - width and 
                        model_y + width <= y_max)
            
            # Default: treat as circular with radius
            else:
                return (x_min <= model_x - base_radius and 
                        model_x + base_radius <= x_max and
                        y_min <= model_y - base_radius and 
                        model_y + base_radius <= y_max)

    def is_position_wholly_in_deployment_zone(self, x: float, y: float, model_base, player_name: str) -> bool:
        """Check if a model base at (x,y) is wholly within the player's deployment zone,
        using mission zones with cutout-aware Shapely checks when available."""
        # Require configured zones
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return False

        # Player must have a zone
        if player_name not in self.deployment_zones:
            return False

        zone_info = self.deployment_zones[player_name]

        # Only support mission_zones from missions.py with cutouts
        if 'mission_zones' in zone_info and zone_info['mission_zones']:
            for mission_zone in zone_info['mission_zones']:
                if model_base.base_type.name == 'CIRCULAR':
                    # Coerce radius to scalar
                    radius_val = getattr(model_base, 'radius', None)
                    if radius_val is None:
                        radius_val = model_base.get_radius() if hasattr(model_base, 'get_radius') else 0.5
                    try:
                        radius_val = float(radius_val)
                    except Exception:
                        try:
                            radius_val = float(max(radius_val))
                        except Exception:
                            radius_val = 0.5
                    if mission_zone.contains_circular_base(x, y, radius_val):
                        return True
                else:
                    # Use provided Shapely geometry from the base itself (no legacy vertex fallback)
                    if not hasattr(model_base, 'get_base_shape_at'):
                        return False
                    base_geom = model_base.get_base_shape_at(x, y, getattr(model_base, 'facing', 0.0))
                    if mission_zone.contains_base_geometry(base_geom):
                        return True
            return False
        return False

    def is_position_in_enemy_deployment_zone(self, x: float, y: float, player_name: str) -> bool:
        """Check if a position is within any enemy deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return False
        
        for zone_player_name, zone in self.deployment_zones.items():
            if zone_player_name != player_name:
                x_min, x_max = zone['x_range']
                y_min, y_max = zone['y_range']
                if x_min <= x <= x_max and y_min <= y <= y_max:
                    return True
        return False

    def get_distance_to_enemy_deployment_zone(self, x: float, y: float, player_name: str) -> float:
        """Get the minimum distance from a position to any enemy deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return float('inf')
        
        min_distance = float('inf')
        
        for zone_player_name, zone in self.deployment_zones.items():
            if zone_player_name != player_name and 'mission_zones' in zone and zone['mission_zones']:
                from shapely.geometry import Point as _ShPoint
                from shapely.geometry import Polygon as _ShPoly
                pt = _ShPoint(x, y)
                for mission_zone in zone['mission_zones']:
                    poly = _ShPoly(mission_zone.vertices)
                    d = pt.distance(poly)
                    if d < min_distance:
                        min_distance = d
        
        return min_distance

    def get_distance_to_enemy_models(self, x: float, y: float, player_name: str) -> float:
        """Get the minimum distance from a position to any enemy model."""
        min_distance = float('inf')
        
        for player in self.players:
            if player.name != player_name and player.get_army():
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
        player_name = unit.get_parent_army().player.name if unit.get_parent_army() and unit.get_parent_army().player else None
        
        if context == 'deployment':
            # For deployment, add deployment zone boundaries (mission-aware) and cutouts as repulsors
            if hasattr(self, 'deployment_zones') and self.deployment_zones and player_name:
                if player_name in self.deployment_zones:
                    zone = self.deployment_zones[player_name]
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
                        # Legacy rectangular ranges
                        x_min, x_max = zone['x_range']
                        y_min, y_max = zone['y_range']
                        # Create repulsor polygons just outside the deployment zone boundaries
                        left_repulsor = Polygon([
                            (x_min - repulsor_thickness, y_min - repulsor_thickness),
                            (x_min, y_min - repulsor_thickness),
                            (x_min, y_max + repulsor_thickness),
                            (x_min - repulsor_thickness, y_max + repulsor_thickness)
                        ])
                        repulsors.append(left_repulsor)
                        right_repulsor = Polygon([
                            (x_max, y_min - repulsor_thickness),
                            (x_max + repulsor_thickness, y_min - repulsor_thickness),
                            (x_max + repulsor_thickness, y_max + repulsor_thickness),
                            (x_max, y_max + repulsor_thickness)
                        ])
                        repulsors.append(right_repulsor)
                        bottom_repulsor = Polygon([
                            (x_min - repulsor_thickness, y_min - repulsor_thickness),
                            (x_max + repulsor_thickness, y_min - repulsor_thickness),
                            (x_max + repulsor_thickness, y_min),
                            (x_min - repulsor_thickness, y_min)
                        ])
                        repulsors.append(bottom_repulsor)
                        top_repulsor = Polygon([
                            (x_min - repulsor_thickness, y_max),
                            (x_max + repulsor_thickness, y_max),
                            (x_max + repulsor_thickness, y_max + repulsor_thickness),
                            (x_min - repulsor_thickness, y_max + repulsor_thickness)
                        ])
                        repulsors.append(top_repulsor)
        
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

    def is_valid_deployment_position(self, unit: 'Unit', x: float, y: float, player_name: str) -> bool:
        """Check if a position is valid for deploying a unit during deployment phase."""
        # Units in reserves don't need position validation
        if unit.reserve_status in ['reserves', 'strategic_reserves']:
            return True
        
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
            model_positions = unit.calculate_model_positions(
                x, y, self.map, avoid_friendly_units=False, boundary_repulsors=deployment_repulsors
            )
            
            if not model_positions:
                return False
                
            for model, position in zip(unit.models, model_positions):
                model_x, model_y = position[0], position[1]
                
                # Check if any part of the model is in enemy deployment zone
                if self.is_position_in_enemy_deployment_zone(model_x, model_y, player_name):
                    return False
                
                # Check 9" distance to enemy deployment zone (from model edge)
                base_radius = model.model_base.get_radius()
                distance_to_enemy_zone = self.get_distance_to_enemy_deployment_zone(model_x, model_y, player_name)
                if distance_to_enemy_zone - base_radius < 9.0:
                    return False
                
                # Check 9" distance to enemy models (from model edge)
                distance_to_enemy_models = self.get_distance_to_enemy_models(model_x, model_y, player_name)
                if distance_to_enemy_models - base_radius < 9.0:
                    return False
            
            return True
        else:
            # Normal units must be WHOLLY within their own deployment zone
            # Check that every model's entire base would be within the deployment zone at the proposed position
            # Calculate model positions using the same logic as unit deployment
            # NOTE: Don't use boundary_repulsors for validation - they make formation finding too restrictive
            # During deployment, use relaxed friendly unit avoidance to allow tighter formations
            deployment_repulsors = self.get_boundary_repulsors(unit, context='deployment')
            model_positions = unit.calculate_model_positions(
                x, y, self.map, avoid_friendly_units=False, boundary_repulsors=deployment_repulsors
            )
            
            if not model_positions:
                return False
                
            for model, position in zip(unit.models, model_positions):
                model_x, model_y = position[0], position[1]
                
                # Check if this model would be wholly within the deployment zone
                if not self.is_position_wholly_in_deployment_zone(model_x, model_y, model.model_base, player_name):
                    try:
                        model_name = getattr(model, 'name', 'model')
                        print(f"🔴 DEBUG: Zone check failed for {unit.name} {model_name} at ({model_x:.1f}, {model_y:.1f}) in player '{player_name}' zone")
                    except Exception:
                        pass
                    return False
            return True

    def get_distance_between_units(self, unit1: 'Unit', unit2: 'Unit') -> float:
        """Calculate the shortest distance between any two models in the units."""
        shortest_distance = float('inf')
        for model1 in unit1.models:
            closest_model, distance = model1.return_closest_model_in_unit(unit2)
            shortest_distance = min(shortest_distance, distance)
        return shortest_distance

    def next_turn(self):
        """Advance to the next turn (legacy method - turn advancement now handled in next_phase)."""
        # This method is kept for compatibility but turn advancement is now handled in next_phase()
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        if self.current_player_index == 0:
            self.turn += 1
            # Reset phase to COMMAND_PHASE at the start of a new turn
            self.phase = BattleRoundPhases.COMMAND_PHASE

    def next_phase(self):
        """Advance to the next phase."""
        current_phase_value = self.phase.value
        next_phase_value = (current_phase_value + 1) % len(BattleRoundPhases)
        self.phase = BattleRoundPhases(next_phase_value)
        
        # Phase-specific resets are no longer needed since we reset all round state at battle round start
        
        if next_phase_value == 0:  # If we've wrapped around to COMMAND_PHASE
            # This means we've finished all phases for the current player
            # Switch to the next player
            self.current_player_index = (self.current_player_index + 1) % len(self.players)

            # Clear enemy model cache when switching players since enemy positions may have changed
            clear_enemy_model_cache(id(self.map))
            print(f"🔄 Player switched to {self.get_current_player().name} - cleared enemy model cache")
            
            # Track who started this battle round if not already set
            if self.battle_round_starting_player_index is None:
                # This is the first player switch of the game - the previous player started the round
                self.battle_round_starting_player_index = (self.current_player_index - 1) % len(self.players)
            
            # Check if we've completed a full battle round (both players have had their turn)
            if self.current_player_index == self.battle_round_starting_player_index:
                # We've cycled back to the player who started this battle round
                self.turn += 1
                self.battle_round_starting_player_index = self.current_player_index  # This player starts the next round
                
                # Reset round state for ALL units at the start of a new battle round
                for player in self.players:
                    for unit in player.get_army().units:
                        unit.initialize_round()

    def is_command_phase(self) -> bool:
        return self.phase == BattleRoundPhases.COMMAND_PHASE
    
    def start_command_phase(self) -> None:
        """Start the command phase - all players gain 1 Command Point and evaluate objectives"""
        for player in self.players:
            player.gain_command_point()

        # Execute command actions for current player's units (without resetting round state)
        current_player = self.get_current_player()
        for unit in current_player.get_army().units:
            # Do battle shock tests and other command phase actions without resetting round state
            if unit.is_below_half_strength():
                print(f"⚠️  {unit.name} is below half strength - taking Battle-Shock test")
                unit.take_battle_shock_test(self.turn)

        # Update and evaluate objectives for the current player
        # NOTE: Objectives cannot grant points until the 2nd battle round
        if self.can_score_objectives():
            for obj in self.map.objectives:
                if hasattr(obj, 'location') and hasattr(obj.location, 'update_control'):
                    obj.location.update_control(self)
                if obj.check_completion(self):
                    current_player.add_score(obj.points)
                    print(f"🎯 {current_player.name} scored {obj.points} points for {obj.name}!")
        else:
            # Still update objective control for tracking purposes, but don't award points
            for obj in self.map.objectives:
                if hasattr(obj, 'location') and hasattr(obj.location, 'update_control'):
                    obj.location.update_control(self)
            print(f"📋 Battle Round {self.get_battle_round()}: Objectives updated but no points awarded (scoring starts in Battle Round 2)")

    def is_movement_phase(self) -> bool:
        return self.phase == BattleRoundPhases.MOVEMENT_PHASE

    def is_shooting_phase(self) -> bool:
        return self.phase == BattleRoundPhases.SHOOTING_PHASE

    def is_charge_phase(self) -> bool:
        return self.phase == BattleRoundPhases.CHARGE_PHASE

    def is_fight_phase(self) -> bool:
        return self.phase == BattleRoundPhases.FIGHT_PHASE

    def can_score_objectives(self) -> bool:
        """Check if objectives can grant points in the current battle round.

        According to Warhammer 40k rules, objectives cannot grant points until
        the 2nd battle round.

        Returns:
            bool: True if objectives can grant points, False otherwise
        """
        return self.turn >= 2

    def get_battle_round(self) -> int:
        """Get the current battle round number.

        Returns:
            int: Current battle round (1-based)
        """
        return self.turn

    def is_game_over(self) -> bool:
        if self.turn > TOTAL_ROUNDS:
            return True
        return False

    def get_winner(self) -> Player | None:
        # Return the winning player or None if the game is not over
        if self.is_game_over():
            return max(self.players, key=lambda player: player.get_score(), default=None)
        return None

    def get_loser(self) -> Player | None:
        if self.is_game_over():
            return min(self.players, key=lambda player: player.get_score(), default=None)
        return None

    def get_state(self) -> Dict[str, Any]:
        # Return the current game state as a dictionary
        # TODO - might be overcome by the implementation of "extract_state_features()" in hrl_agent.py
        return {
            "players": self.players,
            "battlefield": self.battlefield,
            "map": self.map,
            "current_player": self.get_current_player(),
            "turn": self.turn,
            "phase": self.phase,
        }

    def attempt_charge(self, charging_unit: 'Unit', target_unit: 'Unit') -> bool:
        """Attempt a charge move with the given unit against the target.
        
        According to 10th edition rules, a successful charge requires at least one model
        of the charging unit to end their charge with edge-to-edge distance of 1" or less
        from at least one model in the target unit.
        
        CRITICAL: If the charge roll is insufficient to reach within 1" of the enemy,
        the charge fails completely and NO MODELS MOVE AT ALL.
        """
        if not charging_unit.can_declare_charge_against(target_unit, self):
            return False

        # Calculate current edge-to-edge distance between units
        current_distance = self.map.get_distance_between_units(charging_unit, target_unit)
        
        # For a successful charge, we need to achieve edge-to-edge distance of 1" or less
        # So we need to move: current_distance - 1.0 inches
        distance_needed = max(0, current_distance - 1.0)

        # Roll 2D6 for charge distance with modifiers - show individual dice
        dice_collection = DiceCollection.from_string("2D6")
        base_charge_roll, individual_dice = dice_collection.roll_detailed()
        charge_roll = self._apply_charge_modifiers(charging_unit, base_charge_roll)
        
        print(f"⚔️ {charging_unit.name} charging {target_unit.name}")
        print(f"⚔️ Current edge-to-edge distance: {current_distance:.1f}\"")
        print(f"⚔️ Distance needed to achieve ≤1\" edge-to-edge: {distance_needed:.1f}\"")
        print(f"⚔️ Charge roll: {base_charge_roll} (rolled {individual_dice}) (modified: {charge_roll})")
        
        # CRITICAL RULE: If charge roll is insufficient, charge fails and no models move
        if charge_roll < distance_needed:
            print(f"❌ Charge failed: roll {charge_roll}\" insufficient to reach within 1\" (needed {distance_needed:.1f}\")")
            print(f"❌ No models move - charge failed completely")
            return False

        # Charge roll is sufficient - now attempt the movement
        # Find the closest models between the two units for accurate distance calculation
        charging_pos = None
        target_pos = None
        closest_distance = float('inf')

        for charging_model in charging_unit.models:
            if not charging_model.is_alive:
                continue
            for target_model in target_unit.models:
                if not target_model.is_alive:
                    continue

                c_pos = charging_model.get_location()
                t_pos = target_model.get_location()
                distance = get_dist(c_pos[0] - t_pos[0], c_pos[1] - t_pos[1], c_pos[2] - t_pos[2])

                if distance < closest_distance:
                    closest_distance = distance
                    charging_pos = c_pos
                    target_pos = t_pos

        if not charging_pos or not target_pos:
            print(f"❌ Charge failed: invalid positions")
            return False

        # CRITICAL: Store original model positions BEFORE attempting movement
        # This allows proper rollback if charge fails to achieve engagement range
        original_model_positions = []
        for model in charging_unit.models:
            original_model_positions.append(model.get_location())
        
        # Calculate direction vector from charging unit to target
        dx = target_pos[0] - charging_pos[0]
        dy = target_pos[1] - charging_pos[1]
        
        # Normalize the direction vector
        distance_to_target = (dx**2 + dy**2)**0.5
        if distance_to_target == 0:
            print(f"❌ Charge failed: units are at same position")
            return False
        
        dx /= distance_to_target
        dy /= distance_to_target
        
        # Move the charging unit towards the target up to the charge roll distance
        # Move as close as possible within the charge roll distance for better pile-in positioning
        movement_distance = min(charge_roll, current_distance - 0.1)  # Get as close as possible without overlapping
        new_x = charging_pos[0] + dx * movement_distance
        new_y = charging_pos[1] + dy * movement_distance
        new_z = self.map.get_height_at_point(new_x, new_y)
        
        # Attempt to move the unit with special charge movement logic
        # During charge, units should be able to move into engagement range
        success = charging_unit.charge_move((new_x, new_y, new_z), self.map, target_unit)
        if success:
            # Check if the charge actually achieved engagement range (≤1.0")
            final_distance = self.map.get_distance_between_units(charging_unit, target_unit)
            
            if final_distance <= 1.0:
                charging_unit.round_state.declared_charge_this_round = True
                print(f"✅ Charge successful: {charging_unit.name} achieved {final_distance:.1f}\" edge-to-edge distance with {target_unit.name}")
                return True
            else:
                print(f"❌ Charge failed: {charging_unit.name} achieved {final_distance:.1f}\" edge-to-edge distance (not ≤1.0\") with {target_unit.name}")
                # CRITICAL: Revert all model positions if charge failed to achieve engagement range
                # This ensures that NO MODELS MOVE when a charge fails
                print(f"❌ Charge failed: Reverting all model positions - no models should move on failed charge")
                
                # Restore original positions
                for i, original_pos in enumerate(original_model_positions):
                    if i < len(charging_unit.models):
                        charging_unit.models[i].set_location(*original_pos)
                
                # Unit position is now derived from model positions, no need to restore
                
                return False
        else:
            print(f"❌ Charge failed: could not move unit")
            # CRITICAL: Restore original positions if charge_move failed completely
            print(f"❌ Charge failed: Reverting all model positions - no models should move on failed charge")
            
            # Restore original positions
            for i, original_pos in enumerate(original_model_positions):
                if i < len(charging_unit.models):
                    charging_unit.models[i].set_location(*original_pos)
            
            # Unit position is now derived from model positions, no need to restore
            
            return False
    
    def _apply_charge_modifiers(self, charging_unit: 'Unit', base_roll: int) -> int:
        """Apply charge roll modifiers based on unit abilities, stratagems, etc."""
        modified_roll = base_roll
        
        # Check for charge modifiers from abilities
        # TODO: Implement ability-based charge modifiers
        # Examples:
        # - Shock Assault Stratagem: +1" to charge roll
        # - Swift and Deadly ability: re-roll one dice
        # - Relentless Advance trait: roll 3 dice and drop the lowest
        
        # For now, just return the base roll
        return modified_roll
    
    def get_eligible_charging_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that are eligible to declare charges."""
        eligible_units = []
        
        for unit in player.get_army().units:
            if not unit.is_alive() or not unit.deployed:
                continue
            
            # Check if unit has already charged this round
            if unit.round_state.declared_charge_this_round:
                continue
            
            # Check if unit advanced this round (unless special abilities allow charging after advance)
            if unit.round_state.advanced_this_round:
                # TODO: Check for special abilities that allow charging after advance
                continue
            
            # Check if unit fell back this round (unless special abilities allow charging after fall back)
            if unit.round_state.fell_back_this_round:
                # TODO: Check for special abilities that allow charging after fall back
                continue
            
            # Check if unit is already in engagement range
            enemy_units = self.get_enemy_units(player)
            is_engaged = any(self.map.is_within_engagement_range(unit, enemy) 
                           for enemy in enemy_units if enemy.is_alive())
            if is_engaged:
                continue
            
            # Check if there are any valid charge targets
            has_valid_targets = any(unit.can_declare_charge_against(target, self) 
                                  for target in enemy_units if target.is_alive())
            if has_valid_targets:
                eligible_units.append(unit)
        
        return eligible_units
    
    def is_charge_phase_complete(self, player: Player) -> bool:
        """Check if the charge phase is complete for the current player."""
        eligible_units = self.get_eligible_charging_units(player)
        return len(eligible_units) == 0

    ###########################################################################
    # Fight Phase
    ###########################################################################
    def get_eligible_fighting_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that are eligible to fight in the Fight Phase.
        
        A unit is eligible to fight if it:
        - Is alive and deployed
        - Is within engagement range of enemy units OR made a charge move this turn
        
        Args:
            player: The player whose units to check
            
        Returns:
            List of units eligible to fight
        """
        eligible_units = []
        
        for unit in player.get_army().units:
            if unit.is_eligible_to_fight(self.map):
                eligible_units.append(unit)
        
        return eligible_units
    
    def get_fight_first_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that should fight in the Fight First stage.
        
        Units fight first if they:
        - Charged this turn OR
        - Have an inherent Fight First ability
        
        Args:
            player: The player whose units to check
            
        Returns:
            List of units that should fight in the Fight First stage
        """
        fight_first_units = []
        eligible_units = self.get_eligible_fighting_units(player)
        
        for unit in eligible_units:
            if unit.should_fight_first():
                fight_first_units.append(unit)
        
        return fight_first_units
    
    def get_remaining_combatant_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that should fight in the Remaining Combatants stage.
        
        These are units that are eligible to fight but do not fight first.
        
        Args:
            player: The player whose units to check
            
        Returns:
            List of units that should fight in the Remaining Combatants stage
        """
        remaining_units = []
        eligible_units = self.get_eligible_fighting_units(player)
        
        for unit in eligible_units:
            if not unit.should_fight_first():
                remaining_units.append(unit)
        
        return remaining_units
    
    def get_fight_phase_units_by_stage(self, player: Player) -> dict:
        """Get all fighting units for a player categorized by fight stage.
        
        Args:
            player: The player whose units to categorize
            
        Returns:
            Dictionary with 'fight_first' and 'remaining_combatants' keys containing lists of units
        """
        return {
            'fight_first': self.get_fight_first_units(player),
            'remaining_combatants': self.get_remaining_combatant_units(player)
        }
    
    def is_fight_phase_complete(self, player: Player) -> bool:
        """Check if the fight phase is complete for the current player.
        
        The fight phase is complete when there are no more eligible fighting units.
        
        Args:
            player: The player to check
            
        Returns:
            True if the fight phase is complete for this player
        """
        eligible_units = self.get_eligible_fighting_units(player)
        return len(eligible_units) == 0

    ###########################################################################
    ### Reserves System
    ###########################################################################
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
    
    def destroy_units_not_arrived_from_reserves(self, player: Player) -> List['Unit']:
        """Destroy all units that did not arrive from reserves by the deadline."""
        units_to_destroy = []
        
        for unit in self.get_units_in_reserves(player):
            if self.turn > 3:  # After turn 3, units in reserves are destroyed
                units_to_destroy.append(unit)
                logger.warning(f"💀 {unit.name} destroyed - failed to arrive from reserves by turn 3")
        
        # Remove destroyed units from the army
        for unit in units_to_destroy:
            player.get_army().units.remove(unit)
        
        return units_to_destroy
    
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
        
        # For strategic reserves, check edge restrictions
        if unit.is_in_strategic_reserves() and battlefield_edge:
            if not self.is_valid_strategic_reserves_edge(battlefield_edge):
                return False
            
            # Check if unit is within 6" of the specified edge
            edge_distance = self.get_distance_to_battlefield_edge(position, battlefield_edge)
            if edge_distance > 6.0:
                return False
        
        # Check 9" restriction from enemy units
        enemy_units = self.get_enemy_units(unit.get_parent_army().player)
        for enemy_unit in enemy_units:
            if not enemy_unit.is_alive() or not enemy_unit.deployed:
                continue
                
            # Get position from closest model to the arrival position
            enemy_pos = enemy_unit.get_closest_model_position_to_target(position)
            if enemy_pos:
                distance = get_dist(
                    position[0] - enemy_pos[0],
                    position[1] - enemy_pos[1],
                    position[2] - enemy_pos[2]
                )

                if distance < 9.0:
                    return False
        
        return True
    
    def is_valid_strategic_reserves_edge(self, battlefield_edge: str) -> bool:
        """Check if the specified battlefield edge is valid for strategic reserves arrival.
        
        Args:
            battlefield_edge: 'own', 'left', 'right', 'enemy'
        
        Returns:
            bool: True if the edge is valid for the current turn
        """
        if self.turn == 2:
            # Turn 2: Can only arrive from own battlefield edge
            return battlefield_edge == 'own'
        elif self.turn >= 3:
            # Turn 3+: Can arrive from any edge except enemy's
            return battlefield_edge in ['own', 'left', 'right']
        else:
            # Turn 1: No strategic reserves arrivals allowed
            return False
    
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
            Dict mapping player names to lists of units that arrived from reserves
        """
        arrival_results = {}
        current_player = self.get_current_player()
        
        # Handle reserves arrivals for the current player
        units_arrived = self.process_player_reserves_arrivals(current_player)
        arrival_results[current_player.name] = units_arrived
        
        # Destroy units that must arrive but didn't
        destroyed_units = self.destroy_units_not_arrived_from_reserves(current_player)
        if destroyed_units:
            logger.warning(f"💀 {len(destroyed_units)} units destroyed for {current_player.name} - failed to arrive from reserves")
        
        return arrival_results
    
    def process_player_reserves_arrivals(self, player: Player) -> List['Unit']:
        """Process reserves arrivals for a specific player.
        
        This method should be extended or overridden to integrate with AI decision making.
        
        Args:
            player: The player whose reserves arrivals to process
        
        Returns:
            List of units that arrived from reserves
        """
        units_arrived = []
        units_that_can_arrive = self.get_units_that_can_arrive_from_reserves(player)
        units_that_must_arrive = self.get_units_that_must_arrive_from_reserves(player)
        
        # For now, this is a placeholder implementation
        # In the full implementation, this should integrate with AI agents to make decisions
        logger.info(f"🪂 {player.name} has {len(units_that_can_arrive)} units that can arrive from reserves")
        
        # Force arrival of units that must arrive
        for unit in units_that_must_arrive:
            # Try to find a valid placement position
            # Simple automatic deployment - AI agents handle their own deployment decisions
            valid_position = self.find_valid_reserves_position(unit)
            if valid_position:
                if unit.arrive_from_reserves(valid_position, self.turn, self.map):
                    units_arrived.append(unit)
                    self.map.units.append(unit)  # Add to map
                else:
                    logger.error(f"❌ Failed to deploy {unit.name} from reserves despite finding valid position")
            else:
                logger.warning(f"⚠️ No valid position found for {unit.name} - unit will be destroyed")
        
        return units_arrived
    
    def find_valid_reserves_position(self, unit: 'Unit') -> Optional[Tuple[float, float, float]]:
        """Find a valid position for a unit arriving from reserves.
        
        This is a basic implementation that tries to find any valid position.
        Should be enhanced with proper AI decision making.
        
        Args:
            unit: The unit arriving from reserves
        
        Returns:
            Valid position tuple or None if no valid position found
        """
        # Try multiple positions across the battlefield
        attempts = 100
        
        for _ in range(attempts):
            if unit.is_in_strategic_reserves():
                # For strategic reserves, try positions near valid edges
                edge = 'own' if self.turn == 2 else 'own'  # Could be expanded to try different edges
                if edge == 'own':
                    x = self.battlefield.width * 0.5  # Center of battlefield
                    y = 5.0  # 5" from own edge
                elif edge == 'left':
                    x = 5.0  # 5" from left edge
                    y = self.battlefield.height * 0.5
                elif edge == 'right':
                    x = self.battlefield.width - 5.0  # 5" from right edge
                    y = self.battlefield.height * 0.5
                else:
                    continue
                    
                z = self.map.get_height_at_point(x, y)
                position = (x, y, z)
                
                if self.can_place_unit_arriving_from_reserves(unit, position, edge):
                    return position
            else:
                # For standard reserves (Deep Strike), can arrive anywhere more than 9" from enemies
                import random
                x = random.uniform(9.0, self.battlefield.width - 9.0)
                y = random.uniform(9.0, self.battlefield.height - 9.0)
                z = self.map.get_height_at_point(x, y)
                position = (x, y, z)
                
                if self.can_place_unit_arriving_from_reserves(unit, position):
                    return position
        
        return None  # No valid position found

    def get_first_turn_player_index(self) -> int:
        """Get the index of player who goes first (will be set during DETERMINE_FIRST_TURN_ORDER)"""
        return self.first_turn_player_index
    
    def is_in_setup_phase(self) -> bool:
        """Check if we're still in the setup phase."""
        return not self.setup_complete
    
    def get_current_setup_phase(self) -> SetupPhase:
        """Get the current setup phase."""
        return self.setup_phase
    
    def advance_setup_phase(self) -> bool:
        """Advance to the next setup phase. Returns True if setup is complete."""
        if self.setup_complete:
            return True
        
        current_phase_value = self.setup_phase.value
        next_phase_value = current_phase_value + 1
        
        if next_phase_value >= len(SetupPhase):
            # Setup is complete, start battle rounds
            self.setup_complete = True
            # Set current player to first turn player
            if self.first_turn_player_index is not None:
                self.current_player_index = self.first_turn_player_index
            else:
                # Default: attacker goes first
                self.current_player_index = self.attacker_index if self.attacker_index is not None else 0
            
            # Set the battle round starting player to whoever goes first
            self.battle_round_starting_player_index = self.current_player_index
            self.phase = BattleRoundPhases.COMMAND_PHASE

            # Show detailed first turn information
            first_turn_player = self.get_current_player()
            if self.first_turn_player_index == self.attacker_index:
                role = "Attacker"
            elif self.first_turn_player_index == self.defender_index:
                role = "Defender"
            else:
                role = "Player"

            print(f"🎉 Setup complete! {first_turn_player.name} ({role}) goes first")
            return True
        else:
            self.setup_phase = SetupPhase(next_phase_value)
            print(f"📋 Advanced to setup phase: {self.setup_phase.name}")
            return False

    def execute_muster_armies_phase(self, player1_army_file: str = None, player2_army_file: str = None) -> None:
        """Phase 1: Muster Armies - Load army lists for both players."""
        print("📋 MUSTER ARMIES: Loading army lists...")
        
        # Use army files from game.army_files if not provided as parameters
        if player1_army_file is None:
            player1_army_file = getattr(self, 'army_files', {}).get('player1', 'army_lists/warhammer_app_dump.txt')
        if player2_army_file is None:
            player2_army_file = getattr(self, 'army_files', {}).get('player2', 'army_lists/chaos_daemons_GT2023.txt')
        
        # Validate army files exist
        import os
        if not os.path.exists(player1_army_file):
            raise FileNotFoundError(f"Player 1 army file not found: {player1_army_file}")
        if not os.path.exists(player2_army_file):
            raise FileNotFoundError(f"Player 2 army file not found: {player2_army_file}")
        
        # Load armies for both players
        from ..classes.army import parse_army_list
        from ..waha_helper import WahaHelper

        waha_helper = WahaHelper()
        
        if len(self.players) >= 2:
            # Load army for Player 1
            player1_army = parse_army_list(player1_army_file, waha_helper)
            self.players[0].set_army(player1_army)
            
            # Load army for Player 2  
            player2_army = parse_army_list(player2_army_file, waha_helper)
            self.players[1].set_army(player2_army)
            
            player1_units = len(self.players[0].get_army().units)
            player2_units = len(self.players[1].get_army().units)
            print(f"✅ {self.players[0].name}: {player1_units} units loaded from {player1_army_file}")
            print(f"✅ {self.players[1].name}: {player2_units} units loaded from {player2_army_file}")
        else:
            print("⚠️ Not enough players loaded")
    
    def execute_select_mission_objectives_phase(self) -> None:
        """Phase 2: Select Mission Objectives - Choose mission and objectives."""
        print("📋 SELECT MISSION OBJECTIVES: Setting up mission...")
        
        # Set up available commands for high-level strategy
        self.commands = ["attack", "defend", "move"]
        print(f"✅ Commands configured: {self.commands}")
        
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
            print(f"✅ Using default mission: {self.selected_mission_info}")
        else:
            print(f"✅ Mission selected: {self.selected_mission_info}")
        
        # Mission objectives will be placed during CREATE_BATTLEFIELD phase
        print("✅ Mission framework configured")
    
    def execute_create_battlefield_phase(self, mission_name: str = None) -> None:
        """Phase 3: Create Battlefield - Set up map, terrain, deployment zones, and objectives."""
        print("📋 CREATE BATTLEFIELD: Setting up battlefield...")
        
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
        print(f"✅ Map created: {battlefield_width}\" x {battlefield_height}\"")
        
        # 2. Terrain features will be added later based on A-T mission terrain layouts
        print(f"✅ Terrain layout {terrain_layout} noted (terrain placement to be implemented)")
        
        # 3. Set up mission-based deployment zones and objectives
        from .deployment import DeploymentManager
        deployment_manager = DeploymentManager(self, deployment_mission)
        
        # Set up deployment zones for the mission
        mission_zones = deployment_manager.create_deployment_zones()
        
        # Convert to the format expected by the game for visualization
        self.deployment_zones = {}
        for zone in mission_zones:
            if zone['zone_type'] == 'defender':
                # Assign to first player as defender (will be properly assigned later)
                self.deployment_zones[self.players[0].name] = zone
            elif zone['zone_type'] == 'attacker':
                # Assign to second player as attacker
                self.deployment_zones[self.players[1].name] = zone
        
        print(f"✅ Mission deployment zones created: {deployment_mission}")
        
        # 4. Set up mission objectives
        deployment_manager.setup_mission_objectives()
        print(f"✅ Mission objectives placed: {len(self.objectives)} objectives")
        print(f"✅ Primary Mission: {primary_mission}")
    
    def execute_determine_attacker_defender_phase(self) -> None:
        """Phase 4: Determine Attacker and Defender - Roll off to determine roles."""
        print("📋 DETERMINE ATTACKER AND DEFENDER: Rolling off...")
        
        import random
        from ..utility.dice import get_roll
        
        player1_roll = get_roll("1D6")
        player2_roll = get_roll("1D6")
        
        print(f"🎲 {self.players[0].name} rolled: {player1_roll}")
        print(f"🎲 {self.players[1].name} rolled: {player2_roll}")
        
        if player1_roll > player2_roll:
            self.attacker_index = 0
            self.defender_index = 1
            print(f"⚔️ {self.players[0].name} is the Attacker")
            print(f"🛡️ {self.players[1].name} is the Defender")
        elif player2_roll > player1_roll:
            self.attacker_index = 1
            self.defender_index = 0
            print(f"⚔️ {self.players[1].name} is the Attacker")
            print(f"🛡️ {self.players[0].name} is the Defender")
        else:
            # Tie - re-roll
            print("🎲 Tie! Re-rolling...")
            return self.execute_determine_attacker_defender_phase()
        
        # Set deployment turn to defender (defender deploys first)
        self.deployment_turn_index = self.defender_index
    
    def execute_declare_battle_formations_phase(self) -> None:
        """Phase 5: Declare Battle Formations - Attach leaders, declare reserves, etc."""
        print("📋 DECLARE BATTLE FORMATIONS: Configuring formations...")
        # For now, this is empty - battle formations will be implemented later
        print("✅ Battle formations declared")
    
    def execute_deploy_armies_phase(self, manual_phases: bool = False, decision_makers: dict = None) -> None:
        """Phase 6: Deploy Armies - Execute the deployment phase."""
        print("📋 DEPLOY ARMIES: Starting deployment sequence...")
        
        # Check if we have human players that need UI-based deployment
        has_human_players = any(player.type.name == 'HUMAN' for player in self.players)
        
        if has_human_players and manual_phases:
            # For human players in manual mode, set up deployment state but don't auto-deploy
            # The UI will handle the actual deployment decisions
            print("👤 Human deployment mode - use UI to deploy units")
            
            # Set up deployment zones if not already done
            if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
                battlefield_width, battlefield_height = self.get_battlefield_size()
                deployment_depth = 18.0
                self.deployment_zones = {
                    self.players[0].name: {
                        'x_range': (0, deployment_depth),
                        'y_range': (0, battlefield_height)
                    },
                    self.players[1].name: {
                        'x_range': (battlefield_width - deployment_depth, battlefield_width),
                        'y_range': (0, battlefield_height)
                    }
                }
            
            # Initialize deployment tracking
            if not hasattr(self, 'deployment_turn_index'):
                self.deployment_turn_index = getattr(self, 'defender_index', 0)
            
            # Mark that we're in deployment phase
            self.waiting_for_deployment_input = False
            print("✅ Deployment phase initialized - deploy units through UI")
        
        elif decision_makers:
            # Use the proper deployment manager with decision makers for AI vs AI
            from .deployment import DeploymentManager
            deployment_manager = DeploymentManager(self)
            deployment_results = deployment_manager.execute_deployment_sequence(decision_makers)
            
            # Store deployment results for reference
            self.deployment_results = deployment_results
            print("✅ Army deployment complete")
        else:
            # Use the existing complete_deployment_phase method for fallback
            self.complete_deployment_phase(manual_phases=manual_phases)
            
            # Only print completion message if not waiting for manual input
            if not getattr(self, 'waiting_for_deployment_input', False):
                print("✅ Army deployment complete")
    
    def execute_determine_first_turn_order_phase(self) -> None:
        """Phase 7: Determine First Turn Order - Attacker rolls to see who goes first."""
        print("📋 DETERMINE FIRST TURN ORDER: Rolling for first turn...")
        
        from ..utility.dice import get_roll
        
        attacker = self.get_attacker()
        defender = self.get_defender()
        
        # Attacker rolls 1D6
        attacker_roll = get_roll("1D6")
        print(f"🎲 {attacker.name} (Attacker) rolled: {attacker_roll}")
        
        if attacker_roll >= 4:
            # Attacker chooses who goes first
            self.first_turn_player_index = self.attacker_index  # For simplicity, attacker chooses themselves
            print(f"✅ {attacker.name} goes first! (Attacker rolled {attacker_roll}, needed 4+)")
        else:
            # Defender goes first
            self.first_turn_player_index = self.defender_index
            print(f"✅ {defender.name} goes first! (Attacker rolled {attacker_roll}, needed 4+)")
        
        # Clear deployment actions since deployment phase is now complete
        self.clear_deployment_actions()
    
    def execute_resolve_prebattle_rules_phase(self) -> None:
        """Phase 8: Resolve Pre-battle Rules - Resolve any pre-battle rules, abilities, or stratagems."""
        print("📋 RESOLVE PREBATTLE RULES: Resolving pre-battle rules...")
        
        # Handle Scout moves for all players
        self._handle_scout_moves()

        # TODO - other pre-battle rules (e.g., Detachment stuff like WE dice rolls, etc.)
        
        print("✅ Pre-battle rules resolved")
    
    def _handle_scout_moves(self) -> None:
        """Handle scout moves for all players during pre-battle rules phase."""
        print("🔍 Processing Scout moves...")
        
        # Get all units with Scout ability from both players
        scout_units = []
        for player in self.players:
            if player.get_army():
                for unit in player.get_army().units:
                    has_scout, scout_distance = unit.has_scout()
                    if has_scout and unit.deployed and unit.reserve_status == 'deployed':
                        scout_units.append((player, unit, scout_distance))
        
        if not scout_units:
            print("✅ No units with Scout ability found")
            return
        
        print(f"🔍 Found {len(scout_units)} units with Scout ability")
        
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
        
        # Check if we have human players that need UI-based scout moves
        has_human_players = any(player.type.name == 'HUMAN' for player in self.players)
        
        if has_human_players:
            # For human players, let the UI handle scout moves
            # The PreBattlePhaseHandler will manage the scout move sequence
            print("👤 Human scout moves will be handled by UI")
            print("✅ Scout phase initialized - use UI to make scout moves")
        else:
            # For AI-only games, auto-skip scout moves for now
            # In the future, this could integrate with AI decision making
            for player in players_in_order:
                if player in scout_units_by_player:
                    print(f"🔍 {player.name}'s Scout moves:")
                    for unit, scout_distance in scout_units_by_player[player]:
                        print(f"  - {unit.name} (Scout {scout_distance}\")")
                        print(f"    Skipping scout move (auto-skip for AI)")
                        unit.scout_move_made = True  # Mark as skipped
            
            print("✅ Scout moves processed (auto-skipped for AI)")
    
    def execute_current_setup_phase(self, **kwargs) -> None:
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
            self.execute_deploy_armies_phase(
                manual_phases=kwargs.get('manual_phases', False),
                decision_makers=kwargs.get('decision_makers')
            )
        elif self.setup_phase == SetupPhase.DETERMINE_FIRST_TURN_ORDER:
            self.execute_determine_first_turn_order_phase()
        elif self.setup_phase == SetupPhase.RESOLVE_PREBATTLE_RULES:
            self.execute_resolve_prebattle_rules_phase()
