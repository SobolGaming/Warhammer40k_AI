# This is the player that gets put onto a Battlefield and has an Army

import logging
from enum import Enum, auto
from .army import Army
from .unit import Unit
from warhammer40k_ai.classes.map import Objective
from .mission_cards import PrimaryMissionCard, SecondaryMissionCard, default_secondary_deck
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
        # Mission cards
        self.primary_mission: PrimaryMissionCard | None = None
        self.secondary_deck: list[SecondaryMissionCard] = []
        self.active_secondaries: list[SecondaryMissionCard] = []
        self.discarded_secondaries: list[SecondaryMissionCard] = []
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
                # Find the model closest to the objective
                obj_pos = (objective.location.x, objective.location.y, objective.location.z)
                closest_distance = float('inf')

                for model in unit.models:
                    if model.is_alive:
                        model_pos = model.get_location()
                        distance = get_dist(model_pos[0] - obj_pos[0],
                                          model_pos[1] - obj_pos[1],
                                          model_pos[2] - obj_pos[2])
                        if distance < closest_distance:
                            closest_distance = distance

                if closest_distance != float('inf'):
                    distances.append(closest_distance)
        return sum(distances) / len(distances) if distances else 0.0

    # ---------- Mission card helpers ----------

    def set_primary_mission(self, primary: PrimaryMissionCard) -> None:
        self.primary_mission = primary

    def set_secondary_deck(self, cards: list[SecondaryMissionCard] | None = None) -> None:
        # Use provided or default deck
        self.secondary_deck = list(cards) if cards is not None else default_secondary_deck()
        self.active_secondaries = []
        self.discarded_secondaries = []

    def ensure_secondary_deck_initialized(self) -> None:
        if not self.secondary_deck and not self.active_secondaries and not self.discarded_secondaries:
            self.set_secondary_deck()

    def can_draw_secondary(self) -> bool:
        return len(self.secondary_deck) > 0

    def draw_secondary_until_two(self, game) -> None:
        # Initialize deck if needed
        self.ensure_secondary_deck_initialized()
        # Draw until two active if deck allows
        while len(self.active_secondaries) < 2 and self.secondary_deck:
            card = self.secondary_deck.pop(0)
            try:
                if hasattr(card, 'can_be_drawn') and not card.can_be_drawn(game, self):
                    # Discard immediately and continue drawing
                    self.discarded_secondaries.append(card)
                    continue
                # Allow cards to perform on-draw initialization
                if hasattr(card, 'on_draw'):
                    try:
                        card.on_draw(game, self)
                    except Exception:
                        pass
            except Exception:
                pass
            self.active_secondaries.append(card)

    def discard_secondary(self, card: SecondaryMissionCard, gain_cp: bool = False) -> None:
        if card in self.active_secondaries:
            self.active_secondaries.remove(card)
            self.discarded_secondaries.append(card)
            if gain_cp:
                self.gain_command_point()

    def discard_achieved_secondaries(self, achieved_cards: list[SecondaryMissionCard]) -> None:
        for card in list(achieved_cards):
            if card in self.active_secondaries:
                self.active_secondaries.remove(card)
                self.discarded_secondaries.append(card)

    def __str__(self):
        return f"Name: {self.name}\nType: {self.type.name}\nCommand Points: {self.command_points}\nArmy: {self.army}"
