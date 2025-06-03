from typing import List, Dict, Any, Optional, Tuple
from enum import Enum, auto
from .event_system import EventSystem
from .map import Map, Objective, ObstacleType
from .player import Player
from .unit import Unit
from ..utility.constants import TOTAL_ROUNDS
from shapely.geometry import LineString
from ..utility.calcs import get_dist, get_roll, can_traverse_freely

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
            "PointLimit": 500,
            "CommandPoints": 6,
            "DetachmentLimit": 1,
            "Width": 44,
            "Height": 30,
        },
        BattlefieldSize.INCURSION: {
            "PointLimit": 1000,
            "CommandPoints": 6,
            "DetachmentLimit": 1,
            "Width": 44,
            "Height": 30,
        },
        BattlefieldSize.STRIKE_FORCE: {
            "PointLimit": 2000,
            "CommandPoints": 6,
            "DetachmentLimit": 1,
            "Width": 44,
            "Height": 60,
        },
        BattlefieldSize.ONSLAUGHT: {
            "PointLimit": 3000,
            "CommandPoints": 6,
            "DetachmentLimit": 1,
            "Width": 44,
            "Height": 90,
        },
    }

    def __init__(self, size: BattlefieldSize = None, width: int = None, height: int = None):
        if size is not None:
            self.config = self.SIZES[size]
        elif width is not None and height is not None:
            self.config = {
                "Width": width,
                "Height": height,
                "PointLimit": 2000,  # Default values, adjust as needed
                "CommandPoints": 6,
                "DetachmentLimit": 1,
            }
        else:
            raise ValueError("Either 'size' or both 'width' and 'height' must be provided")

    def __str__(self):
        ret = f"{self.config}"
        return ret


class Game:
    def __init__(self, battlefield: Battlefield, players: List[Player] = []):
        self.battlefield = battlefield
        self.players = players
        self.turn = 1
        self.current_player_index = 0
        self.map = Map(battlefield.config["Width"], battlefield.config["Height"])
        self.event_system = EventSystem()
        self.objectives = []
        self.commands = []

    def add_player(self, player: Player) -> None:
        player.command_points = self.battlefield.config["CommandPoints"]
        print(f"Player {player.name} added with {player.command_points} command points and army: {player.army}")
        self.players.append(player)

    def add_objective(self, objective: Objective) -> None:
        self.objectives.append(objective)

    def add_command(self, command: str) -> None:
        self.commands.append(command)

    def get_current_player(self) -> Player:
        player = self.players[self.current_player_index]
        return player

    def get_opponent(self) -> Player:
        opponent_index = (self.current_player_index + 1) % len(self.players)
        return self.players[opponent_index]

    def get_battlefield_size(self) -> tuple[int, int]:
        return (self.battlefield.config["Height"], self.battlefield.config["Width"])

    def next_turn(self):
        if self.is_fight_phase():
            if self.current_player_index == 1:
                self.turn += 1
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
            self.phase = BattleRoundPhases.COMMAND_PHASE
        else:
            self.phase = BattleRoundPhases(self.phase.value + 1)

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

    def get_distance_between_units(self, unit1: 'Unit', unit2: 'Unit') -> float:
        """Calculate the shortest distance between two units."""
        shortest_distance = float('inf')
        
        # Check distance between each model pair
        for model1 in unit1.models:
            for model2 in unit2.models:
                distance = model1.edge_to_edge_distance(model2)
                shortest_distance = min(shortest_distance, distance)
                
        return shortest_distance

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
