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
from warhammer40k_ai.UI.game_ui import GameView, GameState, ROSTER_PANE_WIDTH, BATTLEFIELD_WIDTH, BATTLEFIELD_HEIGHT, INFO_PANE_HEIGHT, handle_zoom, handle_pan, TILE_SIZE
from warhammer40k_ai.waha_helper import WahaHelper
from warhammer40k_ai.agents.hrl_agent import HighLevelAgent, TacticalAgent, LowLevelAgent

# Training configuration
TRAINING_MODE = True  # Set to True for AI training, False for manual play
NUM_TRAINING_EPISODES = 1000
CHECKPOINT_INTERVAL = 10  # Save checkpoints every N episodes
CHECKPOINT_DIR = "checkpoints"

# Setup logging with improved configuration
def setup_logging():
    """Configure logging to reduce noise while preserving important information."""
    # Set up different log levels for different modules
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)  # Changed from DEBUG to INFO to reduce noise
    
    # Create a formatter for clean output
    formatter = logging.Formatter('%(message)s')  # Simplified format
    
    # Console handler for warnings and errors only
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    
    # Custom filter for important combat messages
    class ImportantCombatFilter(logging.Filter):
        def filter(self, record):
            # Allow death messages and important combat info
            if 'has Died' in record.getMessage() or 'has Fled' in record.getMessage():
                return True
            if 'destroyed before attack' in record.getMessage():
                return True
            # Allow episode completion messages
            if 'Episode' in record.getMessage() and ('completed' in record.getMessage() or 'Starting' in record.getMessage()):
                return True
            # Allow training summaries
            if 'TRAINING ANALYSIS' in record.getMessage() or 'FIRST PLAYER' in record.getMessage():
                return True
            # Block other info messages
            if record.levelno == logging.INFO:
                return False
            # Allow warnings and errors
            return record.levelno >= logging.WARNING
    
    # Combat info handler for important combat messages
    combat_handler = logging.StreamHandler()
    combat_handler.setLevel(logging.INFO)
    combat_handler.setFormatter(formatter)
    combat_handler.addFilter(ImportantCombatFilter())
    
    # Add both handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(combat_handler)
    
    # Specifically quiet down noisy modules
    logging.getLogger('warhammer40k_ai.agents.hrl_agent').setLevel(logging.ERROR)
    logging.getLogger('pygame').setLevel(logging.ERROR)
    logging.getLogger('warhammer40k_ai.classes.army').setLevel(logging.ERROR)
    logging.getLogger('warhammer40k_ai.waha_helper').setLevel(logging.ERROR)
    
    # Suppress PyTorch warnings
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning, module="torch")
    
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

def cleanup_destroyed_units(game: Game):
    """Remove destroyed units from the game map and player armies."""
    # Clean up units from the map
    destroyed_units = [unit for unit in game.map.units if not unit.is_alive()]
    for unit in destroyed_units:
        # Reduced logging - only log if many units destroyed
        if len(destroyed_units) > 3:
            logger.debug(f"Removing destroyed unit {unit.name} from the battlefield")
        game.map.units.remove(unit)
    
    # Clean up units from player armies
    for player in game.players:
        destroyed_units = [unit for unit in player.get_army().units if not unit.is_alive()]
        for unit in destroyed_units:
            # Reduced logging - only log if many units destroyed
            if len(destroyed_units) > 3:
                logger.debug(f"Removing destroyed unit {unit.name} from {player.name}'s army")
            player.get_army().units.remove(unit)

