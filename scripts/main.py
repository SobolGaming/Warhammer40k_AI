import pygame
import sys
import os
import random
import argparse
import logging
from typing import Tuple

# Suppress pygame initialization messages before importing pygame
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

from warhammer40k_ai.gym_env.warhammer40k_env import WarhammerEnv
from warhammer40k_ai.classes.game import Game
from warhammer40k_ai.classes.map import Map, Obstacle, ObstacleType, Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.classes.player import Player, PlayerType
from warhammer40k_ai.classes.army import parse_army_list
from warhammer40k_ai.UI.game_ui import GameView, GameState, ROSTER_PANE_WIDTH, BATTLEFIELD_WIDTH, BATTLEFIELD_HEIGHT, INFO_PANE_HEIGHT, handle_zoom, handle_pan, TILE_SIZE, BLACK
from warhammer40k_ai.waha_helper import WahaHelper
from warhammer40k_ai.agents.hrl_agent import HighLevelAgent, TacticalAgent, LowLevelAgent
from warhammer40k_ai.UI.game_ui import HumanUIInterface

# Training configuration
TRAINING_MODE = True  # Set to True for AI training, False for manual play
NUM_TRAINING_EPISODES = 1000
CHECKPOINT_INTERVAL = 10  # Save checkpoints every N episodes
CHECKPOINT_DIR = "checkpoints"

# Setup logging with improved configuration
def setup_logging():
    """Configure logging to show clean training progress while suppressing debug noise."""
    # Set up different log levels for different modules
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)  # Only allow INFO and above at root level
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create a formatter for clean output
    formatter = logging.Formatter('%(message)s')
    
    # Custom filter for training progress and important events
    class TrainingProgressFilter(logging.Filter):
        def filter(self, record):
            message = record.getMessage()
            
            # ALWAYS allow these critical training messages
            if any(keyword in message for keyword in [
                'Starting AI training',
                'Episode ', 'completed!',
                'Progress Update',
                'FINAL TRAINING ANALYSIS',
                'Training completed successfully',
                'Win Rate:', 'Combat:', 'First-Player'
            ]):
                return True
                
            # Allow important combat events (deaths, major actions)
            if any(keyword in message for keyword in [
                'has Died', 'has Fled', 'destroyed before attack',
                'models killed', 'casualties'
            ]):
                return True
                
            # Block all DEBUG level noise (shouldn't reach here due to root level, but safety check)
            if record.levelno == logging.DEBUG:
                return False
                
            # Block INFO level DEBUG statements and deployment spam
            if record.levelno == logging.INFO:
                if any(spam in message for spam in [
                    'DEBUG:', 'DEPLOYMENT:', 'EPISODE DEBUG:', 'MONKEY PATCH:',
                    'AGENTS UPDATE:', 'Map has', 'Added', 'Map now has',
                    'Assessing shooting opportunities', 'Found', 'enemy units total',
                    'belongs to army ID', 'Total units on map:', 'Map unit',
                    'Closest target at', 'with', 'found', 'targets'
                ]):
                    return False
                    
            # Allow warnings and errors
            return record.levelno >= logging.WARNING
    
    # Main console handler with clean output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(TrainingProgressFilter())
    
    # Add handler
    root_logger.addHandler(console_handler)
    
    # Quiet down noisy modules completely during training
    logging.getLogger('warhammer40k_ai.agents.hrl_agent').setLevel(logging.ERROR)
    logging.getLogger('pygame').setLevel(logging.ERROR)
    logging.getLogger('warhammer40k_ai.classes.army').setLevel(logging.ERROR)
    logging.getLogger('warhammer40k_ai.waha_helper').setLevel(logging.ERROR)
    logging.getLogger('warhammer40k_ai.classes.unit').setLevel(logging.ERROR)
    logging.getLogger('warhammer40k_ai.classes.model').setLevel(logging.ERROR)
    # Temporarily enable game logging for debugging auto-deployment
    if not TRAINING_MODE:
        logging.getLogger('warhammer40k_ai.classes.game').setLevel(logging.INFO)
    else:
        logging.getLogger('warhammer40k_ai.classes.game').setLevel(logging.ERROR)
    logging.getLogger('warhammer40k_ai.classes.map').setLevel(logging.ERROR)
    
    # Suppress all print statements from game engine during training
    logging.getLogger('warhammer40k_ai').setLevel(logging.ERROR)
    
    # Suppress PyTorch warnings
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning, module="torch")
    warnings.filterwarnings("ignore", category=UserWarning, module="torch")
    
    return logging.getLogger(__name__)

logger = setup_logging()

# Context manager to suppress print statements during noisy operations
import contextlib
import io

@contextlib.contextmanager
def suppress_stdout():
    """Context manager to suppress stdout prints during noisy operations."""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = old_stdout

# Helper
waha_helper = WahaHelper()

def create_checkpoint_dir():
    """Create checkpoint directory if it doesn't exist."""
    if not os.path.exists(CHECKPOINT_DIR):
        os.makedirs(CHECKPOINT_DIR)

def clear_checkpoints():
    """Clear all existing checkpoint files."""
    if os.path.exists(CHECKPOINT_DIR):
        checkpoint_files = [f for f in os.listdir(CHECKPOINT_DIR) if f.endswith('.pth')]
        for file in checkpoint_files:
            os.remove(os.path.join(CHECKPOINT_DIR, file))
        print(f"🗑️  Cleared {len(checkpoint_files)} checkpoint files")
    else:
        print("📁 No checkpoint directory found")

def cleanup_destroyed_units(game: Game):
    """Remove destroyed units from the map and player armies."""
    for player in game.players:
        units_to_remove = []
        for unit in player.get_army().units:
            if not unit.is_alive():
                # Remove unit from map
                if hasattr(unit, 'position') and unit.position:
                    if hasattr(game.map, 'remove_unit'):
                        game.map.remove_unit(unit)
                units_to_remove.append(unit)
        
        # Remove destroyed units from army
        for unit in units_to_remove:
            player.get_army().units.remove(unit)

def print_current_scores(game: Game):
    """Print the current scores for both players after each phase."""
    if len(game.players) >= 2:
        player1_score = game.players[0].get_score()
        player2_score = game.players[1].get_score()
        print(f"📊 SCORES: {game.players[0].name}: {player1_score} | {game.players[1].name}: {player2_score}")

def execute_simple_deployment(game: Game, player1: Player, player2: Player, manual_phases: bool = False) -> dict:
    """Execute deployment using the game's built-in complete_deployment_phase method."""
    
    logger.info("🚀 Starting Simple Deployment Sequence")
    
    # Set up deployment zones first
    battlefield_width, battlefield_height = game.get_battlefield_size()
    deployment_depth = 18.0  # 18 inches from edge
    
    game.deployment_zones = {
        player1.name: {
            'x_range': (0, deployment_depth),  # Left edge to 18" in
            'y_range': (0, battlefield_height)  # Full height
        },
        player2.name: {
            'x_range': (battlefield_width - deployment_depth, battlefield_width),  # 18" from right edge to edge
            'y_range': (0, battlefield_height)  # Full height
        }
    }
    
    # Use the game's built-in deployment method
    game.complete_deployment_phase(manual_phases=manual_phases)
    
    logger.info("✅ Simple deployment complete!")
    
    # Return basic results for compatibility
    return {
        'attacker': game.get_attacker().name,
        'defender': game.get_defender().name,
        'first_turn_player': game.get_attacker().name,  # Attacker goes first by default
        'deployment_zones': game.deployment_zones,
        'reserves': {player1.name: {}, player2.name: {}},  # Empty for now
        'deployment_order': []
    }

