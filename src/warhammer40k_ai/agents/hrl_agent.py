import random
from typing import List, Tuple
from warhammer40k_ai.classes.game import Game
from warhammer40k_ai.classes.map import Objective
from warhammer40k_ai.classes.unit import Unit
from warhammer40k_ai.classes.player import Player


class HighLevelAgent:
    """Strategic Layer: Coordinates phases and sets objectives."""
    def __init__(self, game: Game, player: Player, objectives: List[Objective] = []) -> None:
        self.game = game
        self.player = player
        self.objectives = objectives

    def add_objective(self, objective: Objective) -> None:
        self.objectives.append(objective)

    def command_phase(self) -> None:
        """Execute high-level commands or stratagems."""
        self.game.event_system.publish("command_phase_start", game_state=self.game.get_state())
        for unit in self.player.army.get_active_units():
            # Apply abilities or buffs here (e.g., stratagems)
            print(f"Commanding {unit.name}")
        self.game.event_system.publish("command_phase_end", game_state=self.game.get_state())

    def choose_objective(self) -> Objective:
        """Select strategic objectives."""
        # Prioritize incomplete objectives that yield the highest points.
        available = [obj for obj in self.objectives if not obj.completed]
        return max(available, key=lambda o: o.points, default=None)


class TacticalAgent:
    """Tactical Layer: Handles per-phase unit actions."""
    def __init__(self, game: Game, player: Player) -> None:
        self.game = game
        self.player = player

    def movement_phase(self, unit: Unit, objective: Objective) -> List[Tuple[float, float, float]]:
        """Handle unit pathing towards objectives."""
        if objective and objective.location:
            self.game.event_system.publish("movement_phase_start", unit=unit, game_state=self.game.get_state())
            path = self.game.map.find_path(unit.position, objective.location)
            return path
        return []

    def shooting_phase(self, unit: Unit) -> None:
        """Select targets and resolve shooting attacks."""
        self.game.event_system.publish("shooting_phase_start", unit=unit, game_state=self.game.get_state())
        targets = self.game.find_enemies_in_shooting_range(unit)
        target = random.choice(targets)
        if target:
            print(f"{unit.name} shoots at {target.name}")
            self.game.attack(unit, target)
        self.game.event_system.publish("shooting_phase_end", unit=unit, game_state=self.game.get_state())

    def charge_phase(self, unit: Unit) -> None:
        """Identify nearby targets and charge."""
        self.game.event_system.publish("charge_phase_start", unit=unit, game_state=self.game.get_state())
        targets = self.game.find_enemies_in_charge_range(unit)
        target = random.choice(targets)
        if target:
            print(f"{unit.name} charges {target.name}")
            self.game.charge(unit, target)
        self.game.event_system.publish("charge_phase_end", unit=unit, game_state=self.game.get_state())

    def fight_phase(self, unit: Unit) -> None:
        """Resolve melee combat."""
        self.game.event_system.publish("fight_phase_start", unit=unit, game_state=self.game.get_state())
        targets = self.game.find_enemies_in_melee_range(unit)
        target = random.choice(targets)
        if target:
            print(f"{unit.name} fights {target.name}")
            self.game.fight(unit, target)
        self.game.event_system.publish("fight_phase_end", unit=unit, game_state=self.game.get_state())


class LowLevelAgent:
    """Operational Layer: Executes precise unit movements and actions."""
    def __init__(self, game: Game, player: Player) -> None:
        self.game = game
        self.player = player

    def execute_movement(self, unit: Unit, path: List[Tuple[float, float, float]]) -> None:
        """Move the unit along the path."""
        for step in path:
            self.game.map.move_unit(unit, step)
            self.game.event_system.publish("movement_phase_step", unit=unit, game_state=self.game.get_state())
        self.game.event_system.publish("movement_phase_end", unit=unit, game_state=self.game.get_state())
        # Check if objective was achieved post-move.
        for obj in self.game.objectives:
            obj.check_completion(self.game.get_state())

    def resolve_combat(self, unit: Unit, target: Unit) -> None:
        """Perform combat calculations and apply damage."""
        self.game.fight(unit, target)