def auto_deploy_units(game: Game, player1: Player, player2: Player):
    """Automatically deploy units for both players in their deployment zones."""
    
    def deploy_player_units(player: Player, zone: dict):
        """Deploy units for a specific player in their zone."""
        # Reduced logging frequency
        x_start, x_end = zone['x_range']
        y_start, y_end = zone['y_range']
        
        units = player.get_army().units
        grid_size = max(2, int((len(units) ** 0.5) + 1))
        x_step = (x_end - x_start) / (grid_size + 1)
        y_step = (y_end - y_start) / (grid_size + 1)
        
        deployed_count = 0
        failed_count = 0
        
        for i, unit in enumerate(units):
            try:
                row = i // grid_size
                col = i % grid_size
                x = x_start + (col + 1) * x_step
                y = y_start + (row + 1) * y_step
                z = game.map.get_height_at_point(x, y)
                
                # Deploy each model in the unit
                for j, model in enumerate(unit.models):
                    model_x = x + (j % 3) * 0.5  # Spread models slightly
                    model_y = y + (j // 3) * 0.5
                    model_z = game.map.get_height_at_point(model_x, model_y)
                    model_facing = 0.0  # Default facing direction
                    model.set_location(model_x, model_y, model_z, model_facing)
                
                # Let unit position be calculated from model positions (don't override!)
                unit.deployed = True
                game.map.units.append(unit)
                deployed_count += 1
                
            except Exception as e:
                failed_count += 1
                # Only log first few failures to avoid spam
                if failed_count <= 2:
                    logger.warning(f"Failed to deploy {unit.name}: {e}")
                # Fallback: simple positioning for models
                for j, model in enumerate(unit.models):
                    model_x = x_start + 2 + (j % 3) * 0.5
                    model_y = y_start + 2 + (j // 3) * 0.5
                    model.set_location(model_x, model_y, 0, 0.0)
                unit.deployed = True
                game.map.units.append(unit)
        
        # Summary logging instead of per-unit logging
        logger.debug(f"Deployed {deployed_count} units for {player.name}" + 
                    (f" ({failed_count} with fallback positioning)" if failed_count > 0 else ""))
    
    # Define deployment zones
    battlefield_width, battlefield_height = game.get_battlefield_size()
    
    player1_zone = {
        'x_range': (2, battlefield_width * 0.4),
        'y_range': (2, battlefield_height - 2)
    }
    
    player2_zone = {
        'x_range': (battlefield_width * 0.6, battlefield_width - 2),
        'y_range': (2, battlefield_height - 2)
    }
    
    deploy_player_units(player1, player1_zone)
    deploy_player_units(player2, player2_zone)

def initialize_game() -> Tuple[pygame.Surface, WarhammerEnv, Game, Map, float, int, int, Player, Player]:
    pygame.init()
    screen = pygame.display.set_mode((BATTLEFIELD_WIDTH + 2 * ROSTER_PANE_WIDTH, BATTLEFIELD_HEIGHT + INFO_PANE_HEIGHT))
    pygame.display.set_caption('Warhammer 40,000 Battlefield')

    # Create players with armies (suppress noisy parsing output)
    with suppress_stdout():
        player1 = Player("Player 1", PlayerType.HUMAN, parse_army_list("army_lists/warhammer_app_dump.txt", waha_helper))
        player2 = Player("Player 2", PlayerType.HUMAN, parse_army_list("army_lists/chaos_daemons_GT2023.txt", waha_helper))
    
    # Only print during first initialization
    if hasattr(initialize_game, '_first_run'):
        pass  # Skip printing on subsequent runs
    else:
        print(f"Player 1 army created with {len(player1.get_army().units)} units")
        print(f"Player 2 army created with {len(player2.get_army().units)} units")
        initialize_game._first_run = True

    # Define obstacles
    obstacles = [
        Obstacle(vertices=[(3, 3), (3, 5), (5, 5), (5, 3)], terrain_type=ObstacleType.CRATER_AND_RUBBLE, height=3.0),
        Obstacle(vertices=[(20, 7), (27, 9), (29, 9), (29, 7)], terrain_type=ObstacleType.DEBRIS_AND_STATUARY, height=6.0)
    ]

    env = WarhammerEnv(players=[player1, player2])
    game = env.game
    
    # RANDOMIZE STARTING PLAYER TO REMOVE FIRST-PLAYER ADVANTAGE
    game.current_player_index = random.randint(0, 1)
    starting_player = game.get_current_player()
    logger.debug(f"Randomized starting player: {starting_player.name}")
    
    # Define objectives - CENTER THE OBJECTIVE TO REMOVE BIAS
    battlefield_width, battlefield_height = game.get_battlefield_size()
    center_x = battlefield_width / 2.0
    center_y = battlefield_height / 2.0

    # Add some randomization to prevent predictable positioning
    random_offset_x = random.uniform(-3, 3)
    random_offset_y = random.uniform(-3, 3)
    objective_x = center_x + random_offset_x
    objective_y = center_y + random_offset_y

    objective_point = ObjectivePoint(objective_x, objective_y, 0, 3.0)
    objectives = [
        Objective(name="Capture Central Point", location=objective_point, category=ObjectiveCategory.PRIMARY, points=10, 
                  description="Capture the central point to gain control of the battlefield.", 
                  conditions=lambda game: objective_point.controlling_player == game.get_current_player())
    ]
    commands = ["attack", "defend", "move"]
    
    game_map = Map(*game.get_battlefield_size())
    game.map = game_map
    game.map.add_obstacles(obstacles)
    game.map.add_objectives(objectives)
    game.commands = commands
    zoom_level = 1.0
    offset_x, offset_y = ROSTER_PANE_WIDTH, 0  # Adjust initial offset to account for left pane

    return screen, env, game, game_map, zoom_level, offset_x, offset_y, player1, player2

def run_training_episode(episode_num: int, agents: dict) -> dict:
    """Run a single training episode and return the results."""
    print(f"Episode {episode_num + 1}/{NUM_TRAINING_EPISODES}: Starting...")
    
    # Initialize a fresh game for this episode
    screen, env, game, game_map, _, _, _, player1, player2 = initialize_game()
    
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
    import types
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
    from warhammer40k_ai.classes.unit import Unit
    original_remove_model = Unit.remove_model
    Unit.remove_model = tracking_remove_model
    
    try:
        # Deploy units automatically
        auto_deploy_units(game, player1, player2)
        
        # Track objective position
        if game.map.objectives:
            obj = game.map.objectives[0]
            episode_stats['objective_position'] = (obj.location.x, obj.location.y)
        
        # Initialize agents for this episode
        high_level_agent_player1 = agents['hla1']
        tactical_agent_player1 = agents['ta1'] 
        low_level_agent_player1 = agents['lla1']
        high_level_agent_player2 = agents['hla2']
        tactical_agent_player2 = agents['ta2']
        low_level_agent_player2 = agents['lla2']
        
        # Run the game loop
        while not game.is_game_over():
            current_player = game.get_current_player()
            current_player_key = 'player1' if current_player == player1 else 'player2'
            
            if current_player == player1:
                high_level_agent = high_level_agent_player1
                tactical_agent = tactical_agent_player1
            else:
                high_level_agent = high_level_agent_player2
                tactical_agent = tactical_agent_player2

            # High-level decision making
            objective, command = high_level_agent.choose_objective_and_command()
            episode_stats['commands_selected'][current_player_key][command] += 1

            # Execute phases for each unit
            for unit in current_player.get_army().units:
                if unit.is_alive():
                    # Movement phase
                    tactical_agent.movement_phase(unit, objective)
                    
                    # Shooting phase  
                    tactical_agent.shooting_phase(unit)
                    
                    # Charge phase
                    charge_reward = tactical_agent.charge_phase(unit)
                    if charge_reward:
                        tactical_agent.movement_rewards.append(charge_reward)
                    
                    # Fight phase
                    tactical_agent.fight_phase(unit)

            # Clean up destroyed units
            cleanup_destroyed_units(game)
            
            # End turn and update policies
            game.next_turn()
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

def run_training_loop():
    """Run the main training loop for the specified number of episodes."""
    print(f"Starting AI training mode for {NUM_TRAINING_EPISODES} episodes...")
    
    # Create checkpoint directory
    create_checkpoint_dir()
    
    # Initialize all agents with first game instance to get proper dimensions
    screen, env, game, game_map, _, _, _, player1, player2 = initialize_game()
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
        episode_stats = run_training_episode(episode, agents)
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
    print(f"   Player 1 Wins: {p1_wins} ({p1_wins/total_episodes*100:.1f}%)")
    print(f"   Player 2 Wins: {p2_wins} ({p2_wins/total_episodes*100:.1f}%)")
    print(f"   Ties: {ties} ({ties/total_episodes*100:.1f}%)")
    
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
    print(f"   Longest game: {max(stats['total_turns'] for stats in all_episode_stats)} turns")
    print(f"   Shortest game: {min(stats['total_turns'] for stats in all_episode_stats)} turns")
    
    print("\n" + "=" * 70)
    print("🎉 Training completed successfully!")
    print("=" * 70)

def main_game_loop() -> None:
    screen, env, game, game_map, _, _, _, player1, player2 = initialize_game()
    game_view = GameView(screen, env, game, game_map, player1, player2)
    game_state = GameState.SETUP
    clicked_unit = None

    # Initialize agents with objectives
    high_level_agent_player1 = HighLevelAgent(game, player1, player2, objectives=game.map.objectives, commands=game.commands)
    tactical_agent_player1 = TacticalAgent(game, player1)
    low_level_agent_player1 = LowLevelAgent(game, player1)
    high_level_agent_player2 = HighLevelAgent(game, player2, player1, objectives=game.map.objectives, commands=game.commands)
    tactical_agent_player2 = TacticalAgent(game, player2)
    low_level_agent_player2 = LowLevelAgent(game, player2)

    # Load checkpoints for manual play mode
    if os.path.exists(CHECKPOINT_DIR):
        print("Loading trained AI models...")
        high_level_agent_player1.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'hla_player1_checkpoint.pth'))
        tactical_agent_player1.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'tactical_agent_player1_checkpoint.pth'))
        low_level_agent_player1.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'low_level_agent_player1_checkpoint.pth'))
        high_level_agent_player2.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'hla_player2_checkpoint.pth'))
        tactical_agent_player2.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'tactical_agent_player2_checkpoint.pth'))
        low_level_agent_player2.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'low_level_agent_player2_checkpoint.pth'))

    print("Starting main game loop")

    running = True
    while running:
        if game_state == GameState.PLAYING and game.do_ai_action:
            # Auto-deploy units if not already deployed
            if not all(unit.deployed for unit in player1.get_army().units + player2.get_army().units):
                auto_deploy_units(game, player1, player2)
            
            while not game.is_game_over():
                current_player = game.get_current_player()
                if current_player == player1:
                    high_level_agent = high_level_agent_player1
                    tactical_agent = tactical_agent_player1
                    low_level_agent = low_level_agent_player1
                else:
                    high_level_agent = high_level_agent_player2
                    tactical_agent = tactical_agent_player2
                    low_level_agent = low_level_agent_player2

                print(f"TURN [{game.turn}] PHASE: {game.phase.name} :: {current_player.name} choosing objective and command")

                objective, command = high_level_agent.choose_objective_and_command()
                print(f"{current_player.name} chose Objective: {objective.name}, Command: {command}")

                # Record average distance at start of turn for high-level reward calculation
                avg_distance_before =current_player.compute_average_distance(objective)

                if game.is_command_phase():
                    # Update objective control at the end of each turn
                    for obj in game.map.objectives:
                        if isinstance(obj.location, ObjectivePoint):
                            obj.location.update_control(game)
                        if obj.check_completion(game):
                            print(f"Objective {obj.name} completed!")
                            current_player.add_score(obj.points)
                    tactical_agent.command_phase(command)
                    game.next_phase()
                elif game.is_movement_phase():
                    for unit in current_player.army.units:
                        tactical_agent.movement_phase(unit, objective)
                    game.next_phase()
                elif game.is_shooting_phase():
                    for unit in current_player.army.units:
                        tactical_agent.shooting_phase(unit)
                    game.next_phase()
                elif game.is_charge_phase():
                    for unit in current_player.army.units:
                        tactical_agent.charge_phase(unit)
                    game.next_phase()
                elif game.is_fight_phase():
                    for unit in current_player.army.units:
                        tactical_agent.fight_phase(unit)
                    game.next_phase()  # This will trigger next_turn() since it's the last phase

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
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if game_state == GameState.PLAYING and event.button == 1:  # Left mouse button
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
                    game_view.on_mouse_press(*event.pos, event.button)
            elif event.type == pygame.MOUSEWHEEL:
                game_view.zoom_level = handle_zoom(game_view.zoom_level, event)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE and game_state == GameState.SETUP:
                    game_state = GameState.PLAYING
                    print("Game started!")
                elif event.key == pygame.K_SPACE and game_state == GameState.PLAYING:
                    game.next_phase()
                    print(f"Advanced to {game.phase.name} phase")
                elif event.key == pygame.K_a and game_state == GameState.PLAYING:
                    game.do_ai_action = True

        keys_pressed = pygame.key.get_pressed()
        game_view.offset_x, game_view.offset_y = handle_pan(keys_pressed, game_view.offset_x, game_view.offset_y, game_view.zoom_level)

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
    parser = argparse.ArgumentParser(description='Warhammer 40k AI Training and Game')
    parser.add_argument('--mode', choices=['train', 'play'], default='train',
                        help='Run mode: train for AI training, play for manual play')
    parser.add_argument('--episodes', type=int, default=1000,
                        help='Number of training episodes (default: 1000)')
    parser.add_argument('--checkpoint-interval', type=int, default=10,
                        help='Save checkpoints every N episodes (default: 10)')
    
    args = parser.parse_args()
    
    # Update global configuration based on arguments
    TRAINING_MODE = (args.mode == 'train')
    NUM_TRAINING_EPISODES = args.episodes
    CHECKPOINT_INTERVAL = args.checkpoint_interval
    
    try:
        if TRAINING_MODE:
            print(f"Starting AI training mode for {NUM_TRAINING_EPISODES} episodes...")
            run_training_loop()
        else:
            print("Starting manual play mode...")
            main_game_loop()
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