def auto_deploy_player_units(game: Game, player: Player, zone: dict):
    """Deploy all units for a single player within their deployment zone."""
    units = player.get_army().units
    x_start, x_end = zone['x_range']
    y_start, y_end = zone['y_range']
    
    print(f"🤖 Auto-deploying {len(units)} units for {player.name}")
    
    for i, unit in enumerate(units):
        x = x_start + (i % 3) * 5
        y = y_start + (i // 3) * 5
        
        # Ensure position stays within zone bounds
        x = max(x_start + 1, min(x, x_end - 1))
        y = max(y_start + 1, min(y, y_end - 1))
        
        for j, model in enumerate(unit.models):
            model_x = x + (j % 2) * 1
            model_y = y + (j // 2) * 1
            model.set_location(model_x, model_y, 0, 0.0)
        
        unit.deployed = True
        game.map.units.append(unit)
        print(f"  ✅ {unit.name} deployed at ({x:.1f}, {y:.1f})")

def auto_deploy_units(game: Game, player1: Player, player2: Player):
    """Legacy function - kept for compatibility. Use execute_simple_deployment instead."""
    logger.warning("⚠️  Using legacy deployment system. Consider using execute_simple_deployment for proper Warhammer 40k rules.")
    
    # Quick fallback deployment using proper Warhammer 40k deployment zones
    battlefield_width, battlefield_height = game.get_battlefield_size()
    deployment_depth = 18.0  # 18 inches from edge
    
    player1_zone = {
        'x_range': (0, deployment_depth),  # Left edge to 18" in
        'y_range': (0, battlefield_height)  # Full height
    }
    
    player2_zone = {
        'x_range': (battlefield_width - deployment_depth, battlefield_width),  # 18" from right edge to edge
        'y_range': (0, battlefield_height)  # Full height
    }
    
    auto_deploy_player_units(game, player1, player1_zone)
    auto_deploy_player_units(game, player2, player2_zone)

def validate_army_files(player1_army_file: str, player2_army_file: str):
    """Validate that army files exist and are readable."""
    if not os.path.exists(player1_army_file):
        raise FileNotFoundError(f"Player 1 army file not found: {player1_army_file}")
    if not os.path.exists(player2_army_file):
        raise FileNotFoundError(f"Player 2 army file not found: {player2_army_file}")

def initialize_game(player1_type: str = 'ai', player2_type: str = 'ai', 
                   player1_army_file: str = 'army_lists/warhammer_app_dump.txt',
                   player2_army_file: str = 'army_lists/chaos_daemons_GT2023.txt') -> Tuple[pygame.Surface, WarhammerEnv, Game, Map, float, int, int, Player, Player]:
    """Initialize basic game structure - armies and setup will be handled in setup phases."""
    pygame.init()
    screen = pygame.display.set_mode((BATTLEFIELD_WIDTH + 2 * ROSTER_PANE_WIDTH, BATTLEFIELD_HEIGHT + INFO_PANE_HEIGHT))
    pygame.display.set_caption('Warhammer 40,000 Battlefield')

    # Convert string types to PlayerType enum
    player1_player_type = PlayerType.HUMAN if player1_type.lower() == 'human' else PlayerType.AI
    player2_player_type = PlayerType.HUMAN if player2_type.lower() == 'human' else PlayerType.AI

    # Create players WITHOUT armies - armies will be loaded in MUSTER_ARMIES phase
    player1 = Player("Player 1", player1_player_type, None)
    player2 = Player("Player 2", player2_player_type, None)
    
    # Create basic game structure
    env = WarhammerEnv(players=[player1, player2])
    game = env.game
    
    # Create empty map - terrain/objectives will be added in CREATE_BATTLEFIELD phase
    game_map = Map(*game.get_battlefield_size())
    game.map = game_map
    
    # Store army file paths for use in setup phases
    game.army_files = {
        'player1': player1_army_file,
        'player2': player2_army_file
    }
    
    zoom_level = 1.0
    offset_x, offset_y = ROSTER_PANE_WIDTH, 0  # Adjust initial offset to account for left pane

    return screen, env, game, game_map, zoom_level, offset_x, offset_y, player1, player2

def run_training_episode(episode_num: int, agents: dict, player_configs: dict = None) -> dict:
    """Run a single training episode and return statistics."""
    try:
        logger.debug(f"Starting episode {episode_num + 1}")
        
        # Use default AI vs AI for training if no config provided
        if player_configs is None:
            player_configs = {
                'player1_type': 'ai',
                'player2_type': 'ai',
                'player1_army_file': 'army_lists/warhammer_app_dump.txt',
                'player2_army_file': 'army_lists/chaos_daemons_GT2023.txt'
            }
        
        # Create fresh game instance for this episode
        screen, env, game, game_map, _, _, _, player1, player2 = initialize_game(
            player_configs['player1_type'],
            player_configs['player2_type'],
            player_configs['player1_army_file'],
            player_configs['player2_army_file']
        )
        logger.debug(f"Game initialization completed for episode {episode_num + 1}")
    except Exception as early_error:
        logger.error(f"❌ EPISODE INITIALIZATION FAILED: {early_error}")
        logger.error(f"Error type: {type(early_error).__name__}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise
    
    # Track detailed statistics
    episode_stats = {
        'episode_num': episode_num + 1,
        'starting_player': game.get_current_player().name,
        'starting_player_index': game.current_player_index,
        'winner': None,
        'player1_score': 0,
        'player2_score': 0,
        'total_turns': 0,
        'objective_position': None,
        # Combat statistics
        'shooting_kills': 0,
        'melee_kills': 0,
        'total_kills': 0,
        'models_destroyed': [],  # Track which models died
        # Command tracking
        'commands_selected': {
            'player1': {'attack': 0, 'defend': 0, 'move': 0},
            'player2': {'attack': 0, 'defend': 0, 'move': 0}
        }
    }
    
    # Track combat stats during the episode
    def track_combat_stats():
        """Track kills by monitoring model count changes."""
        player1_initial_models = sum(len(unit.models) for unit in player1.get_army().units)
        player2_initial_models = sum(len(unit.models) for unit in player2.get_army().units)
        
        # Count current models
        player1_current_models = sum(len(unit.models) for unit in player1.get_army().units if unit.is_alive())
        player2_current_models = sum(len(unit.models) for unit in player2.get_army().units if unit.is_alive())
        
        # Calculate deaths
        player1_deaths = player1_initial_models - player1_current_models
        player2_deaths = player2_initial_models - player2_current_models
        
        episode_stats['total_kills'] = player1_deaths + player2_deaths
        
        return player1_deaths, player2_deaths
    
    # Override the Unit.remove_model method to track deaths
    original_remove_model = None
    
    def tracking_remove_model(self, model, fleed=False):
        """Enhanced remove_model that tracks deaths for statistics."""
        if not fleed:  # Only count actual deaths, not fleeing
            # Determine if this was a shooting or melee kill based on the current game phase
            if game.is_shooting_phase():
                kill_type = 'shooting'
            elif game.is_fight_phase():
                kill_type = 'melee'
            else:
                # Default to melee for other phases (charge phase, etc.)
                kill_type = 'melee'
            
            episode_stats['models_destroyed'].append({
                'model_name': model.name,
                'unit_name': self.name,
                'owner': 'player1' if self in player1.get_army().units else 'player2',
                'turn': game.turn,
                'kill_type': kill_type  # Track whether it was shooting or melee
            })
            
            # Increment the appropriate kill counter
            if kill_type == 'shooting':
                episode_stats['shooting_kills'] += 1
            else:
                episode_stats['melee_kills'] += 1
        # Call original method
        return original_remove_model(self, model, fleed)
    
    # Monkey patch the Unit class to track deaths
    try:
        logger.debug("Setting up kill tracking system...")
        from warhammer40k_ai.classes.unit import Unit
        original_remove_model = Unit.remove_model
        Unit.remove_model = tracking_remove_model
        logger.debug("Kill tracking system activated")
    except Exception as patch_error:
        logger.error(f"❌ KILL TRACKING SETUP FAILED: {patch_error}")
        logger.error(f"Error type: {type(patch_error).__name__}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise  # Re-raise to see the full error
    
    try:
        # Track objective position
        if game.map.objectives:
            obj = game.map.objectives[0]
            episode_stats['objective_position'] = (obj.location.x, obj.location.y)
        
        # Initialize agents for this episode with the NEW game instance
        high_level_agent_player1 = agents['hla1']
        tactical_agent_player1 = agents['ta1'] 
        low_level_agent_player1 = agents['lla1']
        high_level_agent_player2 = agents['hla2']
        tactical_agent_player2 = agents['ta2']
        low_level_agent_player2 = agents['lla2']
        
        # CRITICAL FIX: Update all agents to use the NEW game instance for this episode
        logger.debug("Updating agents to use new game instance...")
        high_level_agent_player1.game = game
        high_level_agent_player1.player = player1
        high_level_agent_player1.opponent = player2
        tactical_agent_player1.game = game
        tactical_agent_player1.player = player1
        low_level_agent_player1.game = game
        low_level_agent_player1.player = player1
        high_level_agent_player2.game = game
        high_level_agent_player2.player = player2
        high_level_agent_player2.opponent = player1
        tactical_agent_player2.game = game
        tactical_agent_player2.player = player2
        low_level_agent_player2.game = game
        low_level_agent_player2.player = player2
        
        # Execute setup phases (BEFORE updating objectives/commands since they're created during setup)
        logger.debug("Starting setup phases...")
        setup_kwargs = {
            'player1_army_file': player_configs.get('player1_army_file'),
            'player2_army_file': player_configs.get('player2_army_file')
        }
        
        while game.is_in_setup_phase():
            current_phase = game.get_current_setup_phase()
            
            # For DEPLOY_ARMIES phase, we need to create AI deployment decision makers
            if current_phase.name == 'DEPLOY_ARMIES':
                from warhammer40k_ai.agents.hrl_agent import AIDeploymentDecisionMaker
                
                # Update objectives and commands BEFORE creating deployment decision makers
                high_level_agent_player1.objectives = game.map.objectives
                high_level_agent_player1.commands = game.commands
                high_level_agent_player1.num_objectives = len(game.map.objectives)
                high_level_agent_player1.num_commands = len(game.commands)
                high_level_agent_player2.objectives = game.map.objectives
                high_level_agent_player2.commands = game.commands
                high_level_agent_player2.num_objectives = len(game.map.objectives)
                high_level_agent_player2.num_commands = len(game.commands)
                
                decision_makers = {
                    player1.name: AIDeploymentDecisionMaker(high_level_agent_player1),
                    player2.name: AIDeploymentDecisionMaker(high_level_agent_player2)
                }
                setup_kwargs['decision_makers'] = decision_makers
                
                logger.debug(f"Updated agents for deployment - Objectives: {len(game.map.objectives)}, Commands: {len(game.commands)}")
            
            game.execute_current_setup_phase(**setup_kwargs)
            setup_complete = game.advance_setup_phase()
            if setup_complete:
                break
        
        # FINAL UPDATE: Ensure agents have the latest objectives and commands after all setup phases
        high_level_agent_player1.objectives = game.map.objectives
        high_level_agent_player1.commands = game.commands
        high_level_agent_player1.num_objectives = len(game.map.objectives)
        high_level_agent_player1.num_commands = len(game.commands)
        high_level_agent_player2.objectives = game.map.objectives
        high_level_agent_player2.commands = game.commands
        high_level_agent_player2.num_objectives = len(game.map.objectives)
        high_level_agent_player2.num_commands = len(game.commands)
        
        logger.debug(f"Final agent state - Objectives: {len(game.map.objectives)}, Commands: {len(game.commands)}")
        logger.debug(f"Objective names: {[obj.name for obj in game.map.objectives]}")
        logger.debug(f"Commands: {game.commands}")
        
        # Store deployment information for later analysis
        episode_stats['deployment'] = {
            'attacker': game.get_attacker().name if game.attacker_index is not None else 'Unknown',
            'defender': game.get_defender().name if game.defender_index is not None else 'Unknown',
            'first_turn_player': game.get_current_player().name,
            'deployment_zones': game.deployment_zones,
            'reserves_count': {
                player1.name: 0,  # Simple deployment doesn't use reserves yet
                player2.name: 0
            }
        }
        
        logger.debug("Setup phases completed successfully")
        
        # Run the game loop (suppress print statements during training)
        with suppress_stdout():
            while not game.is_game_over():
                current_player = game.get_current_player()
                current_player_key = 'player1' if current_player == player1 else 'player2'
                
                if current_player == player1:
                    high_level_agent = high_level_agent_player1
                    tactical_agent = tactical_agent_player1
                else:
                    high_level_agent = high_level_agent_player2
                    tactical_agent = tactical_agent_player2

                # Get objective and command at start of each phase (needed for all phases)
                objective, command = high_level_agent.choose_objective_and_command()
                
                # Execute the current phase based on game state
                if game.is_command_phase():
                    # Command phase - all players gain 1 CP at the start
                    game.start_command_phase()
                    episode_stats['commands_selected'][current_player_key][command] += 1
                    
                    # Update objective control at the start of each turn (like in manual mode)
                    for obj in game.map.objectives:
                        if isinstance(obj.location, ObjectivePoint):
                            obj.location.update_control(game)
                        if obj.check_completion(game):
                            logger.debug(f"Objective {obj.name} completed by {current_player.name}!")
                            current_player.add_score(obj.points)
                    
                    tactical_agent.command_phase(command)
                    game.next_phase()
                    print_current_scores(game)
                    
                elif game.is_movement_phase():
                    # Movement phase for all units
                    for unit in current_player.get_army().units:
                        if unit.is_alive():
                            tactical_agent.movement_phase(unit, objective)
                    game.next_phase()
                    print_current_scores(game)
                    
                elif game.is_shooting_phase():
                    # Shooting phase for all units
                    for unit in current_player.get_army().units:
                        if unit.is_alive():
                            tactical_agent.shooting_phase(unit)
                    game.next_phase()
                    print_current_scores(game)
                    
                elif game.is_charge_phase():
                    # Charge phase for all units
                    for unit in current_player.get_army().units:
                        if unit.is_alive():
                            charge_reward = tactical_agent.charge_phase(unit)
                            if charge_reward:
                                tactical_agent.movement_rewards.append(charge_reward)
                    game.next_phase()
                    print_current_scores(game)
                    
                elif game.is_fight_phase():
                    # Fight phase for all units
                    for unit in current_player.get_army().units:
                        if unit.is_alive():
                            tactical_agent.fight_phase(unit)
                    game.next_phase()  # This will advance to next player or next turn
                    print_current_scores(game)

                # Clean up destroyed units after each phase
                cleanup_destroyed_units(game)
                
                # Update turn counter
                episode_stats['total_turns'] = game.turn

        # Update all agent policies after episode
        for agent_key, agent in agents.items():
            agent.update_policies() if hasattr(agent, 'update_policies') else agent.update_policy()
    
    finally:
        # Restore original method
        Unit.remove_model = original_remove_model
    
    # Final statistics
    episode_stats['player1_score'] = player1.get_score()
    episode_stats['player2_score'] = player2.get_score()
    episode_stats['total_kills'] = len(episode_stats['models_destroyed'])
    
    if player1.get_score() > player2.get_score():
        episode_stats['winner'] = 'player1'
    elif player2.get_score() > player1.get_score():
        episode_stats['winner'] = 'player2'
    else:
        episode_stats['winner'] = 'ties'  # Changed from 'tie' to 'ties' to match the stats dict
    
    print(f"Episode {episode_num + 1} completed! Winner: {episode_stats['winner']}, Score: {episode_stats['player1_score']}-{episode_stats['player2_score']}, Turns: {episode_stats['total_turns']} {'🔄' if episode_stats['winner'] == 'ties' else '🏆'}")
    
    return episode_stats

def run_training_loop(clear_checkpoints_flag=False, player_configs=None):
    """Run the main training loop for the specified number of episodes."""
    print(f"Starting AI training mode for {NUM_TRAINING_EPISODES} episodes...")
    
    # Create checkpoint directory
    create_checkpoint_dir()
    
    # Clear checkpoints if requested
    if clear_checkpoints_flag:
        clear_checkpoints()
    
    # Use default AI vs AI for training if no config provided
    if player_configs is None:
        player_configs = {
            'player1_type': 'ai',
            'player2_type': 'ai',
            'player1_army_file': 'army_lists/warhammer_app_dump.txt',
            'player2_army_file': 'army_lists/chaos_daemons_GT2023.txt'
        }
    
    # Initialize all agents with first game instance to get proper dimensions
    screen, env, game, game_map, _, _, _, player1, player2 = initialize_game(
        player_configs['player1_type'],
        player_configs['player2_type'],
        player_configs['player1_army_file'],
        player_configs['player2_army_file']
    )
    objectives = game.map.objectives
    commands = game.commands
    
    # Initialize agents
    agents = {
        'hla1': HighLevelAgent(game, player1, player2, objectives, commands),
        'ta1': TacticalAgent(game, player1),
        'lla1': LowLevelAgent(game, player1),
        'hla2': HighLevelAgent(game, player2, player1, objectives, commands),
        'ta2': TacticalAgent(game, player2),
        'lla2': LowLevelAgent(game, player2)
    }
    
    # Load existing checkpoints if available
    for agent_key, agent in agents.items():
        checkpoint_file = f"{CHECKPOINT_DIR}/{agent_key}_checkpoint.pth"
        agent.load_checkpoint(checkpoint_file)
    
    # Training statistics
    training_stats = {
        'total_episodes': 0,
        'wins': {'player1': 0, 'player2': 0, 'ties': 0},
        'first_player_advantage': {'starting_player_wins': 0, 'second_player_wins': 0},
        'total_turns': 0,
        'combat_data': {
            'total_shooting_kills': 0,
            'total_melee_kills': 0,
            'shooting_vs_melee_ratio': 0.0
        },
        'command_usage': {'attack': 0, 'defend': 0, 'move': 0},
        'charge_success_rate': 0.0,
        'average_models_lost_per_episode': 0.0,
        'objective_positions': []  # For bias analysis
    }
    
    all_episode_stats = []  # Store all episode data for detailed analysis
    
    print("=" * 60)
    
    # Run training episodes
    for episode in range(NUM_TRAINING_EPISODES):
        try:
            episode_stats = run_training_episode(episode, agents, player_configs)
        except Exception as episode_error:
            logger.error(f"❌ Episode {episode + 1} FAILED: {episode_error}")
            logger.error(f"Error type: {type(episode_error).__name__}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            continue  # Skip to next episode
            
        all_episode_stats.append(episode_stats)
        
        # Update training statistics with episode results
        training_stats['total_episodes'] += 1
        training_stats['total_turns'] += episode_stats['total_turns']
        
        # Ensure winner is handled properly
        winner = episode_stats['winner']
        if winner in training_stats['wins']:
            training_stats['wins'][winner] += 1
        else:
            # This shouldn't happen, but let's be safe
            training_stats['wins']['ties'] += 1
        
        # Combat statistics
        training_stats['combat_data']['total_shooting_kills'] += episode_stats.get('shooting_kills', 0)
        training_stats['combat_data']['total_melee_kills'] += episode_stats.get('melee_kills', 0)
        
        # Command usage tracking
        for player in ['player1', 'player2']:
            for command in ['attack', 'defend', 'move']:
                training_stats['command_usage'][command] += episode_stats['commands_selected'][player][command]
        
        # Objective positioning for bias analysis
        if episode_stats['objective_position']:
            training_stats['objective_positions'].append(episode_stats['objective_position'])
        
        # First player advantage tracking
        starting_player = episode_stats['starting_player_index']
        winning_player = episode_stats['winner']
        
        if winning_player != 'ties':
            if (starting_player == 0 and winning_player == 'player1') or (starting_player == 1 and winning_player == 'player2'):
                training_stats['first_player_advantage']['starting_player_wins'] += 1
            else:
                training_stats['first_player_advantage']['second_player_wins'] += 1
        
        # Progress updates every 10 episodes
        if (episode + 1) % 10 == 0:
            display_progress_update(episode + 1, training_stats, all_episode_stats)
        
        # Save checkpoints periodically
        if (episode + 1) % CHECKPOINT_INTERVAL == 0:
            print(f"💾 Saving checkpoints after episode {episode + 1}...")
            for agent_key, agent in agents.items():
                checkpoint_file = f"{CHECKPOINT_DIR}/{agent_key}_checkpoint.pth"
                agent.save_checkpoint(checkpoint_file)
    
    # Final comprehensive analysis
    display_final_analysis(training_stats, all_episode_stats)

def display_progress_update(episode_num: int, training_stats: dict, all_episode_stats: list):
    """Display progress update with key statistics."""
    total_episodes = training_stats['total_episodes']
    p1_wins = training_stats['wins']['player1']
    p2_wins = training_stats['wins']['player2']
    ties = training_stats['wins']['ties']
    avg_turns = training_stats['total_turns'] / total_episodes if total_episodes > 0 else 0
    
    # First player advantage analysis
    first_wins = training_stats['first_player_advantage']['starting_player_wins']
    second_wins = training_stats['first_player_advantage']['second_player_wins']
    total_decided = first_wins + second_wins
    first_advantage = (first_wins / total_decided * 100) if total_decided > 0 else 50
    
    # Combat effectiveness
    shooting_kills = training_stats['combat_data']['total_shooting_kills']
    melee_kills = training_stats['combat_data']['total_melee_kills']
    total_kills = shooting_kills + melee_kills
    shooting_percentage = (shooting_kills / total_kills * 100) if total_kills > 0 else 0
    
    print(f"📊 Progress Update - Episode {episode_num}/{NUM_TRAINING_EPISODES}")
    print(f"   Player 1 Win Rate: {p1_wins/total_episodes*100:.1f}% ({p1_wins} wins)")
    print(f"   Player 2 Win Rate: {p2_wins/total_episodes*100:.1f}% ({p2_wins} wins)")
    print(f"   First-Player Advantage: {first_advantage:.1f}% (🎯 {first_wins}, 🔄 {second_wins})")
    print(f"   Combat: {shooting_percentage:.1f}% shooting, {100-shooting_percentage:.1f}% melee ({total_kills} total kills)")
    print(f"   Avg Turns/Episode: {avg_turns:.1f}")
    print("----------------------------------------")

def display_final_analysis(training_stats: dict, all_episode_stats: list):
    """Display comprehensive final training analysis."""
    print("\n" + "=" * 70)
    print("🏁 FINAL TRAINING ANALYSIS")
    print("=" * 70)
    
    total_episodes = len(all_episode_stats)
    
    # Win rates
    p1_wins = training_stats['wins']['player1']
    p2_wins = training_stats['wins']['player2']
    ties = training_stats['wins']['ties']
    
    print(f"\n📈 WIN STATISTICS:")
    print(f"   Total Episodes: {total_episodes}")
    if total_episodes > 0:
        print(f"   Player 1 Wins: {p1_wins} ({p1_wins/total_episodes*100:.1f}%)")
        print(f"   Player 2 Wins: {p2_wins} ({p2_wins/total_episodes*100:.1f}%)")
        print(f"   Ties: {ties} ({ties/total_episodes*100:.1f}%)")
    else:
        print("   No completed episodes to analyze.")
    
    # First player advantage analysis
    first_wins = training_stats['first_player_advantage']['starting_player_wins']
    second_wins = training_stats['first_player_advantage']['second_player_wins']
    total_decided = first_wins + second_wins
    
    print(f"\n🎯 FIRST PLAYER ADVANTAGE ANALYSIS:")
    if total_decided > 0:
        print(f"   Starting player wins: {first_wins} ({first_wins/total_decided*100:.1f}%)")
        print(f"   Second player wins: {second_wins} ({second_wins/total_decided*100:.1f}%)")
        bias_indicator = "⚠️ BIAS DETECTED" if abs(first_wins - second_wins) > total_decided * 0.2 else "✅ BALANCED"
        print(f"   Conclusion: {bias_indicator}")
    else:
        print(f"   No decisive games to analyze first-player advantage")
        print(f"   All games were ties - may indicate scoring system issues")
    
    # Combat analysis
    shooting_kills = training_stats['combat_data']['total_shooting_kills']
    melee_kills = training_stats['combat_data']['total_melee_kills']
    total_kills = shooting_kills + melee_kills
    
    print(f"\n⚔️ COMBAT EFFECTIVENESS:")
    if total_kills > 0:
        print(f"   Total Models Killed: {total_kills}")
        print(f"   Shooting Kills: {shooting_kills} ({shooting_kills/total_kills*100:.1f}%)")
        print(f"   Melee Kills: {melee_kills} ({melee_kills/total_kills*100:.1f}%)")
    else:
        # Look at detailed episode stats for actual death tracking
        total_deaths = sum(len(episode['models_destroyed']) for episode in all_episode_stats)
        if total_deaths > 0:
            print(f"   Total Models Killed: {total_deaths}")
            # Analyze deaths by player
            player1_deaths = sum(len([d for d in episode['models_destroyed'] if d['owner'] == 'player2']) for episode in all_episode_stats)
            player2_deaths = sum(len([d for d in episode['models_destroyed'] if d['owner'] == 'player1']) for episode in all_episode_stats) 
            print(f"   Player 1 killed {player1_deaths} enemy models")
            print(f"   Player 2 killed {player2_deaths} enemy models")
            
            # Show some examples of what died
            all_deaths = []
            for episode in all_episode_stats:
                all_deaths.extend(episode['models_destroyed'])
            
            if all_deaths:
                unit_types = {}
                for death in all_deaths[:10]:  # Show first 10 deaths as examples
                    unit_type = death['model_name']
                    unit_types[unit_type] = unit_types.get(unit_type, 0) + 1
                
                print(f"   Most common casualties: {', '.join([f'{name} ({count})' for name, count in list(unit_types.items())[:5]])}")
        else:
            print(f"   Total Models Killed: 0")
            print(f"   No models were killed during training")
            print(f"   May indicate units not engaging or damage system issues")
    
    # Command usage analysis
    total_commands = sum(training_stats['command_usage'].values())
    print(f"\n🎮 COMMAND USAGE ANALYSIS:")
    for command, count in training_stats['command_usage'].items():
        percentage = count / total_commands * 100 if total_commands > 0 else 0
        print(f"   '{command}': {count} times ({percentage:.1f}%)")
    
    # Objective positioning (bias check)
    if training_stats['objective_positions']:
        avg_x = sum(pos[0] for pos in training_stats['objective_positions']) / len(training_stats['objective_positions'])
        avg_y = sum(pos[1] for pos in training_stats['objective_positions']) / len(training_stats['objective_positions'])
        print(f"\n🎯 OBJECTIVE POSITIONING:")
        print(f"   Average position: ({avg_x:.1f}, {avg_y:.1f})")
        print(f"   Randomization: {'✅ Working' if len(set(training_stats['objective_positions'])) > total_episodes * 0.7 else '⚠️ May need improvement'}")
    
    # Average game length
    avg_turns = training_stats['total_turns'] / total_episodes if total_episodes > 0 else 0
    print(f"\n⏱️ GAME LENGTH:")
    print(f"   Average turns per episode: {avg_turns:.1f}")
    if all_episode_stats:
        print(f"   Longest game: {max(stats['total_turns'] for stats in all_episode_stats)} turns")
        print(f"   Shortest game: {min(stats['total_turns'] for stats in all_episode_stats)} turns")
    else:
        print("   No episode data available.")
    
    print("\n" + "=" * 70)
    print("🎉 Training completed successfully!")
    print("=" * 70)

def main_game_loop(player_configs=None) -> None:
    # Use default configurations if none provided
    if player_configs is None:
        player_configs = {
            'player1_type': 'human',
            'player2_type': 'ai',
            'player1_army_file': 'army_lists/warhammer_app_dump.txt',
            'player2_army_file': 'army_lists/chaos_daemons_GT2023.txt'
        }
    
    screen, env, game, game_map, _, _, _, player1, player2 = initialize_game(
        player_configs['player1_type'],
        player_configs['player2_type'],
        player_configs['player1_army_file'],
        player_configs['player2_army_file']
    )
    
    # Setup phases will be handled by pressing SPACE to advance through each phase
    print(f"📋 Game ready! Press SPACE to begin setup phase: {game.get_current_setup_phase().name}")
    
    # Create UI interface for human player interactions
    screen_width, screen_height = screen.get_size()
    ui_interface = HumanUIInterface(screen_width, screen_height)
    
    game_view = GameView(screen, env, game, game_map, player1, player2, ui_interface)
    game_state = GameState.SETUP
    clicked_unit = None

    # Initialize agent variables (will be created after setup phases)
    high_level_agent_player1 = None
    tactical_agent_player1 = None
    low_level_agent_player1 = None
    high_level_agent_player2 = None
    tactical_agent_player2 = None
    low_level_agent_player2 = None

    def create_ai_agents():
        """Create AI agents after setup phases are complete and objectives/commands are available."""
        nonlocal high_level_agent_player1, tactical_agent_player1, low_level_agent_player1
        nonlocal high_level_agent_player2, tactical_agent_player2, low_level_agent_player2
        
        # Create AI agents only for AI players
        if player1.type == PlayerType.AI:
            high_level_agent_player1 = HighLevelAgent(game, player1, player2, objectives=game.map.objectives, commands=game.commands)
            tactical_agent_player1 = TacticalAgent(game, player1)
            low_level_agent_player1 = LowLevelAgent(game, player1)
            
        if player2.type == PlayerType.AI:
            high_level_agent_player2 = HighLevelAgent(game, player2, player1, objectives=game.map.objectives, commands=game.commands)
            tactical_agent_player2 = TacticalAgent(game, player2)
            low_level_agent_player2 = LowLevelAgent(game, player2)
        
        # Load checkpoints for AI players only
        if os.path.exists(CHECKPOINT_DIR):
            print("Loading trained AI models...")
            if high_level_agent_player1:
                high_level_agent_player1.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'hla1_checkpoint.pth'))
                tactical_agent_player1.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'ta1_checkpoint.pth'))
                low_level_agent_player1.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'lla1_checkpoint.pth'))
            if high_level_agent_player2:
                high_level_agent_player2.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'hla2_checkpoint.pth'))
                tactical_agent_player2.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'ta2_checkpoint.pth'))
                low_level_agent_player2.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'lla2_checkpoint.pth'))

    print("Starting main game loop")
    print(f"🎮 Game mode: {player1.name} ({player1.type.name}) vs {player2.name} ({player2.type.name})")
    print("Controls:")
    manual_phases_required = (player1.type == PlayerType.HUMAN or player2.type == PlayerType.HUMAN or 
                             player_configs.get('manual_phases', False))
    
    if manual_phases_required:
        if player_configs.get('manual_phases', False):
            print("🔧 Manual phases mode enabled - SPACE required to advance phases")
        print("  - SPACE: Advance through setup phases and battle round phases")
        print("  - A: Force AI action (if needed)")
        print("  - ESC: Close panels/deselect units")
        print("  - Mouse: Click units for details, drag to move in movement phase")
        print("  - AI players will act automatically when it's their turn")
        print(f"📋 Press SPACE to begin setup phase: {game.get_current_setup_phase().name}")
    else:
        print("🤖 Both players are AI - executing setup phases automatically...")
        # Execute all setup phases automatically for AI vs AI
        setup_kwargs = {
            'player1_army_file': player_configs.get('player1_army_file'),
            'player2_army_file': player_configs.get('player2_army_file')
        }
        
        while game.is_in_setup_phase():
            current_phase = game.get_current_setup_phase()
            print(f"🚀 AI executing setup phase: {current_phase.name}")
            game.execute_current_setup_phase(**setup_kwargs)
            
            # Refresh UI after MUSTER_ARMIES phase
            if current_phase.name == 'MUSTER_ARMIES':
                game_view.refresh_roster_panes()
                print("📋 Roster panes refreshed with loaded armies")
            
            setup_complete = game.advance_setup_phase()
            if setup_complete:
                break
        
        print("✅ AI setup completed! Battle begins!")
        game_state = GameState.PLAYING
        
        # Create AI agents now that objectives and commands are available
        create_ai_agents()

    # Ensure pygame display is properly initialized
    game_view.draw()
    pygame.display.flip()

    running = True
    while running:
        # Deployment is now handled by execute_simple_deployment() - no manual handling needed
        
        # Check if current player is AI and should take action automatically (normal game phases)
        if game_state == GameState.PLAYING and not game.is_deployment_phase():
            current_player = game.get_current_player()
            manual_phases_required = player_configs.get('manual_phases', False)
            should_do_ai_action = (current_player.type == PlayerType.AI and not game.is_game_over() and not manual_phases_required)
            
            # Auto-enable AI action for AI players (unless manual phases mode is enabled)
            if should_do_ai_action:
                game.do_ai_action = True
                #print(f"🤖 {current_player.name} (AI) taking action automatically...")
            #elif manual_phases_required and current_player.type == PlayerType.AI:
                #print(f"🔧 {current_player.name} (AI) waiting for SPACE key (manual phases mode)")
        
        if game_state == GameState.PLAYING and game.do_ai_action:
            # Only do AI actions if at least one player is AI
            if player1.type == PlayerType.AI or player2.type == PlayerType.AI:
                
                while not game.is_game_over():
                    current_player = game.get_current_player()
                    
                    # Skip AI logic for human players
                    if current_player.type == PlayerType.HUMAN:
                        print(f"🎮 TURN {game.turn} | {current_player.name} ({current_player.type.name}) | Phase: {game.phase.name} - Waiting for human input...")
                        game.do_ai_action = False  # Disable AI action for human players
                        break  # Exit AI loop, let human player take control
                    
                    # AI player logic
                    if current_player == player1:
                        high_level_agent = high_level_agent_player1
                        tactical_agent = tactical_agent_player1
                        low_level_agent = low_level_agent_player1
                    else:
                        high_level_agent = high_level_agent_player2
                        tactical_agent = tactical_agent_player2
                        low_level_agent = low_level_agent_player2

                    # Ensure we have AI agents for this player
                    if not high_level_agent or not tactical_agent or not low_level_agent:
                        print(f"⚠️ No AI agents found for {current_player.name} - skipping AI action")
                        break

                    print(f"🎮 TURN {game.turn} | {current_player.name} ({current_player.type.name}) | Phase: {game.phase.name}")

                    objective, command = high_level_agent.choose_objective_and_command()
                    print(f"{current_player.name} chose Objective: {objective.name}, Command: {command}")

                    # Record average distance at start of turn for high-level reward calculation
                    avg_distance_before = current_player.compute_average_distance(objective)

                    if game.is_command_phase():
                        # Command phase - all players gain 1 CP at the start
                        game.start_command_phase()
                        # Update objective control at the end of each turn
                        for obj in game.map.objectives:
                            if isinstance(obj.location, ObjectivePoint):
                                obj.location.update_control(game)
                            if obj.check_completion(game):
                                print(f"Objective {obj.name} completed!")
                                current_player.add_score(obj.points)
                        tactical_agent.command_phase(command)
                        game.next_phase()
                        print_current_scores(game)
                    elif game.is_movement_phase():
                        for unit in current_player.army.units:
                            tactical_agent.movement_phase(unit, objective)
                        game.next_phase()
                        print_current_scores(game)
                    elif game.is_shooting_phase():
                        for unit in current_player.army.units:
                            tactical_agent.shooting_phase(unit)
                        game.next_phase()
                        print_current_scores(game)
                    elif game.is_charge_phase():
                        for unit in current_player.army.units:
                            tactical_agent.charge_phase(unit)
                        game.next_phase()
                        print_current_scores(game)
                    elif game.is_fight_phase():
                        for unit in current_player.army.units:
                            tactical_agent.fight_phase(unit)
                        game.next_phase()  # This will trigger next_turn() since it's the last phase
                        print_current_scores(game)
                    
                    # In manual phases mode, pause after each phase and wait for SPACE
                    if player_configs.get('manual_phases', False):
                        game.do_ai_action = False  # Stop AI loop, wait for SPACE key
                        print(f"🔧 Phase {game.phase.name} completed. Press SPACE to continue...")
                        break  # Exit AI loop, wait for manual input

                    # Compute aggregated reward for the High Level Agent based on distance improvement.
                    avg_distance_after = current_player.compute_average_distance(objective)
                    high_level_reward = (avg_distance_before - avg_distance_after) * 1.0  # scale factor can be tuned
                    print(f"High Level Reward: {high_level_reward} (Avg before: {avg_distance_before}, Avg after: {avg_distance_after})")

                    high_level_agent.store_reward(high_level_reward)
                    high_level_agent.update_policy()
                    tactical_agent.update_policies()
                    low_level_agent.update_policy()
                    
                    # Clean up destroyed units from the map
                    cleanup_destroyed_units(game)

                    # Update the display
                    game_view.draw()
                    pygame.display.flip()

                    if game.is_game_over():
                        print(f"Game over! Winner: {game.get_winner().name} with score: {game.get_winner().get_score()} vs {game.get_loser().get_score()}")
                        # Only update AI agents if they exist
                        if high_level_agent_player1 and high_level_agent_player2:
                            if game.get_winner() == player1:
                                high_level_agent_player1.store_reward(100)
                                high_level_agent_player1.update_policy()
                                high_level_agent_player2.store_reward(-100)
                                high_level_agent_player2.update_policy()
                            else:
                                high_level_agent_player2.store_reward(100)
                                high_level_agent_player2.update_policy()
                                high_level_agent_player1.store_reward(-100)
                                high_level_agent_player1.update_policy()
            game.do_ai_action = False

        for event in pygame.event.get():
            # Let GameView handle UI events first (including deployment dialogs)
            if game_view.handle_pygame_event(event):
                continue  # Event was handled by UI, skip other processing
                
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if game_state == GameState.PLAYING and event.button == 1:  # Left mouse button
                    # Normal game phase handling (deployment is handled by execute_simple_deployment)
                    if clicked_unit:
                        if game.get_current_player().has_unit(clicked_unit):
                            game_view.selected_unit = clicked_unit
                        else:
                            print("Unit not found in current player's army")

                        if game_view.selected_unit:
                            if game.is_movement_phase():
                                # Convert screen coordinates to game coordinates
                                game_x = (event.pos[0] - ROSTER_PANE_WIDTH - game_view.offset_x) / (TILE_SIZE * game_view.zoom_level)
                                game_y = (event.pos[1] - game_view.offset_y) / (TILE_SIZE * game_view.zoom_level)
                                game_z = 0.0
                                # Move the selected unit
                                success = game_view.selected_unit.move((game_x, game_y, game_z), game_view.game_map)
                                game_view.selected_unit = None  # Deselect the unit after moving
                        clicked_unit = None
                        game_view.info_pane.selected_unit = clicked_unit
                    else:
                        clicked_unit = game_view.get_unit_at_position(*event.pos)
                        if clicked_unit:
                            game_view.info_pane.selected_unit = clicked_unit
                            print(f"Selected unit: {clicked_unit.name}")
                        else:
                            print("No unit at this position")
                else:
                    # Always allow game_view to handle mouse events (including during setup/deployment)
                    game_view.on_mouse_press(*event.pos, event.button)
            elif event.type == pygame.MOUSEBUTTONUP:
                # Handle mouse button releases
                game_view.on_mouse_release(*event.pos, event.button)
            elif event.type == pygame.MOUSEMOTION:
                # Handle mouse motion for panning
                game_view.on_mouse_motion(*event.pos)
            elif event.type == pygame.MOUSEWHEEL:
                # Handle mouse wheel scrolling
                mouse_pos = pygame.mouse.get_pos()
                # Always call on_mouse_scroll first - it will handle unit detail panel and roster panes
                # and return early if handled, preventing zoom changes
                game_view.on_mouse_scroll(*mouse_pos, event.y)
                
                # Only handle zoom if scrolling wasn't handled by UI elements
                keys = pygame.key.get_pressed()
                battlefield_area = (ROSTER_PANE_WIDTH < mouse_pos[0] < BATTLEFIELD_WIDTH + ROSTER_PANE_WIDTH)
                if not (game_view.detailed_unit or 
                        game_view.left_roster_pane.rect.collidepoint(mouse_pos) or 
                        game_view.right_roster_pane.rect.collidepoint(mouse_pos) or
                        (battlefield_area and (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] or 
                                             keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]))):
                    game_view.zoom_level = handle_zoom(game_view.zoom_level, event)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE and game_state == GameState.SETUP:
                    # Check if we're waiting for deployment input during DEPLOY_ARMIES phase
                    if getattr(game, 'waiting_for_deployment_input', False):
                        # Continue deployment by calling complete_deployment_phase again
                        print("🔧 Continuing deployment...")
                        game.complete_deployment_phase(manual_phases=player_configs.get('manual_phases', False))
                        
                        # If deployment is now complete, advance to next setup phase
                        if not getattr(game, 'waiting_for_deployment_input', False):
                            setup_complete = game.advance_setup_phase()
                            
                            if setup_complete:
                                # Setup is complete, start battle rounds
                                game_state = GameState.PLAYING
                                print("🎉 All setup phases complete! Battle begins!")
                                print("Press SPACE to advance battle round phases.")
                                
                                # Create AI agents now that objectives and commands are available
                                create_ai_agents()
                            else:
                                # Show next setup phase
                                print(f"📋 Next phase: {game.get_current_setup_phase().name}")
                                print("Press SPACE to continue setup.")
                        continue
                    
                    # Advance through setup phases when user presses SPACE
                    if game.is_in_setup_phase():
                        current_phase = game.get_current_setup_phase()
                        print(f"🚀 Executing setup phase: {current_phase.name}")
                        
                        # Execute current setup phase with necessary parameters
                        setup_kwargs = {
                            'player1_army_file': player_configs.get('player1_army_file'),
                            'player2_army_file': player_configs.get('player2_army_file'),
                            'manual_phases': player_configs.get('manual_phases', False)
                        }
                        game.execute_current_setup_phase(**setup_kwargs)
                        
                        # Refresh UI after MUSTER_ARMIES phase
                        if current_phase.name == 'MUSTER_ARMIES':
                            game_view.refresh_roster_panes()
                            print("📋 Roster panes refreshed with loaded armies")
                        
                        # Update roster pane titles after attacker/defender determination
                        if current_phase.name == 'DETERMINE_ATTACKER_AND_DEFENDER':
                            game_view.update_roster_pane_titles()
                            print("📋 Roster pane titles updated with Attacker/Defender roles")
                        
                        # Check if we're waiting for deployment input (manual phases during DEPLOY_ARMIES)
                        if getattr(game, 'waiting_for_deployment_input', False):
                            # Don't advance setup phase yet, wait for more SPACE presses to continue deployment
                            continue
                        
                        # Advance to next setup phase
                        setup_complete = game.advance_setup_phase()
                        
                        if setup_complete:
                            # Setup is complete, start battle rounds
                            game_state = GameState.PLAYING
                            print("🎉 All setup phases complete! Battle begins!")
                            print("Press SPACE to advance battle round phases.")
                            
                            # Create AI agents now that objectives and commands are available
                            create_ai_agents()
                        else:
                            # Show next setup phase
                            print(f"📋 Next phase: {game.get_current_setup_phase().name}")
                            print("Press SPACE to continue setup.")
                    else:
                        print("⚠️ Setup is already complete")
                elif event.key == pygame.K_SPACE and game_state == GameState.PLAYING:
                    # In manual phases mode, trigger AI action if current player is AI
                    if player_configs.get('manual_phases', False) and game.get_current_player().type == PlayerType.AI:
                        game.do_ai_action = True
                        current_player = game.get_current_player()
                        print(f"🔧 Manual trigger: {current_player.name} (AI) | Phase: {game.phase.name}")
                    else:
                        # Normal human player phase advancement
                        game.next_phase()
                        print(f"Advanced to {game.phase.name} phase")
                        print_current_scores(game)
                elif event.key == pygame.K_a and game_state == GameState.PLAYING:
                    game.do_ai_action = True
                    print("🤖 Manual AI action triggered")
                elif event.key == pygame.K_ESCAPE:
                    # Close unit details panel or deselect units
                    game_view.close_unit_details()
                    game_view.selected_unit = None
                    game_view.left_roster_pane.selected_unit = None
                    game_view.right_roster_pane.selected_unit = None
                else:
                    # Pass other key events to game_view for handling (including detail panel scrolling)
                    game_view.on_key_press(event.key)

        # Only check keys if pygame is properly initialized
        try:
            keys_pressed = pygame.key.get_pressed()
            game_view.offset_x, game_view.offset_y = handle_pan(keys_pressed, game_view.offset_x, game_view.offset_y, game_view.zoom_level)
        except pygame.error as e:
            # If pygame has issues, reinitialize the display
            if "video system not initialized" in str(e):
                print(f"⚠️ Pygame error detected: {e}")
                print("🔄 Attempting to reinitialize pygame...")
                pygame.display.set_mode((BATTLEFIELD_WIDTH + 2 * ROSTER_PANE_WIDTH, BATTLEFIELD_HEIGHT + INFO_PANE_HEIGHT))
                pygame.display.set_caption('Warhammer 40,000 Battlefield')
            else:
                print(f"⚠️ Pygame error: {e}")
                # Skip this frame
                pass

        if game_state == GameState.PLAYING:
            # Update objective control after each human action
            for objective in game.objectives:
                if isinstance(objective, ObjectivePoint):
                    objective.update_control(game)

        game_view.draw()
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    # Check command line arguments to determine mode
    parser = argparse.ArgumentParser(
        description='Warhammer 40k AI Training and Game',
        epilog="""
Examples:
  # AI vs AI training (default)
  python main.py --mode train --episodes 100
  
  # Human vs AI gameplay
  python main.py --mode play --player1 human --player2 ai
  
  # AI vs AI gameplay
  python main.py --mode play --player1 ai --player2 ai
  
  # AI vs AI with manual phase control (for debugging/demonstration)
  python main.py --mode play --player1 ai --player2 ai --manual-phases
  
  # Human vs Human gameplay  
  python main.py --mode play --player1 human --player2 human
  
  # Custom army lists
  python main.py --mode play --player1 human --player2 ai --player1-army my_army.txt --player2-army enemy_army.txt
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--mode', choices=['train', 'play'], default='train',
                        help='Run mode: train for AI training, play for manual play')
    parser.add_argument('--episodes', type=int, default=1000,
                        help='Number of training episodes (default: 1000)')
    parser.add_argument('--checkpoint-interval', type=int, default=10,
                        help='Save checkpoints every N episodes (default: 10)')
    parser.add_argument('--clear-checkpoints', action='store_true',
                        help='Clear existing checkpoints and start fresh (useful after model changes)')
    parser.add_argument('--player1', choices=['ai', 'human'], default='ai',
                        help='Player 1 type: ai or human (default: ai)')
    parser.add_argument('--player2', choices=['ai', 'human'], default='ai',
                        help='Player 2 type: ai or human (default: ai)')
    parser.add_argument('--player1-army', type=str, default='army_lists/warhammer_app_dump.txt',
                        help='Army list file for Player 1 (default: army_lists/warhammer_app_dump.txt)')
    parser.add_argument('--player2-army', type=str, default='army_lists/chaos_daemons_GT2023.txt',
                        help='Army list file for Player 2 (default: army_lists/chaos_daemons_GT2023.txt)')
    parser.add_argument('--manual-phases', action='store_true',
                        help='Require SPACE key to advance phases even in AI vs AI matches (useful for debugging/demonstration)')
    
    args = parser.parse_args()
    
    # Update global configuration based on arguments
    TRAINING_MODE = (args.mode == 'train')
    NUM_TRAINING_EPISODES = args.episodes
    CHECKPOINT_INTERVAL = args.checkpoint_interval
    
    # Create player configuration dictionary
    player_configs = {
        'player1_type': args.player1,
        'player2_type': args.player2,
        'player1_army_file': args.player1_army,
        'player2_army_file': args.player2_army,
        'manual_phases': args.manual_phases
    }
    
    # Validate player configurations
    if TRAINING_MODE and (args.player1 != 'ai' or args.player2 != 'ai'):
        print("⚠️ WARNING: Training mode works best with AI vs AI. Setting both players to AI for training.")
        player_configs['player1_type'] = 'ai'
        player_configs['player2_type'] = 'ai'
    
    # Display configuration
    print(f"🎮 Game Configuration:")
    print(f"   Mode: {args.mode.upper()}")
    print(f"   Player 1: {player_configs['player1_type'].upper()} using {player_configs['player1_army_file']}")
    print(f"   Player 2: {player_configs['player2_type'].upper()} using {player_configs['player2_army_file']}")
    if args.manual_phases:
        print(f"   Manual Phases: ENABLED (SPACE required to advance phases)")
    if TRAINING_MODE:
        print(f"   Training Episodes: {NUM_TRAINING_EPISODES}")
        print(f"   Checkpoint Interval: {CHECKPOINT_INTERVAL}")
    
    try:
        if TRAINING_MODE:
            print(f"\nStarting AI training mode for {NUM_TRAINING_EPISODES} episodes...")
            run_training_loop(args.clear_checkpoints, player_configs)
        else:
            print(f"\nStarting game mode...")
            main_game_loop(player_configs)
    except KeyboardInterrupt:
        print("\nTraining/Game interrupted by user.")
        if TRAINING_MODE:
            # Save emergency checkpoint
            print("Saving emergency checkpoints...")
            create_checkpoint_dir()
            # Note: This would need access to agents, but they're local to run_training_loop()
            # For now, just inform the user
            print("Please restart to continue training from last checkpoint.")
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
