from typing import Callable

class Stratagem:
    def __init__(self, name: str, type: str, description: str, cp_cost: int, turn: str, phase: str, detachment: str, effect: Callable, conditions: Callable):
        self.name = name
        self.type = type
        self.description = description
        self.cp_cost = cp_cost
        self.turn = turn
        self.phase = phase
        self.detachment = detachment
        self.effect = effect  # Function to execute the stratagem's effect
        self.conditions = conditions  # Function to check if stratagem can be used

    def can_use(self, game_state, **kwargs):
        # Check if conditions are met
        return self.conditions(game_state, **kwargs)

    def use(self, player, game_state, **kwargs):
        if player.command_points >= self.cp_cost and self.can_use(game_state, **kwargs):
            player.command_points -= self.cp_cost
            self.effect(player, game_state, **kwargs)
            return True
        return False

    def __str__(self):
        return f"{self.name} ({self.type}): {self.description}"

    def __repr__(self):
        return f"Stratagem(name={self.name}, type={self.type}, description={self.description}, cp_cost={self.cp_cost}, turn={self.turn}, phase={self.phase}, detachment={self.detachment}, effect={self.effect}, conditions={self.conditions})"
