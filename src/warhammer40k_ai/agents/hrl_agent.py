from typing import List, Tuple, Optional
import os
import torch
import torch.nn as nn
import torch.optim as optim
import logging
import time
from collections import defaultdict

from warhammer40k_ai.classes.game import Game
from warhammer40k_ai.classes.map import Objective, ObjectivePoint
from warhammer40k_ai.classes.unit import Unit, MovementAction
from warhammer40k_ai.classes.model import Model
from warhammer40k_ai.classes.wargear import Wargear, WargearProfile
from warhammer40k_ai.classes.player import Player
from warhammer40k_ai.classes.deployment import DeploymentDecisionMaker
from warhammer40k_ai.utility.constants import TOTAL_ROUNDS
from warhammer40k_ai.utility.calcs import get_dist
from warhammer40k_ai.utility.dice import DiceCollection

# Setup logging for the agents
logger = logging.getLogger(__name__)

# Warning throttling system - only log each warning type once per 30 seconds
_warning_throttle = defaultdict(float)
_warning_throttle_interval = 30.0  # seconds

def throttled_warning(message: str, warning_key: str = None):
    """Log a warning message, but throttle repeated warnings."""
    if warning_key is None:
        warning_key = message
    
    current_time = time.time()
    if current_time - _warning_throttle[warning_key] > _warning_throttle_interval:
        logger.debug(message)  # Changed from warning to debug to reduce noise
        _warning_throttle[warning_key] = current_time

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
        
        # Better initialization to prevent NaN values
        nn.init.xavier_uniform_(self.fc1.weight)
        nn.init.zeros_(self.fc1.bias)
        nn.init.xavier_uniform_(self.fc2.weight)
        nn.init.zeros_(self.fc2.bias)

    def forward(self, x):
        # Add small epsilon to prevent numerical instability
        x = torch.clamp(x, -10, 10)  # Clamp extreme values
        x = torch.relu(self.fc1(x))
        x = self.fc2(x)
        x = torch.softmax(x, dim=-1)
        # Ensure minimum probability to prevent exact zeros
        x = torch.clamp(x, min=1e-8, max=1.0)
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

        # Deployment-specific policy networks
        self.deployment_zone_net = PolicyNetwork(input_size=12, output_size=2)  # Choose deployment zone (if defender)
        self.deployment_zone_optimizer = optim.Adam(self.deployment_zone_net.parameters(), lr=learning_rate)
        
        self.reserves_selection_net = PolicyNetwork(input_size=17, output_size=3)  # Deploy, Reserve, or Strategic Reserve
        self.reserves_selection_optimizer = optim.Adam(self.reserves_selection_net.parameters(), lr=learning_rate)
        
        self.unit_deployment_net = PolicyNetwork(input_size=20, output_size=100)  # Position selection within zone
        self.unit_deployment_optimizer = optim.Adam(self.unit_deployment_net.parameters(), lr=learning_rate)

        # Store rewards and log probabilities for training
        self.rewards = []
        self.log_probs = []
        self.episode = 0  # Episode counter for checkpointing
        
        # Deployment-specific tracking
        self.deployment_rewards = []
        self.deployment_log_probs = []
        self.reserves_rewards = []
        self.reserves_log_probs = []

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
        avg_distance = total_distance / (num_player_units * len(self.objectives)) if num_player_units > 0 and len(self.objectives) > 0 else 0
        features.append(avg_distance)

        # Control status of objectives (ensure we always add exactly 1 feature for now)
        objective_control = 0
        if self.objectives:
            obj = self.objectives[0]  # Use first objective
            if hasattr(obj, 'location') and hasattr(obj.location, 'controlling_player'):
                if obj.location.controlling_player == self.game.get_current_player():
                    objective_control = 1
                elif obj.location.controlling_player == self.game.get_opponent():
                    objective_control = -1
        features.append(objective_control)

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

        # Check for NaN values in network output
        if torch.isnan(probs).any():
            throttled_warning("Warning: NaN values detected in high-level policy network output, using uniform distribution")
            probs = torch.ones_like(probs)

        # Split the probabilities for objectives and commands
        obj_probs = probs[:self.num_objectives]
        cmd_probs = probs[self.num_objectives:]

        # Normalize probabilities separately
        obj_sum = obj_probs.sum()
        cmd_sum = cmd_probs.sum()
        
        if obj_sum == 0 or torch.isnan(obj_sum):
            throttled_warning("Warning: Invalid objective probability sum, using uniform distribution")
            obj_probs = torch.ones(self.num_objectives) / self.num_objectives
        else:
            obj_probs = obj_probs / obj_sum
            
        if cmd_sum == 0 or torch.isnan(cmd_sum):
            throttled_warning("Warning: Invalid command probability sum, using uniform distribution")
            cmd_probs = torch.ones(self.num_commands) / self.num_commands
        else:
            cmd_probs = cmd_probs / cmd_sum

        # Final check for NaN values
        if torch.isnan(obj_probs).any():
            obj_probs = torch.ones(self.num_objectives) / self.num_objectives
        if torch.isnan(cmd_probs).any():
            cmd_probs = torch.ones(self.num_commands) / self.num_commands

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
                reward += DESTROY_UNIT_REWARD

        # Penalty for losing a unit
        if len(current_state.player_units) < len(previous_state.player_units):
            for unit in [unit for unit in previous_state.player.army.units if unit not in current_state.player.army.units]:
                reward -= LOSE_UNIT_PENALTY

        # Additional rewards or penalties based on game state
        # ...

        return reward

    def update_policy(self) -> None:
        """Update the policy network using the REINFORCE algorithm."""
        if not self.rewards or not self.log_probs:
            throttled_warning("No rewards or log probabilities to update High Level Agent policy.")
            return  # Skip update if there's nothing to learn from

        R = 0
        policy_loss = []
        returns = []

        # Calculate the discounted rewards (returns)
        for r in self.rewards[::-1]:
            R = r + 0.99 * R  # Discount factor gamma = 0.99
            returns.insert(0, R)

        returns = torch.tensor(returns)
        # Normalize returns if more than one value exists
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-9)
        else:
            returns = returns * 0

        # Calculate policy loss
        for log_prob, R in zip(self.log_probs, returns):
            if log_prob.requires_grad:
                policy_loss.append(-log_prob * R)
            else:
                #print("Warning: log_prob does not require grad, skipping this term")
                continue

        # Update policy network
        if not policy_loss:
            throttled_warning("Warning: No valid policy loss terms to update HighLevelAgent")
            return
            
        self.optimizer.zero_grad()
        policy_loss = torch.stack(policy_loss).sum()
        
        # Check for NaN in loss
        if torch.isnan(policy_loss):
            throttled_warning("Warning: NaN loss detected in HighLevelAgent, skipping update")
            return
            
        policy_loss.backward()
        
        # Clip gradients to prevent explosion
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), max_norm=1.0)
        
        self.optimizer.step()

        # Clear rewards and log probabilities for the next episode
        self.rewards.clear()
        self.log_probs.clear()
        self.episode += 1
        
        # Update deployment-specific policies
        self.update_deployment_policies()
    
    def update_deployment_policies(self) -> None:
        """Update deployment-related policy networks."""
        self.update_deployment_zone_policy()
        self.update_reserves_policy()
    
    def update_deployment_zone_policy(self) -> None:
        """Update the deployment zone selection policy."""
        if not self.deployment_rewards or not self.deployment_log_probs:
            return
            
        R = 0
        policy_loss = []
        returns = []
        gamma = 0.99

        for r in self.deployment_rewards[::-1]:
            R = r + gamma * R
            returns.insert(0, R)
        returns = torch.tensor(returns)
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-9)

        for log_prob, R in zip(self.deployment_log_probs, returns):
            if log_prob.requires_grad:
                policy_loss.append(-log_prob * R)

        if policy_loss:
            self.deployment_zone_optimizer.zero_grad()
            policy_loss = torch.stack(policy_loss).sum()
            if not torch.isnan(policy_loss):
                policy_loss.backward()
                torch.nn.utils.clip_grad_norm_(self.deployment_zone_net.parameters(), max_norm=1.0)
                self.deployment_zone_optimizer.step()

        self.deployment_rewards.clear()
        self.deployment_log_probs.clear()
    
    def update_reserves_policy(self) -> None:
        """Update the reserves selection policy."""
        if not self.reserves_rewards or not self.reserves_log_probs:
            return
            
        R = 0
        policy_loss = []
        returns = []
        gamma = 0.99

        for r in self.reserves_rewards[::-1]:
            R = r + gamma * R
            returns.insert(0, R)
        returns = torch.tensor(returns)
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-9)

        for log_prob, R in zip(self.reserves_log_probs, returns):
            if log_prob.requires_grad:
                policy_loss.append(-log_prob * R)

        if policy_loss:
            self.reserves_selection_optimizer.zero_grad()
            policy_loss = torch.stack(policy_loss).sum()
            if not torch.isnan(policy_loss):
                policy_loss.backward()
                torch.nn.utils.clip_grad_norm_(self.reserves_selection_net.parameters(), max_norm=1.0)
                self.reserves_selection_optimizer.step()

        self.reserves_rewards.clear()
        self.reserves_log_probs.clear()

    # --- Checkpointing for HighLevelAgent ---
    def save_checkpoint(self, filepath: str = 'hla_checkpoint.pth') -> None:
        """
        Save the current state of the HighLevelAgent to a checkpoint file.
        """
        checkpoint = {
            'policy_net_state_dict': self.policy_net.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'deployment_zone_net_state_dict': self.deployment_zone_net.state_dict(),
            'deployment_zone_optimizer_state_dict': self.deployment_zone_optimizer.state_dict(),
            'reserves_selection_net_state_dict': self.reserves_selection_net.state_dict(),
            'reserves_selection_optimizer_state_dict': self.reserves_selection_optimizer.state_dict(),
            'unit_deployment_net_state_dict': self.unit_deployment_net.state_dict(),
            'unit_deployment_optimizer_state_dict': self.unit_deployment_optimizer.state_dict(),
            'episode': self.episode,
            'rewards': self.rewards,
            'log_probs': self.log_probs,
            'deployment_rewards': self.deployment_rewards,
            'deployment_log_probs': self.deployment_log_probs,
            'reserves_rewards': self.reserves_rewards,
            'reserves_log_probs': self.reserves_log_probs
        }
        torch.save(checkpoint, filepath)
        logger.info(f"HighLevelAgent checkpoint saved to {filepath}")

    def load_checkpoint(self, filepath: str = 'hla_checkpoint.pth') -> None:
        """
        Load the HighLevelAgent state from a checkpoint file, if available.
        """
        if os.path.exists(filepath):
            checkpoint = torch.load(filepath, weights_only=False)
            
            # Load main policy network (always present)
            if 'policy_net_state_dict' in checkpoint:
                self.policy_net.load_state_dict(checkpoint['policy_net_state_dict'])
            if 'optimizer_state_dict' in checkpoint:
                self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
            
            # Load deployment networks (may not exist in old checkpoints)
            try:
                if 'deployment_zone_net_state_dict' in checkpoint and checkpoint['deployment_zone_net_state_dict']:
                    self.deployment_zone_net.load_state_dict(checkpoint['deployment_zone_net_state_dict'])
                if 'deployment_zone_optimizer_state_dict' in checkpoint and checkpoint['deployment_zone_optimizer_state_dict']:
                    self.deployment_zone_optimizer.load_state_dict(checkpoint['deployment_zone_optimizer_state_dict'])
            except Exception as e:
                logger.warning(f"Could not load deployment zone network from checkpoint: {e}")
                logger.info("Using fresh deployment zone network")
            
            try:
                if 'reserves_selection_net_state_dict' in checkpoint and checkpoint['reserves_selection_net_state_dict']:
                    self.reserves_selection_net.load_state_dict(checkpoint['reserves_selection_net_state_dict'])
                if 'reserves_selection_optimizer_state_dict' in checkpoint and checkpoint['reserves_selection_optimizer_state_dict']:
                    self.reserves_selection_optimizer.load_state_dict(checkpoint['reserves_selection_optimizer_state_dict'])
            except Exception as e:
                logger.warning(f"Could not load reserves selection network from checkpoint: {e}")
                logger.info("Using fresh reserves selection network")
            
            try:
                if 'unit_deployment_net_state_dict' in checkpoint and checkpoint['unit_deployment_net_state_dict']:
                    self.unit_deployment_net.load_state_dict(checkpoint['unit_deployment_net_state_dict'])
                if 'unit_deployment_optimizer_state_dict' in checkpoint and checkpoint['unit_deployment_optimizer_state_dict']:
                    self.unit_deployment_optimizer.load_state_dict(checkpoint['unit_deployment_optimizer_state_dict'])
            except Exception as e:
                logger.warning(f"Could not load unit deployment network from checkpoint: {e}")
                logger.info("Using fresh unit deployment network")
            
            # Load other state
            self.episode = checkpoint.get('episode', 0)
            self.rewards = checkpoint.get('rewards', [])
            self.log_probs = checkpoint.get('log_probs', [])
            self.deployment_rewards = checkpoint.get('deployment_rewards', [])
            self.deployment_log_probs = checkpoint.get('deployment_log_probs', [])
            self.reserves_rewards = checkpoint.get('reserves_rewards', [])
            self.reserves_log_probs = checkpoint.get('reserves_log_probs', [])
            
            logger.info(f"HighLevelAgent checkpoint loaded from {filepath}")
        else:
            logger.info("No checkpoint found for HighLevelAgent. Starting with fresh state.")

    def handle_deployment_phase(self, is_attacker: bool, available_zones: List[dict]) -> dict:
        """Handle the complete deployment phase according to Warhammer 40k rules."""
        deployment_results = {
            'selected_zone': None,
            'reserves_decisions': {},
            'unit_positions': {},
            'deployment_order': []
        }
        
        # Step 1: Choose deployment zone (if defender)
        if not is_attacker:
            deployment_results['selected_zone'] = self.choose_deployment_zone(available_zones)
        else:
            # Attacker gets the remaining zone
            deployment_results['selected_zone'] = available_zones[0]
        
        # Step 2: Declare reserves and strategic reserves
        deployment_results['reserves_decisions'] = self.declare_reserves()
        
        # Step 3: Prepare for alternating deployment
        units_to_deploy = [unit for unit in self.player.get_army().units 
                          if deployment_results['reserves_decisions'].get(unit.name, 'deploy') == 'deploy']
        
        deployment_results['deployment_order'] = units_to_deploy
        
        return deployment_results
    
    def choose_deployment_zone(self, available_zones: List[dict]) -> dict:
        """Choose deployment zone as the defender."""
        state = self.extract_deployment_zone_features(available_zones)
        probs = self.deployment_zone_net(state)
        
        # Check for NaN values
        if torch.isnan(probs).any():
            throttled_warning("Warning: NaN values in deployment zone selection, using random choice")
            zone_idx = 0  # Default to first zone
        else:
            zone_dist = torch.distributions.Categorical(probs)
            zone_idx = zone_dist.sample().item()
            self.deployment_log_probs.append(zone_dist.log_prob(torch.tensor(zone_idx)))
        
        return available_zones[min(zone_idx, len(available_zones) - 1)]
    
    def declare_reserves(self) -> dict:
        """Decide which units go into reserves, strategic reserves, or deploy normally.
        
        Enforces Warhammer 40k 10th Edition reserve limits:
        - Maximum 50% of units can be in reserves
        - Maximum 50% of army points can be in reserves
        """
        reserves_decisions = {}
        total_units = len(self.player.get_army().units)
        max_reserve_units = total_units // 2  # 50% unit limit
        
        # Calculate total army points and max reserve points
        total_points = sum(unit.get_unit_cost() for unit in self.player.get_army().units)
        max_reserve_points = total_points // 2  # 50% points limit
        
        current_reserve_units = 0
        current_reserve_points = 0
        
        # Sort units by AI preference for reserves (evaluate all first, then decide)
        unit_preferences = []
        
        for unit in self.player.get_army().units:
            state = self.extract_reserves_decision_features(unit)
            probs = self.reserves_selection_net(state)
            
            if torch.isnan(probs).any():
                # Default preference: deploy normally
                preference_scores = [0.8, 0.1, 0.1]  # [deploy, reserves, strategic]
            else:
                # Apply bias toward deploying units (especially for untrained networks)
                deploy_bias = torch.tensor([0.7, 0.2, 0.1])
                biased_probs = probs * 0.3 + deploy_bias * 0.7
                preference_scores = biased_probs.tolist()
            
            # Calculate preference for reserves (reserves + strategic reserves)
            reserves_preference = preference_scores[1] + preference_scores[2]
            
            unit_preferences.append({
                'unit': unit,
                'reserves_preference': reserves_preference,
                'preference_scores': preference_scores,
                'points': unit.get_unit_cost()
            })
        
        # Sort by reserves preference (highest first)
        unit_preferences.sort(key=lambda x: x['reserves_preference'], reverse=True)
        
        # Make decisions while respecting limits
        for unit_data in unit_preferences:
            unit = unit_data['unit']
            preference_scores = unit_data['preference_scores']
            unit_points = unit_data['points']
            
            # Check if we can still put units in reserves
            can_reserve = (current_reserve_units < max_reserve_units and 
                          current_reserve_points + unit_points <= max_reserve_points)
            
            if can_reserve:
                # AI can choose freely
                decision_dist = torch.distributions.Categorical(torch.tensor(preference_scores))
                decision_idx = decision_dist.sample().item()
                self.reserves_log_probs.append(decision_dist.log_prob(torch.tensor(decision_idx)))
                
                decisions = ['deploy', 'reserves', 'strategic_reserves']
                decision = decisions[decision_idx]
                
                # Update counters if unit goes to reserves
                if decision in ['reserves', 'strategic_reserves']:
                    current_reserve_units += 1
                    current_reserve_points += unit_points
            else:
                # Force deployment due to reserve limits
                decision = 'deploy'
                # Still log the decision for learning (with forced deploy probability)
                forced_probs = torch.tensor([1.0, 0.0, 0.0])  # 100% deploy
                decision_dist = torch.distributions.Categorical(forced_probs)
                self.reserves_log_probs.append(decision_dist.log_prob(torch.tensor(0)))  # log prob of deploy
            
            reserves_decisions[unit.name] = decision
        
        # Log reserve allocation for debugging
        total_reserves = sum(1 for d in reserves_decisions.values() if d != 'deploy')
        logger.debug(f"🏗️ {self.player.name} reserves: {total_reserves}/{max_reserve_units} units, "
                    f"{current_reserve_points}/{max_reserve_points} points")
        
        return reserves_decisions
    
    def choose_unit_deployment_position(self, unit: 'Unit', deployment_zone: dict, 
                                       already_deployed: List['Unit']) -> Tuple[float, float]:
        """Choose where to deploy a specific unit within the deployment zone."""
        state = self.extract_unit_deployment_features(unit, deployment_zone, already_deployed)
        probs = self.unit_deployment_net(state)
        
        if torch.isnan(probs).any():
            throttled_warning(f"Warning: NaN values in unit deployment for {unit.name}")
            # Default to center of deployment zone
            x_center = (deployment_zone['x_range'][0] + deployment_zone['x_range'][1]) / 2
            y_center = (deployment_zone['y_range'][0] + deployment_zone['y_range'][1]) / 2
            return x_center, y_center
        
        position_dist = torch.distributions.Categorical(probs)
        position_idx = position_dist.sample().item()
        self.deployment_log_probs.append(position_dist.log_prob(torch.tensor(position_idx)))
        
        # Convert position index to actual coordinates
        return self.index_to_coordinates(position_idx, deployment_zone)
    
    def extract_deployment_zone_features(self, available_zones: List[dict]) -> torch.Tensor:
        """Extract features for deployment zone selection."""
        features = []
        
        for zone in available_zones[:2]:  # Max 2 zones
            x_start, x_end = zone['x_range']
            y_start, y_end = zone['y_range']
            features.extend([x_start, x_end, y_start, y_end])
            
            # Calculate distance to objectives
            zone_center_x = (x_start + x_end) / 2
            zone_center_y = (y_start + y_end) / 2
            
            avg_obj_distance = 0
            if self.objectives:
                total_distance = sum(
                    get_dist(
                        obj.location.x - zone_center_x,
                        obj.location.y - zone_center_y,
                        obj.location.z - 0
                    ) for obj in self.objectives
                )
                avg_obj_distance = total_distance / len(self.objectives)
            
            features.append(avg_obj_distance)
        
        # Pad if only one zone
        while len(features) < 12:
            features.append(0.0)
            
        return torch.tensor(features, dtype=torch.float32)
    
    def extract_reserves_decision_features(self, unit: 'Unit') -> torch.Tensor:
        """Extract features for deciding whether to put a unit in reserves."""
        features = []
        
        # Unit characteristics
        features.append(unit.movement)
        features.append(len(unit.models))
        features.append(unit.get_max_weapon_range())
        features.append(unit.toughness)
        features.append(unit.save)
        
        # Tactical considerations
        features.append(1.0 if unit.has_deep_strike() else 0.0)
        
        # Scout ability and normalized distance for deployment considerations
        has_scout_ability, scout_distance = unit.has_scout()
        features.append(1.0 if has_scout_ability else 0.0)
        features.append(unit.get_scout_distance_normalized())
        
        # TODO - add more tactical considerations (e.g., has_infiltrate(), has_lone_operative(), etc.)
        features.append(1.0 if unit.is_character else 0.0)
        features.append(1.0 if unit.is_vehicle else 0.0)
        
        # Game state
        features.append(len(self.objectives))
        features.append(len(self.opponent.get_army().units))
        
        # Mission considerations
        battlefield_width, battlefield_height = self.game.get_battlefield_size()
        features.extend([battlefield_width, battlefield_height])
        
        # Enemy threat assessment
        enemy_ranged_threat = sum(1 for enemy_unit in self.opponent.get_army().units 
                                if enemy_unit.get_max_weapon_range() > 24)
        features.append(enemy_ranged_threat)
        
        # Pad to expected size (increased from 15 to 17 due to scout features)
        while len(features) < 17:
            features.append(0.0)
            
        return torch.tensor(features, dtype=torch.float32)
    
    def extract_unit_deployment_features(self, unit: 'Unit', deployment_zone: dict, 
                                       already_deployed: List['Unit']) -> torch.Tensor:
        """Extract features for unit deployment position selection."""
        features = []
        
        # Unit characteristics
        features.append(unit.movement)
        features.append(len(unit.models))
        features.append(unit.get_max_weapon_range())
        
        # Deployment zone info
        x_start, x_end = deployment_zone['x_range']
        y_start, y_end = deployment_zone['y_range']
        features.extend([x_start, x_end, y_start, y_end])
        
        # Objective distances from zone center
        zone_center_x = (x_start + x_end) / 2
        zone_center_y = (y_start + y_end) / 2
        
        for obj in self.objectives[:3]:  # Max 3 objectives
            distance = get_dist(
                obj.location.x - zone_center_x,
                obj.location.y - zone_center_y,
                obj.location.z - 0
            )
            features.append(distance)
        
        # Pad objectives
        while len(features) < 13:
            features.append(0.0)
        
        # Already deployed units consideration
        features.append(len(already_deployed))
        
        # Enemy positions (if visible)
        enemy_positions = []
        for enemy_unit in self.opponent.get_army().units:
            if enemy_unit.deployed:
                enemy_pos = enemy_unit.get_position()
                enemy_positions.extend([enemy_pos[0], enemy_pos[1]])
                if len(enemy_positions) >= 4:  # Limit to 2 enemy positions
                    break
        
        # Pad enemy positions
        while len(enemy_positions) < 4:
            enemy_positions.append(0.0)
        features.extend(enemy_positions)
        
        # Pad to expected size
        while len(features) < 20:
            features.append(0.0)
            
        return torch.tensor(features, dtype=torch.float32)
    
    def index_to_coordinates(self, position_idx: int, deployment_zone: dict) -> Tuple[float, float]:
        """Convert a position index to actual coordinates within the deployment zone."""
        x_start, x_end = deployment_zone['x_range']
        y_start, y_end = deployment_zone['y_range']
        
        # Create a 10x10 grid within the deployment zone
        grid_size = 10
        row = position_idx // grid_size
        col = position_idx % grid_size
        
        x_step = (x_end - x_start) / grid_size
        y_step = (y_end - y_start) / grid_size
        
        x = x_start + (col + 0.5) * x_step
        y = y_start + (row + 0.5) * y_step
        
        return x, y
    
    def compute_deployment_reward(self, deployment_results: dict) -> float:
        """Compute reward based on deployment quality."""
        reward = 0.0
        
        # Reward for good zone selection (if defender)
        if deployment_results.get('selected_zone'):
            zone = deployment_results['selected_zone']
            zone_center_x = (zone['x_range'][0] + zone['x_range'][1]) / 2
            zone_center_y = (zone['y_range'][0] + zone['y_range'][1]) / 2
            
            # Reward proximity to objectives
            for obj in self.objectives:
                distance = get_dist(
                    obj.location.x - zone_center_x,
                    obj.location.y - zone_center_y,
                    obj.location.z - 0
                )
                # Closer to objectives is better
                reward += max(0, 10 - distance * 0.5)
        
        # Reward for smart reserves decisions
        reserves_decisions = deployment_results.get('reserves_decisions', {})
        for unit_name, decision in reserves_decisions.items():
            unit = next((u for u in self.player.get_army().units if u.name == unit_name), None)
            if unit:
                if decision == 'reserves' and unit.has_deep_strike():
                    reward += 2.0  # Good decision to put deep strike unit in reserves
                elif decision == 'deploy' and not unit.has_deep_strike():
                    reward += 1.0  # Good decision to deploy normal unit
                    
                # Reward for deploying Scout units (they benefit from pre-game movement)
                has_scout_ability, scout_distance = unit.has_scout()
                if decision == 'deploy' and has_scout_ability:
                    # Reward deploying scout units normally, scaled by scout distance
                    reward += 1.5 * unit.get_scout_distance_normalized()
                elif decision == 'reserves' and has_scout_ability:
                    # Small penalty for putting scout units in reserves (they lose scout benefit)
                    reward -= 0.5 * unit.get_scout_distance_normalized()
        
        return reward


