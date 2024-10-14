from typing import List, Dict, Any
from .unit import Unit
from .player import Player
from enum import Enum
from .event_system import EventSystem


# Constants
ENGAGEMENT_RANGE = 3  # inches

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

    def __init__(self, size: BattlefieldSize):
        self.config = self.SIZES[size]

    def __str__(self):
        ret = f"{self.config}"
        return ret


class Game:
    def __init__(self, battlefield: Battlefield, players: List[Player] = []):
        self.battlefield_size = (battlefield.config["Height"], battlefield.config["Width"])
        self.battle_point_limit = battlefield.config["PointLimit"]
        self.starting_command_points_per_player = battlefield.config["CommandPoints"]
        self.detachment_limit_per_player = battlefield.config["DetachmentLimit"]
        self.current_player_index = 0
        self.turn = 1
        self.phase = BattleRoundPhases.COMMAND_PHASE
        self.battlefield = self._initialize_battlefield()
        self.players: List[Player] = players
        self.event_system = EventSystem()
        self.map = None

    def add_player(self, player: Player):
        player.command_points = self.starting_command_points_per_player
        print(f"Player {player.name} added with {player.command_points} command points and army: {player.army}")
        self.players.append(player)

    def _initialize_battlefield(self) -> List[List[Any]]:
        # Initialize an empty battlefield based on battlefield_size
        return [[None for _ in range(self.battlefield_size[1])] for _ in range(self.battlefield_size[0])]

    def get_current_player(self) -> Player:
        player = self.players[self.current_player_index]
        return player

    def get_battlefield_size(self) -> tuple[int, int]:
        return self.battlefield_size

    def next_turn(self):
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        if self.current_player_index == 0:
            if self.phase == BattleRoundPhases.FIGHT_PHASE:
                self.turn += 1
                self.phase = BattleRoundPhases.COMMAND_PHASE
            else:
                self.phase = BattleRoundPhases(self.phase.value + 1)

    def is_movement_phase(self) -> bool:
        return self.phase == BattleRoundPhases.MOVEMENT_PHASE

    def is_shooting_phase(self) -> bool:
        return self.phase == BattleRoundPhases.SHOOTING_PHASE

    def is_charge_phase(self) -> bool:
        return self.phase == BattleRoundPhases.CHARGE_PHASE

    def is_fight_phase(self) -> bool:
        return self.phase == BattleRoundPhases.FIGHT_PHASE

    def place_unit(self, unit: Unit, position: tuple[int, int]):
        # Place a unit on the battlefield
        x, y = position
        if 0 <= x < self.battlefield_size[0] and 0 <= y < self.battlefield_size[1]:
            self.battlefield[x][y] = unit
        else:
            raise ValueError("Invalid position")

    def get_unit_at(self, position: tuple[int, int]) -> Unit | None:
        # Get the unit at a specific position
        x, y = position
        if 0 <= x < self.battlefield_size[0] and 0 <= y < self.battlefield_size[1]:
            return self.battlefield[x][y]
        else:
            raise ValueError("Invalid position")

    def move_unit(self, from_pos: tuple[int, int], to_pos: tuple[int, int]):
        # Move a unit from one position to another
        unit = self.get_unit_at(from_pos)
        if unit:
            self.place_unit(unit, to_pos)
            self.battlefield[from_pos[0]][from_pos[1]] = None
        else:
            raise ValueError("No unit at the given position")

    def is_game_over(self) -> bool:
        # Implement game-over conditions
        # For example, check if only one player has units left
        return sum(1 for player in self.players if player.has_units()) <= 1

    def get_winner(self) -> Player | None:
        # Return the winning player or None if the game is not over
        if self.is_game_over():
            return next((player for player in self.players if player.has_units()), None)
        return None

    def get_state(self) -> Dict[str, Any]:
        # Return the current game state as a dictionary
        return {
            "players": self.players,
            "battlefield": self.battlefield,
            "map": self.map,
            "current_player": self.get_current_player(),
            "turn": self.turn,
            "phase": self.phase,
        }

    def do_phase_action(self):
        player = self.get_current_player()
        if self.phase == BattleRoundPhases.COMMAND_PHASE:
            self.event_system.publish("command_phase_start", game_state=self.get_state())
        elif self.phase == BattleRoundPhases.MOVEMENT_PHASE:
            for unit in player.get_army().units:
                if unit.deployed:
                    self.event_system.publish("unit_move_start", unit=unit, game_state=self.get_state())
                    unit.do_move_action(self.map)
                    self.event_system.publish("unit_move_end", unit=unit, game_state=self.get_state())
                else:
                    print(f"Unit {unit.name} is not deployed")
        elif self.phase == BattleRoundPhases.SHOOTING_PHASE:
            self.event_system.publish("shooting_phase_start", game_state=self.get_state())
        elif self.phase == BattleRoundPhases.CHARGE_PHASE:
            self.event_system.publish("charge_phase_start", game_state=self.get_state())
        elif self.phase == BattleRoundPhases.FIGHT_PHASE:
            self.event_system.publish("fight_phase_start", game_state=self.get_state())
