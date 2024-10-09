from typing import Callable
from .unit import Unit


class StatusEffect:
    def __init__(self, name: str, duration: int, apply_effect: Callable, remove_effect: Callable):
        self.name = name
        self.duration = duration
        self.remaining_duration = duration
        self.apply_effect = apply_effect  # Function to apply effect
        self.remove_effect = remove_effect  # Function to remove effect
    
    def tick(self, unit: Unit):
        self.remaining_duration -= 1
        if self.remaining_duration <= 0:
            self.remove_effect(unit)
            return False  # Effect has ended
        return True  # Effect is still active