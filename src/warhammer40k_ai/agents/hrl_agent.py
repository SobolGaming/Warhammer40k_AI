import random
from typing import List, Tuple
from warhammer40k_ai.classes.game import Game
from warhammer40k_ai.classes.map import Objective, ObjectivePoint
from warhammer40k_ai.classes.unit import Unit, MovementAction
from warhammer40k_ai.classes.model import Model
from warhammer40k_ai.classes.wargear import Wargear, WargearProfile
from warhammer40k_ai.classes.player import Player
import torch
import torch.nn as nn
import torch.optim as optim
from warhammer40k_ai.utility.constants import TOTAL_ROUNDS
from warhammer40k_ai.utility.calcs import get_dist

# Constants
MAX_TARGETS = 25  # Maximum number of targets to consider
MAX_PROFILES = 3  # Maximum number of profiles per weapon

PRIMARY_OBJECTIVE_REWARD = 10
SECONDARY_OBJECTIVE_REWARD = 5
OPPONENT_PRIMARY_OBJECTIVE_PENALTY = 10
OPPONENT_SECONDARY_OBJECTIVE_PENALTY = 5
DESTROY_UNIT_REWARD = 2
LOSE_UNIT_PENALTY = 2

MOVEMENT_REWARD_SCALING = 1.0
SHOOTING_REWARD_SCALING = 1.0
CHARGE_REWARD_SCALING = 1.0
FIGHT_REWARD_SCALING = 1.0

NUM_MOVEMENT_ACTIONS = len(list(MovementAction))


class PolicyNetwork(nn.Module):
    """A simple neural network to output probabilities for objectives."""
    def __init__(self, input_size, output_size):
        super(PolicyNetwork, self).__init__()
        self.fc1 = nn.Linear(input_size, 128)
        self.fc2 = nn.Linear(128, output_size)

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = self.fc2(x)
        x = torch.softmax(x, dim=-1)
        return x


class State:
    def __init__(self, player: Player, opponent: Player, objectives: List[Objective] = []):
        # Existing state attributes
        self.player_score = 0
        self.opponent_score = 0
        self.remaining_rounds = TOTAL_ROUNDS
        self.objectives = objectives
        self.player = player
        self.opponent = opponent