###############################################################################
# TacticalAgent
###############################################################################
class TacticalAgent:
    """Tactical Layer: Handles per-phase unit actions."""
    def __init__(self, game: Game, player: Player, learning_rate=0.01, ui_interface=None) -> None:
        self.game = game
        self.player = player
        self.ui_interface = ui_interface

        # Policy networks and optimizers for different phases
        self.movement_policy_net = PolicyNetwork(input_size=self.get_movement_state_size(), output_size=NUM_MOVEMENT_ACTIONS)
        self.movement_optimizer = optim.Adam(self.movement_policy_net.parameters(), lr=learning_rate)
        self.shooting_policy_net = PolicyNetwork(input_size=self.get_shooting_state_size(), output_size=self.get_shooting_action_size())
        self.shooting_optimizer = optim.Adam(self.shooting_policy_net.parameters(), lr=learning_rate)
        self.profile_selection_policy_net = PolicyNetwork(input_size=self.get_profile_selection_state_size(), output_size=self.get_profile_selection_action_size())
        self.profile_selection_optimizer = optim.Adam(self.profile_selection_policy_net.parameters(), lr=learning_rate)
        # Fight phase networks
        self.fight_target_policy_net = PolicyNetwork(input_size=self.get_fight_state_size(), output_size=self.get_fight_action_size())
        self.fight_target_optimizer = optim.Adam(self.fight_target_policy_net.parameters(), lr=learning_rate)
        self.fight_profile_selection_policy_net = PolicyNetwork(input_size=self.get_profile_selection_state_size(), output_size=self.get_profile_selection_action_size())
        self.fight_profile_selection_optimizer = optim.Adam(self.fight_profile_selection_policy_net.parameters(), lr=learning_rate)

        # Store rewards and log probabilities for training
        self.movement_rewards = []
        self.movement_log_probs = []
        self.shooting_rewards = []
        self.shooting_log_probs = []
        self.profile_selection_rewards = []
        self.profile_selection_log_probs = []
        # Fight phase rewards and log probs
        self.fight_target_rewards = []
        self.fight_target_log_probs = []
        self.fight_profile_selection_rewards = []
        self.fight_profile_selection_log_probs = []

    def command_phase(self, command: str) -> None:
        """Execute high-level commands or stratagems."""
        self.game.event_system.publish("command_phase_start", game_state=self.game.get_state())
        for unit in self.player.army.get_active_units():
            # Apply abilities or buffs here (e.g., stratagems)
            logger.info(f"Commanding {unit.name}")
        self.game.event_system.publish("command_phase_end", game_state=self.game.get_state())

    ###########################################################################
    # Movement Phase
    ###########################################################################
    def movement_phase(self, unit: Unit, objective: Objective) -> None:
        """Decide on movement actions for the unit and execute them."""
        if not unit.deployed or not unit.is_alive():
            return

        logger.info(f"🚶 {self.player.name}: {unit.name} making movement decision")

        state = unit.get_engagement_state(self.game.map)
        available_actions = unit.get_available_move_actions(state)

        # Agent decides on the action
        chosen_action_idx = self.choose_movement_action(unit, available_actions, objective)
        
        # Convert action index back to MovementAction enum
        chosen_action = MovementAction(chosen_action_idx)
        
        # Decide on the destination
        destination = self.calculate_destination(unit, chosen_action, objective)

        # Record the previous distance to the objective
        unit_position_before = unit.get_position()
        dx_before = objective.location.x - unit_position_before[0]
        dy_before = objective.location.y - unit_position_before[1]
        dz_before = objective.location.z - unit_position_before[2]
        distance_before = get_dist(dx_before, dy_before, dz_before)

        # Assess shooting opportunities before movement
        shooting_opportunity_score = self.assess_shooting_opportunities(unit)
        
        # Execute the movement (unit expects the integer value)
        unit.do_move_action(chosen_action_idx, destination, self.game.map)

        # Record the new distance to the objective
        unit_position_after = unit.get_position()
        dx_after = objective.location.x - unit_position_after[0]
        dy_after = objective.location.y - unit_position_after[1]
        dz_after = objective.location.z - unit_position_after[2]
        distance_after = get_dist(dx_after, dy_after, dz_after)

        # Compute the basic movement reward (positive if unit moved closer)
        movement_reward = MOVEMENT_REWARD_SCALING * (distance_before - distance_after)
        
        # Apply shooting opportunity penalty for advancing
        if chosen_action == MovementAction.ADVANCE and shooting_opportunity_score > 0.5:
            # Heavy penalty for advancing when good shooting opportunities exist
            shooting_penalty = -2.0 * MOVEMENT_REWARD_SCALING * shooting_opportunity_score
            logger.info(f"{unit.name} chose to ADVANCE despite shooting opportunities (penalty: {shooting_penalty:.2f})")
        elif chosen_action == MovementAction.MOVE and shooting_opportunity_score > 0.5:
            # Small bonus for choosing MOVE when shooting opportunities exist
            shooting_penalty = 0.5 * MOVEMENT_REWARD_SCALING * shooting_opportunity_score
            logger.info(f"{unit.name} chose to MOVE preserving shooting opportunities (bonus: {shooting_penalty:.2f})")
        else:
            shooting_penalty = 0.0
        
        # Total reward combines movement and shooting considerations
        reward = movement_reward + shooting_penalty
        
        logger.info(f"Movement reward: {movement_reward:.2f}, Shooting adjustment: {shooting_penalty:.2f}, Total: {reward:.2f}")
        logger.info(f"Distance before: {distance_before:.1f}, Distance after: {distance_after:.1f}, Shooting score: {shooting_opportunity_score:.2f}")
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

        # Check for NaN values in network output
        if torch.isnan(action_probs).any():
            throttled_warning("Warning: NaN values detected in movement policy network output, using uniform distribution")
            action_probs = torch.ones_like(action_probs)

        # Mask unavailable actions
        action_mask = torch.zeros(NUM_MOVEMENT_ACTIONS)
        for action in available_actions:
            action_mask[action - 1] = 1  # Subtract 1 because enum values start at 1, but indices start at 0
        
        # Apply mask and normalize
        masked_probs = action_probs * action_mask
        prob_sum = masked_probs.sum()
        
        # Handle zero sum or NaN cases
        if prob_sum == 0 or torch.isnan(prob_sum):
            throttled_warning("Warning: Invalid probability sum detected, using uniform distribution over valid movement actions")
            masked_probs = action_mask / action_mask.sum()
        else:
            masked_probs = masked_probs / prob_sum
        
        # Final check for NaN values
        if torch.isnan(masked_probs).any():
            throttled_warning("Warning: NaN values after normalization, falling back to uniform distribution")
            masked_probs = action_mask / action_mask.sum()

        # Create a categorical distribution
        action_dist = torch.distributions.Categorical(masked_probs)
        action_idx = action_dist.sample()

        # Store log probability
        self.movement_log_probs.append(action_dist.log_prob(action_idx))
        
        # Convert back to enum value (add 1 because enum values start at 1)
        enum_value = action_idx.item() + 1
        return enum_value

    def extract_movement_state_features(self, unit: Unit, objective: Objective) -> torch.Tensor:
        features = []
        unit_pos = unit.get_position()
        features.extend([unit_pos[0], unit_pos[1], unit_pos[2]])
        obj_pos = (objective.location.x, objective.location.y, objective.location.z)
        features.extend([obj_pos[0], obj_pos[1], obj_pos[2]])
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

    def assess_shooting_opportunities(self, unit: Unit) -> float:
        """
        Assess the quality of shooting opportunities for a unit.
        Returns a score from 0.0 (no opportunities) to 1.0 (excellent opportunities).
        """
        logger.info(f"🎯 Assessing shooting opportunities for {unit.name}")
        
        if not unit.is_alive() or not unit.deployed:
            logger.debug(f"{unit.name} not alive or not deployed")
            return 0.0
            
        total_opportunity_score = 0.0
        model_count = 0
        
        # Evaluate shooting opportunities for each model in the unit
        for model in unit.models:
            if not model.is_alive:
                continue
                
            model_count += 1
            model_shooting_score = 0.0
            weapon_count = 0
            
            # Check each ranged weapon the model has
            for wargear_item in model.wargear:
                # Skip melee weapons
                if wargear_item.is_melee():
                    continue
                    
                weapon_count += 1
                
                # Find the best profile for this weapon
                best_profile = None
                best_range = 0
                for profile in wargear_item.profiles.values():
                    if hasattr(profile, 'range') and profile.range.max > best_range:
                        best_profile = profile
                        best_range = profile.range.max
                
                if not best_profile:
                    continue
                
                # Find targets within range
                try:
                    targets = model.find_targets_in_range(self.game.map, wargear_profile=best_profile)
                    # Filter out destroyed units
                    targets = [target for target in targets if target.is_alive()]
                    
                    # Debug: Print detailed position and distance information
                    model_pos = model.get_location()
                    logger.info(f"DEBUG: {unit.name} model {model.name} at position ({model_pos[0]:.1f}, {model_pos[1]:.1f}, {model_pos[2]:.1f})")
                    logger.info(f"DEBUG: Weapon {wargear_item.name} ({best_profile.name}) has range {best_profile.range.max}")
                    
                    # Check all enemy units and their distances
                    enemy_units = self.game.map.get_enemy_units(unit)
                    logger.info(f"DEBUG: Found {len(enemy_units)} enemy units total")
                    
                    # Debug: Print parent army information
                    logger.info(f"DEBUG: Unit {unit.name} belongs to army ID: {id(unit.get_parent_army())} (Player: {getattr(unit.get_parent_army(), 'player', 'Unknown') if unit.get_parent_army() else 'None'})")
                    
                    # Show all units on the map and their army assignments
                    map_units = self.game.map.units
                    logger.info(f"DEBUG: Total units on map: {len(map_units)}")
                    for i, map_unit in enumerate(map_units):
                        logger.info(f"DEBUG:   Map unit {i+1}: {map_unit.name} - Army ID: {id(map_unit.get_parent_army())} (Player: {getattr(map_unit.get_parent_army(), 'player', 'Unknown') if map_unit.get_parent_army() else 'None'})")
                    
                    for i, enemy_unit in enumerate(enemy_units):
                        if not enemy_unit.is_alive():
                            continue
                        enemy_pos = enemy_unit.get_position()
                        distance = ((model_pos[0] - enemy_pos[0])**2 + (model_pos[1] - enemy_pos[1])**2 + (model_pos[2] - enemy_pos[2])**2)**0.5
                        in_range = distance <= best_profile.range.max
                        logger.info(f"DEBUG:   Enemy {i+1}: {enemy_unit.name} at ({enemy_pos[0]:.1f}, {enemy_pos[1]:.1f}, {enemy_pos[2]:.1f}) - Distance: {distance:.1f}\" - In Range: {in_range}")
                    
                    logger.info(f"DEBUG: {unit.name} model {model.name} with {wargear_item.name} (range {best_profile.range.max}) found {len(targets)} targets")
                    
                    if targets:
                        # Score based on number and quality of targets
                        target_score = min(1.0, len(targets) / 3.0)  # Normalize to max 1.0
                        
                        # Bonus for closer targets (easier to hit)
                        closest_target_distance = min(
                            get_dist(
                                target.get_position()[0] - model.get_location()[0],
                                target.get_position()[1] - model.get_location()[1],
                                target.get_position()[2] - model.get_location()[2]
                            ) for target in targets
                        )
                        # Higher score for closer targets (within half range gets bonus)
                        distance_score = max(0.0, 1.0 - (closest_target_distance / (best_profile.range.max * 0.5)))
                        
                        weapon_opportunity_score = (target_score + distance_score) / 2.0
                        model_shooting_score = max(model_shooting_score, weapon_opportunity_score)
                        
                        logger.info(f"DEBUG:   Closest target at {closest_target_distance:.1f}\", score: {weapon_opportunity_score:.2f}")
                        
                    else:
                        logger.info(f"DEBUG: {unit.name} model {model.name} with {wargear_item.name} found NO targets")
                        
                except Exception as e:
                    # If target finding fails, assume no opportunities
                    logger.error(f"Error assessing shooting opportunities for {model.name}: {e}")
                    continue
            
            # If model has ranged weapons, add its score
            if weapon_count > 0:
                total_opportunity_score += model_shooting_score
            else:
                logger.debug(f"{unit.name} has no ranged weapons")
        
        # Average opportunity score across all models with ranged weapons
        if model_count > 0:
            final_score = total_opportunity_score / model_count
            result = min(1.0, final_score)  # Cap at 1.0
            logger.debug(f"{unit.name} final shooting opportunity score: {result:.2f}")
            return result
        
        logger.debug(f"{unit.name} has no models")
        return 0.0

    ###########################################################################
    # Shooting Phase
    ###########################################################################
    def choose_shooting_target(self, model: Model, profile: WargearProfile, targets: List[Unit]) -> int:
        """Choose a target for the model's weapon/profile."""
        state = self.extract_shooting_state_features(model, profile, targets)
        action_probs = self.shooting_policy_net(state)

        # Check for NaN values in network output
        if torch.isnan(action_probs).any():
            throttled_warning("Warning: NaN values detected in shooting policy network output, using uniform distribution")
            action_probs = torch.ones_like(action_probs)

        # Mask unavailable targets
        action_mask = torch.zeros(self.get_shooting_action_size())
        num_targets = min(len(targets), MAX_TARGETS)
        for idx in range(num_targets):
            action_mask[idx] = 1
        
        # Apply mask and normalize
        masked_probs = action_probs * action_mask
        prob_sum = masked_probs.sum()
        
        # Handle zero sum or NaN cases
        if prob_sum == 0 or torch.isnan(prob_sum):
            throttled_warning("Warning: Invalid probability sum detected, using uniform distribution over valid targets")
            masked_probs = action_mask / action_mask.sum()
        else:
            masked_probs = masked_probs / prob_sum
        
        # Final check for NaN values
        if torch.isnan(masked_probs).any():
            throttled_warning("Warning: NaN values after normalization, falling back to uniform distribution")
            masked_probs = action_mask / action_mask.sum()

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
            return profiles[0]
        state = self.extract_profile_selection_state(model, wargear_item, profiles)
        action_probs = self.profile_selection_policy_net(state)

        # Check for NaN values in network output
        if torch.isnan(action_probs).any():
            throttled_warning("Warning: NaN values detected in profile selection policy network output, using uniform distribution")
            action_probs = torch.ones_like(action_probs)

        # Mask unavailable profiles
        action_mask = torch.zeros(self.get_profile_selection_action_size())
        num_profiles = min(len(profiles), MAX_PROFILES)
        for idx in range(num_profiles):
            action_mask[idx] = 1
        
        # Apply mask and normalize
        masked_probs = action_probs * action_mask
        prob_sum = masked_probs.sum()
        
        # Handle zero sum or NaN cases
        if prob_sum == 0 or torch.isnan(prob_sum):
            throttled_warning("Warning: Invalid probability sum detected, using uniform distribution over valid profiles")
            masked_probs = action_mask / action_mask.sum()
        else:
            masked_probs = masked_probs / prob_sum
        
        # Final check for NaN values
        if torch.isnan(masked_probs).any():
            throttled_warning("Warning: NaN values after normalization, falling back to uniform distribution")
            masked_probs = action_mask / action_mask.sum()

        # Create a categorical distribution for profile selection
        profile_dist = torch.distributions.Categorical(masked_probs)
        profile_idx = profile_dist.sample()

        # Store log probability
        self.profile_selection_log_probs.append(profile_dist.log_prob(profile_idx))
        return profiles[profile_idx.item()]

    def extract_profile_selection_state(self, model: Model, wargear_item, profiles: List[WargearProfile]) -> torch.Tensor:
        """Extract state features for selecting a weapon profile."""
        features = []
        model_pos = model.get_location()
        features.extend([model_pos[0], model_pos[1], model_pos[2]])
        features.append(model.health_percent)
        for profile in profiles[:MAX_PROFILES]:
            features.append(profile.range.max)
            features.append(profile.attacks.stat_average())
            features.append(profile.strength.stat_average() if type(profile.strength) == DiceCollection else profile.strength)
            features.append(profile.ap.stat_average() if type(profile.ap) == DiceCollection else profile.ap)
            features.append(profile.damage.stat_average() if type(profile.damage) == DiceCollection else profile.damage)
        num_profiles = len(profiles)
        if num_profiles < MAX_PROFILES:
            padding = [0.0] * ((MAX_PROFILES - num_profiles) * 5)
            features.extend(padding)

        # Add other relevant features if necessary

        # Convert to tensor
        state = torch.tensor([features], dtype=torch.float32)  # Batch dimension

        return state

    def extract_shooting_state_features(self, model: Model, profile: WargearProfile, targets: List[Unit]) -> torch.Tensor:
        """Extract state features for shooting decision."""
        features = []
        model_pos = model.get_location()
        features.extend([model_pos[0], model_pos[1], model_pos[2]])
        features.append(model.health_percent)
        for enemy in targets[:MAX_TARGETS]:
            features.append(profile.get_damage_potential(enemy))
            enemy_pos = enemy.get_position()
            features.extend([enemy_pos[0], enemy_pos[1], enemy_pos[2]])
            features.append(enemy.health_percent)
        num_targets = len(targets)
        if num_targets < MAX_TARGETS:
            padding = [0.0] * ((MAX_TARGETS - num_targets) * 5)
            features.extend(padding)

        # Convert to tensor
        state = torch.tensor([features], dtype=torch.float32)  # Batch dimension

        return state

    def get_profile_selection_state_size(self) -> int:
        """Calculate the size of the profile selection state vector."""
        # 4 features for the model (x, y, z, health)
        # 5 features per profile * MAX_PROFILES
        return 4 + (MAX_PROFILES * 5)

    def get_profile_selection_action_size(self) -> int:
        """Define the number of possible profiles to select from."""
        return MAX_PROFILES

    def get_shooting_state_size(self) -> int:
        """Calculate the size of the target selection state vector."""
        # 4 features for the model (x, y, z, health)
        # 5 features per target (damage potential, x, y, z, health) * MAX_TARGETS
        return 4 + (MAX_TARGETS * 5)

    def get_shooting_action_size(self) -> int:
        """Define the number of possible targets to select from."""
        return MAX_TARGETS

    def shooting_phase(self, unit: Unit) -> None:
        """Select targets and resolve shooting attacks for each model in the unit."""
        if not unit.deployed or not unit.is_alive():
            return

        self.game.event_system.publish("shooting_phase_start", unit=unit, game_state=self.game.get_state())
        if unit.round_state.fell_back_this_round:
            logger.info(f"{unit.name} cannot shoot after falling back.")
            return

        # Check if unit is within engagement range of any enemy
        unit_position = unit.get_position()
        enemy_units = self.game.map.get_enemy_units(unit)
        in_engagement_range = any(
            self.game.map.is_within_engagement_range(unit_position, enemy_unit) 
            for enemy_unit in enemy_units if enemy_unit.is_alive()
        )

        for model in unit.models:
            if not model.is_alive:
                continue
            
            for wargear_item in model.wargear:
                # Decide which profile to use if the weapon has multiple profiles
                selected_profile = self.choose_weapon_profile(model, wargear_item)
                if selected_profile is None:
                    continue
                
                # Skip if unit advanced and cannot shoot after advancing
                if unit.round_state.advanced_this_round and not unit.can_shoot_after_advance(selected_profile):
                    logger.debug(f"{model.name} cannot shoot {wargear_item.name} ({selected_profile.name}) - advanced and not allowed to shoot")
                    continue
                
                # Skip if in engagement range and cannot shoot in engagement
                if in_engagement_range and not unit.can_shoot_in_engagement_range(selected_profile):
                    logger.debug(f"{model.name} cannot shoot {wargear_item.name} ({selected_profile.name}) - in engagement range and not allowed to shoot")
                    continue
                    
                targets = model.find_targets_in_range(self.game.map, wargear_profile=selected_profile)
                
                # Filter out destroyed units
                targets = [target for target in targets if target.is_alive()]
                
                # Filter out targets that are in engagement range with friendly units
                valid_targets = []
                for target in targets:
                    # Skip if target is in engagement range with any friendly unit
                    target_in_engagement = False
                    for friendly_unit in self.game.map.get_friendly_units(unit):
                        if friendly_unit != unit and friendly_unit.is_alive():
                            if self.game.map.is_within_engagement_range(friendly_unit.get_position(), target):
                                target_in_engagement = True
                                break
                    
                    # Allow target if:
                    # 1. Not in engagement range with friendly units, OR
                    # 2. Weapon is Indirect Fire, OR
                    # 3. Unit is in engagement range and weapon is Pistol
                    if not target_in_engagement or selected_profile.is_indirect_fire() or (in_engagement_range and selected_profile.is_pistol()):
                        # Additional check for Blast weapons
                        if selected_profile.is_blast() and target_in_engagement:
                            logger.debug(f"{model.name} cannot use Blast weapon {wargear_item.name} against {target.name} - target is in engagement range")
                            continue
                            
                        # Check if unit can shoot at this specific target while engaged
                        if not unit.can_shoot_at_target_while_engaged(target, selected_profile, self.game.map):
                            logger.debug(f"{model.name} cannot shoot at {target.name} with {wargear_item.name} ({selected_profile.name}) - engaged and not allowed to shoot at other targets")
                            continue
                            
                        valid_targets.append(target)
                
                if valid_targets:
                    # Agent decides on the target
                    target_idx = self.choose_shooting_target(model, selected_profile, valid_targets)
                    target = valid_targets[target_idx]

                    # Double-check that target is still alive before attacking
                    if not target.is_alive():
                        logger.info(f"Target {target.name} was destroyed before attack could be executed")
                        reward = -0.5 * SHOOTING_REWARD_SCALING
                        self.profile_selection_rewards.append(reward)
                        self.shooting_rewards.append(reward)
                        continue

                    # Record the target's health before attack
                    target_health_before = target.health_percent

                    # Execute the attack
                    logger.info(f"{model.name} of {unit.name} shoots at {target.name} with {wargear_item.name} ({selected_profile.name})")
                    try:
                        model.ranged_attack(target, selected_profile)
                    except Exception as e:
                        logger.error(f"Error during ranged attack: {e}")
                        reward = -1.0 * SHOOTING_REWARD_SCALING
                        self.profile_selection_rewards.append(reward)
                        self.shooting_rewards.append(reward)
                        continue

                    # Record the target's health after attack
                    target_health_after = target.health_percent

                    # Compute the reward (damage inflicted)
                    damage = target_health_before - target_health_after
                    reward = SHOOTING_REWARD_SCALING * damage
                    self.profile_selection_rewards.append(reward)
                    self.shooting_rewards.append(reward)
                else:
                    reward = -1.0 * SHOOTING_REWARD_SCALING
                    self.profile_selection_rewards.append(reward)
                    self.shooting_rewards.append(reward)

        self.game.event_system.publish("shooting_phase_end", unit=unit, game_state=self.game.get_state())

    ###########################################################################
    # Charge Phase
    ###########################################################################
    def charge_phase(self, unit: Unit) -> None:
        """Identify nearby targets and charge."""
        if not unit.deployed or not unit.is_alive():
            return None

        self.game.event_system.publish("charge_phase_start", unit=unit, game_state=self.game.get_state())
        enemy_units = self.game.get_enemy_units(self.player)
        chargeable_targets = [enemy for enemy in enemy_units if unit.can_declare_charge_against(enemy, self.game)]
        if not chargeable_targets:
            return None

        # Select target with highest value-to-risk ratio
        charge_target = max(
            chargeable_targets,
            key=lambda target: target.get_threat_value() / (1 + target.get_overwatch_risk(unit, self.game))
        )

        self.game.event_system.publish("charge_declared", unit=unit, target=charge_target)
        success = self.game.attempt_charge(unit, charge_target)
        self.game.event_system.publish("charge_result", unit=unit, target=charge_target, success=success)
        self.game.event_system.publish("charge_phase_end", unit=unit, game_state=self.game.get_state())

        if success:
            return CHARGE_REWARD_SCALING * charge_target.get_threat_value()
        else:
            return -CHARGE_REWARD_SCALING * 2  # Penalize failed charges

    ###########################################################################
    # Fight Phase
    ###########################################################################
    def execute_fight_phase(self, current_player: Player, opponent_player: Player) -> None:
        """Execute the complete Fight Phase with proper two-stage structure.
        
        The Fight Phase consists of two sub-stages:
        1. Fight First Stage - Units with Fight First abilities or that charged
        2. Remaining Combatants Stage - All other eligible units
        
        Within each stage, players alternate selecting units to fight.
        """
        self.game.event_system.publish("fight_phase_start", game_state=self.game.get_state())
        
        # Execute Fight First Stage
        self._execute_fight_first_stage(current_player, opponent_player)
        
        # Execute Remaining Combatants Stage
        self._execute_remaining_combatants_stage(current_player, opponent_player)
        
        self.game.event_system.publish("fight_phase_end", game_state=self.game.get_state())
    
    def _execute_fight_first_stage(self, current_player: Player, opponent_player: Player) -> None:
        """Execute the Fight First stage of the Fight Phase."""
        print("⚔️ Starting Fight First Stage")
        
        # Get Fight First units for both players
        current_player_units = self.game.get_fight_first_units(current_player)
        opponent_units = self.game.get_fight_first_units(opponent_player)
        
        if not current_player_units and not opponent_units:
            print("📋 No units with Fight First abilities or charges this turn")
            return
        
        # Fight First stage: units that charged or have Fight First abilities
        # Players alternate selecting units to fight
        self._execute_alternating_fights(current_player, opponent_player, 
                                       current_player_units, opponent_units, 
                                       "Fight First")
    
    def _execute_remaining_combatants_stage(self, current_player: Player, opponent_player: Player) -> None:
        """Execute the Remaining Combatants stage of the Fight Phase."""
        print("⚔️ Starting Remaining Combatants Stage")
        
        # Get remaining combatant units for both players
        current_player_units = self.game.get_remaining_combatant_units(current_player)
        opponent_units = self.game.get_remaining_combatant_units(opponent_player)
        
        if not current_player_units and not opponent_units:
            print("📋 No remaining combatant units eligible to fight")
            return
        
        # Remaining combatants stage: all other eligible units
        self._execute_alternating_fights(current_player, opponent_player, 
                                       current_player_units, opponent_units, 
                                       "Remaining Combatants")
    
    def _execute_alternating_fights(self, current_player: Player, opponent_player: Player,
                                  current_player_units: List[Unit], opponent_units: List[Unit],
                                  stage_name: str) -> None:
        """Execute alternating unit selection and fighting within a stage."""
        print(f"⚔️ {stage_name} Stage - Current Player: {len(current_player_units)} units, Opponent: {len(opponent_units)} units")
        
        # Track which units have already fought this stage
        fought_units = set()
        
        # IMPORTANT: In Fight Phase, the player whose turn is NOT taking place goes first
        # So the opponent goes first, not the current player
        active_player = opponent_player
        active_units = opponent_units
        other_player = current_player
        other_units = current_player_units
        
        while True:
            # Get remaining units for active player
            remaining_units = [unit for unit in active_units if unit not in fought_units and unit.is_alive()]
            
            if not remaining_units:
                # Active player has no more units - switch to other player
                # But first check if other player has units
                other_remaining = [unit for unit in other_units if unit not in fought_units and unit.is_alive()]
                if not other_remaining:
                    break  # No more units for either player
                
                # Switch active player
                if active_player == current_player:
                    active_player = opponent_player
                    active_units = opponent_units
                    other_player = current_player
                    other_units = current_player_units
                else:
                    active_player = current_player
                    active_units = current_player_units
                    other_player = opponent_player
                    other_units = opponent_units
                
                # Update remaining units after switch
                remaining_units = [unit for unit in active_units if unit not in fought_units and unit.is_alive()]
                
                # If the switched player also has no units, we're done
                if not remaining_units:
                    break
                
                # Check if other player (who we just switched from) has any units left
                other_remaining_after_switch = [unit for unit in other_units if unit not in fought_units and unit.is_alive()]
                
                # If other player has no units left, active player fights with ALL remaining units
                if not other_remaining_after_switch:
                    print(f"🔥 {other_player.name} has no more units - {active_player.name} fights with all remaining units")
                    for unit in remaining_units:
                        print(f"🤖 {active_player.name} fights with {unit.name}")
                        self._execute_complete_fight_sequence(unit)
                        fought_units.add(unit)
                    break
            
            # Select and fight with one unit
            selected_unit = self._select_unit_to_fight(remaining_units, stage_name)
            if selected_unit:
                print(f"🤖 {active_player.name} selects {selected_unit.name} to fight")
                self._execute_complete_fight_sequence(selected_unit)
                fought_units.add(selected_unit)
            else:
                # This shouldn't happen if remaining_units is not empty
                break
            
            # After fighting, switch to other player for next selection
            # (unless other player has no units, then current player continues)
            other_remaining = [unit for unit in other_units if unit not in fought_units and unit.is_alive()]
            if other_remaining:
                # Switch players for alternating selection
                if active_player == current_player:
                    active_player = opponent_player
                    active_units = opponent_units
                    other_player = current_player
                    other_units = current_player_units
                else:
                    active_player = current_player
                    active_units = current_player_units
                    other_player = opponent_player
                    other_units = opponent_units
            # If other player has no units, active player continues without switching
        
        print(f"✅ {stage_name} Stage complete")
    
    def _execute_complete_fight_sequence(self, unit: Unit) -> None:
        """Execute the complete fight sequence: Pile-in → Make Melee Attacks → Consolidate"""
        # Step 1: Pile-in
        self._execute_pile_in(unit)

        # Step 2: Make Melee Attacks (existing fight_phase logic)
        if self.player.type.name == 'HUMAN' and self.ui_interface:
            # Use dialog to collect melee attack declarations from the human player
            attack_declarations = None
            selection_complete = False
            def on_melee_declaration(declarations):
                nonlocal attack_declarations, selection_complete
                attack_declarations = declarations
                selection_complete = True
                logger.info(f"⚔️ Human player declared melee attacks for {unit.name}")
            self.ui_interface.show_melee_weapon_declaration_dialog(unit, on_melee_declaration, self.game.map)
            import pygame
            clock = pygame.time.Clock()
            while not selection_complete and self.ui_interface.melee_weapon_declaration_dialog.visible:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        return
                    if self.ui_interface.handle_event(event):
                        continue
                clock.tick(60)
            # Now resolve the attacks using the declarations
            if attack_declarations:
                self._resolve_attack_declarations(attack_declarations)
        else:
            # AI or non-human: use existing logic
            self._execute_melee_attacks(unit)

        # Step 3: Consolidate
        self._execute_consolidate(unit)
    
    def _execute_pile_in(self, unit: Unit) -> None:
        """Execute pile-in move - up to 3 inches towards nearest enemy unit"""
        if not unit.is_alive():
            return
        
        print(f"📍 {unit.name} piles in...")
        success = unit.pile_in_towards_enemies(self.game.map)
        if not success:
            print(f"   {unit.name} could not pile in")
    
    def _execute_consolidate(self, unit: Unit) -> None:
        """Execute consolidate move - up to 3 inches further into enemy lines"""
        if not unit.is_alive():
            return
        
        print(f"🔄 {unit.name} consolidates...")
        success = unit.consolidate_towards_enemies(self.game.map)
        if not success:
            print(f"   {unit.name} could not consolidate")
    
    def _select_unit_to_fight(self, eligible_units: List[Unit], stage_name: str = "") -> Optional[Unit]:
        """Select which unit should fight next.
        
        For human players, shows a dialog for unit selection.
        For AI players, uses heuristic-based selection.
        """
        if not eligible_units:
            return None
        
        # Check if this is a human player
        if self.player.type.name == 'HUMAN' and self.ui_interface:
            # Use UI dialog for human player selection
            selected_unit = None
            selection_complete = False
            
            def on_unit_selected(unit: Unit):
                nonlocal selected_unit, selection_complete
                selected_unit = unit
                selection_complete = True
                logger.info(f"⚔️ Human player selected {unit.name} to fight in {stage_name} stage")
            
            def on_cancel():
                nonlocal selection_complete
                selection_complete = True
                logger.info(f"⚔️ Human player cancelled unit selection for {stage_name} stage")
            
            # Show the fight unit selection dialog
            self.ui_interface.show_fight_unit_selection_dialog(
                stage_name, eligible_units, on_unit_selected, on_cancel
            )
            
            # Wait for user selection
            import pygame
            clock = pygame.time.Clock()
            while not selection_complete and self.ui_interface.fight_unit_selection_dialog.visible:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        return None
                    
                    # Let the UI interface handle the event
                    if self.ui_interface.handle_event(event):
                        continue
                
                # Draw the current screen (this would be called by the main game loop)
                # For now, we'll assume the screen is being drawn elsewhere
                clock.tick(60)
            
            return selected_unit
        
        else:
            # AI logic: simple heuristic - could be enhanced with ML
            # Prioritize units that charged this turn, then highest threat
            charged_units = [unit for unit in eligible_units if unit.round_state.declared_charge_this_round]
            if charged_units:
                selected_unit = max(charged_units, key=lambda u: u.get_threat_value())
                logger.info(f"🤖 AI selected {selected_unit.name} to fight in {stage_name} stage (charged this turn)")
                return selected_unit
            
            # Otherwise, select unit with highest threat value
            selected_unit = max(eligible_units, key=lambda u: u.get_threat_value())
            logger.info(f"🤖 AI selected {selected_unit.name} to fight in {stage_name} stage (highest threat)")
            return selected_unit

    def find_enemies_in_melee_range(self, unit: Unit) -> List[Unit]:
        """Find all enemy units within engagement range of the given unit."""
        enemies_in_range = []
        unit_position = unit.get_position()
        enemy_units = self.game.map.get_enemy_units(unit)
        
        for enemy_unit in enemy_units:
            if self.game.map.is_within_engagement_range(unit_position, enemy_unit):
                enemies_in_range.append(enemy_unit)
        
        return enemies_in_range
    
    def choose_fight_target(self, model: Model, profile: WargearProfile, targets: List[Unit]) -> int:
        """Choose a target for the model's melee weapon/profile in the fight phase."""
        state = self.extract_fight_state_features(model, profile, targets)
        action_probs = self.fight_target_policy_net(state)

        # Check for NaN values in network output
        if torch.isnan(action_probs).any():
            throttled_warning("Warning: NaN values detected in fight target policy network output, using uniform distribution")
            action_probs = torch.ones_like(action_probs)

        # Mask unavailable targets
        action_mask = torch.zeros(self.get_fight_action_size())
        num_targets = min(len(targets), MAX_TARGETS)
        for idx in range(num_targets):
            action_mask[idx] = 1
        
        # Apply mask and normalize
        masked_probs = action_probs * action_mask
        prob_sum = masked_probs.sum()
        
        # Handle zero sum or NaN cases
        if prob_sum == 0 or torch.isnan(prob_sum):
            throttled_warning("Warning: Invalid probability sum detected, using uniform distribution over valid fight targets")
            masked_probs = action_mask / action_mask.sum()
        else:
            masked_probs = masked_probs / prob_sum
        
        # Final check for NaN values
        if torch.isnan(masked_probs).any():
            throttled_warning("Warning: NaN values after normalization, falling back to uniform distribution")
            masked_probs = action_mask / action_mask.sum()

        # Create a categorical distribution
        action_dist = torch.distributions.Categorical(masked_probs)
        action_idx = action_dist.sample()

        # Store log probability
        self.fight_target_log_probs.append(action_dist.log_prob(action_idx))
        return action_idx.item()
    
    def choose_melee_weapon_profile(self, model: Model, wargear_item: Wargear) -> WargearProfile:
        """Choose a melee weapon profile to use from the wargear item."""
        profiles = list(wargear_item.profiles.values())
        if len(profiles) == 1:
            return profiles[0]
        
        state = self.extract_profile_selection_state(model, wargear_item, profiles)
        action_probs = self.fight_profile_selection_policy_net(state)

        # Check for NaN values in network output
        if torch.isnan(action_probs).any():
            throttled_warning("Warning: NaN values detected in fight profile selection policy network output, using uniform distribution")
            action_probs = torch.ones_like(action_probs)

        # Mask unavailable profiles
        action_mask = torch.zeros(self.get_profile_selection_action_size())
        num_profiles = min(len(profiles), MAX_PROFILES)
        for idx in range(num_profiles):
            action_mask[idx] = 1
        
        # Apply mask and normalize
        masked_probs = action_probs * action_mask
        prob_sum = masked_probs.sum()
        
        # Handle zero sum or NaN cases
        if prob_sum == 0 or torch.isnan(prob_sum):
            throttled_warning("Warning: Invalid probability sum detected, using uniform distribution over valid melee profiles")
            masked_probs = action_mask / action_mask.sum()
        else:
            masked_probs = masked_probs / prob_sum
        
        # Final check for NaN values
        if torch.isnan(masked_probs).any():
            throttled_warning("Warning: NaN values after normalization, falling back to uniform distribution")
            masked_probs = action_mask / action_mask.sum()

        # Create a categorical distribution for profile selection
        profile_dist = torch.distributions.Categorical(masked_probs)
        profile_idx = profile_dist.sample()

        # Store log probability
        self.fight_profile_selection_log_probs.append(profile_dist.log_prob(profile_idx))
        return profiles[profile_idx.item()]
    
    def extract_fight_state_features(self, model: Model, profile: WargearProfile, targets: List[Unit]) -> torch.Tensor:
        """Extract state features for fight target selection."""
        features = []
        model_pos = model.get_location()
        features.extend([model_pos[0], model_pos[1], model_pos[2]])
        features.append(model.health_percent)
        
        for enemy in targets[:MAX_TARGETS]:
            features.append(profile.get_damage_potential(enemy))
            enemy_pos = enemy.get_position()
            features.extend([enemy_pos[0], enemy_pos[1], enemy_pos[2]])
            features.append(enemy.health_percent)
        
        num_targets = len(targets)
        if num_targets < MAX_TARGETS:
            padding = [0.0] * ((MAX_TARGETS - num_targets) * 5)
            features.extend(padding)

        # Convert to tensor
        state = torch.tensor([features], dtype=torch.float32)  # Batch dimension
        return state
    
    def get_fight_state_size(self) -> int:
        """Calculate the size of the fight target selection state vector."""
        # 4 features for the model (x, y, z, health)
        # 5 features per target (damage potential, x, y, z, health) * MAX_TARGETS
        return 4 + (MAX_TARGETS * 5)

    def get_fight_action_size(self) -> int:
        """Define the number of possible fight targets to select from."""
        return MAX_TARGETS

    def fight_phase(self, unit: Unit) -> None:
        """Resolve melee combat according to official Warhammer 40k rules."""
        if not unit.deployed or not unit.is_alive():
            return

        self.game.event_system.publish("fight_phase_start", unit=unit, game_state=self.game.get_state())
        
        # Find enemies in melee range
        enemies_in_range = self.find_enemies_in_melee_range(unit)
        # Filter out destroyed units
        enemies_in_range = [enemy for enemy in enemies_in_range if enemy.is_alive()]
        
        if not enemies_in_range:
            logger.info(f"{unit.name} has no enemies in melee range.")
            self.game.event_system.publish("fight_phase_end", unit=unit, game_state=self.game.get_state())
            return

        # Step 1: Determine which models can fight
        models_that_can_fight = self._get_models_that_can_fight(unit, enemies_in_range)
        
        if not models_that_can_fight:
            logger.info(f"{unit.name} has no models that can fight.")
            self.game.event_system.publish("fight_phase_end", unit=unit, game_state=self.game.get_state())
            return
        
        print(f"⚔️ {unit.name} - {len(models_that_can_fight)} models can fight")
        
        # Step 2: Collect all attack declarations before resolving any
        attack_declarations = self._collect_attack_declarations(models_that_can_fight, enemies_in_range)
        
        if not attack_declarations:
            logger.info(f"{unit.name} has no valid attack declarations.")
            self.game.event_system.publish("fight_phase_end", unit=unit, game_state=self.game.get_state())
            return
        
        # Step 3: Resolve all attacks by target unit and weapon profile
        self._resolve_attack_declarations(attack_declarations)

        self.game.event_system.publish("fight_phase_end", unit=unit, game_state=self.game.get_state())
    
    def _get_models_that_can_fight(self, unit: Unit, enemies_in_range: List[Unit]) -> List['Model']:
        """Determine which models in the unit can fight.
        
        Models can fight if they are:
        - Within Engagement Range of an enemy unit, OR
        - In base-to-base contact with another model from the same unit that is itself in base-to-base contact with an enemy unit
        """
        models_that_can_fight = []
        
        for model in unit.models:
            if not model.is_alive:
                continue
            
            # Check if model is within engagement range of any enemy
            model_position = (model.x, model.y, model.z, model.facing)
            is_in_engagement_range = any(
                self.game.map.is_within_engagement_range(model_position, enemy)
                for enemy in enemies_in_range
            )
            
            if is_in_engagement_range:
                models_that_can_fight.append(model)
                continue
            
            # Check if model is in base-to-base contact with another model that can fight
            # This is a simplified check - in full implementation would check actual base contact
            for other_model in unit.models:
                if other_model == model or not other_model.is_alive:
                    continue
                
                # Check if other model is in engagement range
                other_position = (other_model.x, other_model.y, other_model.z, other_model.facing)
                other_can_fight = any(
                    self.game.map.is_within_engagement_range(other_position, enemy)
                    for enemy in enemies_in_range
                )
                
                if other_can_fight:
                    # Check if this model is in base-to-base contact with the other model
                    # Simplified: check if they're very close (within 1")
                    dx = other_model.x - model.x
                    dy = other_model.y - model.y
                    distance = (dx*dx + dy*dy) ** 0.5
                    
                    if distance <= 1.0:  # Base-to-base contact threshold
                        models_that_can_fight.append(model)
                        break
        
        return models_that_can_fight
    
    def _collect_attack_declarations(self, models_that_can_fight: List['Model'], enemies_in_range: List[Unit]) -> List[dict]:
        """Collect all attack declarations before resolving any attacks.
        
        Each declaration includes:
        - attacking_model: The model making the attack
        - weapon: The melee weapon being used
        - profile: The weapon profile being used
        - target_unit: The target unit
        - num_attacks: Number of attacks to make
        """
        attack_declarations = []
        
        for model in models_that_can_fight:
            # Find melee weapons for this model
            melee_weapons = [wargear for wargear in model.wargear if wargear.is_melee()]
            
            if not melee_weapons:
                continue
            
            # Select weapons to use (respecting EXTRA ATTACKS rule)
            weapons_to_use = self._select_weapons_for_model(model, melee_weapons)
            
            for weapon in weapons_to_use:
                # Choose which profile to use if the weapon has multiple profiles
                selected_profile = self.choose_melee_weapon_profile(model, weapon)
                if selected_profile is None:
                    continue
                
                # Get number of attacks from weapon profile
                num_attacks = selected_profile.attacks
                if num_attacks <= 0:
                    continue
                
                # Select targets for all attacks
                target_declarations = self._select_targets_for_attacks(
                    model, selected_profile, num_attacks, enemies_in_range
                )
                
                # Add declarations for each target
                for target_unit, target_attacks in target_declarations.items():
                    attack_declarations.append({
                        'attacking_model': model,
                        'weapon': weapon,
                        'profile': selected_profile,
                        'target_unit': target_unit,
                        'num_attacks': target_attacks
                    })
        
        return attack_declarations
    
    def _select_weapons_for_model(self, model: 'Model', melee_weapons: List) -> List:
        """Select which weapons the model will use for attacks.
        
        Rules:
        - Model can only use ONE melee weapon (unless it has EXTRA ATTACKS)
        - Weapons with EXTRA ATTACKS keyword can be used in addition to another weapon
        """
        weapons_to_use = []
        
        # Find weapons with EXTRA ATTACKS keyword
        extra_attack_weapons = []
        regular_weapons = []
        
        for weapon in melee_weapons:
            # Check if weapon has EXTRA ATTACKS keyword
            has_extra_attacks = False
            if hasattr(weapon, 'keywords'):
                has_extra_attacks = 'EXTRA ATTACKS' in weapon.keywords
            elif hasattr(weapon, 'name'):
                has_extra_attacks = 'extra attacks' in weapon.name.lower()
            
            if has_extra_attacks:
                extra_attack_weapons.append(weapon)
            else:
                regular_weapons.append(weapon)
        
        # Select one regular weapon (if any)
        if regular_weapons:
            # For AI, select the weapon with the most attacks
            selected_regular = max(regular_weapons, key=lambda w: self._get_weapon_attack_value(w))
            weapons_to_use.append(selected_regular)
        
        # Add all extra attack weapons
        weapons_to_use.extend(extra_attack_weapons)
        
        return weapons_to_use
    
    def _get_weapon_attack_value(self, weapon) -> int:
        """Get the attack value for a weapon (for selection purposes)."""
        if hasattr(weapon, 'profiles') and weapon.profiles:
            # Return the highest attack value from all profiles
            return max(profile.attacks for profile in weapon.profiles if hasattr(profile, 'attacks'))
        elif hasattr(weapon, 'attacks'):
            return weapon.attacks
        else:
            return 0
    
    def _select_targets_for_attacks(self, model: 'Model', profile, num_attacks: int, enemies_in_range: List[Unit]) -> dict:
        """Select targets for all attacks from a weapon profile.
        
        Rules:
        - All attacks can go to the same target OR be split between eligible targets
        - Target declaration must be completed before any attacks are resolved
        - Model must follow engagement range restrictions for target selection
        """
        target_declarations = {}
        
        # For AI, we'll use a simple strategy: put all attacks on the highest priority target
        # In a more sophisticated implementation, this could split attacks between targets
        
        # Find the best target (highest threat value)
        best_target = max(enemies_in_range, key=lambda enemy: enemy.get_threat_value())
        
        # Check if the target is still valid (within engagement range)
        model_position = (model.x, model.y, model.z, model.facing)
        if self.game.map.is_within_engagement_range(model_position, best_target):
            target_declarations[best_target] = num_attacks
        else:
            # Fallback: find any valid target
            for enemy in enemies_in_range:
                if self.game.map.is_within_engagement_range(model_position, enemy):
                    target_declarations[enemy] = num_attacks
                    break
        
        return target_declarations
    
    def _resolve_attack_declarations(self, attack_declarations: List[dict]) -> None:
        """Resolve all attack declarations.
        
        Rules:
        - Resolve all attacks against one unit before moving to the next
        - Resolve all attacks with the same weapon profile before resolving any with a different profile
        - All declared attacks are resolved even if models are no longer in engagement range
        """
        # Group attacks by target unit and weapon profile
        grouped_attacks = {}
        
        for declaration in attack_declarations:
            target_unit = declaration['target_unit']
            profile = declaration['profile']
            key = (target_unit, profile)
            
            if key not in grouped_attacks:
                grouped_attacks[key] = []
            
            grouped_attacks[key].append(declaration)
        
        # Resolve attacks by group
        for (target_unit, profile), declarations in grouped_attacks.items():
            print(f"⚔️ Resolving {len(declarations)} attack declarations against {target_unit.name} with {profile.name}")
            
            # Record target health before all attacks
            target_health_before = target_unit.health_percent
            
            for declaration in declarations:
                attacking_model = declaration['attacking_model']
                weapon = declaration['weapon']
                num_attacks = declaration['num_attacks']
                
                print(f"   {attacking_model.name} attacks {target_unit.name} with {weapon.name} ({num_attacks} attacks)")
                
                # Execute the attacks
                try:
                    # For now, use the existing melee_attack method
                    # In a full implementation, this would resolve hit/wound/save/damage/feel-no-pain
                    attacking_model.melee_attack(target_unit, profile)
                except Exception as e:
                    logger.error(f"Error during melee attack: {e}")
                    continue
            
            # Record target health after all attacks
            target_health_after = target_unit.health_percent
            damage = target_health_before - target_health_after
            
            # Compute rewards for this group of attacks
            reward = FIGHT_REWARD_SCALING * damage
            self.fight_profile_selection_rewards.append(reward)
            self.fight_target_rewards.append(reward)
            
            print(f"   {target_unit.name} took {damage:.1f}% damage")

    ###########################################################################
    # Policy Updates
    ###########################################################################
    def update_policies(self) -> None:
        self.update_movement_policy()
        self.update_shooting_policy()
        self.update_profile_selection_policy()
        self.update_fight_target_policy()
        self.update_fight_profile_selection_policy()

    def update_movement_policy(self) -> None:
        if not self.movement_rewards or not self.movement_log_probs:
            throttled_warning("No rewards or log probabilities to update Tactical Agent movement policy.")
            return

        R = 0
        policy_loss = []
        returns = []
        gamma = 0.99

        for r in self.movement_rewards[::-1]:
            R = r + gamma * R
            returns.insert(0, R)
        returns = torch.tensor(returns)
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-9)
        else:
            returns = returns * 0

        for log_prob, R in zip(self.movement_log_probs, returns):
            if log_prob.requires_grad:
                policy_loss.append(-log_prob * R)
            else:
                #print("Warning: movement log_prob does not require grad, skipping this term")
                continue

        if not policy_loss:
            throttled_warning("Warning: No valid policy loss terms to update movement policy")
            return

        self.movement_optimizer.zero_grad()
        policy_loss = torch.stack(policy_loss).sum()
        
        # Check for NaN in loss
        if torch.isnan(policy_loss):
            throttled_warning("Warning: NaN loss detected in movement policy, skipping update")
            return
            
        policy_loss.backward()
        
        # Clip gradients to prevent explosion
        torch.nn.utils.clip_grad_norm_(self.movement_policy_net.parameters(), max_norm=1.0)
        
        self.movement_optimizer.step()

        self.movement_rewards.clear()
        self.movement_log_probs.clear()

    def update_shooting_policy(self) -> None:
        if not self.shooting_rewards or not self.shooting_log_probs:
            throttled_warning("No rewards or log probabilities to update Tactical Agent shooting policy.")
            return

        R = 0
        policy_loss = []
        returns = []
        gamma = 0.99

        for r in self.shooting_rewards[::-1]:
            R = r + gamma * R
            returns.insert(0, R)
        returns = torch.tensor(returns)
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-9)
        else:
            returns = returns * 0

        for log_prob, R in zip(self.shooting_log_probs, returns):
            if log_prob.requires_grad:
                policy_loss.append(-log_prob * R)
            else:
                #print("Warning: shooting log_prob does not require grad, skipping this term")
                continue

        if not policy_loss:
            throttled_warning("Warning: No valid policy loss terms to update shooting policy")
            return

        self.shooting_optimizer.zero_grad()
        policy_loss = torch.stack(policy_loss).sum()
        
        # Check for NaN in loss
        if torch.isnan(policy_loss):
            throttled_warning("Warning: NaN loss detected in shooting policy, skipping update")
            return
            
        policy_loss.backward()
        
        # Clip gradients to prevent explosion
        torch.nn.utils.clip_grad_norm_(self.shooting_policy_net.parameters(), max_norm=1.0)
        
        self.shooting_optimizer.step()

        self.shooting_rewards.clear()
        self.shooting_log_probs.clear()

    def update_profile_selection_policy(self) -> None:
        if not self.profile_selection_rewards or not self.profile_selection_log_probs:
            throttled_warning("No rewards or log probabilities to update profile selection policy.")
            return

        R = 0
        policy_loss = []
        returns = []
        gamma = 0.99

        for r in self.profile_selection_rewards[::-1]:
            R = r + gamma * R
            returns.insert(0, R)
        returns = torch.tensor(returns)
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-9)
        else:
            returns = returns * 0

        for log_prob, R in zip(self.profile_selection_log_probs, returns):
            if log_prob.requires_grad:
                policy_loss.append(-log_prob * R)
            else:
                #print("Warning: profile selection log_prob does not require grad, skipping this term")
                continue

        if not policy_loss:
            throttled_warning("Warning: No valid policy loss terms to update profile selection policy")
            return

        self.profile_selection_optimizer.zero_grad()
        policy_loss = torch.stack(policy_loss).sum()
        
        # Check for NaN in loss
        if torch.isnan(policy_loss):
            throttled_warning("Warning: NaN loss detected in profile selection policy, skipping update")
            return
            
        policy_loss.backward()
        
        # Clip gradients to prevent explosion
        torch.nn.utils.clip_grad_norm_(self.profile_selection_policy_net.parameters(), max_norm=1.0)
        
        self.profile_selection_optimizer.step()

        self.profile_selection_rewards.clear()
        self.profile_selection_log_probs.clear()

    def update_fight_target_policy(self) -> None:
        if not self.fight_target_rewards or not self.fight_target_log_probs:
            throttled_warning("No rewards or log probabilities to update fight target policy.")
            return

        R = 0
        policy_loss = []
        returns = []
        gamma = 0.99

        for r in self.fight_target_rewards[::-1]:
            R = r + gamma * R
            returns.insert(0, R)
        returns = torch.tensor(returns)
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-9)
        else:
            returns = returns * 0

        for log_prob, R in zip(self.fight_target_log_probs, returns):
            if log_prob.requires_grad:
                policy_loss.append(-log_prob * R)
            else:
                #print("Warning: fight target log_prob does not require grad, skipping this term")
                continue

        if not policy_loss:
            throttled_warning("Warning: No valid policy loss terms to update fight target policy")
            return

        self.fight_target_optimizer.zero_grad()
        policy_loss = torch.stack(policy_loss).sum()
        
        # Check for NaN in loss
        if torch.isnan(policy_loss):
            throttled_warning("Warning: NaN loss detected in fight target policy, skipping update")
            return
            
        policy_loss.backward()
        
        # Clip gradients to prevent explosion
        torch.nn.utils.clip_grad_norm_(self.fight_target_policy_net.parameters(), max_norm=1.0)
        
        self.fight_target_optimizer.step()

        self.fight_target_rewards.clear()
        self.fight_target_log_probs.clear()

    def update_fight_profile_selection_policy(self) -> None:
        if not self.fight_profile_selection_rewards or not self.fight_profile_selection_log_probs:
            throttled_warning("No rewards or log probabilities to update fight profile selection policy.")
            return

        R = 0
        policy_loss = []
        returns = []
        gamma = 0.99

        for r in self.fight_profile_selection_rewards[::-1]:
            R = r + gamma * R
            returns.insert(0, R)
        returns = torch.tensor(returns)
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-9)
        else:
            returns = returns * 0

        for log_prob, R in zip(self.fight_profile_selection_log_probs, returns):
            if log_prob.requires_grad:
                policy_loss.append(-log_prob * R)
            else:
                #print("Warning: fight profile selection log_prob does not require grad, skipping this term")
                continue

        if not policy_loss:
            throttled_warning("Warning: No valid policy loss terms to update fight profile selection policy")
            return

        self.fight_profile_selection_optimizer.zero_grad()
        policy_loss = torch.stack(policy_loss).sum()
        
        # Check for NaN in loss
        if torch.isnan(policy_loss):
            throttled_warning("Warning: NaN loss detected in fight profile selection policy, skipping update")
            return
            
        policy_loss.backward()
        
        # Clip gradients to prevent explosion
        torch.nn.utils.clip_grad_norm_(self.fight_profile_selection_policy_net.parameters(), max_norm=1.0)
        
        self.fight_profile_selection_optimizer.step()

        self.fight_profile_selection_rewards.clear()
        self.fight_profile_selection_log_probs.clear()

    # --- Checkpointing for TacticalAgent ---
    def save_checkpoint(self, filepath: str = 'ta_checkpoint.pth') -> None:
        checkpoint = {
            'movement_policy_net_state_dict': self.movement_policy_net.state_dict(),
            'movement_optimizer_state_dict': self.movement_optimizer.state_dict(),
            'shooting_policy_net_state_dict': self.shooting_policy_net.state_dict(),
            'shooting_optimizer_state_dict': self.shooting_optimizer.state_dict(),
            'profile_selection_policy_net_state_dict': self.profile_selection_policy_net.state_dict(),
            'profile_selection_optimizer_state_dict': self.profile_selection_optimizer.state_dict(),
            'fight_target_policy_net_state_dict': self.fight_target_policy_net.state_dict(),
            'fight_target_optimizer_state_dict': self.fight_target_optimizer.state_dict(),
            'fight_profile_selection_policy_net_state_dict': self.fight_profile_selection_policy_net.state_dict(),
            'fight_profile_selection_optimizer_state_dict': self.fight_profile_selection_optimizer.state_dict(),
            'movement_rewards': self.movement_rewards,
            'movement_log_probs': self.movement_log_probs,
            'shooting_rewards': self.shooting_rewards,
            'shooting_log_probs': self.shooting_log_probs,
            'profile_selection_rewards': self.profile_selection_rewards,
            'profile_selection_log_probs': self.profile_selection_log_probs,
            'fight_target_rewards': self.fight_target_rewards,
            'fight_target_log_probs': self.fight_target_log_probs,
            'fight_profile_selection_rewards': self.fight_profile_selection_rewards,
            'fight_profile_selection_log_probs': self.fight_profile_selection_log_probs
        }
        torch.save(checkpoint, filepath)
        logger.info(f"TacticalAgent checkpoint saved to {filepath}")

    def load_checkpoint(self, filepath: str = 'ta_checkpoint.pth') -> None:
        if os.path.exists(filepath):
            checkpoint = torch.load(filepath, weights_only=False)
            self.movement_policy_net.load_state_dict(checkpoint.get('movement_policy_net_state_dict', {}))
            self.movement_optimizer.load_state_dict(checkpoint.get('movement_optimizer_state_dict', {}))
            self.shooting_policy_net.load_state_dict(checkpoint.get('shooting_policy_net_state_dict', {}))
            self.shooting_optimizer.load_state_dict(checkpoint.get('shooting_optimizer_state_dict', {}))
            self.profile_selection_policy_net.load_state_dict(checkpoint.get('profile_selection_policy_net_state_dict', {}))
            self.profile_selection_optimizer.load_state_dict(checkpoint.get('profile_selection_optimizer_state_dict', {}))
            self.fight_target_policy_net.load_state_dict(checkpoint.get('fight_target_policy_net_state_dict', {}))
            self.fight_target_optimizer.load_state_dict(checkpoint.get('fight_target_optimizer_state_dict', {}))
            self.fight_profile_selection_policy_net.load_state_dict(checkpoint.get('fight_profile_selection_policy_net_state_dict', {}))
            self.fight_profile_selection_optimizer.load_state_dict(checkpoint.get('fight_profile_selection_optimizer_state_dict', {}))
            self.movement_rewards = checkpoint.get('movement_rewards', [])
            self.movement_log_probs = checkpoint.get('movement_log_probs', [])
            self.shooting_rewards = checkpoint.get('shooting_rewards', [])
            self.shooting_log_probs = checkpoint.get('shooting_log_probs', [])
            self.profile_selection_rewards = checkpoint.get('profile_selection_rewards', [])
            self.profile_selection_log_probs = checkpoint.get('profile_selection_log_probs', [])
            self.fight_target_rewards = checkpoint.get('fight_target_rewards', [])
            self.fight_target_log_probs = checkpoint.get('fight_target_log_probs', [])
            self.fight_profile_selection_rewards = checkpoint.get('fight_profile_selection_rewards', [])
            self.fight_profile_selection_log_probs = checkpoint.get('fight_profile_selection_log_probs', [])
            logger.info(f"TacticalAgent checkpoint loaded from {filepath}")
        else:
            logger.info("No TacticalAgent checkpoint found. Starting with fresh state.")


