from typing import List, Dict, Any, Optional, Tuple
from enum import Enum, auto
from dataclasses import dataclass
import logging
from .event_system import EventSystem
from .map import Map, Objective
from .player import Player
from .unit import Unit
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
        
        # Deployment tracking
        self.deployment_turn_index = 0  # Track whose turn it is to deploy (0 = defender, 1 = attacker)
        self.attacker_index = 0  # Index of the attacking player (will be set during setup)
        self.defender_index = 1  # Index of the defending player (will be set during setup)
        self.deployment_zones = {}  # Store deployment zones for visualization {player_name: zone_dict}

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
        """Set which player is the attacker and which is the defender."""
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
    
    def complete_deployment_phase(self) -> None:
        """Force complete the deployment phase by auto-deploying remaining units."""
        for player in self.players:
            army = player.get_army()
            if army:
                # Only auto-deploy units that are meant to be deployed to battlefield
                # (not units in reserves or strategic reserves)
                undeployed_units = [u for u in army.units 
                                  if not u.deployed and u.reserve_status == 'deployed']
                for unit in undeployed_units:
                    # Auto-deploy at a random valid position
                    self.auto_deploy_unit(unit)
    
    def auto_deploy_unit(self, unit: 'Unit') -> bool:
        """Auto-deploy a unit at a random valid position."""
        import random
        
        # Try to find a valid deployment position
        battlefield_width, battlefield_height = self.get_battlefield_size()
        
        # Try random positions within the deployment zone
        for _ in range(50):  # Max 50 attempts
            x = random.uniform(5, battlefield_width - 5)
            y = random.uniform(5, battlefield_height - 5)
            z = 0.0
            
            # Simple validation - just check if position is within bounds
            if 0 < x < battlefield_width and 0 < y < battlefield_height:
                # Use the proper deployment flow like manual deployment
                if self._deploy_unit_at_position(unit, x, y, z):
                    logger.info(f"Auto-deployed {unit.name} at ({x:.1f}, {y:.1f})")
                    return True
        
        # If we can't find a valid position, just place it anyway
        x = random.uniform(10, battlefield_width - 10)
        y = random.uniform(10, battlefield_height - 10)
        
        # Use the proper deployment flow like manual deployment
        if self._deploy_unit_at_position(unit, x, y, 0.0):
            logger.info(f"Force-deployed {unit.name} at ({x:.1f}, {y:.1f})")
            return True
        else:
            logger.error(f"Failed to deploy {unit.name} at ({x:.1f}, {y:.1f})")
            return False

    def _deploy_unit_at_position(self, unit: 'Unit', x: float, y: float, z: float) -> bool:
        """Deploy a unit at the specified position using the proper deployment flow."""
        try:
            # Calculate model positions (this is the same as manual deployment)
            model_positions = unit.calculate_model_positions(x, y, self.map, 1.0, [])
            
            if not model_positions:
                logger.warning(f"Could not calculate model positions for {unit.name}")
                return False
            
            # Set individual model locations
            for model, position in zip(unit.models, model_positions):
                model_x, model_y, model_z, model_facing = position
                model.set_location(model_x, model_y, model_z, model_facing)
            
            # Calculate unit centroid position
            unit_x = sum(pos[0] for pos in model_positions) / len(model_positions)
            unit_y = sum(pos[1] for pos in model_positions) / len(model_positions)
            unit.set_position(unit_x, unit_y, z)
            
            # CRITICAL: Register unit with the game map (this makes it appear on battlefield)
            if self.map and self.map.place_unit(unit):
                unit.deployed = True
                return True
            else:
                logger.warning(f"Failed to place {unit.name} on game map")
                return False
                
        except Exception as e:
            logger.error(f"Error deploying {unit.name}: {e}")
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
        
        if next_phase_value == 0:  # If we've wrapped around to COMMAND_PHASE
            # This means we've finished all phases for the current player
            # Switch to the next player
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
            
            # If we've gone through all players, start a new turn
            if self.current_player_index == 0:
                self.turn += 1
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
            # This is a simple fallback - should be improved with proper AI integration
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
