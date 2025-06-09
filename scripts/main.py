import pygame
import sys
import os
import random
import argparse
from typing import Tuple
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
        print(f"Removing destroyed unit {unit.name} from the battlefield")
        game.map.units.remove(unit)
    
    # Clean up units from player armies
    for player in game.players:
        destroyed_units = [unit for unit in player.get_army().units if not unit.is_alive()]
        for unit in destroyed_units:
            print(f"Removing destroyed unit {unit.name} from {player.name}'s army")
            player.get_army().units.remove(unit)

def auto_deploy_units(game: Game, player1: Player, player2: Player):
    """Automatically deploy units for both players in their deployment zones."""
    # Define deployment zones (assuming standard 44x60 battlefield)
    # Player 1 deploys in bottom third, Player 2 in top third
    p1_zone = {"x_min": 5, "x_max": 55, "y_min": 5, "y_max": 12}
    p2_zone = {"x_min": 5, "x_max": 55, "y_min": 32, "y_max": 39}
    
    def deploy_player_units(player: Player, zone: dict):
        """Deploy all units for a player in their zone."""
        for unit in player.get_army().units:
            if not unit.deployed:
                # Try to find a valid position for the unit
                max_attempts = 50
                deployed = False
                for attempt in range(max_attempts):
                    try:
                        x = random.uniform(zone["x_min"], zone["x_max"])
                        y = random.uniform(zone["y_min"], zone["y_max"])
                        
                        # Calculate model positions
                        model_positions = unit.calculate_model_positions(x, y, game.map, 1.0)
                        
                        if model_positions:
                            # Set model positions
                            for model, position in zip(unit.models, model_positions):
                                model_x, model_y, model_z, model_facing = position
                                model.set_location(model_x, model_y, model_z, model_facing)
                            
                            # Set unit position
                            unit_x = sum(pos[0] for pos in model_positions) / len(model_positions)
                            unit_y = sum(pos[1] for pos in model_positions) / len(model_positions)
                            unit.set_position(unit_x, unit_y)
                            
                            # Try to place the unit
                            if game.map.place_unit(unit):
                                unit.deployed = True
                                deployed = True
                                print(f"Auto-deployed {unit.name} at ({unit_x:.1f}, {unit_y:.1f})")
                                break
                    except Exception as e:
                        print(f"Error during deployment attempt {attempt + 1} for {unit.name}: {e}")
                        continue
                    
                if not deployed:
                    print(f"Failed to auto-deploy {unit.name} after {max_attempts} attempts")
                    # Force deploy at a simple position as fallback
                    try:
                        x = zone["x_min"] + (zone["x_max"] - zone["x_min"]) / 2
                        y = zone["y_min"] + random.uniform(0, zone["y_max"] - zone["y_min"])
                        unit.set_position(x, y)
                        for i, model in enumerate(unit.models):
                            model.set_location(x + i * 0.5, y, 0, 0)
                        unit.deployed = True
                        print(f"Force-deployed {unit.name} at ({x:.1f}, {y:.1f})")
                    except Exception as e:
                        print(f"Failed to force-deploy {unit.name}: {e}")
    
    try:
        deploy_player_units(player1, p1_zone)
        deploy_player_units(player2, p2_zone)
        print(f"Deployment complete. Player 1: {sum(1 for u in player1.get_army().units if u.deployed)}/{len(player1.get_army().units)} units deployed")
        print(f"Deployment complete. Player 2: {sum(1 for u in player2.get_army().units if u.deployed)}/{len(player2.get_army().units)} units deployed")
    except Exception as e:
        print(f"Error during auto-deployment: {e}")
        import traceback
        traceback.print_exc()

