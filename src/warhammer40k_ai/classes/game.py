from typing import List, Dict, Any
from enum import Enum
from .event_system import EventSystem
from .map import Objective
from .player import Player


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
        self.do_ai_action = False
        self.map = None
        self.objectives: List[Objective] = []

    def add_player(self, player: Player) -> None:
        player.command_points = self.starting_command_points_per_player
        print(f"Player {player.name} added with {player.command_points} command points and army: {player.army}")
        self.players.append(player)

    def add_objective(self, objective: Objective) -> None:
        self.objectives.append(objective)

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
        # Implement game-over conditions
        # For example, check if only one player has units left
        if sum(1 for player in self.players if player.has_units()) <= 1:
            return True
        if self.turn > 5:
            return True
        return False

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