###############################################################################
# LowLevelAgent
###############################################################################
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
        if not self.rewards or not self.log_probs:
            throttled_warning("No rewards or log probabilities to update Low Level Agent movement policy.")
            return

        R = 0
        policy_loss = []
        returns = []
        gamma = 0.99

        for r in self.rewards[::-1]:
            R = r + gamma * R
            returns.insert(0, R)
        returns = torch.tensor(returns)
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-9)
        else:
            returns = returns * 0

        for log_prob, R in zip(self.log_probs, returns):
            if log_prob.requires_grad:
                policy_loss.append(-log_prob * R)
            else:
                #print("Warning: LowLevelAgent log_prob does not require grad, skipping this term")
                continue

        if not policy_loss:
            throttled_warning("Warning: No valid policy loss terms to update LowLevelAgent policy")
            return

        self.optimizer.zero_grad()
        policy_loss = torch.stack(policy_loss).sum()
        
        # Check for NaN in loss
        if torch.isnan(policy_loss):
            throttled_warning("Warning: NaN loss detected in LowLevelAgent, skipping update")
            return
            
        policy_loss.backward()
        
        # Clip gradients to prevent explosion
        torch.nn.utils.clip_grad_norm_(self.movement_execution_net.parameters(), max_norm=1.0)
        
        self.optimizer.step()

        self.rewards.clear()
        self.log_probs.clear()

    # --- Checkpointing for LowLevelAgent ---
    def save_checkpoint(self, filepath: str = 'lla_checkpoint.pth') -> None:
        checkpoint = {
            'movement_execution_net_state_dict': self.movement_execution_net.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'rewards': self.rewards,
            'log_probs': self.log_probs
        }
        torch.save(checkpoint, filepath)
        logger.info(f"LowLevelAgent checkpoint saved to {filepath}")

    def load_checkpoint(self, filepath: str = 'lla_checkpoint.pth') -> None:
        if os.path.exists(filepath):
            checkpoint = torch.load(filepath, weights_only=False)
            self.movement_execution_net.load_state_dict(checkpoint.get('movement_execution_net_state_dict', {}))
            self.optimizer.load_state_dict(checkpoint.get('optimizer_state_dict', {}))
            self.rewards = checkpoint.get('rewards', [])
            self.log_probs = checkpoint.get('log_probs', [])
            logger.info(f"LowLevelAgent checkpoint loaded from {filepath}")
        else:
            logger.info("No LowLevelAgent checkpoint found. Starting with fresh state.")