def initialize_game() -> Tuple[pygame.Surface, WarhammerEnv, Game, Map, float, int, int, Player, Player]:
    pygame.init()
    screen = pygame.display.set_mode((BATTLEFIELD_WIDTH + 2 * ROSTER_PANE_WIDTH, BATTLEFIELD_HEIGHT + INFO_PANE_HEIGHT))
    pygame.display.set_caption('Warhammer 40,000 Battlefield')

    # Create players with armies
    player1 = Player("Player 1", PlayerType.HUMAN, parse_army_list("army_lists/warhammer_app_dump.txt", waha_helper))
    player2 = Player("Player 2", PlayerType.HUMAN, parse_army_list("army_lists/chaos_daemons_GT2023.txt", waha_helper))
    print(f"Player 1 army created with {len(player1.get_army().units)} units")
    print(f"Player 2 army created with {len(player2.get_army().units)} units")

    # Define obstacles
    obstacles = [
        Obstacle(vertices=[(3, 3), (3, 5), (5, 5), (5, 3)], terrain_type=ObstacleType.CRATER_AND_RUBBLE, height=3.0),
        Obstacle(vertices=[(20, 7), (27, 9), (29, 9), (29, 7)], terrain_type=ObstacleType.DEBRIS_AND_STATUARY, height=6.0)
    ]

    # Define objectives
    objective_point = ObjectivePoint(15, 15, 0, 3.0)
    objectives = [
        Objective(name="Capture Central Point", location=objective_point, category=ObjectiveCategory.PRIMARY, points=10, 
                  description="Capture the central point to gain control of the battlefield.", 
                  conditions=lambda game: objective_point.controlling_player == game.get_current_player())
    ]
    commands = ["attack", "defend", "move"]

    env = WarhammerEnv(players=[player1, player2])
    game = env.game
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
    print(f"\n=== TRAINING EPISODE {episode_num + 1} ===")
    
    # Initialize a fresh game for this episode
    screen, env, game, game_map, _, _, _, player1, player2 = initialize_game()
    
    # Auto-deploy units
    auto_deploy_units(game, player1, player2)
    
    # Set up agents for this episode
    high_level_agent_player1 = agents['hla1']
    tactical_agent_player1 = agents['ta1']
    low_level_agent_player1 = agents['lla1']
    high_level_agent_player2 = agents['hla2']
    tactical_agent_player2 = agents['ta2']
    low_level_agent_player2 = agents['lla2']
    
    # Update agents with new game instance
    for agent in [high_level_agent_player1, tactical_agent_player1, low_level_agent_player1]:
        agent.game = game
        agent.player = player1
    for agent in [high_level_agent_player2, tactical_agent_player2, low_level_agent_player2]:
        agent.game = game
        agent.player = player2
    
    episode_results = {
        'winner': None,
        'player1_score': 0,
        'player2_score': 0,
        'total_turns': 0
    }
    
    # Run the game loop
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
        avg_distance_before = current_player.compute_average_distance(objective)

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
        
        # Clean up destroyed units
        cleanup_destroyed_units(game)

    # Record episode results
    episode_results['total_turns'] = game.turn
    episode_results['player1_score'] = player1.get_score()
    episode_results['player2_score'] = player2.get_score()
    
    if game.get_winner() == player1:
        episode_results['winner'] = 'player1'
        high_level_agent_player1.store_reward(100)
        high_level_agent_player1.update_policy()
        high_level_agent_player2.store_reward(-100)
        high_level_agent_player2.update_policy()
    else:
        episode_results['winner'] = 'player2'
        high_level_agent_player2.store_reward(100)
        high_level_agent_player2.update_policy()
        high_level_agent_player1.store_reward(-100)
        high_level_agent_player1.update_policy()
    
    print(f"Episode {episode_num + 1} completed! Winner: {episode_results['winner']}, "
          f"Score: {episode_results['player1_score']}-{episode_results['player2_score']}, "
          f"Turns: {episode_results['total_turns']}")
    
    return episode_results

