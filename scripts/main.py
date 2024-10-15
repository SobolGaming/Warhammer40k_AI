import pygame
import sys
from typing import Tuple
from warhammer40k_ai.gym_env.warhammer40k_env import WarhammerEnv
from warhammer40k_ai.classes.game import Game
from warhammer40k_ai.classes.map import Map
from warhammer40k_ai.classes.player import Player, PlayerType
from warhammer40k_ai.classes.army import parse_army_list
from warhammer40k_ai.UI.game_ui import GameView, GameState, ROSTER_PANE_WIDTH, BATTLEFIELD_WIDTH, BATTLEFIELD_HEIGHT, INFO_PANE_HEIGHT, handle_zoom, handle_pan, TILE_SIZE
from warhammer40k_ai.waha_helper import WahaHelper
from warhammer40k_ai.agents.hrl_agent import HighLevelAgent, TacticalAgent, LowLevelAgent


# Helper
waha_helper = WahaHelper()

def initialize_game() -> Tuple[pygame.Surface, WarhammerEnv, Game, Map, float, int, int, Player, Player]:
    pygame.init()
    screen = pygame.display.set_mode((BATTLEFIELD_WIDTH + 2 * ROSTER_PANE_WIDTH, BATTLEFIELD_HEIGHT + INFO_PANE_HEIGHT))
    pygame.display.set_caption('Warhammer 40,000 Battlefield')

    # Create players with armies
    player1 = Player("Player 1", PlayerType.HUMAN, parse_army_list("army_lists/warhammer_app_dump.txt", waha_helper))
    player2 = Player("Player 2", PlayerType.HUMAN, parse_army_list("army_lists/chaos_daemons_GT2023.txt", waha_helper))
    print(f"Player 1 army created with {len(player1.get_army().units)} units")
    print(f"Player 2 army created with {len(player2.get_army().units)} units")

    env = WarhammerEnv(players=[player1, player2])
    game = env.game
    game_map = Map(*game.get_battlefield_size())
    game.map = game_map

    zoom_level = 1.0
    offset_x, offset_y = ROSTER_PANE_WIDTH, 0  # Adjust initial offset to account for left pane

    return screen, env, game, game_map, zoom_level, offset_x, offset_y, player1, player2


def main_game_loop() -> None:
    screen, env, game, game_map, _, _, _, player1, player2 = initialize_game()
    game_view = GameView(screen, env, game, game_map, player1, player2)
    game_state = GameState.SETUP
    clicked_unit = None

    # Initialize agents
    high_level_agent_player1 = HighLevelAgent(game, player1)
    tactical_agent_player1 = TacticalAgent(game, player1)
    low_level_agent_player1 = LowLevelAgent(game, player1)
    high_level_agent_player2 = HighLevelAgent(game, player2)
    tactical_agent_player2 = TacticalAgent(game, player2)
    low_level_agent_player2 = LowLevelAgent(game, player2)

    print("Starting main game loop")

    running = True
    while running:
        '''
        if game_state == GameState.PLAYING:
            if game.get_current_player() == player1:
                if game.is_command_phase():
                    high_level_agent_player1.command_phase()
                elif game.is_movement_phase():
                    objective = high_level_agent_player1.choose_objective()
                    for unit in player1.army.units:
                        path = tactical_agent_player1.movement_phase(unit, objective)
                        low_level_agent_player1.execute_movement(unit, path)
                elif game.is_shooting_phase():
                    for unit in player1.army.units:
                        tactical_agent_player1.shooting_phase(unit)
                elif game.is_charge_phase():
                    for unit in player1.army.units:
                        tactical_agent_player1.charge_phase(unit)
                elif game.is_fight_phase():
                    for unit in player1.army.units:
                        tactical_agent_player1.fight_phase(unit)
            else:
                if game.is_command_phase():
                    high_level_agent_player2.command_phase()
                elif game.is_movement_phase():
                    objective = high_level_agent_player2.choose_objective()
                    for unit in player2.army.units:
                        path = tactical_agent_player2.movement_phase(unit, objective)
                        low_level_agent_player2.execute_movement(unit, path)
                elif game.is_shooting_phase():
                    for unit in player2.army.units:
                        tactical_agent_player2.shooting_phase(unit)
                elif game.is_charge_phase():
                    for unit in player2.army.units: 
                        tactical_agent_player2.charge_phase(unit)
                elif game.is_fight_phase():
                    for unit in player2.army.units:
                        tactical_agent_player2.fight_phase(unit)
        '''

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
                                if success: 
                                    print(f"Moved {game_view.selected_unit.name} to ({game_x}, {game_y})")
                                else:
                                    print(f"Failed to move {game_view.selected_unit.name} to ({game_x}, {game_y})")
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
                    game.next_turn()
                elif event.key == pygame.K_a and game_state == GameState.PLAYING:
                    game.do_phase_action()

        keys_pressed = pygame.key.get_pressed()
        game_view.offset_x, game_view.offset_y = handle_pan(keys_pressed, game_view.offset_x, game_view.offset_y, game_view.zoom_level)

        game_view.draw()
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main_game_loop()
