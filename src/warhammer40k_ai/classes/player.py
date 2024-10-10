# This is the player that gets put onto a Battlefield and has an Army

import logging
from enum import Enum, auto
from .army import Army

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

    def __str__(self):
        return f"Name: {self.name}\nType: {self.type.name}"
    
    def set_army(self, army: Army):
        self.army = army

    def get_army(self) -> Army:
        return self.army