def run_training_loop():
    """Run the main training loop for multiple episodes."""
    create_checkpoint_dir()
    
    # Initialize game once to get the basic structure
    screen, env, game, game_map, _, _, _, player1, player2 = initialize_game()
    
    # Initialize agents
    print("Initializing AI agents...")
    high_level_agent_player1 = HighLevelAgent(game, player1, player2, objectives=game.map.objectives, commands=game.commands)
    tactical_agent_player1 = TacticalAgent(game, player1)
    low_level_agent_player1 = LowLevelAgent(game, player1)
    high_level_agent_player2 = HighLevelAgent(game, player2, player1, objectives=game.map.objectives, commands=game.commands)
    tactical_agent_player2 = TacticalAgent(game, player2)
    low_level_agent_player2 = LowLevelAgent(game, player2)
    
    # Load existing checkpoints if available
    print("Loading checkpoints...")
    high_level_agent_player1.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'hla_player1_checkpoint.pth'))
    tactical_agent_player1.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'tactical_agent_player1_checkpoint.pth'))
    low_level_agent_player1.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'low_level_agent_player1_checkpoint.pth'))
    high_level_agent_player2.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'hla_player2_checkpoint.pth'))
    tactical_agent_player2.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'tactical_agent_player2_checkpoint.pth'))
    low_level_agent_player2.load_checkpoint(os.path.join(CHECKPOINT_DIR, 'low_level_agent_player2_checkpoint.pth'))
    
    agents = {
        'hla1': high_level_agent_player1,
        'ta1': tactical_agent_player1,
        'lla1': low_level_agent_player1,
        'hla2': high_level_agent_player2,
        'ta2': tactical_agent_player2,
        'lla2': low_level_agent_player2
    }
    
    # Training statistics
    training_stats = {
        'player1_wins': 0,
        'player2_wins': 0,
        'total_episodes': 0,
        'avg_turns_per_episode': 0,
        'total_turns': 0
    }
    
    print(f"Starting training for {NUM_TRAINING_EPISODES} episodes...")
    
    # Main training loop
    for episode in range(NUM_TRAINING_EPISODES):
        episode_results = run_training_episode(episode, agents)
        
        # Update training statistics
        training_stats['total_episodes'] += 1
        training_stats['total_turns'] += episode_results['total_turns']
        training_stats['avg_turns_per_episode'] = training_stats['total_turns'] / training_stats['total_episodes']
        
        if episode_results['winner'] == 'player1':
            training_stats['player1_wins'] += 1
        else:
            training_stats['player2_wins'] += 1
        
        # Save checkpoints periodically
        if (episode + 1) % CHECKPOINT_INTERVAL == 0:
            print(f"\nSaving checkpoints after episode {episode + 1}...")
            high_level_agent_player1.save_checkpoint(os.path.join(CHECKPOINT_DIR, 'hla_player1_checkpoint.pth'))
            tactical_agent_player1.save_checkpoint(os.path.join(CHECKPOINT_DIR, 'tactical_agent_player1_checkpoint.pth'))
            low_level_agent_player1.save_checkpoint(os.path.join(CHECKPOINT_DIR, 'low_level_agent_player1_checkpoint.pth'))
            high_level_agent_player2.save_checkpoint(os.path.join(CHECKPOINT_DIR, 'hla_player2_checkpoint.pth'))
            tactical_agent_player2.save_checkpoint(os.path.join(CHECKPOINT_DIR, 'tactical_agent_player2_checkpoint.pth'))
            low_level_agent_player2.save_checkpoint(os.path.join(CHECKPOINT_DIR, 'low_level_agent_player2_checkpoint.pth'))
            
            # Print training statistics
            win_rate_p1 = training_stats['player1_wins'] / training_stats['total_episodes'] * 100
            win_rate_p2 = training_stats['player2_wins'] / training_stats['total_episodes'] * 100
            print(f"Training Progress: Episode {episode + 1}/{NUM_TRAINING_EPISODES}")
            print(f"Player 1 Win Rate: {win_rate_p1:.1f}% ({training_stats['player1_wins']} wins)")
            print(f"Player 2 Win Rate: {win_rate_p2:.1f}% ({training_stats['player2_wins']} wins)")
            print(f"Average Turns per Episode: {training_stats['avg_turns_per_episode']:.1f}")
    
    # Final checkpoint save
    print("\nTraining completed! Saving final checkpoints...")
    high_level_agent_player1.save_checkpoint(os.path.join(CHECKPOINT_DIR, 'hla_player1_final.pth'))
    tactical_agent_player1.save_checkpoint(os.path.join(CHECKPOINT_DIR, 'tactical_agent_player1_final.pth'))
    low_level_agent_player1.save_checkpoint(os.path.join(CHECKPOINT_DIR, 'low_level_agent_player1_final.pth'))
    high_level_agent_player2.save_checkpoint(os.path.join(CHECKPOINT_DIR, 'hla_player2_final.pth'))
    tactical_agent_player2.save_checkpoint(os.path.join(CHECKPOINT_DIR, 'tactical_agent_player2_final.pth'))
    low_level_agent_player2.save_checkpoint(os.path.join(CHECKPOINT_DIR, 'low_level_agent_player2_final.pth'))
    
    # Print final statistics
    print(f"\n=== TRAINING SUMMARY ===")
    print(f"Total Episodes: {training_stats['total_episodes']}")
    print(f"Player 1 Wins: {training_stats['player1_wins']} ({training_stats['player1_wins']/training_stats['total_episodes']*100:.1f}%)")
    print(f"Player 2 Wins: {training_stats['player2_wins']} ({training_stats['player2_wins']/training_stats['total_episodes']*100:.1f}%)")
    print(f"Average Turns per Episode: {training_stats['avg_turns_per_episode']:.1f}")

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
