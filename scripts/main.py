#!/usr/bin/env python3
"""
Unified Warhammer 40k AI Training and Gameplay System

This module provides a single unified game loop that works for both:
- Training mode: AI vs AI with no UI rendering
- Play mode: Human vs AI or Human vs Human with full UI

Key principles:
1. Single game loop - no fallback functions
2. Training mode skips UI rendering entirely
3. AI decisions bypass UI dialogs and call underlying functions directly
4. Manual phases work consistently across both modes
"""

import pygame
import os
import argparse
import logging
import sys
from typing import Tuple, Optional

# Suppress pygame initialization messages before importing pygame
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

from warhammer40k_ai.gym_env.warhammer40k_env import WarhammerEnv
from warhammer40k_ai.classes.game import Game
from warhammer40k_ai.classes.map import Map
from warhammer40k_ai.classes.player import Player, PlayerType
from warhammer40k_ai.agents.hrl_agent import HighLevelAgent, TacticalAgent, LowLevelAgent, AIDeploymentDecisionMaker
from warhammer40k_ai.classes.deployment import HumanDeploymentDecisionMaker

# Constants
CHECKPOINT_DIR = "checkpoints"

def setup_logging(training_mode: bool = False):
    """Configure logging based on mode."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR if training_mode else logging.INFO)
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    if not training_mode:
        # Setup console logging for play mode
        formatter = logging.Formatter('%(message)s')
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # Suppress noisy modules
    for module in ['warhammer40k_ai.agents.hrl_agent', 'pygame', 'warhammer40k_ai.classes.army', 
                   'warhammer40k_ai.waha_helper', 'warhammer40k_ai.classes.unit', 
                   'warhammer40k_ai.classes.model', 'warhammer40k_ai.classes.game', 
                   'warhammer40k_ai.classes.map', 'warhammer40k_ai']:
        logging.getLogger(module).setLevel(logging.ERROR)
    
    return logging.getLogger(__name__)

def create_checkpoint_dir():
    """Create checkpoint directory if it doesn't exist."""
    if not os.path.exists(CHECKPOINT_DIR):
        os.makedirs(CHECKPOINT_DIR)

def clear_checkpoints():
    """Clear all checkpoint files."""
    if os.path.exists(CHECKPOINT_DIR):
        for filename in os.listdir(CHECKPOINT_DIR):
            if filename.endswith('.pth'):
                os.remove(os.path.join(CHECKPOINT_DIR, filename))
        print("Cleared existing checkpoints")

def cleanup_destroyed_units(game: Game):
    """Remove destroyed units from the map."""
    units_to_remove = [unit for unit in game.map.units if not unit.is_alive()]
    for unit in units_to_remove:
        game.map.units.remove(unit)

