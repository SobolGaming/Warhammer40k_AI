#!/usr/bin/env python3
"""
Example demonstrating the Mission Selection Dialog for Chapter Approved 2025/2026.
This shows how to integrate the dialog into the game setup process.
"""

import sys
import os
import pygame
import logging
logger = logging.getLogger(__name__)

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from warhammer40k_ai.UI.dialogs.mission_selection_dialog import MissionSelectionDialog
from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.roster.player import Player, PlayerControl


def main():
    """Run the mission selection dialog example."""
    
    # Initialize pygame
    pygame.init()
    screen_width, screen_height = 1200, 800
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption('Mission Selection Dialog - Chapter Approved 2025/2026')
    
    # Create game instance for context
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    player1 = Player("Player 1", PlayerControl.LOCAL, None)
    player2 = Player("Player 2", PlayerControl.REMOTE, None)
    game = Game(battlefield, [player1, player2])
    
    # Create and show the mission selection dialog
    mission_dialog = MissionSelectionDialog(screen_width, screen_height)
    
    clock = pygame.time.Clock()
    running = True
    dialog_result = None
    
    logger.info("ðŸŽ¯ Mission Selection Dialog Example")
    logger.info("=" * 50)
    logger.info("Instructions:")
    logger.info("- Click on mission combinations to select them")
    logger.info("- Click on terrain layout numbers to choose layout")
    logger.info("- Click 'Pick Random' or press 'R' for random selection")
    logger.info("- Use mouse wheel or arrow keys to scroll")
    logger.info("- Press ESC to cancel or ENTER to confirm")
    logger.info("- Click Cancel/Confirm buttons to close dialog")
    
    while running and dialog_result is None:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                result = mission_dialog.handle_event(event)
                if result:
                    dialog_result = result
                    break
        
        # Clear screen
        screen.fill((40, 40, 50))
        
        # Draw some background context
        font = pygame.font.Font(None, 36)
        title = font.render("Warhammer 40k Chapter Approved 2025/2026", True, (200, 200, 200))
        title_rect = title.get_rect(center=(screen_width // 2, 50))
        screen.blit(title, title_rect)
        
        # Draw the dialog
        mission_dialog.draw(screen)
        
        # Update display
        pygame.display.flip()
        clock.tick(60)
    
    # Handle dialog result
    if dialog_result:
        if dialog_result["action"] == "confirm":
            combination = dialog_result["combination"]
            layout = dialog_result["layout"]
            
            logger.info(f"\nâœ… Mission Selected:")
            logger.info(f"   ID: {combination['id']}")
            logger.info(f"   Primary Mission: {combination['primary']}")
            logger.info(f"   Deployment: {combination['deployment']}")
            logger.info(f"   Terrain Layout: {layout}")
            
            # Apply the selection to the game
            game.selected_mission_info = {
                "primary": combination["primary"],
                "deployment": combination["deployment"],
                "layout": layout
            }
            
            logger.info(f"\nðŸŽ® Setting up battlefield with selected mission...")
            
            # Execute the mission setup phases
            try:
                game.execute_select_mission_objectives_phase()
                game.execute_create_battlefield_phase()
                logger.info(f"âœ… Battlefield setup complete!")
                
                # Show mission summary
                logger.info(f"\nðŸ“‹ Mission Summary:")
                logger.info(f"   Battlefield: {game.get_battlefield_size()}")
                logger.info(f"   Deployment zones: {len(game.deployment_zones)}")
                logger.info(f"   Objectives: {len(game.objectives)}")
                
            except Exception as e:
                logger.exception(f"âŒ Error setting up battlefield: {e}")
                import traceback
                traceback.print_exc()
                
        else:
            logger.info("\nâŒ Mission selection cancelled")
    else:
        logger.info("\nâŒ Dialog closed without selection")
    
    pygame.quit()
    logger.info("\nðŸŽ‰ Example completed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