class HighLevelAgent:
    """Strategic Layer: Coordinates phases and sets objectives."""
    def __init__(self, game: Game, player: Player, opponent: Player, objectives: List[Objective] = [], commands: List[str] = [], learning_rate=0.01) -> None:
        self.game = game
        self.player = player
        self.opponent = opponent
        self.objectives = objectives
        self.num_objectives = len(objectives)
        self.commands = commands
        self.num_commands = len(commands)

        # State attributes
        self.state = State(player, opponent, objectives)

        # Initialize Policy Network and Optimizer
        self.policy_net = PolicyNetwork(input_size=8, output_size=self.num_objectives + self.num_commands)
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=learning_rate)

        # Store rewards and log probabilities for training
        self.rewards = []
        self.log_probs = []

    def extract_state_features(self) -> torch.Tensor:
        """Extract features from the game state for the policy network."""
        features = []

        # Player's score
        player_score = self.game.get_current_player().get_score()
        features.append(player_score)

        # Opponent's score
        opponent_score = self.game.get_opponent().get_score()
        features.append(opponent_score)

        # Number of player's units
        num_player_units = len([unit for unit in self.game.get_current_player().get_army().units if unit.is_alive()])
        features.append(num_player_units)

        # Number of opponent's units
        num_opponent_units = len([unit for unit in self.game.get_opponent().get_army().units if unit.is_alive()])
        features.append(num_opponent_units)

        # Average distance to objectives
        total_distance = 0
        for obj in self.objectives:
            for unit in self.game.get_current_player().get_army().units:
                if unit.is_alive():
                    unit_pos = unit.get_position()
                    obj_pos = (obj.location.x, obj.location.y, obj.location.z)
                    distance = get_dist(unit_pos[0] - obj_pos[0], unit_pos[1] - obj_pos[1], unit_pos[2] - obj_pos[2])
                    total_distance += distance
        avg_distance = total_distance / (num_player_units * len(self.objectives)) if num_player_units > 0 else 0
        features.append(avg_distance)

        # Control status of objectives
        for obj in [obj for obj in self.objectives if isinstance(obj.location, ObjectivePoint)]:
            if obj.location.controlling_player == self.game.get_current_player():
                features.append(1)
            elif obj.location.controlling_player == self.game.get_opponent():
                features.append(-1)
            else:
                features.append(0)

        # Current turn number
        features.append(self.game.turn)

        # Remaining turns
        features.append(TOTAL_ROUNDS - self.game.turn)

        # Convert features to tensor
        state = torch.tensor(features, dtype=torch.float32)

        return state

    def choose_objective_and_command(self) -> Tuple[Objective, str]:
        """Select both an objective and a command action."""
        state = self.extract_state_features()
        probs = self.policy_net(state)

        # Check if we have both objectives and commands
        if self.num_objectives == 0 or self.num_commands == 0:
            raise ValueError("No objectives or commands available")

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

    def compute_reward(self, previous_state: State, current_state: State, action: Tuple[Objective, str]) -> float:
        reward = 0

        # Reward for capturing an objective
        for obj in current_state.objectives:
            if obj.controlled_by == 'player' and obj.controlled_by != previous_state.get_objective_control(obj):
                if obj.objective_type == 'primary':
                    reward += PRIMARY_OBJECTIVE_REWARD
                elif obj.objective_type == 'secondary':
                    reward += SECONDARY_OBJECTIVE_REWARD

        # Penalty for opponent capturing an objective
        for obj in current_state.objectives:
            if obj.controlled_by == 'opponent' and obj.controlled_by != previous_state.get_objective_control(obj):
                if obj.objective_type == 'primary':
                    reward -= OPPONENT_PRIMARY_OBJECTIVE_PENALTY
                elif obj.objective_type == 'secondary':
                    reward -= OPPONENT_SECONDARY_OBJECTIVE_PENALTY

        # Reward for destroying an opponent unit
        if len(current_state.opponent_units) < len(previous_state.opponent_units):
            for unit in [unit for unit in previous_state.opponent.army.units if unit not in current_state.opponent.army.units]:
                #unit_value = unit.get_unit_cost() / 10.0
                reward += DESTROY_UNIT_REWARD

        # Penalty for losing a unit
        if len(current_state.player_units) < len(previous_state.player_units):
            for unit in [unit for unit in previous_state.player.army.units if unit not in current_state.player.army.units]:
                #unit_value = unit.get_unit_cost() / 10.0
                reward -= LOSE_UNIT_PENALTY

        # Additional rewards or penalties based on game state
        # ...

        return reward

    def update_policy(self) -> None:
        """Update the policy network using the REINFORCE algorithm."""
        if not self.rewards or not self.log_probs:
            print("No rewards or log probabilities to update High Level Agent policy.")
            return  # Skip update if there's nothing to learn from

        R = 0
        policy_loss = []
        returns = []

        # Calculate the discounted rewards (returns)
        for r in self.rewards[::-1]:
            R = r + 0.99 * R  # Discount factor gamma = 0.99
            returns.insert(0, R)

        returns = torch.tensor(returns)
        # Check the length before normalizing
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-9)
        else:
            returns = returns * 0  # Or keep as is without normalization

        # Calculate policy loss
        for log_prob, R in zip(self.log_probs, returns):
            policy_loss.append(-log_prob * R)

        # Update policy network
        self.optimizer.zero_grad()
        policy_loss = torch.stack(policy_loss).sum()
        policy_loss.backward()
        self.optimizer.step()

        # Clear rewards and log probabilities for the next episode
        self.rewards.clear()
        self.log_probs.clear()