def initialize_game(player1_type: str, player2_type: str, 
                   player1_army_file: str, player2_army_file: str,
                   training_mode: bool = False) -> Tuple[Optional[pygame.Surface], WarhammerEnv, Game, Map, Player, Player]:
    """Initialize basic game structure."""
    
    # Only initialize pygame for non-training modes
    screen = None
    if not training_mode:
        pygame.init()
        from warhammer40k_ai.UI.game_ui import ROSTER_PANE_WIDTH, STRATAGEM_PANE_WIDTH, BATTLEFIELD_WIDTH, BATTLEFIELD_HEIGHT, INFO_PANE_HEIGHT, TILE_SIZE
        
        # Calculate desired window size
        desired_width = BATTLEFIELD_WIDTH + 2 * (ROSTER_PANE_WIDTH + STRATAGEM_PANE_WIDTH)
        # Add 2" top status pane height to default window
        TOP_PANE_HEIGHT = int(2 * TILE_SIZE)
        desired_height = BATTLEFIELD_HEIGHT + INFO_PANE_HEIGHT + TOP_PANE_HEIGHT
        
        # Create the window at full desired size first, then determine which display it actually landed on.
        # This avoids incorrectly scaling based on the primary monitor when the OS places the window on
        # a larger external monitor (common with extended displays).
        screen = pygame.display.set_mode((desired_width, desired_height), pygame.RESIZABLE)
        pygame.display.set_caption('Warhammer 40,000 Battlefield')

        def _get_target_display_size_for_window() -> Tuple[int, int]:
            """Best-effort: return (w,h) of the display containing the window."""
            # Default fallback: use pygame.display.Info (often primary display)
            info = pygame.display.Info()
            fallback_w, fallback_h = int(info.current_w), int(info.current_h)

            # SDL2/pygame2 path: determine window position and map it to a display bounds.
            try:
                if hasattr(pygame.display, 'get_window_position'):
                    wx, wy = pygame.display.get_window_position()
                else:
                    return fallback_w, fallback_h

                # Try bounds-aware selection when available
                if hasattr(pygame.display, 'get_num_displays') and hasattr(pygame.display, 'get_display_bounds'):
                    num = int(pygame.display.get_num_displays())
                    # Use window center point for robust display selection
                    cx = int(wx + desired_width // 2)
                    cy = int(wy + desired_height // 2)
                    for i in range(num):
                        bx, by, bw, bh = pygame.display.get_display_bounds(i)
                        if bx <= cx < bx + bw and by <= cy < by + bh:
                            return int(bw), int(bh)
            except Exception:
                pass

            # Fallback: use largest display if we can enumerate, otherwise Info()
            try:
                if hasattr(pygame.display, 'get_desktop_sizes'):
                    desktop_sizes = pygame.display.get_desktop_sizes()
                    if desktop_sizes:
                        best_w, best_h = max(desktop_sizes, key=lambda s: int(s[0]) * int(s[1]))
                        return int(best_w), int(best_h)
            except Exception:
                pass

            return fallback_w, fallback_h

        monitor_width, monitor_height = _get_target_display_size_for_window()

        # Leave margin for decorations. On macOS, the display height reported by SDL/pygame can already
        # be the usable work area, so aggressive margins can cause unnecessary downscaling.
        margin_w = 100
        margin_h = 150
        if sys.platform == 'darwin':
            margin_w = 40
            margin_h = 60

        usable_width = max(1, monitor_width - margin_w)
        usable_height = max(1, monitor_height - margin_h)

        # Compute scale factor to fit within usable area
        scale_factor = min(1.0, usable_width / desired_width, usable_height / desired_height)

        # If the desired window already fits in the reported display size, never downscale.
        # This prevents false positives when the "usable" size is already baked into monitor_height.
        if (desired_width <= monitor_width and desired_height <= monitor_height) and scale_factor < 1.0:
            scale_factor = 1.0

        if os.environ.get("WH_UI_DISPLAY_DEBUG", "").strip():
            try:
                info = pygame.display.Info()
                print(f"🧭 Display debug: desired={desired_width}x{desired_height} "
                      f"info={int(info.current_w)}x{int(info.current_h)} "
                      f"chosen_display={monitor_width}x{monitor_height} "
                      f"usable={usable_width}x{usable_height} "
                      f"scale={scale_factor:.2f}")
            except Exception:
                pass

        if scale_factor < 1.0:
            actual_width = int(desired_width * scale_factor)
            actual_height = int(desired_height * scale_factor)
            print(f"🖥️  Scaling window to fit display: {desired_width}x{desired_height} → {actual_width}x{actual_height} (scale: {scale_factor:.2f})")
            screen = pygame.display.set_mode((actual_width, actual_height), pygame.RESIZABLE)
        else:
            print(f"🖥️  Using full size window: {desired_width}x{desired_height}")

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

    return screen, env, game, game_map, player1, player2

def create_ai_agents(game: Game, player1: Player, player2: Player, ui_interface=None) -> dict:
    """Create AI agents for players that need them."""
    agents = {}
    
    # Create agents for each player (both AI and human need TacticalAgent for fight phase)
    for i, player in enumerate([player1, player2]):
        opponent = player2 if player == player1 else player1
        
        # Create TacticalAgent for all players (needed for fight phase)
        agents[f'ta{i+1}'] = TacticalAgent(game, player, ui_interface=ui_interface)
        
        # Create other agents only for AI players
        if player.type == PlayerType.AI:
            # Get objectives and commands, with fallbacks if not available yet
            objectives = getattr(game, 'objectives', [])
            if not objectives and hasattr(game, 'map') and hasattr(game.map, 'objectives'):
                objectives = game.map.objectives
            
            commands = getattr(game, 'commands', ['attack', 'defend', 'move'])
            
            # Ensure we have at least some objectives and commands
            if not objectives:
                print("⚠️ No objectives available yet - creating default objective")
                from warhammer40k_ai.classes.map import Objective, ObjectiveCategory, ObjectivePoint
                default_objective = Objective(
                    name="Default Objective",
                    location=ObjectivePoint(30, 22, 0, 3.0),  # Center of battlefield
                    category=ObjectiveCategory.PRIMARY,
                    points=10,
                    description="Default objective for AI training",
                    conditions=lambda game: True  # Always true for now
                )
                objectives = [default_objective]
            
            if not commands:
                commands = ['attack', 'defend', 'move']
            
            agents[f'hla{i+1}'] = HighLevelAgent(game, player, opponent, objectives, commands)
            agents[f'lla{i+1}'] = LowLevelAgent(game, player)
    
    # Load checkpoints if available
    if os.path.exists(CHECKPOINT_DIR):
        for agent_key, agent in agents.items():
            checkpoint_file = os.path.join(CHECKPOINT_DIR, f'{agent_key}_checkpoint.pth')
            agent.load_checkpoint(checkpoint_file)
    
    return agents

def execute_setup_phases(game: Game, player_configs: dict, agents: dict = None) -> None:
    """Execute all setup phases automatically."""
    setup_kwargs = {
        'player1_army_file': player_configs.get('player1_army_file'),
        'player2_army_file': player_configs.get('player2_army_file')
    }
    
    while game.is_in_setup_phase():
        current_phase = game.get_current_setup_phase()
        
        # For DEPLOY_ARMIES phase, create deployment decision makers
        if current_phase.name == 'DEPLOY_ARMIES' and agents:
            decision_makers = {}
            
            for player in game.players:
                if player.type == PlayerType.AI:
                    # Find corresponding agent
                    player_num = 1 if player == game.players[0] else 2
                    agent = agents.get(f'hla{player_num}')
                    if agent:
                        decision_makers[player.name] = AIDeploymentDecisionMaker(agent)
                else:
                    # For human players in training mode, use AI decision maker
                    if player_configs.get('training_mode', False):
                        player_num = 1 if player == game.players[0] else 2
                        agent = agents.get(f'hla{player_num}')
                        if agent:
                            decision_makers[player.name] = AIDeploymentDecisionMaker(agent)
                    else:
                        decision_makers[player.name] = HumanDeploymentDecisionMaker(ui_interface=None)
            
            setup_kwargs['decision_makers'] = decision_makers
        
        game.execute_current_setup_phase(**setup_kwargs)
        setup_complete = game.advance_setup_phase()
        
        if setup_complete:
            break

def execute_ai_turn(game: Game, player: Player, agents: dict, episode_stats: dict = None) -> None:
    """Execute a single AI player's turn."""
    player_num = 1 if player == game.players[0] else 2
    current_player_key = f'player{player_num}'
    
    high_level_agent = agents.get(f'hla{player_num}')
    tactical_agent = agents.get(f'ta{player_num}')
    
    if not high_level_agent or not tactical_agent:
        return
        
    # Get AI decision
    objective, command = high_level_agent.choose_objective_and_command()
    
    # Track command usage for training stats
    if episode_stats and 'commands_selected' in episode_stats:
        episode_stats['commands_selected'][current_player_key][command] += 1
    
    # Execute current phase
    if game.is_command_phase():
        game.start_command_phase()
        tactical_agent.command_phase(command)
        game.next_phase()
    elif game.is_movement_phase():
        for unit in player.army.units:
            if unit.is_alive():
                tactical_agent.movement_phase(unit, objective)
        game.next_phase()
    elif game.is_shooting_phase():
        for unit in player.army.units:
            if unit.is_alive():
                tactical_agent.shooting_phase(unit)
        game.next_phase()
    elif game.is_charge_phase():
        for unit in player.army.units:
            if unit.is_alive():
                tactical_agent.charge_phase(unit)
        game.next_phase()
    elif game.is_fight_phase():
        # Execute the complete Fight Phase with proper two-stage structure
        opponent = game.get_opponent()
        tactical_agent.execute_fight_phase(player, opponent)
        game.next_phase()
    
    # Update AI policies
    high_level_agent.update_policy()
    tactical_agent.update_policies()
    if f'lla{player_num}' in agents:
        agents[f'lla{player_num}'].update_policy()

def execute_human_turn(game: Game, player: Player, agents: dict, ui_interface=None) -> None:
    """Execute a single human player's turn."""
    player_num = 1 if player == game.players[0] else 2
    current_player_key = f'player{player_num}'
    
    # For human players, the fight phase is handled by the UI system, not the agent
    if game.is_fight_phase():
        # Human fight phase is handled through UI interactions (clicking units, dialogs, etc.)
        # The phase will advance automatically when the fight phase is complete
        # No need to call agent - the UI system handles everything
        print(f"🎯 {player.name} fight phase - use UI to select units and fight")
        return
    elif game.is_command_phase():
        # Execute command phase for human players (same as AI)
        game.start_command_phase()
        game.next_phase()
    else:
        # For other phases, just advance to next phase
        # Human players will handle their actions through the UI
        game.next_phase()

def run_unified_game_loop(player_configs: dict) -> dict:
    """Unified game loop that works for both training and play modes."""
    training_mode = player_configs.get('training_mode', False)
    manual_phases = player_configs.get('manual_phases', False) and not training_mode
    
    # Initialize game
    screen, env, game, game_map, player1, player2 = initialize_game(
        player_configs['player1_type'],
        player_configs['player2_type'], 
        player_configs['player1_army_file'],
        player_configs['player2_army_file'],
        training_mode
    )
    
    # Initialize UI components early for play mode so they can be updated during setup
    game_view = None
    ui_interface = None
    if not training_mode:
        from warhammer40k_ai.UI.game_ui import GameView, HumanUIInterface
        screen_width, screen_height = screen.get_size()
        ui_interface = HumanUIInterface(screen_width, screen_height)
        
        game_view = GameView(screen, env, game, game_map, player1, player2, ui_interface)
        # Initial roster panes will be empty until armies are loaded
    
    # Create AI agents after basic setup
    agents = create_ai_agents(game, player1, player2, ui_interface)
    
    # Game statistics
    episode_stats = {
        'winner': None,
        'player1_score': 0,
        'player2_score': 0,
        'total_turns': 0,
        'shooting_kills': 0,
        'melee_kills': 0,
        'commands_selected': {
            'player1': {'attack': 0, 'defend': 0, 'move': 0},
            'player2': {'attack': 0, 'defend': 0, 'move': 0}
        }
    }
    
    # Main game loop
    if training_mode:
        # Training mode - pure AI vs AI execution
        # Execute setup phases automatically
        execute_setup_phases(game, player_configs, agents)
        
        while not game.is_game_over():
            current_player = game.get_current_player()
            execute_ai_turn(game, current_player, agents, episode_stats)
            cleanup_destroyed_units(game)
            episode_stats['total_turns'] = game.turn
    else:
        # Play mode - handle both AI and human players with UI        
        running = True
        setup_complete = False
        
        while running and not game.is_game_over():
            # Handle pygame events for human players
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    # Recreate window with new size and notify UI to relayout
                    new_size = (event.w, event.h)
                    screen = pygame.display.set_mode(new_size, pygame.RESIZABLE)
                    if game_view:
                        game_view.resize_layout(new_size[0], new_size[1])
                elif game_view and game_view.handle_pygame_event(event):
                    continue  # Event handled by UI
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        if game.is_in_setup_phase():
                            # Handle setup phase advancement
                            current_phase = game.get_current_setup_phase()
                            
                            # Check if we're in deployment phase and waiting for deployment input
                            if (current_phase.name == 'DEPLOY_ARMIES' and 
                                hasattr(game, 'waiting_for_deployment_input') and 
                                game.waiting_for_deployment_input):
                                # Continue deployment
                                game.waiting_for_deployment_input = False
                                continue
                            
                            # Execute the current setup phase
                            setup_kwargs = {
                                'player1_army_file': player_configs.get('player1_army_file'),
                                'player2_army_file': player_configs.get('player2_army_file')
                            }
                            
                            # For DEPLOY_ARMIES phase, create deployment decision makers
                            if current_phase.name == 'DEPLOY_ARMIES':
                                decision_makers = {}
                                
                                for player in game.players:
                                    if player.type == PlayerType.AI:
                                        # Find corresponding agent
                                        player_num = 1 if player == game.players[0] else 2
                                        agent = agents.get(f'hla{player_num}')
                                        if agent:
                                            decision_makers[player.name] = AIDeploymentDecisionMaker(agent)
                                    else:
                                        # Human player gets UI interface
                                        decision_makers[player.name] = HumanDeploymentDecisionMaker(ui_interface=ui_interface)
                                
                                setup_kwargs['decision_makers'] = decision_makers
                                setup_kwargs['manual_phases'] = manual_phases
                            
                            # Execute the setup phase
                            game.execute_current_setup_phase(**setup_kwargs)
                            
                            # Update UI after specific setup phases
                            if game_view:
                                if current_phase.name == 'MUSTER_ARMIES':
                                    # Refresh roster panes after armies are loaded
                                    game_view.refresh_roster_panes()
                                    print("📋 Roster panes updated with army units")
                                elif current_phase.name == 'DETERMINE_ATTACKER_AND_DEFENDER':
                                    # Update roster pane titles after attacker/defender determination
                                    game_view.update_roster_pane_titles()
                                    print("📋 Roster pane titles updated with roles")
                            
                            # Check if we should advance to next setup phase
                            should_advance = True
                            
                            # Special handling for deployment phase
                            if current_phase.name == 'DEPLOY_ARMIES':
                                # Check whose turn it is to deploy
                                current_deployment_player = game.get_current_deployment_player()
                                
                                if current_deployment_player and current_deployment_player.type == PlayerType.AI:
                                    # It's AI's turn - deploy one unit
                                    undeployed_units = game.get_deployable_units(current_deployment_player)
                                    if undeployed_units:
                                        unit_to_deploy = undeployed_units[0]  # Simple: deploy first unit
                                        print(f"🤖 AI deploying {unit_to_deploy.name}...")
                                        
                                        success = game.auto_deploy_unit(unit_to_deploy)
                                        if success:
                                            print(f"✅ AI successfully deployed {unit_to_deploy.name}")
                                            # Record deployment action
                                            if unit_to_deploy.position:
                                                game.record_deployment_action(current_deployment_player, unit_to_deploy, 'deployed', unit_to_deploy.position)
                                            # Mark unit as deployed and advance to next player's turn
                                            unit_to_deploy.deployed = True
                                            game.advance_deployment_turn()
                                        else:
                                            print(f"❌ AI failed to deploy {unit_to_deploy.name}, placing in reserves")
                                            # Force deployment to prevent infinite loop
                                            unit_to_deploy.deployed = True
                                            unit_to_deploy.reserve_status = 'reserves'
                                            # Record reserves action
                                            game.record_deployment_action(current_deployment_player, unit_to_deploy, 'reserves')
                                            game.advance_deployment_turn()
                                        
                                        # Don't advance setup phase yet - continue deployment
                                        should_advance = False
                                    else:
                                        # AI has no more units to deploy, check if deployment is complete
                                        print(f"🤖 {current_deployment_player.name} has no more units to deploy")
                                        # Let the normal logic handle phase advancement
                                
                                # Check if any human players still have units to deploy
                                human_players_deploying = False
                                for player in game.players:
                                    if player.type.name == 'HUMAN':
                                        undeployed_units = [unit for unit in player.get_army().units 
                                                          if not unit.deployed and unit.reserve_status != 'reserves' and unit.reserve_status != 'strategic_reserves']
                                        if undeployed_units:
                                            human_players_deploying = True
                                            print(f"⏳ {player.name} still has {len(undeployed_units)} units to deploy")
                                            break
                                
                                if human_players_deploying:
                                    should_advance = False
                                    print("📋 Press SPACE again after all units are deployed")
                            
                            # Regular check for waiting_for_deployment_input
                            if hasattr(game, 'waiting_for_deployment_input') and game.waiting_for_deployment_input:
                                should_advance = False
                            
                            if should_advance:
                                setup_complete = game.advance_setup_phase()
                                
                                if setup_complete:
                                    print("🎉 Setup complete! Battle begins!")
                        elif manual_phases:
                            # Manual phase advancement during battle
                            current_player = game.get_current_player()
                            if current_player.type == PlayerType.AI:
                                execute_ai_turn(game, current_player, agents)
                            else:
                                # Human player manual advancement
                                # Special handling: at end of Command phase, open a brief stratagem window
                                if game.is_command_phase():
                                    # Start your Command phase processing (draw cards, tests, etc.)
                                    game.start_command_phase()
                                    # No window needed; advance immediately
                                    game.next_phase()
                                elif game.is_fight_phase():
                                    # UI-managed fight phase; do nothing and let UI handle it
                                    pass
                                else:
                                    # Other phases advance immediately
                                    game.next_phase()
                    elif event.key == pygame.K_ESCAPE:
                        if game_view:
                            game_view.close_unit_details()
            
            # Handle automatic progression for non-manual modes
            if not manual_phases and not game.is_in_setup_phase():
                current_player = game.get_current_player()
                if current_player.type == PlayerType.AI:
                    execute_ai_turn(game, current_player, agents)
                else:
                    # For human players, execute turn with fight phase support
                    execute_human_turn(game, current_player, agents, ui_interface)
            
            # Auto-execute setup phases if not manual phases mode
            if not manual_phases and game.is_in_setup_phase() and not setup_complete:
                # Track which phase we're executing for UI updates
                current_phase = game.get_current_setup_phase()
                
                execute_setup_phases(game, player_configs, agents)
                setup_complete = True
                
                # Update UI after setup phases complete
                if game_view:
                    game_view.refresh_roster_panes()
                    game_view.update_roster_pane_titles()
                    print("📋 UI updated after automatic setup completion")
            
            # Update display for play mode
            if game_view:
                game_view.draw()
                pygame.display.flip()
                pygame.time.Clock().tick(60)
    
    # Finalize episode stats
    if game.is_game_over():
        winner = game.get_winner()
        episode_stats['winner'] = winner.name if winner else 'ties'
        episode_stats['player1_score'] = player1.get_score()
        episode_stats['player2_score'] = player2.get_score()
    
    return episode_stats

def run_training_episodes(num_episodes: int, player_configs: dict, checkpoint_interval: int = 10) -> None:
    """Run multiple training episodes."""
    training_stats = {
        'total_episodes': 0,
        'wins': {'player1': 0, 'player2': 0, 'ties': 0},
        'total_turns': 0
    }
    
    create_checkpoint_dir()
    
    print(f"Starting AI training mode for {num_episodes} episodes...")
    
    for episode in range(num_episodes):
        try:
            episode_stats = run_unified_game_loop(player_configs)
            
            # Update training statistics
            training_stats['total_episodes'] += 1
            training_stats['total_turns'] += episode_stats['total_turns']
            winner = episode_stats['winner']
            if winner in training_stats['wins']:
                training_stats['wins'][winner] += 1
            else:
                training_stats['wins']['ties'] += 1
            
            if (episode + 1) % 10 == 0:
                print(f"Episode {episode + 1}/{num_episodes} completed")
                
        except Exception as e:
            print(f"Episode {episode + 1} failed: {e}")
            continue
    
    # Final results
    total = training_stats['total_episodes']
    if total > 0:
        print(f"\nTraining completed!")
        print(f"Player 1 wins: {training_stats['wins']['player1']} ({training_stats['wins']['player1']/total*100:.1f}%)")
        print(f"Player 2 wins: {training_stats['wins']['player2']} ({training_stats['wins']['player2']/total*100:.1f}%)")
        print(f"Ties: {training_stats['wins']['ties']} ({training_stats['wins']['ties']/total*100:.1f}%)")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Warhammer 40,000 AI Training and Gameplay System',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--mode', choices=['train', 'play'], default='train',
                        help='Run mode: train for AI training, play for manual play')
    parser.add_argument('--episodes', type=int, default=1000,
                        help='Number of training episodes (default: 1000)')
    parser.add_argument('--checkpoint-interval', type=int, default=10,
                        help='Save checkpoints every N episodes (default: 10)')
    parser.add_argument('--clear-checkpoints', action='store_true',
                        help='Clear existing checkpoints and start fresh')
    parser.add_argument('--player1', choices=['ai', 'human'], default='ai',
                        help='Player 1 type: ai or human (default: ai)')
    parser.add_argument('--player2', choices=['ai', 'human'], default='ai', 
                        help='Player 2 type: ai or human (default: ai)')
    parser.add_argument('--player1-army', type=str, default='army_lists/chaos_test.txt',
                        help='Army list file for Player 1')
    parser.add_argument('--player2-army', type=str, default='army_lists/aeldari_test.txt',
                        help='Army list file for Player 2')
    parser.add_argument('--manual-phases', action='store_true',
                        help='Require SPACE key to advance phases')
    
    args = parser.parse_args()
    
    # Setup logging
    training_mode = (args.mode == 'train')
    logger = setup_logging(training_mode)
    
    # Clear checkpoints if requested
    if args.clear_checkpoints:
        clear_checkpoints()
    
    # Create player configuration
    player_configs = {
        'player1_type': 'ai' if training_mode else args.player1,
        'player2_type': 'ai' if training_mode else args.player2,
        'player1_army_file': args.player1_army,
        'player2_army_file': args.player2_army,
        'manual_phases': args.manual_phases,
        'training_mode': training_mode
    }
    
    print(f"🎮 Game Configuration:")
    print(f"   Mode: {args.mode.upper()}")
    print(f"   Player 1: {player_configs['player1_type'].upper()} using {player_configs['player1_army_file']}")
    print(f"   Player 2: {player_configs['player2_type'].upper()} using {player_configs['player2_army_file']}")
    if args.manual_phases and not training_mode:
        print(f"   Manual Phases: ENABLED")
    
    try:
        if training_mode:
            run_training_episodes(args.episodes, player_configs, args.checkpoint_interval)
        else:
            print("Starting game mode...")
            run_unified_game_loop(player_configs)
    except KeyboardInterrupt:
        print("\nGame interrupted by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 
