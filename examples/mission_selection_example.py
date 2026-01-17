#!/usr/bin/env python3
"""
Example demonstrating the Mission Selection Dialog for Chapter Approved 2025/2026.
This shows how to integrate the dialog into the game setup process.
"""

import sys
import os
import pygame

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
    
    print("ðŸŽ¯ Mission Selection Dialog Example")
    print("=" * 50)
    print("Instructions:")
    print("- Click on mission combinations to select them")
    print("- Click on terrain layout numbers to choose layout")
    print("- Click 'Pick Random' or press 'R' for random selection")
    print("- Use mouse wheel or arrow keys to scroll")
    print("- Press ESC to cancel or ENTER to confirm")
    print("- Click Cancel/Confirm buttons to close dialog")
    
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
            
            print(f"\nâœ… Mission Selected:")
            print(f"   ID: {combination['id']}")
            print(f"   Primary Mission: {combination['primary']}")
            print(f"   Deployment: {combination['deployment']}")
            print(f"   Terrain Layout: {layout}")
            
            # Apply the selection to the game
            game.selected_mission_info = {
                "primary": combination["primary"],
                "deployment": combination["deployment"],
                "layout": layout
            }
            
            print(f"\nðŸŽ® Setting up battlefield with selected mission...")
            
            # Execute the mission setup phases
            try:
                game.execute_select_mission_objectives_phase()
                game.execute_create_battlefield_phase()
                print(f"âœ… Battlefield setup complete!")
                
                # Show mission summary
                print(f"\nðŸ“‹ Mission Summary:")
                print(f"   Battlefield: {game.get_battlefield_size()}")
                print(f"   Deployment zones: {len(game.deployment_zones)}")
                print(f"   Objectives: {len(game.objectives)}")
                
            except Exception as e:
                print(f"âŒ Error setting up battlefield: {e}")
                import traceback
                traceback.print_exc()
                
        else:
            print("\nâŒ Mission selection cancelled")
    else:
        print("\nâŒ Dialog closed without selection")
    
    pygame.quit()
    print("\nðŸŽ‰ Example completed!")


if __name__ == "__main__":
    main()
