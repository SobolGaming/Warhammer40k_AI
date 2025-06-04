from typing import List, Dict, Any, Optional, Tuple
from enum import Enum, auto
from dataclasses import dataclass
from .event_system import EventSystem
from .map import Map, Objective
from .player import Player
from .unit import Unit
from ..utility.calcs import get_dist
from ..utility.dice import get_roll
from ..utility.constants import TOTAL_ROUNDS

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
        """Advance to the next turn."""
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
            self.next_turn()

    def is_command_phase(self) -> bool:
        return self.phase == BattleRoundPhases.COMMAND_PHASE

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
