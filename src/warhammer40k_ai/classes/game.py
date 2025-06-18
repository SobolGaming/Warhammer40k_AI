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
