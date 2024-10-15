import random
from typing import List, Tuple
from warhammer40k_ai.classes.game import Game
from warhammer40k_ai.classes.map import ObjectivePoint
from warhammer40k_ai.classes.unit import Unit
from warhammer40k_ai.classes.player import Player


class HighLevelAgent:
    """Strategic Layer: Coordinates phases and sets objectives."""
    def __init__(self, game: Game, player: Player) -> None:
        self.game = game
        self.player = player

    def command_phase(self) -> None:
        """Execute high-level commands or stratagems."""
        for unit in self.player.army.units:
            # Apply abilities or buffs here (e.g., stratagems)
            print(f"Commanding {unit.name}")

    def choose_objective(self) -> ObjectivePoint:
        """Select strategic objectives."""
        return random.choice(self.game.map.get_objectives())


class TacticalAgent:
    """Tactical Layer: Handles per-phase unit actions."""
    def __init__(self, game: Game, player: Player) -> None:
        self.game = game
        self.player = player

    def movement_phase(self, unit: Unit, objective: ObjectivePoint) -> List[Tuple[float, float, float]]:
        """Handle unit pathing towards objectives."""
        path = self.game.map.find_path(unit.position, objective.position)
        return path

    def shooting_phase(self, unit: Unit) -> None:
        """Select targets and resolve shooting attacks."""
        targets = self.game.find_enemies_in_shooting_range(unit)
        target = random.choice(targets)
        if target:
            print(f"{unit.name} shoots at {target.name}")
            self.game.attack(unit, target)

    def charge_phase(self, unit: Unit) -> None:
        """Identify nearby targets and charge."""
        targets = self.game.find_enemies_in_charge_range(unit)
        target = random.choice(targets)
        if target:
            print(f"{unit.name} charges {target.name}")
            self.game.charge(unit, target)

    def fight_phase(self, unit: Unit) -> None:
        """Resolve melee combat."""
        targets = self.game.find_enemies_in_melee_range(unit)
        target = random.choice(targets)
        if target:
            print(f"{unit.name} fights {target.name}")
            self.game.fight(unit, target)


class LowLevelAgent:
    """Operational Layer: Executes precise unit movements and actions."""
    def __init__(self, game: Game, player: Player) -> None:
        self.game = game
        self.player = player

    def execute_movement(self, unit: Unit, path: List[Tuple[float, float, float]]) -> None:
        """Move the unit along the path."""
        for step in path:
            self.game.map.move_unit(unit, step)

    def resolve_combat(self, unit: Unit, target: Unit) -> None:
        """Perform combat calculations and apply damage."""
        self.game.fight(unit, target)