class TacticalAgent:
    """Tactical Layer: Handles per-phase unit actions."""
    def __init__(self, game: Game, player: Player, learning_rate=0.01) -> None:
        self.game = game
        self.player = player

        # Policy networks and optimizers for different phases
        self.movement_policy_net = PolicyNetwork(input_size=self.get_movement_state_size(), output_size=NUM_MOVEMENT_ACTIONS)
        self.movement_optimizer = optim.Adam(self.movement_policy_net.parameters(), lr=learning_rate)
        self.shooting_policy_net = PolicyNetwork(input_size=self.get_shooting_state_size(), output_size=self.get_shooting_action_size())
        self.shooting_optimizer = optim.Adam(self.shooting_policy_net.parameters(), lr=learning_rate)
        # Add similar networks for charge and fight phases if desired

        # Store rewards and log probabilities for training
        self.movement_rewards = []
        self.movement_log_probs = []
        self.shooting_rewards = []
        self.shooting_log_probs = []
        # Add similar buffers for charge and fight phases

    def command_phase(self, command: str) -> None:
        """Execute high-level commands or stratagems."""
        self.game.event_system.publish("command_phase_start", game_state=self.game.get_state())
        for unit in self.player.army.get_active_units():
            # Apply abilities or buffs here (e.g., stratagems)
            print(f"Commanding {unit.name}")
        self.game.event_system.publish("command_phase_end", game_state=self.game.get_state())

    ###########################################################################
    # Movement Phase
    ###########################################################################
    def movement_phase(self, unit: Unit, objective: Objective) -> None:
        """Decide on movement actions for the unit and execute them."""
        if not unit.deployed or not unit.is_alive():
            return

        # Determine the unit's engagement state
        state = unit.get_engagement_state(self.game.map)
        available_actions = unit.get_available_move_actions(state)

        # Agent decides on the action
        chosen_action = self.choose_movement_action(unit, available_actions, objective)

        # Decide on the destination
        destination = self.calculate_destination(unit, chosen_action, objective)

        # Record the previous distance to the objective
        unit_position_before = unit.get_position()
        dx_before = objective.location.x - unit_position_before[0]
        dy_before = objective.location.y - unit_position_before[1]
        dz_before = objective.location.z - unit_position_before[2]
        distance_before = get_dist(dx_before, dy_before, dz_before)

        # Execute the movement
        unit.do_move_action(chosen_action, destination, self.game.map)

        # Record the new distance to the objective
        unit_position_after = unit.get_position()
        dx_after = objective.location.x - unit_position_after[0]
        dy_after = objective.location.y - unit_position_after[1]
        dz_after = objective.location.z - unit_position_after[2]
        distance_after = get_dist(dx_after, dy_after, dz_after)

        # Compute the reward (positive if unit moved closer)
        reward = MOVEMENT_REWARD_SCALING * (distance_before - distance_after)
        self.movement_rewards.append(reward)

    def calculate_destination(self, unit: Unit, action: MovementAction, objective: Objective) -> Tuple[float, float, float]:
        if action == MovementAction.REMAIN_STATIONARY:
            return unit.get_position()
        elif action in [MovementAction.MOVE, MovementAction.ADVANCE]:
            # Move towards the objective
            unit_position = unit.get_position()
            obj_position = (objective.location.x, objective.location.y, objective.location.z)
            # Calculate direction vector
            dx = obj_position[0] - unit_position[0]
            dy = obj_position[1] - unit_position[1]
            dz = self.game.map.get_height_at_point(obj_position[0], obj_position[1]) - unit_position[2]
            distance = get_dist(dx, dy, dz)
            # Determine movement range
            movement_range = unit.movement
            if action == MovementAction.ADVANCE:
                # For simplicity, assume maximum advance roll
                movement_range += 6
            # Calculate new position
            if distance <= movement_range:
                return obj_position
            else:
                scale = movement_range / distance
                new_x = unit_position[0] + dx * scale
                new_y = unit_position[1] + dy * scale
                new_z = self.game.map.get_height_at_point(new_x, new_y)
                return (new_x, new_y, new_z)
        else:
            return unit.get_position()

    def choose_movement_action(self, unit: Unit, available_actions: List[int], objective: Objective) -> int:
        state = self.extract_movement_state_features(unit, objective)
        action_probs = self.movement_policy_net(state)

        # Mask unavailable actions
        action_mask = torch.zeros(NUM_MOVEMENT_ACTIONS)
        for action in available_actions:
            action_mask[action.value] = 1
        masked_probs = action_probs * action_mask
        masked_probs = masked_probs / masked_probs.sum()

        # Create a categorical distribution
        action_dist = torch.distributions.Categorical(masked_probs)
        action_idx = action_dist.sample()

        # Store log probability
        self.movement_log_probs.append(action_dist.log_prob(action_idx))

        return action_idx.item()

    def extract_movement_state_features(self, unit: Unit, objective: Objective) -> torch.Tensor:
        features = []

        # Unit's current position
        unit_pos = unit.get_position()
        features.extend([unit_pos[0], unit_pos[1], unit_pos[2]])

        # Objective's position
        obj_pos = (objective.location.x, objective.location.y, objective.location.z)
        features.extend([obj_pos[0], obj_pos[1], obj_pos[2]])

        # Distance to objective
        dx = obj_pos[0] - unit_pos[0]
        dy = obj_pos[1] - unit_pos[1]
        dz = obj_pos[2] - unit_pos[2]
        distance_to_objective = get_dist(dx, dy, dz)
        features.append(distance_to_objective)

        # Unit's movement range
        features.append(unit.movement)

        # Engagement state
        engagement_state = unit.get_engagement_state(self.game.map)
        features.append(engagement_state.value)

        # Remaining features can be added as needed

        # Convert to tensor
        assert len(features) == self.get_movement_state_size()
        state = torch.tensor(features, dtype=torch.float32)
        return state

    def get_movement_state_size(self) -> int:
        # Define the size of the movement state vector
        return 9  # Adjust based on actual features

    ###########################################################################
    # Shooting Phase
    ###########################################################################
    def choose_shooting_target(self, model: Model, profile: WargearProfile, targets: List[Unit]) -> int:
        """Choose a target for the model's weapon/profile."""
        state = self.extract_shooting_state_features(model, profile, targets)
        action_probs = self.shooting_policy_net(state)

        # Mask unavailable targets
        action_mask = torch.zeros(self.get_shooting_action_size())
        num_targets = min(len(targets), MAX_TARGETS)
        for idx in range(num_targets):
            action_mask[idx] = 1
        # The target selection probabilities come after the profile selection probabilities
        masked_probs = action_probs[self.get_profile_selection_action_size():] * action_mask
        masked_probs = masked_probs / masked_probs.sum()

        # Create a categorical distribution
        action_dist = torch.distributions.Categorical(masked_probs)
        action_idx = action_dist.sample()

        # Store log probability
        self.shooting_log_probs.append(action_dist.log_prob(action_idx))

        return action_idx.item()

    def choose_weapon_profile(self, model: Model, wargear_item: Wargear) -> WargearProfile:
        """Choose a weapon profile to use from the wargear item."""
        profiles = list(wargear_item.profiles.values())

        if len(profiles) == 1:
            # Only one profile available
            return profiles[0]

        # Extract state features for profile selection
        state = self.extract_profile_selection_state(model, wargear_item, profiles)
        action_probs = self.shooting_policy_net(state)

        # Mask unavailable profiles
        action_mask = torch.zeros(self.get_profile_selection_action_size())
        num_profiles = min(len(profiles), MAX_PROFILES)
        for idx in range(num_profiles):
            action_mask[idx] = 1
        masked_probs = action_probs[:self.get_profile_selection_action_size()] * action_mask
        masked_probs = masked_probs / masked_probs.sum()

        # Create a categorical distribution for profile selection
        profile_dist = torch.distributions.Categorical(masked_probs)
        profile_idx = profile_dist.sample()

        # Store log probability
        self.shooting_log_probs.append(profile_dist.log_prob(profile_idx))

        return profiles[profile_idx.item()]

    def extract_profile_selection_state(self, model: Model, wargear_item: Wargear, profiles: List[WargearProfile]) -> torch.Tensor:
        """Extract state features for selecting a weapon profile."""
        features = []

        # Model's position and health
        model_pos = model.get_position()
        features.extend([model_pos[0], model_pos[1], model_pos[2]])
        features.append(model.health_percent)

        # Characteristics of each profile
        for profile in profiles[:MAX_PROFILES]:
            features.append(profile.range)
            features.append(profile.attacks)
            features.append(profile.strength)
            features.append(profile.AP)
            features.append(profile.damage)

        # If fewer than MAX_PROFILES, pad with zeros
        num_profiles = len(profiles)
        if num_profiles < MAX_PROFILES:
            padding = [0.0] * ((MAX_PROFILES - num_profiles) * 5)  # 5 features per profile
            features.extend(padding)

        # Add other relevant features if necessary

        # Convert to tensor
        state = torch.tensor([features], dtype=torch.float32)  # Batch dimension

        return state

    def extract_profile_selection_state(self, model: Model, wargear_item, profiles: List[WargearProfile]) -> torch.Tensor:
        """Extract state features for selecting a weapon profile."""
        features = []

        # Model's position and health
        model_pos = model.get_location()
        features.extend([model_pos[0], model_pos[1], model_pos[2]])
        features.append(model.health_percent)

        # Characteristics of each profile
        for profile in profiles[:MAX_PROFILES]:
            features.append(profile.range)
            features.append(profile.attacks)
            features.append(profile.strength)
            features.append(profile.AP)
            features.append(profile.damage)

        # If fewer than MAX_PROFILES, pad with zeros
        num_profiles = len(profiles)
        if num_profiles < MAX_PROFILES:
            padding = [0.0] * ((MAX_PROFILES - num_profiles) * 5)  # 5 features per profile
            features.extend(padding)

        # Add other relevant features if necessary

        # Convert to tensor
        state = torch.tensor([features], dtype=torch.float32)  # Batch dimension

        return state

    def extract_shooting_state_features(self, model: Model, profile: WargearProfile, targets: List[Unit]) -> torch.Tensor:
        """Extract state features for shooting decision."""
        features = []

        # Model's position and health
        model_pos = model.get_location()
        features.extend([model_pos[0], model_pos[1], model_pos[2]])
        features.append(model.health_percent)

        # Weapon/profile characteristics
        features.append(profile.range.max)
        features.append(profile.attacks)
        features.append(profile.strength)
        features.append(profile.ap)
        features.append(profile.damage)

        # Enemy units' positions and health
        for enemy in targets[:MAX_TARGETS]:
            enemy_pos = enemy.get_position()
            features.extend([enemy_pos[0], enemy_pos[1], enemy_pos[2]])
            features.append(enemy.health_percent)

        # If fewer than MAX_TARGETS, pad with zeros
        num_targets = len(targets)
        if num_targets < MAX_TARGETS:
            padding = [0.0] * ((MAX_TARGETS - num_targets) * 4)  # 4 features per target
            features.extend(padding)

        # Convert to tensor
        state = torch.tensor([features], dtype=torch.float32)  # Batch dimension

        return state

    def get_shooting_state_size(self) -> int:
        """Calculate the size of the shooting state vector."""
        # For profile selection:
        # 4 features for the model (x, y, z, health)
        # 5 features per profile * MAX_PROFILES

        # For target selection:
        # 4 features for the model (x, y, z, health)
        # 5 features for the selected profile
        # 4 features per target * MAX_TARGETS

        # We need to ensure the input size matches the largest possible input (either profile selection or target selection)
        profile_selection_size = 4 + (MAX_PROFILES * 5)
        target_selection_size = 4 + 5 + (MAX_TARGETS * 4)

        # Return the maximum of the two
        return max(profile_selection_size, target_selection_size)

    def get_profile_selection_action_size(self) -> int:
        """Define the number of possible profiles to select from."""
        return MAX_PROFILES

    def get_shooting_action_size(self) -> int:
        """Define the total number of possible actions (profile selection + target selection)."""
        # Total action size is the sum of profile selection actions and target selection actions
        return self.get_profile_selection_action_size() + MAX_TARGETS

    def shooting_phase(self, unit: Unit) -> None:
        """Select targets and resolve shooting attacks for each model in the unit."""
        if not unit.deployed or not unit.is_alive():
            return

        self.game.event_system.publish("shooting_phase_start", unit=unit, game_state=self.game.get_state())

        if unit.round_state.advanced_this_round:
            print(f"{unit.name} cannot shoot after advancing.")
            return
        if unit.round_state.fell_back_this_round:
            print(f"{unit.name} cannot shoot after falling back.")
            return

        # Loop over each model in the unit
        for model in unit.models:
            if not model.is_alive:
                continue

            # For each wargear (weapon) the model has
            for wargear_item in model.wargear:
                # Decide which profile to use if the weapon has multiple profiles
                selected_profile = self.choose_weapon_profile(model, wargear_item)
                
                if selected_profile is None:
                    continue  # No valid profile selected

                # Find targets in range for this weapon/profile
                targets = model.find_targets_in_range(self.game.map, wargear_profile=selected_profile)

                if targets:
                    # Agent decides on the target
                    target_idx = self.choose_shooting_target(model, selected_profile, targets)
                    target = targets[target_idx]

                    # Record the target's health before attack
                    target_health_before = target.health_percent

                    # Execute the attack
                    print(f"{model.name} of {unit.name} shoots at {target.name} with {wargear_item.name} ({selected_profile.name})")
                    model.ranged_attack(target, selected_profile)

                    # Record the target's health after attack
                    target_health_after = target.health_percent

                    # Compute the reward (damage inflicted)
                    damage = target_health_before - target_health_after
                    reward = SHOOTING_REWARD_SCALING * damage
                    self.shooting_rewards.append(reward)
                else:
                    # No targets, negative reward for missed opportunity
                    reward = -1.0 * SHOOTING_REWARD_SCALING
                    self.shooting_rewards.append(reward)

        self.game.event_system.publish("shooting_phase_end", unit=unit, game_state=self.game.get_state())


    ###########################################################################
    # Charge Phase
    ###########################################################################
    def charge_phase(self, unit: Unit) -> None:
        """Identify nearby targets and charge."""
        if not unit.deployed or not unit.is_alive():
            return

        self.game.event_system.publish("charge_phase_start", unit=unit, game_state=self.game.get_state())
        #targets = self.game.find_enemies_in_charge_range(unit)
        #target = random.choice(targets)
        #if target:
        #    print(f"{unit.name} charges {target.name}")
        #    self.game.charge(unit, target)
        self.game.event_system.publish("charge_phase_end", unit=unit, game_state=self.game.get_state())

    ###########################################################################
    # Fight Phase
    ###########################################################################
    def fight_phase(self, unit: Unit) -> None:
        """Resolve melee combat."""
        if not unit.deployed or not unit.is_alive():
            return

        self.game.event_system.publish("fight_phase_start", unit=unit, game_state=self.game.get_state())
        #targets = self.game.find_enemies_in_melee_range(unit)
        #target = random.choice(targets)
        #if target:
        #    print(f"{unit.name} fights {target.name}")
        #    self.game.fight(unit, target)
        self.game.event_system.publish("fight_phase_end", unit=unit, game_state=self.game.get_state())

    ###########################################################################
    # Policy Updates
    ###########################################################################
    def update_policies(self) -> None:
        self.update_movement_policy()
        self.update_shooting_policy()
        # Add updates for charge and fight policies if implemented

    def update_movement_policy(self) -> None:
        """Update the movement policy network."""
        if not self.movement_rewards or not self.movement_log_probs:
            print("No rewards or log probabilities to update Tactical Agent movement policy.")
            return  # Skip update if there's nothing to learn from

        R = 0
        policy_loss = []
        returns = []
        gamma = 0.99  # Discount factor

        # Calculate discounted rewards
        for r in self.movement_rewards[::-1]:
            R = r + gamma * R
            returns.insert(0, R)
        returns = torch.tensor(returns)
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-9)
        else:
            returns = returns * 0

        for log_prob, R in zip(self.movement_log_probs, returns):
            policy_loss.append(-log_prob * R)

        # Update the policy network
        self.movement_optimizer.zero_grad()
        policy_loss = torch.stack(policy_loss).sum()
        policy_loss.backward()
        self.movement_optimizer.step()

        # Clear buffers
        self.movement_rewards.clear()
        self.movement_log_probs.clear()

    def update_shooting_policy(self) -> None:
        """Update the shooting policy network."""
        if not self.shooting_rewards or not self.shooting_log_probs:
            print("No rewards or log probabilities to update Tactical Agent shooting policy.")
            return  # Skip update if there's nothing to learn from

        R = 0
        policy_loss = []
        returns = []
        gamma = 0.99  # Discount factor

        # Calculate discounted rewards
        for r in self.shooting_rewards[::-1]:
            R = r + gamma * R
            returns.insert(0, R)
        returns = torch.tensor(returns)
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-9)
        else:
            returns = returns * 0

        for log_prob, R in zip(self.shooting_log_probs, returns):
            policy_loss.append(-log_prob * R)

        # Update the policy network
        self.shooting_optimizer.zero_grad()
        policy_loss = torch.stack(policy_loss).sum()
        policy_loss.backward()
        self.shooting_optimizer.step()

        # Clear buffers
        self.shooting_rewards.clear()
        self.shooting_log_probs.clear()


