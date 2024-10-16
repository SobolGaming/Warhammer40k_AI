# This is the player that gets put onto a Battlefield and has an Army

import logging
from enum import Enum, auto
from .army import Army
from .unit import Unit

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
        self.command_points: int = 0
        self.army: Army = army
        #print(f"Player {self.name} created with army: {self.army}")
    
    def set_army(self, army: Army) -> None:
        self.army = army

    def get_army(self) -> Army | None:
        return self.army

    def has_unit(self, unit: Unit) -> bool:
        return unit in self.army.units

    def has_units(self) -> bool:
        return len(self.army.units) > 0

    def __str__(self):
        return f"Name: {self.name}\nType: {self.type.name}\nCommand Points: {self.command_points}\nArmy: {self.army}"