###############################################################################
# AI Deployment Decision Maker - Integrates with HighLevelAgent
###############################################################################
class AIDeploymentDecisionMaker(DeploymentDecisionMaker):
    """Implementation for AI players making deployment decisions via neural networks."""
    
    def __init__(self, high_level_agent: HighLevelAgent):
        self.agent = high_level_agent
    
    def choose_deployment_zone(self, available_zones: List[dict]) -> dict:
        """AI chooses deployment zone using neural network."""
        return self.agent.choose_deployment_zone(available_zones)
    
    def declare_reserves(self, player: Player) -> dict:
        """AI declares reserves using neural network."""
        return self.agent.declare_reserves()
    
    def choose_unit_deployment_position(self, unit: 'Unit', deployment_zone: dict, 
                                       already_deployed: List['Unit']) -> Tuple[float, float]:
        """AI chooses unit position using neural network."""
        return self.agent.choose_unit_deployment_position(unit, deployment_zone, already_deployed)
    
    def compute_deployment_reward(self, deployment_results: dict) -> float:
        """Compute and store deployment rewards for learning."""
        reward = self.agent.compute_deployment_reward(deployment_results)
        
        # Store rewards for both deployment zone selection and reserves
        self.agent.deployment_rewards.append(reward)
        self.agent.reserves_rewards.append(reward)
        
        logger.info(f"📊 {self.agent.player.name} deployment reward: {reward:.2f}")
        return reward

    ###########################################################################
    ### Reserves Arrival System
    ###########################################################################
    def handle_reserves_arrival_phase(self, game: 'Game') -> List['Unit']:
        """Handle reserves arrival decisions for the AI player.
        
        Args:
            game: The current game instance
        
        Returns:
            List of units that arrived from reserves this turn
        """
        from warhammer40k_ai.classes.game import Game
        assert isinstance(game, Game)
        
        units_arrived = []
        units_that_can_arrive = game.get_units_that_can_arrive_from_reserves(self.player)
        units_that_must_arrive = game.get_units_that_must_arrive_from_reserves(self.player)
        
        logger.info(f"🪂 {self.player.name} reserves phase: {len(units_that_can_arrive)} can arrive, {len(units_that_must_arrive)} must arrive")
        
        # Always bring in units that must arrive (to avoid destruction)
        for unit in units_that_must_arrive:
            position, edge = self.choose_reserves_arrival_position(unit, game, forced=True)
            if position and unit.arrive_from_reserves(position, game.turn):
                units_arrived.append(unit)
                game.map.units.append(unit)
                logger.info(f"✅ {unit.name} forced arrival from reserves at turn {game.turn}")
                
                # Store reward for forced arrivals (neutral, since it was mandatory)
                self.reserves_rewards.append(0.0)
            else:
                logger.error(f"❌ Failed to deploy {unit.name} despite being forced - unit will be destroyed")
                self.reserves_rewards.append(-5.0)  # Heavy penalty for failing mandatory deployment
        
        # Make strategic decisions for optional arrivals
        optional_units = [unit for unit in units_that_can_arrive if unit not in units_that_must_arrive]
        
        for unit in optional_units:
            should_arrive = self.decide_whether_to_arrive_from_reserves(unit, game)
            
            if should_arrive:
                position, edge = self.choose_reserves_arrival_position(unit, game, forced=False)
                if position and unit.arrive_from_reserves(position, game.turn):
                    units_arrived.append(unit)
                    game.map.units.append(unit)
                    logger.info(f"🎯 {unit.name} strategic arrival from reserves at turn {game.turn}")
                    
                    # Compute reward based on tactical value of arrival
                    arrival_reward = self.compute_reserves_arrival_reward(unit, position, game)
                    self.reserves_rewards.append(arrival_reward)
                else:
                    logger.warning(f"⚠️ Failed to deploy {unit.name} despite decision to arrive")
                    self.reserves_rewards.append(-2.0)  # Penalty for failed deployment
        
        return units_arrived
    
    def decide_whether_to_arrive_from_reserves(self, unit: 'Unit', game: 'Game') -> bool:
        """Decide whether a unit should arrive from reserves this turn.
        
        Args:
            unit: The unit in reserves
            game: The current game instance
        
        Returns:
            bool: True if the unit should arrive this turn
        """
        state = self.extract_reserves_arrival_features(unit, game)
        probs = self.reserves_selection_net(state)
        
        # Check for NaN values
        if torch.isnan(probs).any():
            throttled_warning(f"Warning: NaN values in reserves arrival decision for {unit.name}")
            # Default to arriving (conservative choice)
            return True
        
        # Use the deployment network for arrival decisions (index 0 = don't arrive, 1 = arrive)
        # We'll interpret the first two outputs as [stay_in_reserves, arrive_now]
        arrival_probs = torch.softmax(probs[:2], dim=0)
        
        arrival_dist = torch.distributions.Categorical(arrival_probs)
        decision = arrival_dist.sample().item()
        
        # Store log probability for learning
        self.reserves_log_probs.append(arrival_dist.log_prob(torch.tensor(decision)))
        
        return decision == 1  # 1 means arrive now
    
    def choose_reserves_arrival_position(self, unit: 'Unit', game: 'Game', forced: bool = False) -> Tuple[Optional[Tuple[float, float, float]], Optional[str]]:
        """Choose where to place a unit arriving from reserves.
        
        Args:
            unit: The unit arriving from reserves
            game: The current game instance
            forced: Whether this is a forced arrival (affects decision making)
        
        Returns:
            Tuple of (position, battlefield_edge) or (None, None) if no valid position
        """
        # Get valid edges for strategic reserves
        valid_edges = []
        if unit.is_in_strategic_reserves():
            if game.turn == 2:
                valid_edges = ['own']
            elif game.turn >= 3:
                valid_edges = ['own', 'left', 'right']
        
        # Try to find the best position
        best_position = None
        best_edge = None
        best_score = -float('inf')
        
        attempts = 50 if not forced else 100  # More attempts for forced arrivals
        
        for _ in range(attempts):
            if unit.is_in_strategic_reserves() and valid_edges:
                # Choose edge (could be enhanced with AI decision making)
                import random
                edge = random.choice(valid_edges)
                
                # Generate position near that edge
                if edge == 'own':
                    x = random.uniform(10, game.battlefield.width - 10)
                    y = random.uniform(0, 6)  # Within 6" of own edge
                elif edge == 'left':
                    x = random.uniform(0, 6)  # Within 6" of left edge
                    y = random.uniform(10, game.battlefield.height - 10)
                elif edge == 'right':
                    x = random.uniform(game.battlefield.width - 6, game.battlefield.width)
                    y = random.uniform(10, game.battlefield.height - 10)
                else:
                    continue
                    
                z = game.map.get_height_at_point(x, y)
                position = (x, y, z)
                
                if game.can_place_unit_arriving_from_reserves(unit, position, edge):
                    # Score this position
                    score = self.score_reserves_position(unit, position, game)
                    if score > best_score:
                        best_score = score
                        best_position = position
                        best_edge = edge
            else:
                # Standard reserves (Deep Strike) - can arrive anywhere more than 9" from enemies
                import random
                x = random.uniform(15, game.battlefield.width - 15)  # Stay away from edges
                y = random.uniform(15, game.battlefield.height - 15)
                z = game.map.get_height_at_point(x, y)
                position = (x, y, z)
                
                if game.can_place_unit_arriving_from_reserves(unit, position):
                    # Score this position
                    score = self.score_reserves_position(unit, position, game)
                    if score > best_score:
                        best_score = score
                        best_position = position
                        best_edge = None
        
        return best_position, best_edge
    
    def score_reserves_position(self, unit: 'Unit', position: Tuple[float, float, float], game: 'Game') -> float:
        """Score a potential reserves arrival position.
        
        Args:
            unit: The unit arriving from reserves
            position: The potential position
            game: The current game instance
        
        Returns:
            float: Score for this position (higher is better)
        """
        score = 0.0
        
        # Prefer positions closer to objectives
        for objective in self.objectives:
            distance = get_dist(
                objective.location.x - position[0],
                objective.location.y - position[1],
                objective.location.z - position[2]
            )
            # Closer to objectives is better
            score += max(0, 20 - distance)
        
        # Consider threat to enemy units
        enemy_units = game.get_enemy_units(self.player)
        for enemy_unit in enemy_units:
            if not enemy_unit.is_alive() or not enemy_unit.deployed:
                continue
                
            enemy_pos = enemy_unit.get_position()
            distance = get_dist(
                enemy_pos[0] - position[0],
                enemy_pos[1] - position[1],
                enemy_pos[2] - position[2]
            )
            
            # Prefer positions within threat range but not too close
            if 9 < distance < unit.get_max_weapon_range():
                score += 10  # Good threatening position
            elif distance > unit.get_max_weapon_range():
                score -= distance * 0.1  # Penalty for being too far away
        
        # Avoid being too isolated from friendly units
        friendly_units = [u for u in self.player.get_army().units if u != unit and u.deployed and u.is_alive()]
        if friendly_units:
            closest_friendly_distance = min(
                get_dist(
                    friendly_unit.get_position()[0] - position[0],
                    friendly_unit.get_position()[1] - position[1],
                    friendly_unit.get_position()[2] - position[2]
                ) for friendly_unit in friendly_units
            )
            
            # Prefer moderate distance from friendlies (not too close, not too far)
            if 6 < closest_friendly_distance < 18:
                score += 5
            elif closest_friendly_distance > 24:
                score -= 5  # Penalty for being too isolated
        
        return score
    
    def extract_reserves_arrival_features(self, unit: 'Unit', game: 'Game') -> torch.Tensor:
        """Extract features for reserves arrival decision.
        
        Args:
            unit: The unit in reserves
            game: The current game instance
        
        Returns:
            torch.Tensor: Feature vector for the neural network
        """
        features = []
        
        # Current turn and urgency
        features.append(game.turn)
        features.append(1.0 if unit.must_arrive_from_reserves(game.turn) else 0.0)
        
        # Unit characteristics
        features.append(unit.movement)
        features.append(len(unit.models))
        features.append(unit.get_max_weapon_range())
        features.append(unit.toughness)
        features.append(unit.save)
        
        # Game state
        friendly_units_on_board = len([u for u in self.player.get_army().units if u.deployed and u.is_alive()])
        enemy_units_on_board = len([u for u in self.opponent.get_army().units if u.deployed and u.is_alive()])
        features.extend([friendly_units_on_board, enemy_units_on_board])
        
        # Objective control situation
        objectives_controlled = sum(1 for obj in self.objectives 
                                  if hasattr(obj.location, 'controlling_player') and 
                                     obj.location.controlling_player == self.player)
        objectives_contested = len(self.objectives) - objectives_controlled
        features.extend([objectives_controlled, objectives_contested])
        
        # Threat assessment
        enemy_ranged_threat = sum(1 for enemy_unit in self.opponent.get_army().units 
                                if enemy_unit.deployed and enemy_unit.get_max_weapon_range() > 24)
        features.append(enemy_ranged_threat)
        
        # Player scores (if available)
        try:
            features.append(self.player.get_score())
            features.append(self.opponent.get_score())
        except:
            features.extend([0.0, 0.0])
        
        # Pad to expected size
        while len(features) < 17:  # Match reserves decision feature size
            features.append(0.0)
        
        return torch.tensor(features, dtype=torch.float32)
    
    def compute_reserves_arrival_reward(self, unit: 'Unit', position: Tuple[float, float, float], game: 'Game') -> float:
        """Compute reward for a reserves arrival decision.
        
        Args:
            unit: The unit that arrived
            position: Where it was placed
            game: The current game instance
        
        Returns:
            float: Reward value
        """
        reward = 1.0  # Base reward for successful arrival
        
        # Bonus for arriving at optimal times
        if game.turn == 2:
            reward += 0.5  # Good timing for most units
        elif game.turn == 3:
            reward += 0.2  # Still reasonable timing
        
        # Bonus for threat positioning
        enemy_units = game.get_enemy_units(self.player)
        for enemy_unit in enemy_units:
            if not enemy_unit.is_alive() or not enemy_unit.deployed:
                continue
                
            distance = get_dist(
                enemy_unit.get_position()[0] - position[0],
                enemy_unit.get_position()[1] - position[1],
                enemy_unit.get_position()[2] - position[2]
            )
            
            # Bonus for good threatening positions
            if 9 < distance < unit.get_max_weapon_range():
                reward += 1.0
        
        # Bonus for objective proximity
        for objective in self.objectives:
            distance = get_dist(
                objective.location.x - position[0],
                objective.location.y - position[1],
                objective.location.z - position[2]
            )
            if distance < 12:  # Within reasonable objective range
                reward += 0.5
        
        return reward

    ###########################################################################
    # Reserves Phase (end of Movement Phase)
    ###########################################################################
    def handle_reserves_arrival_phase(self, high_level_agent: 'HighLevelAgent') -> List['Unit']:
        """Handle reserves arrivals at the end of the movement phase.
        
        Args:
            high_level_agent: The high-level agent to make reserves decisions
        
        Returns:
            List of units that arrived from reserves
        """
        if high_level_agent and hasattr(high_level_agent, 'handle_reserves_arrival_phase'):
            return high_level_agent.handle_reserves_arrival_phase(self.game)
        else:
            # Use basic game logic
            return self.game.process_player_reserves_arrivals(self.player)