class LowLevelAgent:
    """Operational Layer: Executes precise unit movements and actions."""
    def __init__(self, game: Game, player: Player, learning_rate=0.01) -> None:
        self.game = game
        self.player = player

        # Policy network for movement execution
        self.movement_execution_net = PolicyNetwork(input_size=self.get_state_size(), output_size=self.get_action_size())
        self.optimizer = optim.Adam(self.movement_execution_net.parameters(), lr=learning_rate)

        # Store rewards and log probabilities
        self.rewards = []
        self.log_probs = []

    def execute_movement(self, unit: Unit, model_paths: List[List[Tuple[float, float, float]]]) -> None:
        """Move the unit along the path."""
        success = unit.do_move_action(self.game.map)
        self.game.event_system.publish("movement_phase_end", unit=unit, game_state=self.game.get_state())
        # Check if objective was achieved post-move.
        for obj in self.game.objectives:
            obj.check_completion(self.game.get_state())

    def resolve_combat(self, unit: Unit, target: Unit) -> None:
        """Perform combat calculations and apply damage."""
        self.game.fight(unit, target)

    def get_state_size(self) -> int:
        # Define the size of the state vector
        return 20  # Adjust based on actual features

    def get_action_size(self) -> int:
        # Define the number of possible movement directions or steps
        return 8  # For example, 8 possible movement directions

    def update_policy(self) -> None:
        """Update the movement execution policy network."""
        if not self.rewards or not self.log_probs:
            print("No rewards or log probabilities to update Low Level Agent movement policy.")
            return  # Skip update if there's nothing to learn from

        R = 0
        policy_loss = []
        returns = []
        gamma = 0.99  # Discount factor

        # Calculate discounted rewards
        for r in self.rewards[::-1]:
            R = r + gamma * R
            returns.insert(0, R)
        returns = torch.tensor(returns)
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-9)
        else:
            returns = returns * 0

        for log_prob, R in zip(self.log_probs, returns):
            policy_loss.append(-log_prob * R)

        # Update the policy network
        self.optimizer.zero_grad()
        policy_loss = torch.stack(policy_loss).sum()
        policy_loss.backward()
        self.optimizer.step()

        # Clear buffers
        self.rewards.clear()
        self.log_probs.clear()
