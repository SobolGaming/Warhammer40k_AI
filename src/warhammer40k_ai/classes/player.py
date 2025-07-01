# This is the player that gets put onto a Battlefield and has an Army

import logging
from enum import Enum, auto
from .army import Army
from .unit import Unit
from warhammer40k_ai.classes.map import Objective
from warhammer40k_ai.utility.calcs import get_dist

logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


class PlayerType(Enum):
    AI = auto()
    HUMAN = auto()
    RANDOM = auto()
    NULL = auto()


class Player:
    def __init__(self, name: str, player_type: PlayerType = PlayerType.NULL, army: Army = None):
        self.name = name
        if player_type not in (PlayerType.AI, PlayerType.HUMAN):
            raise ValueError(f"Invalid player type: {player_type}")
        self.type = player_type
        self.round: int = 0
        self.command_points: int = 0  # Players start with 0 Command Points in 10th edition
        self.army: Army = army
        self.score: int = 0
        # Set the player reference on the army
        if self.army:
            self.army.set_player(self)
        #print(f"Player {self.name} created with army: {self.army}")
    
    def set_army(self, army: Army) -> None:
        self.army = army
        army.set_player(self)

    def set_game(self, game) -> None:
        """Set the game reference for this player."""
        self.game = game

    def get_army(self) -> Army | None:
        return self.army

    def has_unit(self, unit: Unit) -> bool:
        return unit in self.army.units

    def has_units(self) -> bool:
        return len(self.army.units) > 0

    def get_score(self) -> int:
        return self.score

    def add_score(self, points: int) -> None:
        self.score += points
    
    def gain_command_point(self) -> None:
        """Gain a command point (typically done at the start of each turn)"""
        self.command_points += 1
    
    def spend_command_points(self, amount: int) -> bool:
        """Spend command points if available"""
        if self.command_points >= amount:
            self.command_points -= amount
            return True
        return False

    def compute_average_distance(self, objective: Objective) -> float:
        """Compute the average distance of the player's alive units to the objective."""
        distances = []
        for unit in self.get_army().units:
            if unit.is_alive() and unit.deployed:
                unit_pos = unit.get_position()
                obj_pos = (objective.location.x, objective.location.y, objective.location.z)
                distances.append(get_dist(unit_pos[0] - obj_pos[0],
                                        unit_pos[1] - obj_pos[1],
                                        unit_pos[2] - obj_pos[2]))
        return sum(distances) / len(distances) if distances else 0.0

    def __str__(self):
        return f"Name: {self.name}\nType: {self.type.name}\nCommand Points: {self.command_points}\nArmy: {self.army}"
