from typing import List, Dict, Any, Optional, Tuple
from enum import Enum, auto
from dataclasses import dataclass
import logging
from .event_system import EventSystem
from .map import Map, Objective
from .player import Player
from .unit import Unit
from .model import Model
from ..utility.calcs import get_dist
from ..utility.dice import get_roll
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
        """Auto-deploy a unit at a random valid position within deployment constraints."""
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
                x_min, x_max = zone['x_range']
                y_min, y_max = zone['y_range']
                
                # Add buffer for unit base size (use largest possible base as safety margin)
                base_buffer = 2.0  # 2 inch buffer for safety
                search_zones = [(
                    max(x_min + base_buffer, 0), 
                    min(x_max - base_buffer, battlefield_width),
                    max(y_min + base_buffer, 0), 
                    min(y_max - base_buffer, battlefield_height)
                )]
            else:
                logger.error(f"No deployment zone found for {player_name}")
                return False
        
        # Try to find a valid position within search zones
        for zone_idx, zone in enumerate(search_zones):
            x_min, x_max, y_min, y_max = zone
            
            if x_max <= x_min or y_max <= y_min:
                continue  # Skip invalid zones
            
            for attempt in range(25):  # 25 attempts per zone
                x = random.uniform(x_min, x_max)
                y = random.uniform(y_min, y_max)
                z = 0.0
                
                # Check if this position would place all models wholly within the deployment zone
                if self.is_valid_deployment_position(unit, x, y, player_name):
                    # Use the proper deployment flow
                    if self._deploy_unit_at_position(unit, x, y, z):
                        print(f"✅ Successfully auto-deployed {unit.name} at ({x:.1f}, {y:.1f})")
                        return True
        
        print(f"❌ Failed to auto-deploy {unit.name}")
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
            # Calculate model positions (this is the same as manual deployment)
            model_positions = unit.calculate_model_positions(x, y, self.map)
            
            if not model_positions:
                return False
            
            # Set individual model locations (same as manual)
            for model, position in zip(unit.models, model_positions):
                model_x, model_y, model_z, model_facing = position
                model.set_location(model_x, model_y, model_z, model_facing)
            
            # Calculate unit centroid position (same as manual)
            unit_x = sum(pos[0] for pos in model_positions) / len(model_positions)
            unit_y = sum(pos[1] for pos in model_positions) / len(model_positions)
            unit.set_position(unit_x, unit_y, z)
            
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
            return True  # If no deployment zones defined, allow anywhere
        
        if player_name not in self.deployment_zones:
            return False
        
        zone = self.deployment_zones[player_name]
        x_min, x_max = zone['x_range']
        y_min, y_max = zone['y_range']
        
        return x_min <= x <= x_max and y_min <= y <= y_max

    def is_model_wholly_in_deployment_zone(self, model: 'Model', player_name: str) -> bool:
        """Check if a model's entire base is wholly within a player's deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return True  # If no deployment zones defined, allow anywhere
        
        if player_name not in self.deployment_zones:
            return False
        
        zone = self.deployment_zones[player_name]
        x_min, x_max = zone['x_range']
        y_min, y_max = zone['y_range']
        
        # Get model position and base size
        model_x, model_y = model.get_location()[:2]
        base = model.model_base
        base_radius = base.get_radius()
        
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

    def is_position_wholly_in_deployment_zone(self, x: float, y: float, base, player_name: str) -> bool:
        """Check if a position with the given base would be wholly within the deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return True  # If no deployment zones defined, allow anywhere
        
        if player_name not in self.deployment_zones:
            return False
        
        zone = self.deployment_zones[player_name]
        x_min, x_max = zone['x_range']
        y_min, y_max = zone['y_range']
        
        base_radius = base.get_radius()
        
        # For circular bases, check that center +/- radius is within zone
        if base.base_type.name == 'CIRCULAR':
            return (x_min <= x - base_radius and 
                    x + base_radius <= x_max and
                    y_min <= y - base_radius and 
                    y + base_radius <= y_max)
        
        # For elliptical bases, use the major axis as the effective radius
        elif base.base_type.name == 'ELLIPTICAL':
            major_radius = max(base.radius) if isinstance(base.radius, tuple) else base.radius
            return (x_min <= x - major_radius and 
                    x + major_radius <= x_max and
                    y_min <= y - major_radius and 
                    y + major_radius <= y_max)
        
        # For hull bases, use a rectangular approximation
        elif base.base_type.name == 'HULL':
            length, width = base.radius if isinstance(base.radius, tuple) else (base.radius, base.radius)
            return (x_min <= x - length and 
                    x + length <= x_max and
                    y_min <= y - width and 
                    y + width <= y_max)
        
        # Default: treat as circular with radius
        else:
            return (x_min <= x - base_radius and 
                    x + base_radius <= x_max and
                    y_min <= y - base_radius and 
                    y + base_radius <= y_max)

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
            if zone_player_name != player_name:
                x_min, x_max = zone['x_range']
                y_min, y_max = zone['y_range']
                
                # Calculate distance to the closest edge of the zone
                if x < x_min:
                    closest_x = x_min
                elif x > x_max:
                    closest_x = x_max
                else:
                    closest_x = x
                
                if y < y_min:
                    closest_y = y_min
                elif y > y_max:
                    closest_y = y_max
                else:
                    closest_y = y
                
                distance = ((x - closest_x) ** 2 + (y - closest_y) ** 2) ** 0.5
                min_distance = min(min_distance, distance)
        
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

    def is_valid_deployment_position(self, unit: 'Unit', x: float, y: float, player_name: str) -> bool:
        """Check if a position is valid for deploying a unit during deployment phase."""
        # Units in reserves don't need position validation
        if unit.reserve_status in ['reserves', 'strategic_reserves']:
            return True
        
        # Temporarily position the unit to check if the proposed position is valid
        # We need to calculate where each model would be positioned
        unit.calculate_model_positions(x, y, self.map)  # This sets relative positions
        
        # Check if unit has Infiltrate ability
        if unit.has_infiltrate():
            # Infiltrate units can deploy anywhere except:
            # 1. Inside enemy deployment zone
            # 2. Within 9" of enemy deployment zone
            # 3. Within 9" of enemy models
            
            # For infiltrate units, we need to check each model's base at the proposed position
            # Calculate model positions using the same logic as unit deployment
            model_positions = unit.calculate_model_positions(x, y, self.map)
            
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
            model_positions = unit.calculate_model_positions(x, y, self.map)
            
            if not model_positions:
                return False
                
            for model, position in zip(unit.models, model_positions):
                model_x, model_y = position[0], position[1]
                
                # Check if this model would be wholly within the deployment zone
                if not self.is_position_wholly_in_deployment_zone(model_x, model_y, model.model_base, player_name):
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
            # Reset round state for all units
            for player in self.players:
                for unit in player.get_army().units:
                    unit.initialize_round()
            # Reset phase to COMMAND_PHASE at the start of a new turn
            self.phase = BattleRoundPhases.COMMAND_PHASE

    def next_phase(self):
        """Advance to the next phase."""
        current_phase_value = self.phase.value
        next_phase_value = (current_phase_value + 1) % len(BattleRoundPhases)
        self.phase = BattleRoundPhases(next_phase_value)
        
        # Reset movement tracking when entering Movement Phase
        if self.phase == BattleRoundPhases.MOVEMENT_PHASE:
            current_player = self.get_current_player()
            for unit in current_player.get_army().units:
                if hasattr(unit.round_state, 'moved_this_round'):
                    unit.round_state.moved_this_round = False
        
        if next_phase_value == 0:  # If we've wrapped around to COMMAND_PHASE
            # This means we've finished all phases for the current player
            # Switch to the next player
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
            
            # Track who started this battle round if not already set
            if self.battle_round_starting_player_index is None:
                # This is the first player switch of the game - the previous player started the round
                self.battle_round_starting_player_index = (self.current_player_index - 1) % len(self.players)
            
            # Check if we've completed a full battle round (both players have had their turn)
            if self.current_player_index == self.battle_round_starting_player_index:
                # We've cycled back to the player who started this battle round
                self.turn += 1
                self.battle_round_starting_player_index = self.current_player_index  # This player starts the next round
                # Reset round state for all units at the start of a new turn
                for player in self.players:
                    for unit in player.get_army().units:
                        unit.initialize_round()

    def is_command_phase(self) -> bool:
        return self.phase == BattleRoundPhases.COMMAND_PHASE
    
    def start_command_phase(self) -> None:
        """Start the command phase - all players gain 1 Command Point"""
        for player in self.players:
            player.gain_command_point()

    def is_movement_phase(self) -> bool:
        return self.phase == BattleRoundPhases.MOVEMENT_PHASE

    def is_shooting_phase(self) -> bool:
        return self.phase == BattleRoundPhases.SHOOTING_PHASE

    def is_charge_phase(self) -> bool:
        return self.phase == BattleRoundPhases.CHARGE_PHASE

    def is_fight_phase(self) -> bool:
        return self.phase == BattleRoundPhases.FIGHT_PHASE

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
        """Attempt a charge move with the given unit against the target."""
        if not charging_unit.can_declare_charge_against(target_unit, self):
            return False

        # Calculate charge distance needed
        current_pos = charging_unit.get_position()
        target_pos = target_unit.get_position()
        dx = target_pos[0] - current_pos[0]
        dy = target_pos[1] - current_pos[1]
        distance = get_dist(dx, dy)

        # Roll 2D6 for charge distance
        charge_roll = get_roll("2D6")
        if charge_roll < distance:
            return False

        # Calculate the actual movement vector
        scale = charge_roll / distance
        new_x = current_pos[0] + dx * scale
        new_y = current_pos[1] + dy * scale
        new_z = self.map.get_height_at_point(new_x, new_y)
        
        # Move the unit
        charging_unit.move((new_x, new_y, new_z), self.map)
        charging_unit.round_state.declared_charge_this_round = True
        return True

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
                
            enemy_pos = enemy_unit.get_position()
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
                if unit.arrive_from_reserves(valid_position, self.turn):
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
            print(f"🎉 Setup complete! {self.get_current_player().name} goes first")
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
        
        # Mission objectives will be placed during CREATE_BATTLEFIELD phase
        print("✅ Mission framework configured")
    
    def execute_create_battlefield_phase(self) -> None:
        """Phase 3: Create Battlefield - Set up map, terrain, deployment zones, and objectives."""
        print("📋 CREATE BATTLEFIELD: Setting up battlefield...")
        
        # 1. Create the Map (already done in __init__)
        battlefield_width, battlefield_height = self.get_battlefield_size()
        print(f"✅ Map created: {battlefield_width}\" x {battlefield_height}\"")
        
        # 2. Add terrain (obstacles)
        from .map import Obstacle, ObstacleType
        obstacles = [
            Obstacle(vertices=[(3, 3), (3, 5), (5, 5), (5, 3)], terrain_type=ObstacleType.CRATER_AND_RUBBLE, height=3.0),
            Obstacle(vertices=[(20, 7), (27, 9), (29, 9), (29, 7)], terrain_type=ObstacleType.DEBRIS_AND_STATUARY, height=6.0)
        ]
        self.map.add_obstacles(obstacles)
        print(f"✅ Terrain added: {len(obstacles)} obstacles")
        
        # 3. Add deployment zones (18" from edges for Strike Force)
        deployment_depth = 18.0  # 18 inches from edge
        self.deployment_zones = {
            self.players[0].name: {
                'x_range': (0, deployment_depth),  # Left edge to 18" in
                'y_range': (0, battlefield_height)  # Full height
            },
            self.players[1].name: {
                'x_range': (battlefield_width - deployment_depth, battlefield_width),  # 18" from right edge to edge
                'y_range': (0, battlefield_height)  # Full height
            }
        }
        print(f"✅ Deployment zones created: 18\" depth zones")
        
        # 4. Add objectives
        import random
        from .map import ObjectivePoint
        center_x = battlefield_width / 2.0
        center_y = battlefield_height / 2.0
        # Add some randomization to prevent predictable positioning
        random_offset_x = random.uniform(-3, 3)
        random_offset_y = random.uniform(-3, 3)
        objective_x = center_x + random_offset_x
        objective_y = center_y + random_offset_y
        
        objective_point = ObjectivePoint(objective_x, objective_y, 0, 3.0)
        from .map import Objective, ObjectiveCategory
        objectives = [
            Objective(name="Capture Central Point", location=objective_point, category=ObjectiveCategory.PRIMARY, points=10, 
                      description="Capture the central point to gain control of the battlefield.", 
                      conditions=lambda game: objective_point.controlling_player == game.get_current_player())
        ]
        self.map.add_objectives(objectives)
        self.objectives = objectives  # Store for game access
        print(f"✅ Objectives placed: {len(objectives)} objectives")
    
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
            print(f"✅ {attacker.name} goes first!")
        else:
            # Defender goes first
            self.first_turn_player_index = self.defender_index
            print(f"✅ {defender.name} goes first!")
        
        # Clear deployment actions since deployment phase is now complete
        self.clear_deployment_actions()
    
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
