"""
InfoPane component for displaying game status and phase information.
"""

import pygame
from typing import List, Optional, Tuple, Dict

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.roster.player import Player
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.game import SetupPhase

# Font sizes
FONT_LARGE = 20
FONT_MEDIUM = 16
FONT_SMALL = 14
FONT_TINY = 12

# Modern UI Colors
PANEL_BG = (45, 45, 48)  # Dark background
PANEL_BORDER = (63, 63, 70)  # Subtle border
BUTTON_BG = (60, 60, 67)  # Button background
BUTTON_HOVER = (75, 75, 82)  # Button hover
BUTTON_SELECTED = (0, 122, 204)  # Selected button
TEXT_PRIMARY = (255, 255, 255)  # Primary text
TEXT_SECONDARY = (200, 200, 200)  # Secondary text
TEXT_ACCENT = (100, 149, 237)  # Accent text
DARK_GREY = (30, 30, 30)  # Dark grey for headers
RULE_NOTICE = (255, 200, 80)  # Warm highlight for rule notifications

# Deploy button colors
DEPLOY_BUTTON_BG = (40, 160, 40)  # Brighter green for deploy

class InfoPane(pygame.sprite.Sprite):
    """UI Panel for displaying game status and phase information."""
    
    def __init__(self, left: int, bottom: int, width: int, height: int, selected_unit: Unit):
        super().__init__()
        self.rect = pygame.Rect(left, bottom, width, height)
        self.selected_unit = selected_unit
        self.background_color = PANEL_BG
        
        # Fonts
        try:
            self.font_large = pygame.font.SysFont('Arial', FONT_LARGE, bold=True)
            self.font_medium = pygame.font.SysFont('Arial', FONT_MEDIUM, bold=False)
            self.font_small = pygame.font.SysFont('Arial', FONT_SMALL, bold=False)
            self.font_tiny = pygame.font.SysFont('Arial', FONT_TINY, bold=False)
        except:
            # Use default fonts if system fonts fail
            self.font_large = pygame.font.Font(None, FONT_LARGE)
            self.font_medium = pygame.font.Font(None, FONT_MEDIUM)
            self.font_small = pygame.font.Font(None, FONT_SMALL)
            self.font_tiny = pygame.font.Font(None, FONT_TINY)

    def handle_click(self, x: int, y: int, game_view) -> bool:
        """Handle mouse clicks on the info pane. Returns True if click was handled."""
        # No interactive elements in info pane anymore
        return False
    
    def update_hover(self, x: int, y: int):
        """Update hover state for interactive elements."""
        pass  # No interactive elements to hover over
    
    def _truncate_to_width(self, text: str, font: pygame.font.Font, max_width: int) -> str:
        """Truncate text with ellipsis so it fits within max_width pixels."""
        if not text:
            return ""
        try:
            if font.size(text)[0] <= max_width:
                return text
            ell = "..."
            # Fast path: progressively shrink
            lo, hi = 0, len(text)
            best = ell
            while lo <= hi:
                mid = (lo + hi) // 2
                candidate = text[:mid].rstrip() + ell
                if font.size(candidate)[0] <= max_width:
                    best = candidate
                    lo = mid + 1
                else:
                    hi = mid - 1
            return best
        except Exception:
            return text

    def draw(self, surface: pygame.Surface, game: Game, game_view=None):
        """Draw the info pane and its contents."""
        # Draw background
        pygame.draw.rect(surface, self.background_color, self.rect)
        pygame.draw.rect(surface, PANEL_BORDER, self.rect, 2)

        # Get game information
        current_player = game.get_current_player()
        opponent = game.get_opponent()
        
        y_offset = self.rect.top + 10
        x_left = self.rect.left + 15
        x_center = self.rect.centerx
        x_right = self.rect.right - 15

        # Game status line 1: Setup Phase, Deployment Phase, or Battle Round
        # Define deployment phase variables for later use
        in_deployment_phase = game.is_deployment_phase()
        deployment_zones_loaded = hasattr(game, 'deployment_zones') and game.deployment_zones
        
        if game.is_in_setup_phase():
            # Show current setup phase
            setup_phase_name = game.get_current_setup_phase().name.replace('_', ' ').title()
            game_status = f"SETUP: {setup_phase_name}"
            text_color = TEXT_ACCENT  # Use accent color to highlight setup phase
        elif in_deployment_phase:
            if deployment_zones_loaded:
                # Show whose turn it is to deploy with enhanced visibility
                deployment_player = game.get_current_deployment_player()
                deployable_units = game.get_deployable_units(deployment_player)
                game_status = f"DEPLOYMENT - {deployment_player.name}'s Turn ({len(deployable_units)} units left)"
                text_color = TEXT_ACCENT  # Use accent color to highlight deployment phase
            else:
                # Show battlefield creation phase before deployment zones are loaded
                game_status = "CREATING BATTLEFIELD"
                text_color = TEXT_SECONDARY  # Different color to indicate pre-deployment state
        else:
            # Show battle round with current player
            current_player_name = current_player.name if current_player else "Unknown"
            game_status = f"Turn {game.turn} - {current_player_name} - {game.phase.name.replace('_', ' ').title()}"
            text_color = TEXT_PRIMARY
        
        game_text = self.font_medium.render(game_status, True, text_color)
        game_rect = game_text.get_rect(center=(x_center, y_offset + 10))
        surface.blit(game_text, game_rect)
        
        y_offset += 30
        
        # Show mission information if selected
        if hasattr(game, 'selected_mission_info') and game.selected_mission_info:
            mission_info = game.selected_mission_info
            if 'combination_id' in mission_info:
                mission_text = f"Mission {mission_info['combination_id']}: {mission_info['primary']} / {mission_info['deployment']} / Layout {mission_info['layout']}"
            else:
                mission_text = f"Mission: {mission_info['primary']} / {mission_info['deployment']} / Layout {mission_info['layout']}"
            
            mission_surface = self.font_small.render(mission_text, True, TEXT_SECONDARY)
            mission_rect = mission_surface.get_rect(center=(x_center, y_offset + 5))
            surface.blit(mission_surface, mission_rect)
            y_offset += 20
        
        # Setup phase, deployment, or player information
        if game.is_in_setup_phase():
            # Show setup phase information
            setup_phase = game.get_current_setup_phase()
            setup_descriptions = {
                'MUSTER_ARMIES': 'Loading army lists and preparing forces',
                'SELECT_MISSION_OBJECTIVES': 'Configuring mission objectives and commands',
                'CREATE_BATTLEFIELD': 'Creating battlefield, terrain, and objectives',
                'DETERMINE_ATTACKER_AND_DEFENDER': 'Rolling dice to determine attacker/defender roles',
                'DECLARE_BATTLE_FORMATIONS': 'Declaring battle formations and reserves',
                'DEPLOY_ARMIES': 'Deploying armies to the battlefield',
                'DETERMINE_FIRST_TURN_ORDER': 'Rolling dice to determine who goes first'
            }
            
            # Special handling for DEPLOY_ARMIES phase to show whose turn it is
            if setup_phase.name == 'DEPLOY_ARMIES' and game.is_deployment_phase():
                deployment_player = game.get_current_deployment_player()
                if deployment_player:
                    if deployment_player == game.get_attacker():
                        description = 'DEPLOY ARMIES: Attacker\'s Turn'
                    elif deployment_player == game.get_defender():
                        description = 'DEPLOY ARMIES: Defender\'s Turn'
                    else:
                        description = f'DEPLOY ARMIES: {deployment_player.name}\'s Turn'
                else:
                    description = setup_descriptions.get(setup_phase.name, f"Executing {setup_phase.name}")
            else:
                description = setup_descriptions.get(setup_phase.name, f"Executing {setup_phase.name}")
            
            setup_text = description
            setup_surface = self.font_small.render(setup_text, True, TEXT_ACCENT)
            setup_rect = setup_surface.get_rect(center=(x_center, y_offset))
            surface.blit(setup_surface, setup_rect)
            
            # Show progress indicator
            phase_number = setup_phase.value + 1
            total_phases = len(SetupPhase.__members__)
            
            # Check if we're waiting for deployment input
            if getattr(game, 'waiting_for_deployment_input', False):
                progress_text = f"Phase {phase_number}/{total_phases} - Manual Deployment Mode: Press SPACE to continue each deployment"
            else:
                progress_text = f"Phase {phase_number}/{total_phases} - Press SPACE to continue"
            
            progress_surface = self.font_tiny.render(progress_text, True, TEXT_SECONDARY)
            progress_rect = progress_surface.get_rect(center=(x_center, y_offset + 20))
            surface.blit(progress_surface, progress_rect)
            y_offset += 20
        elif in_deployment_phase:
            if deployment_zones_loaded:
                # Show detailed deployment phase information
                deployment_player = game.get_current_deployment_player()
                deployable_units = game.get_deployable_units(deployment_player)
                
                # Show player role and deployment status
                player_role = "Attacker" if deployment_player == game.get_attacker() else "Defender"
                role_text = f"{deployment_player.name} ({player_role}) - {len(deployable_units)} units to deploy"
                role_surface = self.font_small.render(role_text, True, TEXT_ACCENT)
                role_rect = role_surface.get_rect(center=(x_center, y_offset))
                surface.blit(role_surface, role_rect)
                y_offset += 20
                
                # Show deployment zone info
                if hasattr(game, 'deployment_zones') and deployment_player.id in game.deployment_zones:
                    zone = game.deployment_zones[deployment_player.id]
                    # Display bounds derived from mission polygons (no rectangular deployment zones)
                    try:
                        xs, ys = [], []
                        for mz in (zone.get('mission_zones') or []):
                            for vx, vy in getattr(mz, 'vertices', []):
                                xs.append(float(vx)); ys.append(float(vy))
                        if xs and ys:
                            zone_text = f"Zone: X({min(xs):.0f}\"-{max(xs):.0f}\") Y({min(ys):.0f}\"-{max(ys):.0f}\")"
                        else:
                            zone_text = "Zone: (mission polygons)"
                    except Exception:
                        zone_text = "Zone: (mission polygons)"
                    zone_surface = self.font_small.render(zone_text, True, TEXT_SECONDARY)
                    zone_rect = zone_surface.get_rect(center=(x_center, y_offset))
                    surface.blit(zone_surface, zone_rect)
                    y_offset += 20
                
                # Show deployment instructions
                if deployment_player.has_control():
                    instruction_text = "Click units in roster to select, then click battlefield to deploy"
                    instruction_surface = self.font_tiny.render(instruction_text, True, TEXT_SECONDARY)
                    instruction_rect = instruction_surface.get_rect(center=(x_center, y_offset))
                    surface.blit(instruction_surface, instruction_rect)
                else:
                    instruction_text = "Waiting for remote player to deploy..."
                    instruction_surface = self.font_tiny.render(instruction_text, True, TEXT_SECONDARY)
                    instruction_rect = instruction_surface.get_rect(center=(x_center, y_offset))
                    surface.blit(instruction_surface, instruction_rect)

                # Rule notification banner (teaches why a player might deploy twice in a row)
                notice = getattr(game, "deployment_notice", None)
                if notice:
                    y_offset += 15
                    max_w = max(50, self.rect.width - 30)
                    notice_text = self._truncate_to_width(str(notice), self.font_tiny, max_w)
                    notice_surface = self.font_tiny.render(notice_text, True, RULE_NOTICE)
                    notice_rect = notice_surface.get_rect(center=(x_center, y_offset))
                    surface.blit(notice_surface, notice_rect)
            else:
                # Show battlefield creation status
                setup_text = "Preparing battlefield for deployment..."
                setup_surface = self.font_small.render(setup_text, True, TEXT_ACCENT)
                setup_rect = setup_surface.get_rect(center=(x_center, y_offset))
                surface.blit(setup_surface, setup_rect)
        elif game_view and hasattr(game_view, 'selected_unit') and game_view.selected_unit and not game_view.selected_unit.deployed:
            deployment_text = f"Click battlefield to deploy: {game_view.selected_unit.name}"
            deployment_surface = self.font_small.render(deployment_text, True, DEPLOY_BUTTON_BG)
            deployment_rect = deployment_surface.get_rect(center=(x_center, y_offset))
            surface.blit(deployment_surface, deployment_rect)
        else:
            # Always display Player 1 on the left and Player 2 on the right
            player1 = game.players[0] if len(game.players) > 0 else None
            player2 = game.players[1] if len(game.players) > 1 else None
            
            if player1:
                # Highlight current player with accent color
                player1_color = TEXT_ACCENT if current_player == player1 else TEXT_SECONDARY
                player1_text = f"{player1.name}: {player1.command_points} CP | Score: {player1.score}"
                player1_surface = self.font_small.render(player1_text, True, player1_color)
                surface.blit(player1_surface, (x_left, y_offset))
            
            if player2:
                # Highlight current player with accent color
                player2_color = TEXT_ACCENT if current_player == player2 else TEXT_SECONDARY
                player2_text = f"{player2.name}: {player2.command_points} CP | Score: {player2.score}"
                player2_surface = self.font_small.render(player2_text, True, player2_color)
                player2_rect = player2_surface.get_rect()
                surface.blit(player2_surface, (x_right - player2_rect.width, y_offset))
        
        y_offset += 25
        
        # Fight phase status display
        if game.is_fight_phase() and game_view and hasattr(game_view, 'get_fight_phase_status'):
            fight_status = game_view.get_fight_phase_status()
            if fight_status:
                # Display current fight stage
                stage_text = f"Stage: {fight_status['current_stage']}"
                stage_surface = self.font_small.render(stage_text, True, TEXT_ACCENT)
                stage_rect = stage_surface.get_rect(center=(x_center, y_offset))
                surface.blit(stage_surface, stage_rect)
                y_offset += 20
                
                # Show unit counts for each stage
                if fight_status['current_stage'] != 'Complete':
                    # Current player units
                    current_fight_first = fight_status['current_player_fight_first']
                    current_remaining = fight_status['current_player_remaining']
                    
                    # Opponent units
                    opponent_fight_first = fight_status['opponent_fight_first']
                    opponent_remaining = fight_status['opponent_remaining']
                    
                    # Display unit counts
                    if current_fight_first > 0 or opponent_fight_first > 0:
                        fight_first_text = f"Fight First: {current_fight_first} vs {opponent_fight_first}"
                        fight_first_surface = self.font_tiny.render(fight_first_text, True, TEXT_SECONDARY)
                        fight_first_rect = fight_first_surface.get_rect(center=(x_center, y_offset))
                        surface.blit(fight_first_surface, fight_first_rect)
                        y_offset += 15
                    
                    if current_remaining > 0 or opponent_remaining > 0:
                        remaining_text = f"Remaining: {current_remaining} vs {opponent_remaining}"
                        remaining_surface = self.font_tiny.render(remaining_text, True, TEXT_SECONDARY)
                        remaining_rect = remaining_surface.get_rect(center=(x_center, y_offset))
                        surface.blit(remaining_surface, remaining_rect)
                        y_offset += 15
                
                y_offset += 10
        
        # Deployment actions display during deployment phase
        if in_deployment_phase and hasattr(game, 'deployment_actions') and game.deployment_actions:
            # Display deployment actions on the appropriate side of the InfoPane
            # Left side for player 1, right side for player 2
            player1 = game.players[0] if len(game.players) > 0 else None
            player2 = game.players[1] if len(game.players) > 1 else None
            
            # Draw deployment actions for each player
            if player1:
                self._draw_deployment_actions(surface, game, player1, x_left, y_offset)
            if player2:
                self._draw_deployment_actions(surface, game, player2, x_right, y_offset)
        
        # Draw allowed actions if in battle phase
        if not game.is_in_setup_phase() and not in_deployment_phase and game_view:
            allowed_actions = game_view.phase_manager.get_current_allowed_actions()
            if allowed_actions:
                self._draw_allowed_actions(surface, allowed_actions, x_center, y_offset)

    def _draw_deployment_actions(self, surface: pygame.Surface, game: Game, player: Player, x_pos: int, y_offset: int):
        """Draw deployment actions for a specific player."""
        # Get deployment action for this player
        if player.name in game.deployment_actions:
            # Draw header
            header_text = f"{player.name}'s Deployment:"
            header_surface = self.font_small.render(header_text, True, TEXT_ACCENT)
            header_rect = header_surface.get_rect()
            if x_pos == self.rect.right - 15:  # Right side
                surface.blit(header_surface, (x_pos - header_rect.width, y_offset))
            else:  # Left side
                surface.blit(header_surface, (x_pos, y_offset))
            
            # Draw action
            y_pos = y_offset + 20
            action_text = game.deployment_actions[player.name]
            action_surface = self.font_tiny.render(action_text, True, TEXT_SECONDARY)
            action_rect = action_surface.get_rect()
            if x_pos == self.rect.right - 15:  # Right side
                surface.blit(action_surface, (x_pos - action_rect.width, y_pos))
            else:  # Left side
                surface.blit(action_surface, (x_pos, y_pos))

    def _draw_allowed_actions(self, surface: pygame.Surface, allowed_actions: List[str], x_center: int, y_offset: int) -> None:
        """Draw the list of allowed actions for the current phase."""
        # Draw header
        header_text = "Available Actions:"
        header_surface = self.font_small.render(header_text, True, TEXT_ACCENT)
        header_rect = header_surface.get_rect(center=(x_center, y_offset))
        surface.blit(header_surface, header_rect)
        
        # Draw actions
        y_pos = y_offset + 20
        for action in allowed_actions:
            # Format action text with emoji indicators
            if action == 'MOVE':
                action_text = "Move unit"
            elif action == 'ADVANCE':
                action_text = "Advance unit"
            elif action == 'SHOOT':
                action_text = "Shoot weapons"
            elif action == 'CHARGE':
                action_text = "Charge enemy"
            elif action == 'FIGHT':
                action_text = "Fight in melee"
            elif action == 'FALL_BACK':
                action_text = "Fall back"
            else:
                action_text = f"{action.title()}"
            
            # Draw action text
            action_surface = self.font_small.render(action_text, True, TEXT_SECONDARY)
            action_rect = action_surface.get_rect(center=(x_center, y_pos))
            surface.blit(action_surface, action_rect)
            y_pos += 20 
