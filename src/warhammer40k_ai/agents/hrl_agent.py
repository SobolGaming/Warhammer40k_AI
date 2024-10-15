import random
from typing import List, Tuple
from warhammer40k_ai.classes.game import Game
from warhammer40k_ai.classes.map import Objective
from warhammer40k_ai.classes.unit import Unit
from warhammer40k_ai.classes.player import Player
import torch
import torch.nn as nn
import torch.optim as optim


class PolicyNetwork(nn.Module):
    """A simple neural network to output probabilities for objectives."""
    def __init__(self, input_size, output_size):
        super(PolicyNetwork, self).__init__()
        self.fc1 = nn.Linear(input_size, 128)
        self.fc2 = nn.Linear(128, output_size)

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        return torch.softmax(self.fc2(x), dim=-1)


class HighLevelAgent:
    """Strategic Layer: Coordinates phases and sets objectives."""
    def __init__(self, game: Game, player: Player, objectives: List[Objective] = [], commands: List[str] = [], learning_rate=0.01) -> None:
        self.game = game
        self.player = player
        self.objectives = objectives
        self.num_objectives = len(objectives)
        self.commands = commands
        self.num_commands = len(commands)

        # Initialize Policy Network and Optimizer
        self.policy_net = PolicyNetwork(input_size=1, output_size=self.num_objectives + self.num_commands)
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=learning_rate)

        # Store rewards and log probabilities for training
        self.rewards = []
        self.log_probs = []

    def choose_objective_and_command(self, game_state: Game) -> Tuple[Objective, str]:
        """Select both an objective and a command action."""
        state = torch.tensor([1.0])  # Example input state
        probs = self.policy_net(state)

        # Split the probabilities for objectives and commands
        obj_probs = probs[:self.num_objectives]
        cmd_probs = probs[self.num_objectives:]

        # Sample from both distributions
        obj_dist = torch.distributions.Categorical(obj_probs)
        cmd_dist = torch.distributions.Categorical(cmd_probs)

        obj_idx = obj_dist.sample()
        cmd_idx = cmd_dist.sample()

        # Store log probabilities for learning
        self.log_probs.append(obj_dist.log_prob(obj_idx))
        self.log_probs.append(cmd_dist.log_prob(cmd_idx))

        return self.objectives[obj_idx.item()], self.commands[cmd_idx.item()]

    def store_reward(self, reward: float) -> None:
        """Store the reward for later policy update."""
        self.rewards.append(reward)

    def update_policy(self) -> None:
        """Update the policy network using the REINFORCE algorithm."""
        R = 0
        policy_loss = []
        returns = []

        # Calculate the discounted rewards (returns)
        for r in self.rewards[::-1]:
            R = r + 0.99 * R  # Discount factor gamma = 0.99
            returns.insert(0, R)

        returns = torch.tensor(returns)
        returns = (returns - returns.mean()) / (returns.std() + 1e-9)  # Normalize returns

        # Calculate policy loss
        for log_prob, R in zip(self.log_probs, returns):
            policy_loss.append(-log_prob * R)

        # Update policy network
        self.optimizer.zero_grad()
        policy_loss = torch.cat(policy_loss).sum()
        policy_loss.backward()
        self.optimizer.step()

        # Clear rewards and log probabilities for the next episode
        self.rewards = []
        self.log_probs = []


class TacticalAgent:
    """Tactical Layer: Handles per-phase unit actions."""
    def __init__(self, game: Game, player: Player) -> None:
        self.game = game
        self.player = player

    def command_phase(self, command: str) -> None:
        """Execute high-level commands or stratagems."""
        self.game.event_system.publish("command_phase_start", game_state=self.game.get_state())
        for unit in self.player.army.get_active_units():
            # Apply abilities or buffs here (e.g., stratagems)
            print(f"Commanding {unit.name}")
        self.game.event_system.publish("command_phase_end", game_state=self.game.get_state())

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