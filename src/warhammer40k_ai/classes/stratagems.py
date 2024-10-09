from typing import Callable

class Stratagem:
    def __init__(self, name: str, description: str, cp_cost: int, timing: str, effect: Callable, conditions: Callable):
        self.name = name
        self.description = description
        self.cp_cost = cp_cost
        self.timing = timing  # When the stratagem can be used (event name)
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