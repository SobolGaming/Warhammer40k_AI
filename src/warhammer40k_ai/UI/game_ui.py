import pygame
import math
import re
from pathlib import Path
from typing import Optional, Tuple, Dict, List, Protocol, Callable, Any
from abc import ABC, abstractmethod
from warhammer40k_ai.classes.unit import Unit
from warhammer40k_ai.classes.model import Model
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.utility.calcs import get_unit_movement_path_preview, clear_enemy_model_cache
from warhammer40k_ai.classes.player import Player
from warhammer40k_ai.utility.dice import get_roll
from warhammer40k_ai.classes.map import TerrainFeature, TerrainType, Objective, ObjectivePoint
from warhammer40k_ai.classes.fight_phase_manager import FightPhaseManager, FightStage

# Import UI panels
from .panels.roster_pane import RosterPane
from .panels.stratagem_pane import StratagemPane
from .panels.info_pane import InfoPane
from ..utility.event_bus import get_recent_actions, get_recent_dice
from .panels.reserves_arrival_panel import ReservesArrivalPanel
from .panels.unit_detail_panel import UnitDetailPanel

# Import shared UI utilities
from .ui_utils import (
    get_unit_color_variation,
    draw_character_icon,
    draw_vehicle_icon,
    draw_monster_icon,
    draw_battleline_icon,
    draw_aircraft_icon,
    draw_beast_icon,
    draw_psyker_icon,
    draw_generic_icon
)
from .dialogs.secondary_discard_dialog import SecondaryDiscardDialog
from .dialogs.overwatch_shooter_dialog import OverwatchShooterDialog

# Constants
TILE_SIZE = 20  # 20 pixels per inch
BATTLEFIELD_WIDTH_INCHES = 60
BATTLEFIELD_HEIGHT_INCHES = 44
BATTLEFIELD_WIDTH = BATTLEFIELD_WIDTH_INCHES * TILE_SIZE
BATTLEFIELD_HEIGHT = BATTLEFIELD_HEIGHT_INCHES * TILE_SIZE

# Enhanced Colors - Modern UI Palette
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (50, 50, 50)
LIGHT_GREY = (200, 200, 200)
DARK_GREY = (40, 40, 40)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
RED = (255, 0, 0)
PURPLE = (128, 0, 128)

# Modern UI Colors
PANEL_BG = (45, 45, 48)  # Dark background
PANEL_BORDER = (63, 63, 70)  # Subtle border
BUTTON_BG = (60, 60, 67)  # Button background
BUTTON_HOVER = (75, 75, 82)  # Button hover
BUTTON_SELECTED = (0, 122, 204)  # Selected button
BUTTON_DISABLED = (40, 40, 40)  # Disabled button
TEXT_PRIMARY = (255, 255, 255)  # Primary text
TEXT_SECONDARY = (200, 200, 200)  # Secondary text
TEXT_ACCENT = (100, 149, 237)  # Accent text
TEXT_DISABLED = (100, 100, 100)  # Disabled text
HEALTH_GOOD = (76, 175, 80)  # Green for good health
HEALTH_DAMAGED = (255, 193, 7)  # Yellow for damaged
HEALTH_CRITICAL = (244, 67, 54)  # Red for critical

# Reserves UI Colors
RESERVES_BUTTON_BG = (140, 80, 200)  # Brighter purple for reserves
RESERVES_BUTTON_HOVER = (160, 100, 220)  # Lighter purple
STRATEGIC_RESERVES_BG = (60, 120, 200)  # Brighter blue for strategic reserves
STRATEGIC_RESERVES_HOVER = (80, 140, 220)  # Lighter blue
STRATEGIC_BUTTON_BG = (60, 120, 200)  # Brighter blue for strategic button
DEPLOY_BUTTON_BG = (40, 160, 40)  # Brighter green for deploy
DEPLOY_BUTTON_HOVER = (60, 180, 60)  # Lighter green

# Game states
class GameState:
    SETUP = 0
    PLAYING = 1
    GAME_OVER = 2

# Add these new constants
MIN_ZOOM = 1.0
MAX_ZOOM = 2.0
ZOOM_SPEED = 0.1
PAN_SPEED = 15  # Increased from 5 for faster keyboard panning
MOUSE_PAN_SPEED = 1.0  # New constant for mouse panning sensitivity

# Enhanced constants for the roster panes
ROSTER_PANE_WIDTH = 350  # Wider for more information
ROSTER_PANE_BUTTON_HEIGHT = 80  # Taller for more details
ROSTER_FONT_SIZE = 16
ROSTER_LINE_HEIGHT = 18
INFO_PANE_HEIGHT = 120  # Taller for more game info
STRATAGEM_PANE_WIDTH = 260

# Font sizes
FONT_LARGE = 20
FONT_MEDIUM = 16
FONT_SMALL = 14
FONT_TINY = 12

# Add new constants for icon drawing
ICON_SCALE_FACTOR = 0.8  # Larger icons that are more prominent
ICON_MIN_SIZE = 16  # Minimum icon size regardless of zoom
ICON_OVERLAY_ALPHA = 220  # Semi-transparent background for better visibility

# Color variations for multiple units of same type
UNIT_COLOR_VARIATIONS = [
    (255, 100, 100),  # Light red
    (100, 255, 100),  # Light green  
    (100, 100, 255),  # Light blue
    (255, 255, 100),  # Light yellow
    (255, 100, 255),  # Light magenta
    (100, 255, 255),  # Light cyan
    (255, 200, 100),  # Light orange
    (200, 100, 255),  # Light purple
]

class HumanUIInterface:
    """Interface class that bridges human UI components with the deployment system."""
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # UI components
        

        from .dialogs import ScoutChoiceDialog
        self.scout_choice_dialog = ScoutChoiceDialog(screen_width, screen_height)
        from .dialogs import FightUnitSelectionDialog
        self.fight_unit_selection_dialog = FightUnitSelectionDialog(screen_width, screen_height)
        # Note: melee weapon declaration dialog is now handled directly through game_view instance
        self.reserves_arrival_panel = ReservesArrivalPanel()
        
        # State for handling UI interactions
        self.pending_reserves_callback = None
        self.pending_position_callback = None
        self.current_unit_for_placement = None
        self.current_deployment_zone = None
        self.placement_mode = False
        
    def choose_deployment_zone(self, available_zones: List[dict]) -> dict:
        """Human chooses deployment zone via UI."""
        # For now, return the first available zone
        # In a full implementation, this would show a zone selection dialog
        return available_zones[0]
    

    
    def choose_unit_deployment_position(self, unit: 'Unit', deployment_zone: dict, 
                                       already_deployed: List['Unit']) -> Tuple[float, float]:
        """Human chooses unit position via UI clicking."""
        
        # Set up for position selection
        self.current_unit_for_placement = unit
        self.current_deployment_zone = deployment_zone
        self.placement_mode = True
        
        selected_position = None
        position_selected = False
        
        print(f"Click on the battlefield to place {unit.name}")
        # Compute a bounding box for display only from mission polygons
        try:
            xs, ys = [], []
            for mz in (deployment_zone.get('mission_zones') or []):
                for vx, vy in getattr(mz, 'vertices', []):
                    xs.append(float(vx)); ys.append(float(vy))
            if xs and ys:
                print(f"Deployment zone bounds: X({min(xs):.1f} - {max(xs):.1f}), Y({min(ys):.1f} - {max(ys):.1f})")
        except Exception:
            pass
        
        # Wait for position selection
        clock = pygame.time.Clock()
        while not position_selected and self.placement_mode:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    # Return center of deployment zone as default
                    x_center, y_center = self._zone_centroid(deployment_zone)
                    return x_center, y_center
                
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # Convert screen coordinates to game coordinates
                    game_x, game_y = self.screen_to_game_coords(event.pos)
                    
                    # Check if position is within deployment zone
                    if self.is_position_in_zone(game_x, game_y, deployment_zone):
                        selected_position = (game_x, game_y)
                        position_selected = True
                        print(f"Unit {unit.name} will be placed at ({game_x:.1f}, {game_y:.1f})")
                    else:
                        print(f"Invalid position ({game_x:.1f}, {game_y:.1f}) - must be within deployment zone")
                
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    # Cancel and use center of deployment zone
                    x_center, y_center = self._zone_centroid(deployment_zone)
                    selected_position = (x_center, y_center)
                    position_selected = True
                    print(f"Position selection cancelled, using center of deployment zone")
            
            clock.tick(60)
        
        self.placement_mode = False
        self.current_unit_for_placement = None
        self.current_deployment_zone = None
        
        if selected_position:
            return selected_position
        return self._zone_centroid(deployment_zone)
    
    def screen_to_game_coords(self, screen_pos: Tuple[int, int]) -> Tuple[float, float]:
        """Convert screen coordinates to game coordinates."""
        # This would need to account for zoom, pan, and coordinate system
        # For now, simplified conversion assuming 1:1 mapping
        x, y = screen_pos
        # Convert from screen pixels to game inches
        game_x = x / TILE_SIZE
        game_y = y / TILE_SIZE
        return game_x, game_y
    
    def is_position_in_zone(self, x: float, y: float, zone: dict) -> bool:
        """Check if a position is within the deployment zone."""
        mzs = zone.get('mission_zones') or []
        if not mzs:
            raise RuntimeError("Deployment zone missing mission_zones polygons (invalid configuration).")
        for mz in mzs:
            if mz.contains_point(x, y):
                return True
        return False

    def _zone_centroid(self, zone: dict) -> Tuple[float, float]:
        """Best-effort centroid for a compound mission zone."""
        mzs = zone.get('mission_zones') or []
        if not mzs:
            raise RuntimeError("Deployment zone missing mission_zones polygons (invalid configuration).")
        try:
            xs, ys = [], []
            for mz in mzs:
                for vx, vy in getattr(mz, 'vertices', []):
                    xs.append(float(vx)); ys.append(float(vy))
            if xs and ys:
                return (sum(xs) / len(xs), sum(ys) / len(ys))
        except Exception:
            pass
        # Fallback to battlefield center if something is very wrong
        return (30.0, 22.0)
    
    def update(self, screen):
        """Update and draw UI components."""
        if self.reserves_arrival_panel.visible:
            self.reserves_arrival_panel.draw(screen)
        
        # Draw placement indicator if in placement mode
        if self.placement_mode and self.current_unit_for_placement:
            self.draw_placement_indicator(screen)
    
    def draw_placement_indicator(self, screen):
        """Draw visual indicator for unit placement."""
        if not self.current_unit_for_placement or not self.current_deployment_zone:
            return
        
        # Draw deployment zone outline (mission polygons)
        zone = self.current_deployment_zone
        mzs = zone.get('mission_zones') or []
        if not mzs:
            raise RuntimeError("Deployment zone missing mission_zones polygons (invalid configuration).")
        for mz in mzs:
            pts = []
            for vx, vy in getattr(mz, "vertices", []):
                sx = int(vx * TILE_SIZE * self.zoom_level)
                sy = int(vy * TILE_SIZE * self.zoom_level)
                pts.append((sx, sy))
            if len(pts) >= 3:
                pygame.draw.polygon(screen, TEXT_ACCENT, pts, 3)
        
        # Draw unit name
        font = pygame.font.SysFont('Arial', 16, bold=True)
        text = font.render(f"Place {self.current_unit_for_placement.name}", True, TEXT_PRIMARY)
        screen.blit(text, (10, 10))
        
        # Draw instructions
        instr_font = pygame.font.SysFont('Arial', 14)
        instructions = [
            "Left click to place unit",
            "ESC to use center position",
            f"Must be in highlighted zone"
        ]
        
        for i, instruction in enumerate(instructions):
            instr_text = instr_font.render(instruction, True, TEXT_SECONDARY)
            screen.blit(instr_text, (10, 40 + i * 20))
    
    def handle_event(self, event):
        """Handle pygame events for non-dialog UI components only.

        Dialogs are exclusively handled by DialogManager.
        """
        if self.reserves_arrival_panel.visible:
            return bool(self.reserves_arrival_panel.handle_event(event))
        return False

    def show_scout_dialog(self, unit, callback, game_map=None):
        """Show the scout move dialog for a unit."""
        # print(f"🔍 HumanUIInterface.show_scout_dialog called for {unit.name}")
        self.scout_choice_dialog.show(unit, callback, game_map)
        # print(f"🔍 DEBUG: Scout dialog show() completed, visible={self.scout_choice_dialog.visible}")
    
    def show_fight_unit_selection_dialog(self, stage_name: str, eligible_units: List['Unit'], 
                                        on_unit_selected: Callable[['Unit'], None], 
                                        on_cancel: Callable[[], None] = None):
        """Show the fight unit selection dialog for a stage."""
        print(f"⚔️ HumanUIInterface.show_fight_unit_selection_dialog called for {stage_name} stage with {len(eligible_units)} units")
        self.fight_unit_selection_dialog.show(stage_name, eligible_units, on_unit_selected, on_cancel)

    def show_melee_weapon_declaration_dialog(self, unit, callback, game_map=None):
        """Show the melee weapon declaration dialog for a unit."""
        print(f"⚔️ HumanUIInterface.show_melee_weapon_declaration_dialog called for {unit.name}")
        # Delegate to the game view's dialog instance to avoid duplicates
        if hasattr(self, 'game_view') and hasattr(self.game_view, 'melee_weapon_declaration_dialog'):
            self.game_view.melee_weapon_declaration_dialog.show(unit, callback, game_map)
        else:
            print(f"❌ Error: melee_weapon_declaration_dialog not found on game_view")
            # Call callback with empty declarations to prevent hanging
            if callback:
                callback([])


class GameView:
    def __init__(self, screen, env, game, game_map, player1, player2, ui_interface=None):
        self.screen = screen
        self.env = env
        self.game = game
        self.game_map = game_map
        self.player1 = player1
        self.player2 = player2
        self.selected_unit = None
        self.dragging_unit = None
        self.dragging = False
        self.drag_offset = (0, 0)
        self.zoom_level = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.detailed_unit = None
        self.detail_panel_pos = (0, 0)
        self.unit_detail_panel = UnitDetailPanel()
        
        # UI scaling factor removed – rendering uses fixed inch grid with zoom only
        
        # UI interface for human player interaction
        self.ui_interface = ui_interface

        # Set reference back to game view in UI interface for dialog access
        if ui_interface:
            ui_interface.game_view = self

        # Central dialog manager (modal stack)
        from .dialogs import DialogManager
        self.dialog_manager = DialogManager(self)

        # Wire combat UI hooks into the Map (used by core combat code like WargearProfile.attack()).
        try:
            if self.game and getattr(self.game, "map", None) is not None:
                self.game.map.precision_allocation_provider = self._precision_allocation_provider
                self.game.map.damage_allocation_provider = self._damage_allocation_provider
                self.game.map.hazardous_allocation_provider = self._hazardous_allocation_provider
                self.game.map.roll_reroll_provider = self._roll_reroll_provider
        except Exception:
            pass
        try:
            if self.game_map is not None:
                self.game_map.precision_allocation_provider = self._precision_allocation_provider
                self.game_map.damage_allocation_provider = self._damage_allocation_provider
                self.game_map.hazardous_allocation_provider = self._hazardous_allocation_provider
                self.game_map.roll_reroll_provider = self._roll_reroll_provider
        except Exception:
            pass
        
        # Phase-based event handling system
        self.phase_manager = PhaseManager(self)
        
        # Mouse panning support
        self.panning = False
        self.pan_start_pos = (0, 0)
        self.pan_start_offset = (0, 0)

        # Create roster and stratagem panes with reference to all units for color correlation
        # Fixed panes; battlefield viewport derived from actual screen size
        scaled_roster_width = ROSTER_PANE_WIDTH
        scaled_stratagem_width = STRATAGEM_PANE_WIDTH
        scaled_info_height = INFO_PANE_HEIGHT
        screen_width, screen_height = self.screen.get_size()
        scaled_battlefield_width = max(100, screen_width - 2 * (scaled_roster_width + scaled_stratagem_width))
        scaled_battlefield_height = max(100, screen_height - scaled_info_height)

        # Roster panes should not overlap the bottom logs pane; limit to battlefield height
        roster_pane_height = scaled_battlefield_height
        player1_units = player1.get_army().units if player1.get_army() else []
        player2_units = player2.get_army().units if player2.get_army() else []

        self.scaled_stratagem_width = scaled_stratagem_width
        self.battlefield_left = scaled_stratagem_width + scaled_roster_width
        self.battlefield_right = self.battlefield_left + scaled_battlefield_width

        self.left_stratagem_pane = StratagemPane(0, 0, scaled_stratagem_width, roster_pane_height,
                                                 f"Player 1 ({player1.name})")
        self.right_stratagem_pane = StratagemPane(self.battlefield_right + scaled_roster_width, 0,
                                                  scaled_stratagem_width, roster_pane_height,
                                                  f"Player 2 ({player2.name})")

        self.left_roster_pane = RosterPane(scaled_stratagem_width, 0, scaled_roster_width, roster_pane_height,
                                           player1_units, f"Player 1 ({player1.name})")
        self.right_roster_pane = RosterPane(self.battlefield_right, 0, scaled_roster_width,
                                            roster_pane_height, player2_units,
                                            f"Player 2 ({player2.name})")
        
        # Store scaled dimensions for mouse coordinate conversion
        self.scaled_roster_width = scaled_roster_width
        self.scaled_battlefield_width = scaled_battlefield_width
        self.scaled_battlefield_height = scaled_battlefield_height
        self.scaled_info_height = scaled_info_height
        
        # Pass all units to roster panes for color correlation
        all_units = player1_units + player2_units
        self.left_roster_pane.all_units = all_units
        self.right_roster_pane.all_units = all_units
        self.left_stratagem_pane.player = self.player1
        self.right_stratagem_pane.player = self.player2
        
        # Set game_view reference in roster panes for deployment dialog
        self.left_roster_pane.game_view = self
        self.right_roster_pane.game_view = self
        
        # Position InfoPane between roster panes and below battlefield
        self.info_pane = InfoPane(self.battlefield_left, scaled_battlefield_height,
                                  scaled_battlefield_width, scaled_info_height, self.selected_unit)
        
        # Stratagem interaction dialogs
        screen_width, screen_height = self.screen.get_size()
        # Generic Yes/No prompt dialog (used for optional abilities, confirmations, etc.)
        from .dialogs import YesNoDialog
        self.yes_no_dialog = YesNoDialog(screen_width, screen_height)
        self.secondary_discard_dialog = SecondaryDiscardDialog(screen_width, screen_height)
        self.overwatch_shooter_dialog = OverwatchShooterDialog(screen_width, screen_height)
        # WORLD EATERS: Blessings of Khorne dialog (lazy-create only if needed)
        self.blessings_of_khorne_dialog = None
        # Stratagem interaction helpers
        def _request_secondary_discard(player, game, on_chosen):
            cards = list(getattr(player, 'active_secondaries', []) or [])
            if not cards:
                on_chosen(None)
                return
            self.secondary_discard_dialog.show(cards, lambda chosen: (self.secondary_discard_dialog.hide(), on_chosen(chosen)))
        self._request_secondary_discard = _request_secondary_discard

        def _request_overwatch_shooter(player, game, enemy_unit, on_chosen):
            # Build candidate list as StratagemManager did, but UI-driven
            candidates = []
            for unit in player.get_army().units or []:
                if not unit.is_alive() or not unit.deployed:
                    continue
                if getattr(unit, 'is_titanic', False):
                    continue
                dist = self.game.map.get_distance_between_units(unit, enemy_unit)
                if dist is not None and dist <= 24.0:
                    candidates.append(unit)
            if not candidates:
                on_chosen(None)
                return
            # Show selection dialog for Overwatch shooter
            if hasattr(self, 'overwatch_shooter_dialog') and self.overwatch_shooter_dialog:
                self.overwatch_shooter_dialog.show(candidates, enemy_unit, lambda unit: (self.overwatch_shooter_dialog.hide(), on_chosen(unit)))
            else:
                on_chosen(candidates[0])
        self._request_overwatch_shooter = _request_overwatch_shooter

        def _request_rapid_ingress_unit(player, game, candidates, on_chosen):
            # Candidates are the units in reserves that can arrive this battle round
            cand = list(candidates or [])
            if not cand:
                # Fallback: compute from game state
                try:
                    cand = list(game.get_units_that_can_arrive_from_reserves(player))
                except Exception:
                    cand = []
            if not cand:
                on_chosen(None)
                return
            if hasattr(self, 'overwatch_shooter_dialog') and self.overwatch_shooter_dialog:
                self.overwatch_shooter_dialog.show(
                    cand,
                    None,
                    lambda unit: (self.overwatch_shooter_dialog.hide(), on_chosen(unit)),
                    title="Select Rapid Ingress Unit",
                    subtitle="Choose a unit in Reserves to arrive now",
                )
            else:
                on_chosen(cand[0])
        self._request_rapid_ingress_unit = _request_rapid_ingress_unit

        def _request_counter_offensive_unit(player, game, candidates, on_chosen):
            cand = list(candidates or [])
            if not cand:
                try:
                    cand = list(game.get_eligible_fighting_units(player))
                except Exception:
                    cand = []
            try:
                fight_mgr = getattr(game, "fight_phase_manager", None)
                fought = getattr(fight_mgr, "fought_units", set()) if fight_mgr else set()
                cand = [u for u in cand if u not in fought]
            except Exception:
                pass
            if not cand:
                on_chosen(None)
                return
            if hasattr(self, 'overwatch_shooter_dialog') and self.overwatch_shooter_dialog:
                self.overwatch_shooter_dialog.show(
                    cand,
                    None,
                    lambda unit: (self.overwatch_shooter_dialog.hide(), on_chosen(unit)),
                    title="Select Counter-Offensive Unit",
                    subtitle="Choose a unit to fight next",
                )
            else:
                on_chosen(cand[0])
        self._request_counter_offensive_unit = _request_counter_offensive_unit

        # Generic yes/no prompt hook for optional ability decisions (e.g., Direct the Slaughter)
        def _request_yes_no(title: str, message: str, yes_label: str, no_label: str, on_chosen):
            self.yes_no_dialog.show(
                title,
                message,
                lambda choice: (self.yes_no_dialog.hide(), on_chosen(bool(choice))),
                yes_label=yes_label,
                no_label=no_label,
            )
            try:
                # Make it explicitly topmost
                self.dialog_manager.open(self.yes_no_dialog, modal=True)
            except Exception:
                pass
        self._request_yes_no = _request_yes_no

        def _request_overwatch_shooting(shooter_unit, enemy_unit, on_done):
            # Reuse ShootingDeclarationDialog for interactive weapon selection/targeting
            if not hasattr(self, 'shooting_declaration_dialog'):
                from .dialogs import ShootingDeclarationDialog
                self.shooting_declaration_dialog = ShootingDeclarationDialog(self.screen.get_width(), self.screen.get_height())
            # Configure dialog to auto-target the moved enemy unit
            try:
                self.shooting_declaration_dialog.force_single_target_unit = enemy_unit
            except Exception:
                pass
            def _cb(_):
                # Determine success by checking if any declarations were made and executed
                # The dialog's execute_shooting already executed and hides itself
                # We approximate success if the shooter's shot_this_round is now True
                executed = bool(getattr(shooter_unit.round_state, 'shot_this_round', False))
                on_done(executed)
            self.shooting_declaration_dialog.show(shooter_unit, _cb, self.game.map, self)
            # Ensure dialog is visible and receives events immediately
            self.shooting_declaration_dialog.visible = True
        self._request_overwatch_shooting = _request_overwatch_shooting

        # WORLD EATERS: SKULLS FOR THE SKULL THRONE! -> interactive Blessings roll (extra global Blessing)
        def _request_blessings_roll(player, game, context, on_done):
            try:
                army = player.get_army()
            except Exception:
                on_done(False)
                return
            mgr = getattr(army, "blessings_of_khorne", None)
            if mgr is None:
                on_done(False)
                return
            if self.blessings_of_khorne_dialog is None:
                try:
                    from .dialogs import BlessingsOfKhorneDialog
                    sw, sh = self.screen.get_size()
                    self.blessings_of_khorne_dialog = BlessingsOfKhorneDialog(sw, sh)
                except Exception:
                    self.blessings_of_khorne_dialog = None
            if self.blessings_of_khorne_dialog is None:
                on_done(False)
                return

            # Determine if Favoured of Khorne reroll is available (bearer on battlefield)
            rerolls_allowed = 0
            try:
                for u in list(getattr(army, "units", []) or []):
                    enh = getattr(u, "enhancement", None)
                    if enh is not None and str(getattr(enh, "name", "")).strip().lower() == "favoured of khorne":
                        if getattr(u, "deployed", False) and u.is_alive() and getattr(u, "reserve_status", "deployed") == "deployed":
                            rerolls_allowed = 2
                            break
            except Exception:
                rerolls_allowed = 0

            from ..classes.blessings_of_khorne import BlessingsTiming
            ctx = mgr.create_roll_context(
                battle_round=int(getattr(game, "turn", 0) or 0),
                timing=BlessingsTiming.OTHER,
                extra_dice_from_idols=0,
                rerolls_allowed=rerolls_allowed,
                max_activations=1,
                counts_toward_baseline_limit=False,
                already_active_keys=set(getattr(mgr, "active_blessing_keys", set()) or set()),
                reborn_in_blood_available=False,
            )

            def _on_confirm(payload):
                # Spend CP for stratagem AFTER successful blessing selection/apply
                ok = False
                try:
                    cp_cost = int(context.get("cp_cost", 1) or 1)
                    if not player.spend_command_points(cp_cost):
                        on_done(False)
                        return
                    # Dequeue reaction if present
                    try:
                        if getattr(player, "stratagems", None) is not None and hasattr(player.stratagems, "_dequeue_reaction_by_name"):
                            player.stratagems._dequeue_reaction_by_name("SKULLS FOR THE SKULL THRONE!")
                    except Exception:
                        pass
                    ok = True
                finally:
                    on_done(ok)

            self.blessings_of_khorne_dialog.show(player=player, game=game, army=army, ctx=ctx, on_confirm=_on_confirm)
            try:
                self.dialog_manager.open(self.blessings_of_khorne_dialog, modal=True)
            except Exception:
                pass
        self._request_blessings_roll = _request_blessings_roll
        self._stratagem_panes = {
            self.player1: self.left_stratagem_pane,
            self.player2: self.right_stratagem_pane,
        }
        self._overwatch_flow_active = False
        self._optional_flow_active = False
        self._blessings_flow_active = False

        # Initialize shared UI state
        self._ui_hitboxes = {}
        self._mission_popup = None
        # Cache loaded mission card images (path string -> pygame.Surface)
        self._mission_image_surface_cache: Dict[str, pygame.Surface] = {}
        # Cache "does this card have an image?" lookups (cache_key -> Optional[str path])
        self._mission_image_path_cache: Dict[str, Optional[str]] = {}

        # WORLD EATERS: start-of-battle-round Blessings hook
        self._pending_blessings_queue = []
        # SLAANESH/DAEMONS (Shalaxi): Monarch of the Hunt quarry selection queue
        self._pending_quarry_queue = []
        try:
            if self.game and getattr(self.game, "event_system", None) is not None:
                self.game.event_system.subscribe("battle_round_started", self._on_battle_round_started)
                # Optional ability prompts (phase-start timing windows)
                self.game.event_system.subscribe("phase_start", self._on_phase_start_optional_ability_prompts)
                # Quarry re-pick when quarry is destroyed
                self.game.event_system.subscribe("unit_destroyed", self._on_unit_destroyed_for_monarch_of_the_hunt)
        except Exception:
            pass

    def _on_battle_round_started(self, game=None, battle_round: int = 0, **_kwargs):
        """Event hook: at start of battle round, prompt WE human players for Blessings of Khorne selection."""
        try:
            game = game or self.game
            br = int(battle_round or getattr(game, "turn", 0) or 0)
        except Exception:
            return
        if br <= 0:
            return

        # Build queue of players to prompt (human WE only), starting with the current player.
        try:
            current = game.get_current_player()
            others = [p for p in list(getattr(game, "players", []) or []) if p is not current]
            order = [current] + others
        except Exception:
            order = list(getattr(game, "players", []) or [])

        queue = []
        for p in order:
            try:
                if p is None or p.type.name != "HUMAN":
                    continue
                army = p.get_army()
                if getattr(army, "faction_id", None) != "WE":
                    continue
                if getattr(army, "blessings_of_khorne", None) is None:
                    continue
                queue.append(p)
            except Exception:
                continue

        if queue:
            self._pending_blessings_queue = list(queue)
            self._open_next_blessings_prompt(br)

        # SHALAXI: Monarch of the Hunt triggers at the start of the first battle round.
        if br == 1:
            self._queue_monarch_of_the_hunt_prompts(game)

    # ---------------- Optional ability prompt windows (UI-driven) ----------------

    def _on_phase_start_optional_ability_prompts(self, player=None, phase=None, **_kwargs):
        """
        UI-driven optional ability prompts.

        - Possessed Lord: once per battle, start of Fight phase, prompt to activate.
        """
        # Only care about Fight phase
        try:
            pname = str(getattr(phase, "name", "") or "").strip().upper()
        except Exception:
            pname = ""
        if pname != "FIGHT_PHASE":
            return
        if player is None:
            return
        try:
            # Only prompt the active player (avoid double prompts from opponent publishes)
            if player is not self.game.get_current_player():
                return
        except Exception:
            pass
        # Only for human players (AI will decide via decision_hook / agent)
        try:
            if getattr(player, "type", None) is None or getattr(player.type, "name", "") != "HUMAN":
                return
        except Exception:
            return

        army = getattr(player, "army", None)
        if army is None:
            return

        # Build queue of (unit, model) that can activate Possessed Lord
        queue = []
        for unit in list(getattr(army, "units", []) or []):
            try:
                if not unit.is_alive():
                    continue
            except Exception:
                continue
            has_possessed_lord = False
            for ab in (getattr(unit, "possible_abilities", []) or []):
                nm = str(getattr(ab, "name", "") or "").strip().lower()
                if nm == "possessed lord":
                    has_possessed_lord = True
                    break
            if not has_possessed_lord:
                continue
            for m in list(getattr(unit, "models", []) or []):
                try:
                    if not getattr(m, "is_alive", True):
                        continue
                except Exception:
                    continue
                try:
                    if getattr(m, "has_used_once_per_battle", lambda _k: False)("possessed_lord"):
                        continue
                except Exception:
                    pass
                queue.append((unit, m))
                break  # typical character: prompt once per unit

        if not queue:
            return

        # Store and process sequentially so we don't stack multiple modals at once.
        self._pending_optional_ability_queue = list(queue)
        self._process_next_optional_ability_prompt(player)

    def _process_next_optional_ability_prompt(self, player):
        q = list(getattr(self, "_pending_optional_ability_queue", []) or [])
        if not q:
            self._pending_optional_ability_queue = []
            return
        unit, model = q.pop(0)
        self._pending_optional_ability_queue = q

        title = "Optional Ability"
        msg = f"Use Possessed Lord for {getattr(model, 'name', 'Model')} ({getattr(unit, 'name', 'Unit')})?\n\nOnce per battle: +3A (melee) and Devastating Wounds until end of Fight phase."

        def _done(chosen: bool):
            if chosen:
                try:
                    model.activate_possessed_lord()
                except Exception:
                    pass
            # Continue queue
            self._process_next_optional_ability_prompt(player)

        # Show modal yes/no
        try:
            self.yes_no_dialog.show(title, msg, _done, yes_label="Use", no_label="Skip")
            self.dialog_manager.open(self.yes_no_dialog, modal=True)
        except Exception:
            # If UI wiring is missing, just skip
            _done(False)

    def _roll_reroll_provider(self, player=None, unit=None, roll_type: str = "", value=None, dice=None, **_kwargs):
        """
        Blocking modal prompt for rule-based (free) re-rolls.
        Returns True to reroll, False to keep.
        """
        try:
            if player is None or getattr(player, "type", None) is None or getattr(player.type, "name", "") != "HUMAN":
                return False
        except Exception:
            return False

        try:
            from .dialogs import RollRerollDialog
        except Exception:
            return False

        if not hasattr(self, "roll_reroll_dialog") or self.roll_reroll_dialog is None:
            self.roll_reroll_dialog = RollRerollDialog(self.screen.get_width(), self.screen.get_height())

        rt = str(roll_type or "").strip().lower()
        title = "Re-roll?"
        if rt == "advance":
            title = "Advance Roll"
        elif rt == "charge":
            title = "Charge Roll"
        elif rt == "hit":
            title = "Hit Roll"
        elif rt == "wound":
            title = "Wound Roll"

        ulabel = getattr(unit, "name", "Unit")
        msg = f"{ulabel} rolled {value}."
        try:
            if rt == "charge" and dice:
                msg = f"{ulabel} rolled {value} (dice: {list(dice)})."
        except Exception:
            pass
        # For attack rolls, show needed/eligible status with colored border
        roll_text = ""
        roll_border = None
        try:
            needed = _kwargs.get("needed", None)
            success = _kwargs.get("success", None)
            if rt in ("hit", "wound") and needed is not None and success is not None:
                roll_text = f"Rolled {int(value)} (need {int(needed)}+)"
                roll_border = "success" if bool(success) else "fail"
        except Exception:
            roll_text = ""
            roll_border = None

        if rt in ("hit", "wound"):
            msg = f"{msg}\n\nEligible for re-roll (Monarch of the Hunt). You may re-roll even if successful."
        else:
            msg = f"{msg}\n\nYou may re-roll this {rt} roll."

        dlg = self.roll_reroll_dialog
        choice_holder = {"choice": False, "done": False}

        def _on_choice(chosen: bool):
            choice_holder["choice"] = bool(chosen)
            choice_holder["done"] = True

        allow_reroll = True
        try:
            if "allow_reroll" in _kwargs:
                allow_reroll = bool(_kwargs.get("allow_reroll", True))
        except Exception:
            allow_reroll = True

        dlg.show(
            title=title,
            message=msg,
            roll_text=roll_text,
            roll_border=roll_border,
            allow_reroll=allow_reroll,
            callback=_on_choice,
            keep_label="Keep",
            reroll_label="Re-roll",
        )
        try:
            self.dialog_manager.open(dlg, modal=True)
        except Exception:
            pass

        clock = pygame.time.Clock()
        while dlg.visible and not choice_holder["done"]:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return False
                try:
                    self.dialog_manager.handle_event(event)
                except Exception:
                    pass
            try:
                self.draw()
            except Exception:
                try:
                    dlg.draw(self.screen)
                    pygame.display.update()
                except Exception:
                    pass
            clock.tick(60)

        return bool(choice_holder["choice"])

    # ---------------- Monarch of the Hunt (Shalaxi) ----------------

    def _queue_monarch_of_the_hunt_prompts(self, game):
        """
        At BR1 start: prompt each human player who has a unit with 'Monarch of the Hunt' to pick a quarry.
        """
        try:
            current = game.get_current_player()
            others = [p for p in list(getattr(game, "players", []) or []) if p is not current]
            order = [current] + others
        except Exception:
            order = list(getattr(game, "players", []) or [])

        queue = []
        for p in order:
            try:
                if p is None:
                    continue
                army = p.get_army()
                if army is None:
                    continue
                for u in list(getattr(army, "units", []) or []):
                    try:
                        if not u.is_alive():
                            continue
                    except Exception:
                        continue
                    # Find Monarch of the Hunt ability by name
                    try:
                        found, _ = u._find_ability_with_patterns(["monarch of the hunt"])
                    except Exception:
                        found = False
                    if not found:
                        continue
                    # Only prompt if not already set
                    if getattr(u, "_monarch_of_the_hunt_quarry_ids", None):
                        continue
                    queue.append((p, u))
            except Exception:
                continue

        if not queue:
            return
        self._pending_quarry_queue.extend(queue)
        # If nothing is currently visible, open immediately.
        self._open_next_quarry_prompt()

    def _open_next_quarry_prompt(self):
        if not self._pending_quarry_queue:
            return
        p, shalaxi_unit = self._pending_quarry_queue.pop(0)

        # Determine enemy army (2-player game assumed)
        enemy_player = None
        try:
            for op in list(getattr(self.game, "players", []) or []):
                if op is not p:
                    enemy_player = op
                    break
        except Exception:
            enemy_player = None
        if enemy_player is None:
            self._open_next_quarry_prompt()
            return

        enemy_army = getattr(enemy_player, "army", None)
        if enemy_army is None:
            self._open_next_quarry_prompt()
            return

        # Build eligible enemy units:
        # - include reserves
        # - exclude embarked units
        # - attached leaders collapsed into bodyguard root
        eligible = []
        seen = set()
        for u in list(getattr(enemy_army, "units", []) or []):
            try:
                # Hide attached leaders as separate entries
                if bool(getattr(u, "is_attached_leader", False)):
                    continue
            except Exception:
                pass
            try:
                root = u.get_attached_unit_root()
            except Exception:
                root = u
            try:
                rid = getattr(root, "_id", None)
                if not rid or rid in seen:
                    continue
                seen.add(rid)
            except Exception:
                continue
            try:
                if not root.is_alive():
                    continue
            except Exception:
                continue
            # Cannot select embarked units as quarry (rules commentary)
            try:
                if callable(getattr(root, "is_embarked", None)) and bool(root.is_embarked()):
                    continue
                if getattr(root, "embarked_in", None) is not None:
                    continue
            except Exception:
                pass
            eligible.append(root)

        eligible.sort(key=lambda x: str(getattr(x, "name", "")))
        if not eligible:
            self._open_next_quarry_prompt()
            return

        # AI owners: auto-pick first eligible
        try:
            if getattr(p, "type", None) is not None and getattr(p.type, "name", "") != "HUMAN":
                self._set_monarch_quarry(shalaxi_unit, eligible[0])
                self._open_next_quarry_prompt()
                return
        except Exception:
            pass

        try:
            from .dialogs import QuarrySelectionDialog
        except Exception:
            self._set_monarch_quarry(shalaxi_unit, eligible[0])
            self._open_next_quarry_prompt()
            return

        if not hasattr(self, "quarry_selection_dialog") or self.quarry_selection_dialog is None:
            self.quarry_selection_dialog = QuarrySelectionDialog(self.screen.get_width(), self.screen.get_height())

        dlg = self.quarry_selection_dialog

        def _on_confirm(chosen_unit):
            self._set_monarch_quarry(shalaxi_unit, chosen_unit)
            self._open_next_quarry_prompt()

        def _on_cancel():
            # Monarch of the Hunt is mandatory; if cancelled, default to first eligible.
            self._set_monarch_quarry(shalaxi_unit, eligible[0])
            self._open_next_quarry_prompt()

        subtitle = "Embarked units cannot be selected. Units in Reserves may be selected."
        dlg.show(
            title="Monarch of the Hunt",
            subtitle=subtitle,
            choices=eligible,
            on_confirm=_on_confirm,
            on_cancel=_on_cancel,
        )
        try:
            self.dialog_manager.open(dlg, modal=True)
        except Exception:
            pass

    def _set_monarch_quarry(self, shalaxi_unit, enemy_unit_root):
        # Store all members of the attached unit (reflecting persisting effects on split)
        ids = set()
        try:
            members = list(enemy_unit_root.get_attached_unit_members() or [])
        except Exception:
            members = [enemy_unit_root]
        for m in members:
            try:
                mid = getattr(m, "_id", None)
                if mid:
                    ids.add(mid)
            except Exception:
                continue
        setattr(shalaxi_unit, "_monarch_of_the_hunt_quarry_ids", ids)
        try:
            setattr(shalaxi_unit, "_monarch_of_the_hunt_quarry_name", str(getattr(enemy_unit_root, "name", "")))
        except Exception:
            pass

    def _on_unit_destroyed_for_monarch_of_the_hunt(self, unit=None, **_kwargs):
        """
        When a quarry is destroyed, immediately prompt Shalaxi to select a new quarry.

        Persisting effects:
        - If quarry was an attached unit that later splits, the designation persists on the survivor.
        - We track this by storing IDs of all attached members, then pruning to the alive subset.
        """
        if unit is None:
            return

        try:
            destroyed_owner = unit.get_parent_army().player
        except Exception:
            destroyed_owner = None

        # For each potential Shalaxi unit in the *opponent* armies, prune and repick if needed.
        for p in list(getattr(self.game, "players", []) or []):
            try:
                army = p.get_army()
            except Exception:
                army = None
            if army is None:
                continue
            for shalaxi_unit in list(getattr(army, "units", []) or []):
                quarry_ids = getattr(shalaxi_unit, "_monarch_of_the_hunt_quarry_ids", None)
                if not quarry_ids:
                    continue
                # Only if this destroyed unit is part of the quarry group
                try:
                    if getattr(unit, "_id", None) not in quarry_ids:
                        continue
                except Exception:
                    continue

                # Quarry must be an enemy unit, not friendly
                try:
                    if destroyed_owner is not None and destroyed_owner is shalaxi_unit.get_parent_army().player:
                        continue
                except Exception:
                    pass

                # Prune quarry ids to the alive subset (supports attached-unit split persistence)
                alive_ids = set()
                enemy_army = None
                try:
                    enemy_army = destroyed_owner.get_army() if destroyed_owner is not None else None
                except Exception:
                    enemy_army = None
                if enemy_army is not None:
                    by_id = {getattr(u2, "_id", None): u2 for u2 in list(getattr(enemy_army, "units", []) or [])}
                    for qid in list(quarry_ids):
                        u2 = by_id.get(qid)
                        if u2 is None:
                            continue
                        try:
                            if u2.is_alive():
                                alive_ids.add(qid)
                        except Exception:
                            continue
                setattr(shalaxi_unit, "_monarch_of_the_hunt_quarry_ids", alive_ids)

                # If none alive, repick
                if not alive_ids:
                    # Queue prompt for this Shalaxi
                    self._pending_quarry_queue.append((shalaxi_unit.get_parent_army().player, shalaxi_unit))
                    self._open_next_quarry_prompt()

    def _open_next_blessings_prompt(self, battle_round: int) -> None:
        if not self._pending_blessings_queue:
            return
        player = self._pending_blessings_queue.pop(0)
        army = player.get_army()
        mgr = getattr(army, "blessings_of_khorne", None)
        if mgr is None:
            self._open_next_blessings_prompt(battle_round)
            return
        if self.blessings_of_khorne_dialog is None:
            try:
                from .dialogs import BlessingsOfKhorneDialog
                sw, sh = self.screen.get_size()
                self.blessings_of_khorne_dialog = BlessingsOfKhorneDialog(sw, sh)
            except Exception:
                self.blessings_of_khorne_dialog = None
        if self.blessings_of_khorne_dialog is None:
            self._open_next_blessings_prompt(battle_round)
            return

        # Favoured of Khorne rerolls (unique enhancement; bearer must be on battlefield)
        rerolls_allowed = 0
        try:
            for u in list(getattr(army, "units", []) or []):
                enh = getattr(u, "enhancement", None)
                if enh is not None and str(getattr(enh, "name", "")).strip().lower() == "favoured of khorne":
                    if getattr(u, "deployed", False) and u.is_alive() and getattr(u, "reserve_status", "deployed") == "deployed":
                        rerolls_allowed = 2
                        break
        except Exception:
            rerolls_allowed = 0

        # Idol of the Blessed Blood (+1D6 per such model on battlefield) - start-of-battle-round only.
        idol_bonus = 0
        try:
            for u in list(getattr(army, "units", []) or []):
                if not (getattr(u, "deployed", False) and u.is_alive() and getattr(u, "reserve_status", "deployed") == "deployed"):
                    continue
                found, _ = u._find_ability_with_patterns(["idol of the blessed blood"])
                if found:
                    idol_bonus += 1
        except Exception:
            idol_bonus = 0

        # Reborn in Blood availability (Angron destroyed at start of battle round)
        reborn_available = False
        try:
            for u in list(getattr(army, "units", []) or []):
                found, _ = u._find_ability_with_patterns(["reborn in blood"])
                if found and (not u.is_alive()):
                    reborn_available = True
                    break
        except Exception:
            reborn_available = False

        from ..classes.blessings_of_khorne import BlessingsTiming
        ctx = mgr.create_roll_context(
            battle_round=int(battle_round),
            timing=BlessingsTiming.START_OF_BATTLE_ROUND,
            extra_dice_from_idols=idol_bonus,
            rerolls_allowed=rerolls_allowed,
            max_activations=2,
            counts_toward_baseline_limit=True,
            already_active_keys=set(),
            reborn_in_blood_available=reborn_available,
        )

        def _on_confirm(payload):
            try:
                res = payload.get("result") or {}
                if res.get("reborn_used", False):
                    army.schedule_reborn_in_blood(game=self.game)
            except Exception:
                pass
            # Continue prompting any other human WE player
            self._open_next_blessings_prompt(battle_round)

        self.blessings_of_khorne_dialog.show(player=player, game=self.game, army=army, ctx=ctx, on_confirm=_on_confirm)
        try:
            self.dialog_manager.open(self.blessings_of_khorne_dialog, modal=True)
        except Exception:
            pass

    def _precision_allocation_provider(self, attacker_model, target_unit, character_models, weapon_profile):
        """
        Blocking modal prompt for PRECISION allocation.
        Returns: selected CHARACTER model to allocate to, or None to allocate normally to bodyguard.
        """
        try:
            from .dialogs import PrecisionAllocationDialog
        except Exception:
            return None

        # Create (or reuse) dialog instance
        if not hasattr(self, "precision_allocation_dialog") or self.precision_allocation_dialog is None:
            self.precision_allocation_dialog = PrecisionAllocationDialog(self.screen.get_width(), self.screen.get_height())

        dlg = self.precision_allocation_dialog
        choice_holder = {"choice": None, "done": False}

        def _on_choice(chosen):
            choice_holder["choice"] = chosen
            choice_holder["done"] = True

        # Weapon label
        try:
            wname = getattr(getattr(weapon_profile, "parent_wargear", None), "name", None) or getattr(weapon_profile, "name", "Weapon")
        except Exception:
            wname = "Weapon"

        dlg.show(attacker_model, target_unit, wname, list(character_models or []), on_choice=_on_choice)
        try:
            self.dialog_manager.open(dlg, modal=True)
        except Exception:
            pass

        # Block until choice is made (or ESC closes dialog -> defaults to bodyguard)
        clock = pygame.time.Clock()
        while dlg.visible and not choice_holder["done"]:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return None
                # Route only through dialog manager (modal)
                try:
                    self.dialog_manager.handle_event(event)
                except Exception:
                    pass
            try:
                self.draw()
            except Exception:
                try:
                    dlg.draw(self.screen)
                    pygame.display.update()
                except Exception:
                    pass
            clock.tick(60)

        return choice_holder["choice"]

    def _damage_allocation_provider(self, target_unit, eligible_models, ctx):
        """
        Blocking modal prompt for defender damage allocation.
        Returns: selected model, or None to fall back to deterministic engine choice.
        """
        try:
            from .dialogs import DamageAllocationDialog
        except Exception:
            return None

        if not hasattr(self, "damage_allocation_dialog") or self.damage_allocation_dialog is None:
            self.damage_allocation_dialog = DamageAllocationDialog(self.screen.get_width(), self.screen.get_height())

        dlg = self.damage_allocation_dialog
        choice_holder = {"choice": None, "done": False}

        def _on_choice(chosen):
            choice_holder["choice"] = chosen
            choice_holder["done"] = True

        reason = ""
        try:
            reason = (ctx or {}).get("reason", "") or "Allocate Damage"
        except Exception:
            reason = "Allocate Damage"
        weapon = ""
        attacker = ""
        try:
            weapon = (ctx or {}).get("weapon_name", "") or ""
            attacker = (ctx or {}).get("attacker_name", "") or ""
        except Exception:
            pass
        subtitle = getattr(target_unit, "name", "Unit")
        if weapon and attacker:
            subtitle = f"{subtitle} (from {attacker} - {weapon})"
        instruction = "If a model is already wounded, you must continue allocating to a wounded eligible model."

        dlg.show(
            target_unit,
            list(eligible_models or []),
            title=reason,
            subtitle=subtitle,
            instruction=instruction,
            on_choice=_on_choice,
        )
        try:
            self.dialog_manager.open(dlg, modal=True)
        except Exception:
            pass

        clock = pygame.time.Clock()
        while dlg.visible and not choice_holder["done"]:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return None
                try:
                    self.dialog_manager.handle_event(event)
                except Exception:
                    pass
            try:
                self.draw()
            except Exception:
                try:
                    dlg.draw(self.screen)
                    pygame.display.update()
                except Exception:
                    pass
            clock.tick(60)

        return choice_holder["choice"]

    def _hazardous_allocation_provider(self, attacker_unit_root, eligible_models, ctx):
        """
        Blocking modal prompt for selecting the model that suffers a failed HAZARDOUS test.
        Returns: selected model, or None to fall back to deterministic engine choice.
        """
        try:
            from .dialogs import DamageAllocationDialog
        except Exception:
            return None

        if not hasattr(self, "damage_allocation_dialog") or self.damage_allocation_dialog is None:
            self.damage_allocation_dialog = DamageAllocationDialog(self.screen.get_width(), self.screen.get_height())

        dlg = self.damage_allocation_dialog
        choice_holder = {"choice": None, "done": False}

        def _on_choice(chosen):
            choice_holder["choice"] = chosen
            choice_holder["done"] = True

        subtitle = getattr(attacker_unit_root, "name", "Unit")
        instruction = "HAZARDOUS priority: wounded eligible model; otherwise non-Character; otherwise Character."
        title = "HAZARDOUS - Select Model"
        try:
            title = (ctx or {}).get("reason", "") or title
        except Exception:
            pass

        dlg.show(
            attacker_unit_root,
            list(eligible_models or []),
            title=title,
            subtitle=subtitle,
            instruction=instruction,
            on_choice=_on_choice,
        )
        try:
            self.dialog_manager.open(dlg, modal=True)
        except Exception:
            pass

        clock = pygame.time.Clock()
        while dlg.visible and not choice_holder["done"]:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return None
                try:
                    self.dialog_manager.handle_event(event)
                except Exception:
                    pass
            try:
                self.draw()
            except Exception:
                try:
                    dlg.draw(self.screen)
                    pygame.display.update()
                except Exception:
                    pass
            clock.tick(60)

        return choice_holder["choice"]

    def resize_layout(self, screen_width: int, screen_height: int) -> None:
        """Handle window resize: recompute pane sizes and positions based on new screen size."""
        # Recompute scaled dimensions
        scaled_roster_width = ROSTER_PANE_WIDTH
        scaled_stratagem_width = STRATAGEM_PANE_WIDTH
        scaled_info_height = INFO_PANE_HEIGHT
        scaled_battlefield_width = max(100, screen_width - 2 * (scaled_roster_width + scaled_stratagem_width))
        scaled_battlefield_height = max(100, screen_height - scaled_info_height)

        # Update stored dimensions
        self.scaled_roster_width = scaled_roster_width
        self.scaled_stratagem_width = scaled_stratagem_width
        self.scaled_battlefield_width = scaled_battlefield_width
        self.scaled_battlefield_height = scaled_battlefield_height
        self.scaled_info_height = scaled_info_height
        self.battlefield_left = scaled_stratagem_width + scaled_roster_width
        self.battlefield_right = self.battlefield_left + scaled_battlefield_width

        # Resize roster panes
        # Roster panes should not overlap the bottom logs pane; limit to battlefield height
        roster_pane_height = scaled_battlefield_height
        self.left_stratagem_pane.update_rect(0, 0, scaled_stratagem_width, roster_pane_height)
        self.right_stratagem_pane.update_rect(self.battlefield_right + scaled_roster_width, 0,
                                              scaled_stratagem_width, roster_pane_height)
        self.left_roster_pane.rect.update(scaled_stratagem_width, 0, scaled_roster_width, roster_pane_height)
        self.right_roster_pane.rect.update(self.battlefield_right, 0, scaled_roster_width, roster_pane_height)
        # After rect updates, recreate buttons and clamp scroll to fix misalignment
        if hasattr(self.left_roster_pane, 'create_buttons'):
            self.left_roster_pane.create_buttons()
        if hasattr(self.right_roster_pane, 'create_buttons'):
            self.right_roster_pane.create_buttons()

        # Resize info pane
        self.info_pane.rect.update(self.battlefield_left, scaled_battlefield_height,
                                   scaled_battlefield_width, scaled_info_height)

        # No UI scale factor; rendering uses only zoom and pan

        # Optionally clamp offsets to keep view in bounds
        self.offset_x = max(min(self.offset_x, scaled_battlefield_width), -scaled_battlefield_width)
        self.offset_y = max(min(self.offset_y, scaled_battlefield_height), -scaled_battlefield_height)
    
    def refresh_roster_panes(self):
        """Refresh roster panes when armies are loaded during setup phases."""
        if self.player1 and self.player2:
            player1_units = self.player1.get_army().units if self.player1.get_army() else []
            player2_units = self.player2.get_army().units if self.player2.get_army() else []

            # Collapse attached Leaders into their bodyguard unit in roster panes:
            # hide leader units that have `attached_to` set.
            def _visible_roster(units):
                visible = []
                for u in list(units or []):
                    try:
                        if bool(getattr(u, "is_leader", False)) and getattr(u, "attached_to", None) is not None:
                            continue
                    except Exception:
                        pass
                    visible.append(u)
                return visible

            player1_units = _visible_roster(player1_units)
            player2_units = _visible_roster(player2_units)
            
            print(f"🔄 Refreshing roster panes: Player1 has {len(player1_units)} units, Player2 has {len(player2_units)} units")
            
            # Update roster units
            self.left_roster_pane.roster = player1_units
            self.right_roster_pane.roster = player2_units
            
            # Update player references
            self.left_roster_pane.player = self.player1
            self.right_roster_pane.player = self.player2
            self.left_stratagem_pane.player = self.player1
            self.right_stratagem_pane.player = self.player2
            self.left_stratagem_pane.player_name = f"Player 1 ({self.player1.name})"
            self.right_stratagem_pane.player_name = f"Player 2 ({self.player2.name})"
            
            # Update all_units for color correlation
            all_units = player1_units + player2_units
            self.left_roster_pane.all_units = all_units
            self.right_roster_pane.all_units = all_units
            
            # Reset scroll positions
            self.left_roster_pane.scroll_offset = 0
            self.right_roster_pane.scroll_offset = 0
            
            # Recreate buttons with new roster data
            self.left_roster_pane.create_buttons()
            self.right_roster_pane.create_buttons()
            
            print(f"✅ Roster panes refreshed successfully")

    def _draw_top_status_pane(self, pane_height_px: int) -> None:
        left = self.battlefield_left
        width = self.scaled_battlefield_width
        pygame.draw.rect(self.screen, (35, 35, 38), (left, 0, width, pane_height_px))
        pygame.draw.rect(self.screen, (63, 63, 70), (left, 0, width, pane_height_px), 2)
        # Clear stale mission/secondary hitboxes before rebuilding
        try:
            if hasattr(self, "_ui_hitboxes"):
                for key in list(self._ui_hitboxes.keys()):
                    if key == "primary" or str(key).startswith("sec_"):
                        self._ui_hitboxes.pop(key, None)
        except Exception:
            pass

        third = width // 3
        p1_rect = pygame.Rect(left, 0, third, pane_height_px)
        mid_rect = pygame.Rect(left + third, 0, third, pane_height_px)
        p2_rect = pygame.Rect(left + 2 * third, 0, third, pane_height_px)

        try:
            font = pygame.font.SysFont('Arial', 16, bold=True)
            small = pygame.font.SysFont('Arial', 14)
            status_font = pygame.font.SysFont('Arial', 18, bold=True)
        except Exception:
            font = pygame.font.Font(None, 16)
            small = pygame.font.Font(None, 14)
            status_font = pygame.font.Font(None, 18)

        def draw_box(rect: pygame.Rect, text: str, align: str = 'left', bg=(60,60,67)):
            pygame.draw.rect(self.screen, bg, rect)
            pygame.draw.rect(self.screen, (90,90,100), rect, 1)
            ts = font.render(text, True, (255,255,255))
            tr = ts.get_rect()
            if align == 'left':
                tr.topleft = (rect.x + 8, rect.y + rect.height//2 - ts.get_height()//2)
            elif align == 'right':
                tr.topright = (rect.right - 8, rect.y + rect.height//2 - ts.get_height()//2)
            else:
                tr.center = rect.center
            self.screen.blit(ts, tr)

        p1 = self.player1
        p2 = self.player2

        box_w = p1_rect.width // 6 - 6
        x0 = p1_rect.x + 6
        y0 = p1_rect.y + 6
        h = pane_height_px - 12
        draw_box(pygame.Rect(x0, y0, box_w, h), f"VP: {p1.score}")
        draw_box(pygame.Rect(x0 + box_w + 6, y0, box_w, h), f"CP: {p1.command_points}")
        sec_area_width = int((p1_rect.width - (2 * (box_w + 6)) - 12) * 0.95)
        self._draw_secondaries_buttons(pygame.Rect(x0 + 2*(box_w + 6), y0, sec_area_width, h), p1, align='left')

        # Move primary button 1" (TILE_SIZE px) further left
        primary_rect = pygame.Rect(mid_rect.x + 6 - int(1 * TILE_SIZE), y0, int(mid_rect.width * 0.45 * 0.9), h)
        self._draw_primary_button(primary_rect)
        if self.game.is_in_setup_phase():
            round_text = self.game.get_current_setup_phase().name.replace('_', ' ').title()
        else:
            round_text = f"Turn {self.game.turn} - {self.game.get_current_player().name} - {self.game.phase.name.replace('_',' ').title()}"
        st = status_font.render(round_text, True, (255, 140, 0))
        info_rect = pygame.Rect(primary_rect.right + 10, y0, mid_rect.right - (primary_rect.right + 18), h)
        sr = st.get_rect(center=info_rect.center)
        self.screen.blit(st, sr)

        box_w2 = p2_rect.width // 6 - 6
        y2 = p2_rect.y + 6
        h2 = h
        draw_box(pygame.Rect(p2_rect.right - box_w2 - 6, y2, box_w2, h2), f"VP: {p2.score}", align='right')
        draw_box(pygame.Rect(p2_rect.right - 2*(box_w2 + 6), y2, box_w2, h2), f"CP: {p2.command_points}", align='right')
        sec2_area_width = int((p2_rect.width - (2 * (box_w2 + 6)) - 12) * 0.95)
        # Position Player 2 secondaries area immediately to the left of the CP/VP boxes
        sec2_x = p2_rect.right - 2*(box_w2 + 6) - 6 - sec2_area_width
        self._draw_secondaries_buttons(pygame.Rect(sec2_x, y2, sec2_area_width, h2), p2, align='right')

    def _draw_primary_button(self, rect: pygame.Rect) -> None:
        pygame.draw.rect(self.screen, (60,60,67), rect)
        pygame.draw.rect(self.screen, (90,90,100), rect, 1)
        card = getattr(self.game.get_current_player(), 'primary_mission', None)
        label = card.name if card else 'Primary: None'
        try:
            font = pygame.font.SysFont('Arial', 16, bold=True)
        except Exception:
            font = pygame.font.Font(None, 16)
        ts = font.render(label, True, (255,255,255))
        tr = ts.get_rect(center=rect.center)
        self.screen.blit(ts, tr)
        # register for click detection
        if not hasattr(self, '_ui_hitboxes'):
            self._ui_hitboxes = {}
        self._ui_hitboxes['primary'] = (pygame.Rect(rect), card)

    def _draw_secondaries_buttons(self, rect: pygame.Rect, player, align: str = 'left') -> None:
        pygame.draw.rect(self.screen, (50,50,55), rect)
        pygame.draw.rect(self.screen, (90,90,100), rect, 1)
        try:
            font = pygame.font.SysFont('Arial', 14, bold=False)
        except Exception:
            font = pygame.font.Font(None, 14)
        actives = getattr(player, 'active_secondaries', []) or []
        btn_w = (rect.width - 12) // 2
        for i in range(2):
            sub = pygame.Rect(rect.x + 4 + i * (btn_w + 4), rect.y + 4, btn_w, rect.height - 8)
            name = actives[i].name if i < len(actives) else 'None'
            bg = (80,80,90) if i < len(actives) else (70,70,75)
            pygame.draw.rect(self.screen, bg, sub)
            pygame.draw.rect(self.screen, (100,100,110), sub, 1)
            ts = font.render(name, True, (230,230,230))
            tr = ts.get_rect(center=sub.center)
            self.screen.blit(ts, tr)
            if not hasattr(self, '_ui_hitboxes'):
                self._ui_hitboxes = {}
            self._ui_hitboxes[f"sec_{id(sub)}"] = (pygame.Rect(sub), actives[i] if i < len(actives) else None)

    def _draw_bottom_logs_pane(self) -> None:
        height = self.scaled_info_height
        y = self.scaled_battlefield_height
        left = 0
        width = self.screen.get_width()
        pygame.draw.rect(self.screen, (45,45,48), (left, y, width, height))
        pygame.draw.rect(self.screen, (63,63,70), (left, y, width, height), 2)

        # Layout: Stratagem - P1 Actions - P1 Dice - P2 Dice - P2 Actions - Stratagem
        strat_w = max(120, int(width * 0.10))
        remaining = max(0, width - (strat_w * 2))
        box_w = remaining // 4

        x_cursor = left
        strat_left_rect = pygame.Rect(x_cursor, y, strat_w, height)
        x_cursor += strat_w
        boxes = [
            pygame.Rect(x_cursor + i * box_w, y, box_w, height) for i in range(4)
        ]
        x_cursor += box_w * 4
        strat_right_rect = pygame.Rect(x_cursor, y, width - x_cursor, height)  # Fill to end

        p1_name = self.player1.name
        p2_name = self.player2.name
        p1_actions = get_recent_actions(p1_name, limit=50)
        p1_dice = get_recent_dice(p1_name, limit=50)
        p2_actions = get_recent_actions(p2_name, limit=50)
        p2_dice = get_recent_dice(p2_name, limit=50)

        # Draw left/right Stratagem buttons
        self._draw_stratagem_button(strat_left_rect, self.player1)
        self._draw_stratagem_button(strat_right_rect, self.player2)

        # Save hitboxes for click handling
        if not hasattr(self, '_ui_hitboxes'):
            self._ui_hitboxes = {}
        self._ui_hitboxes['strat_p1'] = (pygame.Rect(strat_left_rect), self.player1)
        self._ui_hitboxes['strat_p2'] = (pygame.Rect(strat_right_rect), self.player2)

        # Initialize bottom log scroll state and hitboxes
        if not hasattr(self, '_bottom_log_scroll'):
            self._bottom_log_scroll = {
                'p1_actions': 0,
                'p1_dice': 0,
                'p2_dice': 0,
                'p2_actions': 0,
            }
        self._bottom_log_boxes = {
            'p1_actions': boxes[0],
            'p1_dice': boxes[1],
            'p2_dice': boxes[2],
            'p2_actions': boxes[3],
        }

        # Draw the four log boxes with wrapping and scroll support
        self._draw_scroll_text_box(boxes[0], p1_actions, key='p1_actions', title=f"{p1_name} Actions")
        self._draw_scroll_text_box(boxes[1], p1_dice, key='p1_dice', title=f"{p1_name} Dice")
        self._draw_scroll_text_box(boxes[2], p2_dice, key='p2_dice', title=f"{p2_name} Dice")
        self._draw_scroll_text_box(boxes[3], p2_actions, key='p2_actions', title=f"{p2_name} Actions")

    def _draw_stratagem_panes(self) -> None:
        if not hasattr(self, '_ui_hitboxes'):
            self._ui_hitboxes = {}
        # Clear old stratagem item hitboxes
        for key in list(self._ui_hitboxes.keys()):
            if str(key).startswith("strat_item_"):
                self._ui_hitboxes.pop(key, None)

        panes = [
            ("p1", self.player1, self.left_stratagem_pane),
            ("p2", self.player2, self.right_stratagem_pane),
        ]
        for prefix, player, pane in panes:
            if pane is None or player is None:
                continue
            mgr = getattr(player, "stratagems", None)
            items = []
            try:
                if mgr is not None:
                    items = mgr.get_phase_stratagem_items() or []
            except Exception:
                items = []
            for item in items:
                try:
                    item["owner"] = player
                except Exception:
                    pass
            pane.set_items(items)
            pane.draw(self.screen, hitboxes=self._ui_hitboxes, key_prefix=prefix)

    def _draw_stratagem_button(self, rect: pygame.Rect, player) -> None:
        in_setup = False
        try:
            if hasattr(self.game, "is_in_setup_phase") and callable(self.game.is_in_setup_phase):
                in_setup = bool(self.game.is_in_setup_phase())
            else:
                in_setup = not bool(getattr(self.game, "setup_complete", True))
        except Exception:
            in_setup = False

        pane = self._stratagem_panes.get(player)
        is_open = bool(getattr(pane, "is_open", False)) if pane else False

        bg = (60, 60, 67) if not is_open else (100, 149, 237)
        fg = (255, 255, 255)
        pygame.draw.rect(self.screen, bg, rect)
        pygame.draw.rect(self.screen, (63,63,70), rect, 1)
        try:
            title_font = pygame.font.SysFont('Arial', 16, bold=True)
            sub_font = pygame.font.SysFont('Arial', 14, bold=False)
        except Exception:
            title_font = pygame.font.Font(None, 16)
            sub_font = pygame.font.Font(None, 14)

        # Two-line label: "Player 1/2" on first line, "Stratagem" (with count) on second line
        if player is self.player1:
            player_label = "Player 1"
        elif player is self.player2:
            player_label = "Player 2"
        else:
            player_label = getattr(player, 'name', 'Player')

        strat_label = "Stratagems"
        if in_setup:
            strat_label = "Stratagems (Setup)"

        ts1 = title_font.render(strat_label, True, fg)
        ts2 = sub_font.render(player_label, True, fg)

        # Center both lines vertically within the rect
        total_h = ts1.get_height() + ts2.get_height() + 2
        start_y = rect.y + (rect.height - total_h) // 2

        tr1 = ts1.get_rect(centerx=rect.centerx)
        tr1.y = start_y
        tr2 = ts2.get_rect(centerx=rect.centerx)
        tr2.y = tr1.bottom + 2

        self.screen.blit(ts1, tr1)
        self.screen.blit(ts2, tr2)

    def _draw_scroll_text_box(self, rect: pygame.Rect, lines, key: str, title: str = "Logs") -> None:
        pygame.draw.rect(self.screen, (40,40,44), rect)
        pygame.draw.rect(self.screen, (70,70,78), rect, 1)
        try:
            msg_font = pygame.font.SysFont('Consolas', 12)
            title_font = pygame.font.SysFont('Arial', 14, bold=True)
        except Exception:
            msg_font = pygame.font.Font(None, 12)
            title_font = pygame.font.Font(None, 14)
        # Title
        ts = title_font.render(title, True, (220,220,230))
        self.screen.blit(ts, (rect.x + 6, rect.y + 4))

        # Word-wrap all lines into wrapped_lines list
        content_left = rect.x + 6
        content_top = rect.y + 24
        content_width = rect.width - 12
        content_height = rect.height - (content_top - rect.y) - 6

        def wrap_text(text: str) -> list:
            words = text.split(' ')
            wrapped = []
            line = ''
            for w in words:
                test = (line + ' ' + w).strip()
                surf = msg_font.render(test, True, (0,0,0))
                if surf.get_width() > content_width and line:
                    wrapped.append(line)
                    line = w
                else:
                    line = test
            if line:
                wrapped.append(line)
            return wrapped

        wrapped_lines = []
        for ln in lines:
            wrapped_lines.extend(wrap_text(str(ln)))

        # Determine how many wrapped lines fit and apply scroll offset (from bottom)
        line_height = msg_font.get_height() + 2
        max_visible = max(0, content_height // line_height)
        offset = int(self._bottom_log_scroll.get(key, 0) or 0)
        start_index = max(0, len(wrapped_lines) - max_visible - offset)
        end_index = len(wrapped_lines) - offset if offset > 0 else len(wrapped_lines)
        to_show = wrapped_lines[start_index:end_index]

        # Draw from bottom up for consistent feel with logs
        y_cursor = rect.y + rect.height - 6
        for line in reversed(to_show):
            surf = msg_font.render(line, True, (200,200,200))
            y_cursor -= line_height
            if y_cursor < content_top:
                break
            self.screen.blit(surf, (content_left, y_cursor))

    def _slugify_mission_card_name(self, name: str) -> str:
        """
        Convert a mission card name into the expected PNG suffix used under RuleSets mission_cards.
        Examples:
          "Take and Hold" -> "take_and_hold"
          "Purge the Foe" -> "purge_the_foe"
        """
        s = (name or "").strip().lower()
        # Replace common separators with underscores, drop other punctuation.
        s = re.sub(r"[\s\-]+", "_", s)
        s = re.sub(r"[^a-z0-9_]+", "", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return s

    def _get_mission_cards_dir(self) -> Path:
        """
        Locate the repo's Chapter Approved 2025/2026 mission card images directory.
        Prefer repo-relative to this source file, but fall back to CWD if needed.
        """
        # src/warhammer40k_ai/UI/game_ui.py -> repo root is parents[3]
        try:
            repo_root = Path(__file__).resolve().parents[3]
        except Exception:
            repo_root = Path.cwd()
        p = repo_root / "RuleSets" / "ChapterApproved_2025_2026" / "mission_cards"
        if p.exists():
            return p
        # Fallback: when running from a different CWD
        p2 = Path.cwd() / "RuleSets" / "ChapterApproved_2025_2026" / "mission_cards"
        return p2

    def _find_mission_card_image_path(self, card, is_primary: bool) -> Optional[str]:
        """
        Returns a filesystem path to a PNG image for the given card if present, else None.
        File naming convention:
          primary_<slug>.png
          secondary_<slug>.png
        """
        if card is None:
            return None
        name = getattr(card, "name", None) or "mission"
        slug = self._slugify_mission_card_name(str(name))
        prefix = "primary" if is_primary else "secondary"
        cache_key = f"{prefix}:{slug}"
        if cache_key in self._mission_image_path_cache:
            return self._mission_image_path_cache[cache_key]

        cards_dir = self._get_mission_cards_dir()
        candidate = cards_dir / f"{prefix}_{slug}.png"
        path_str = str(candidate) if candidate.exists() else None
        self._mission_image_path_cache[cache_key] = path_str
        return path_str

    def _load_image_surface_cached(self, image_path: str) -> Optional[pygame.Surface]:
        if not image_path:
            return None
        if image_path in self._mission_image_surface_cache:
            return self._mission_image_surface_cache[image_path]
        # pygame.image.load can raise if file is missing/corrupt; let caller handle fallback.
        surf = pygame.image.load(image_path).convert_alpha()
        self._mission_image_surface_cache[image_path] = surf
        return surf

    def _draw_mission_popup_overlay(self, title: str, body: str, image_path: Optional[str] = None) -> None:
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        # Slightly larger to fit mission card images comfortably.
        width = int(self.screen.get_width() * 0.62)
        height = int(self.screen.get_height() * 0.78)
        rect = pygame.Rect(0, 0, width, height)
        rect.center = (self.screen.get_width() // 2, self.screen.get_height() // 2)
        pygame.draw.rect(self.screen, (35,35,38), rect)
        pygame.draw.rect(self.screen, (90,90,100), rect, 2)
        try:
            title_font = pygame.font.SysFont('Arial', 18, bold=True)
            body_font = pygame.font.SysFont('Arial', 16)
            hint_font = pygame.font.SysFont('Arial', 14)
        except Exception:
            title_font = pygame.font.Font(None, 18)
            body_font = pygame.font.Font(None, 16)
            hint_font = pygame.font.Font(None, 14)
        ts = title_font.render(title, True, (255,255,255))
        tr = ts.get_rect(center=(rect.centerx, rect.y + 28))
        self.screen.blit(ts, tr)

        # Content area (below title; above hint)
        content_rect = pygame.Rect(rect.x + 16, rect.y + 56, rect.width - 32, rect.height - 56 - 36)

        # If an image is available, show it instead of text.
        if image_path:
            try:
                img = self._load_image_surface_cached(image_path)
                if img is not None:
                    iw, ih = img.get_width(), img.get_height()
                    if iw > 0 and ih > 0:
                        scale = min(content_rect.width / iw, content_rect.height / ih)
                        new_w = max(1, int(iw * scale))
                        new_h = max(1, int(ih * scale))
                        scaled = pygame.transform.smoothscale(img, (new_w, new_h))
                        dest = scaled.get_rect(center=content_rect.center)
                        self.screen.blit(scaled, dest)
                        hint = hint_font.render("Click anywhere to close", True, (180, 180, 180))
                        self.screen.blit(hint, (rect.x + 16, rect.bottom - 28))
                        return
            except Exception:
                # Fall back to text rendering below.
                pass

        # Fallback: simple wrapped text
        x = content_rect.x
        y = content_rect.y
        max_w = content_rect.width
        line = ''
        for word in (body or '').split(' '):
            test = (line + ' ' + word).strip()
            surf = body_font.render(test, True, (220,220,220))
            if surf.get_width() > max_w and line:
                ls = body_font.render(line, True, (220,220,220))
                self.screen.blit(ls, (x, y))
                y += ls.get_height() + 4
                line = word
            else:
                line = test
        if line:
            ls = body_font.render(line, True, (220,220,220))
            self.screen.blit(ls, (x, y))
        hint = hint_font.render("Click anywhere to close", True, (180, 180, 180))
        self.screen.blit(hint, (rect.x + 16, rect.bottom - 28))
    
    def update_roster_pane_titles(self):
        """Update roster pane titles to show Attacker/Defender after roles are determined."""
        if self.game and hasattr(self.game, 'attacker_index') and self.game.attacker_index is not None:
            # Update player names to include role
            if self.game.attacker_index == 0:  # Player 1 is attacker
                self.left_roster_pane.player_name = f"{self.player1.name} (Attacker)"
                self.right_roster_pane.player_name = f"{self.player2.name} (Defender)"
                self.left_stratagem_pane.player_name = f"Player 1 ({self.player1.name})"
                self.right_stratagem_pane.player_name = f"Player 2 ({self.player2.name})"
            else:  # Player 2 is attacker
                self.left_roster_pane.player_name = f"{self.player1.name} (Defender)"
                self.right_roster_pane.player_name = f"{self.player2.name} (Attacker)"
                self.left_stratagem_pane.player_name = f"Player 1 ({self.player1.name})"
                self.right_stratagem_pane.player_name = f"Player 2 ({self.player2.name})"

    def handle_pygame_event(self, event):
        """Handle pygame events using phase-based routing."""
        # Debug: Log all events received by GameView
        # TODO: Uncomment for event debugging
        # if event.type in [pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION]:
        #     event_name = {
        #         pygame.KEYDOWN: "KEYDOWN",
        #         pygame.MOUSEBUTTONDOWN: "MOUSEBUTTONDOWN",
        #         pygame.MOUSEBUTTONUP: "MOUSEBUTTONUP",
        #         pygame.MOUSEMOTION: "MOUSEMOTION"
        #     }.get(event.type, f"TYPE_{event.type}")
        #
        #     if event.type == pygame.KEYDOWN:
        #         print(f"🔍 DEBUG: GameView.handle_pygame_event - {event_name}: key={pygame.key.name(event.key)}")
        #     elif event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP]:
        #         print(f"🔍 DEBUG: GameView.handle_pygame_event - {event_name}: button={event.button}, pos={event.pos}")
        #     elif event.type == pygame.MOUSEMOTION:
        #         # Only log mouse motion occasionally to avoid spam
        #         if hasattr(self, '_last_motion_log') and pygame.time.get_ticks() - self._last_motion_log < 100:
        #             pass  # Skip logging
        #         else:
        #             print(f"🔍 DEBUG: GameView.handle_pygame_event - {event_name}: pos={event.pos}")
        #             self._last_motion_log = pygame.time.get_ticks()

        # PRIORITY 0: Handle unit detail panel escape key
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.detailed_unit and hasattr(self.unit_detail_panel, 'handle_event') and hasattr(self.unit_detail_panel, 'visible') and self.unit_detail_panel.visible:
                # print(f"🔍 DEBUG: GameView - Delegating ESC to unit detail panel")
                if self.unit_detail_panel.handle_event(event):
                    self.close_unit_details()
                    return True

        # PRIORITY 1: Top pane and overlay handling BEFORE phase-specific handlers
        if event.type == pygame.MOUSEBUTTONDOWN:
            # Mission popup overlay closes on any click
            if getattr(self, '_mission_popup', None):
                self._mission_popup = None
                return True
            # Intercept clicks in the top status pane so they don't fall through
            if True:
                left = self.battlefield_left
                width = self.scaled_battlefield_width
                top_rect = pygame.Rect(left, 0, width, self.top_pane_height_px)
                if top_rect.collidepoint(event.pos):
                    # If clicking on mission buttons (primary/secondaries), open popup
                    if self._ui_hitboxes:
                        for key, (rect, card) in list(self._ui_hitboxes.items()):
                            if key != 'primary' and not str(key).startswith('sec_'):
                                continue
                            if rect.collidepoint(event.pos) and card is not None:
                                title = getattr(card, 'name', 'Mission')
                                body = getattr(card, 'description', '')
                                image_path = self._find_mission_card_image_path(card, is_primary=(key == 'primary'))
                                self._mission_popup = {'title': title, 'body': body, 'image_path': image_path}
                                return True
                    # Otherwise consume the click within top pane
                    return True

            # Handle stratagem pane item clicks
            if self._ui_hitboxes:
                for key, payload in list(self._ui_hitboxes.items()):
                    if not str(key).startswith("strat_item_"):
                        continue
                    rect, item = payload
                    if rect.collidepoint(event.pos):
                        owner = item.get("owner")
                        if owner is None:
                            return True
                        if item.get("available"):
                            self._attempt_use_stratagem(owner, item)
                        return True

            # Consume clicks inside stratagem panes to avoid map interactions
            try:
                if self.left_stratagem_pane and self.left_stratagem_pane.rect.collidepoint(event.pos):
                    return True
                if self.right_stratagem_pane and self.right_stratagem_pane.rect.collidepoint(event.pos):
                    return True
            except Exception:
                pass

            # Handle bottom stratagem button clicks (collapse/expand)
            if self._ui_hitboxes:
                for key in ('strat_p1', 'strat_p2'):
                    if key in self._ui_hitboxes:
                        rect, player = self._ui_hitboxes[key]
                        if rect.collidepoint(event.pos):
                            try:
                                in_setup = False
                                if hasattr(self.game, "is_in_setup_phase") and callable(self.game.is_in_setup_phase):
                                    in_setup = bool(self.game.is_in_setup_phase())
                                else:
                                    in_setup = not bool(getattr(self.game, "setup_complete", True))
                                if in_setup:
                                    return True
                            except Exception:
                                pass
                            pane = self._stratagem_panes.get(player)
                            if pane is not None:
                                pane.toggle()
                            return True

        # PRIORITY 2: Let phase manager handle phase-specific events next
        # print(f"🔍 DEBUG: GameView - Delegating to phase manager")
        if self.phase_manager.handle_event(event):
            # print(f"🔍 DEBUG: GameView - Event was handled by phase manager")
            return True
        else:
            # print(f"🔍 DEBUG: GameView - Event was not handled by phase manager")
            pass
        
        # PRIORITY 3: Handle universal UI events that apply to all phases
        if event.type == pygame.MOUSEBUTTONDOWN:
            # Check for unit detail panel clicks (highest priority)
            if self.detailed_unit and event.button == 1:  # Left click
                if hasattr(self.unit_detail_panel, 'rect') and self.unit_detail_panel.rect:
                    if self.unit_detail_panel.rect.collidepoint(event.pos):
                        return True  # Consume the click on detail panel
                    else:
                        self.close_unit_details()
                        return True
            # Check for middle mouse button panning
            elif event.button == 2:  # Middle mouse button - start panning
                x, y = event.pos
                if self.battlefield_left < x < self.battlefield_right:
                    self.panning = True
                    self.pan_start_pos = (x, y)
                    self.pan_start_offset = (self.offset_x, self.offset_y)
                    return True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.on_mouse_release(event.pos[0], event.pos[1], event.button)
        elif event.type == pygame.MOUSEMOTION:
            self.on_mouse_motion(event.pos[0], event.pos[1])
        elif event.type == pygame.MOUSEWHEEL:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            self.on_mouse_scroll(mouse_x, mouse_y, event.y)
        elif event.type == pygame.KEYDOWN:
            # Close mission popup with ESC
            if event.key == pygame.K_ESCAPE and getattr(self, '_mission_popup', None):
                self._mission_popup = None
                return True
            # Handle unit detail panel scrolling
            if self.detailed_unit:
                if event.key == pygame.K_UP or event.key == pygame.K_w:
                    self.unit_detail_panel.scroll(-30)  # Scroll up
                    return True
                elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                    self.unit_detail_panel.scroll(30)   # Scroll down
                    return True
                elif event.key == pygame.K_PAGEUP:
                    self.unit_detail_panel.scroll(-150)  # Page up
                    return True
                elif event.key == pygame.K_PAGEDOWN:
                    self.unit_detail_panel.scroll(150)   # Page down
                    return True
                elif event.key == pygame.K_HOME:
                    self.unit_detail_panel.scroll_offset = 0  # Go to top
                    return True
                elif event.key == pygame.K_END:
                    self.unit_detail_panel.scroll_offset = self.unit_detail_panel.max_scroll  # Go to bottom
                    return True
        
        return False

    # -------- Stratagem pane helpers --------
    def _attempt_use_stratagem(self, player, item: Dict[str, Any]) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        name = item.get("name")
        if not name:
            return

        context = dict(item.get("context", {}) or {})
        if item.get("is_reaction"):
            context["dequeue"] = True
        if "phase_name" not in context:
            phase_name = getattr(manager, "_current_phase_name", None)
            if phase_name:
                context["phase_name"] = phase_name

        name_u = str(name).strip().upper()
        if name_u == "NEW ORDERS" and "secondary_card" not in context:
            if callable(getattr(self, "_request_secondary_discard", None)):
                self._request_secondary_discard(player, self.game, lambda chosen: self._finalize_new_orders(player, name, context, chosen))
            return

        if name_u in ("FIRE OVERWATCH", "OVERWATCH") and "shooter_unit" not in context:
            if callable(getattr(self, "_request_overwatch_shooter", None)):
                enemy = context.get("enemy_unit")
                self._request_overwatch_shooter(player, self.game, enemy, lambda shooter: self._finalize_overwatch(player, name, context, shooter))
            return

        if name_u == "RAPID INGRESS" and "unit" not in context and "target_unit" not in context:
            if callable(getattr(self, "_request_rapid_ingress_unit", None)):
                candidates = context.get("candidates") or []
                self._request_rapid_ingress_unit(player, self.game, candidates, lambda unit: self._finalize_rapid_ingress(player, name, context, unit))
            return

        if name_u == "COUNTER-OFFENSIVE" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_counter_offensive_unit", None)):
                candidates = context.get("candidates") or []
                self._request_counter_offensive_unit(player, self.game, candidates, lambda unit: self._finalize_counter_offensive(player, name, context, unit))
            return

        if name_u == "SKULLS FOR THE SKULL THRONE!" and "attacker_unit" in context:
            if callable(getattr(self, "_request_blessings_roll", None)):
                if self._blessings_flow_active:
                    return
                self._blessings_flow_active = True

                def _done(executed: bool):
                    self._blessings_flow_active = False
                    if executed:
                        print(f"Used stratagem: {name}")
                    else:
                        print("Skulls for the Skull Throne cancelled or failed")

                self._request_blessings_roll(player, self.game, context, _done)
            return

        if callable(getattr(self, "_request_yes_no", None)):
            try:
                target_unit = context.get("target_unit", None)
                strat = manager.get_by_name(str(name)) if manager else None
                if strat is not None and target_unit is not None:
                    prev = player.preview_stratagem_cp_cost(strat, target_unit=target_unit, assume_optional_discounts=True)
                    if int(prev.get("discount", 0) or 0) >= 1:
                        if self._optional_flow_active:
                            return
                        self._optional_flow_active = True
                        base = int(prev.get("base", getattr(strat, "cp_cost", 0) or 0) or 0)
                        msg = f"Use Direct the Slaughter to reduce CP cost by 1?\n\n{str(name)}: {base}CP -> {max(0, base-1)}CP"

                        def _done(chosen: bool):
                            self._optional_flow_active = False
                            try:
                                player.set_next_optional_decision("DIRECT_THE_SLAUGHTER", bool(chosen))
                            except Exception:
                                pass
                            ok2 = manager.use(name, **context)
                            if ok2:
                                print(f"Used stratagem: {name}")
                            else:
                                print(f"Could not use stratagem: {name}")

                        self._request_yes_no("Direct the Slaughter", msg, "Use", "Skip", _done)
                        return
            except Exception:
                pass

        ok = manager.use(name, **context)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_new_orders(self, player, name: str, context: Dict[str, Any], selected_card) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        ctx = dict(context)
        ctx["secondary_card"] = selected_card
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_overwatch(self, player, name: str, context: Dict[str, Any], shooter_unit) -> None:
        if self._overwatch_flow_active:
            return
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        if shooter_unit is None:
            print("Overwatch: no shooter selected")
            return
        ctx = dict(context)
        ctx["shooter_unit"] = shooter_unit
        if "phase_name" not in ctx:
            phase_name = getattr(manager, "_current_phase_name", None)
            if phase_name:
                ctx["phase_name"] = phase_name
        enemy = ctx.get("enemy_unit")
        if callable(getattr(self, "_request_overwatch_shooting", None)):
            try:
                setattr(shooter_unit, "_overwatch_sixes_only", True)
            except Exception:
                pass
            self._overwatch_flow_active = True

            def _done_callback(executed: bool):
                try:
                    delattr(shooter_unit, "_overwatch_sixes_only")
                except Exception:
                    pass
                self._overwatch_flow_active = False
                if executed:
                    s = manager.get_by_name(str(name)) if manager else None
                    if s and player.spend_command_points(s.cp_cost):
                        manager._used_this_turn["OVERWATCH"] = True
                        if ctx.get("dequeue") is True and hasattr(manager, "_dequeue_reaction_by_name"):
                            manager._dequeue_reaction_by_name(s.name)
                        print(f"Used stratagem: {name}")
                    else:
                        print("Overwatch: failed to spend CP")
                else:
                    print("Overwatch cancelled or failed")

            self._request_overwatch_shooting(shooter_unit, enemy, _done_callback)
            return

        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_rapid_ingress(self, player, name: str, context: Dict[str, Any], unit) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        ctx = dict(context)
        ctx["unit"] = unit
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_counter_offensive(self, player, name: str, context: Dict[str, Any], unit) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        ctx = dict(context)
        ctx["target_unit"] = unit
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    # Note: on_mouse_press is now handled by phase-specific handlers in PhaseManager

    def on_mouse_release(self, x, y, button):
        """Handle mouse button release events"""
        if button == 2:  # Middle mouse button - stop panning
            self.panning = False

    def on_mouse_motion(self, x, y):
        """Handle mouse motion events"""
        if self.panning:
            # Calculate pan delta
            dx = x - self.pan_start_pos[0]
            dy = y - self.pan_start_pos[1]
            
            # Apply panning with sensitivity adjustment
            self.offset_x = self.pan_start_offset[0] + dx * MOUSE_PAN_SPEED
            self.offset_y = self.pan_start_offset[1] + dy * MOUSE_PAN_SPEED
            
            # Apply panning limits
            self.offset_x, self.offset_y = self._apply_pan_limits(self.offset_x, self.offset_y)
        
        # Update hover state for info pane
        self.info_pane.update_hover(x, y)

    def on_mouse_scroll(self, x, y, scroll_y):
        """Handle mouse scroll events"""
        # PRIORITY 0.5: Bottom logs scroll (before other panes if mouse over the boxes)
        try:
            if hasattr(self, '_bottom_log_boxes') and hasattr(self, '_bottom_log_scroll'):
                for key, rect in self._bottom_log_boxes.items():
                    if rect.collidepoint(x, y):
                        self._bottom_log_scroll[key] = max(0, int(self._bottom_log_scroll.get(key, 0)) - scroll_y)
                        return
        except Exception:
            pass
        # PRIORITY 1: Stratagem pane scrolling
        try:
            if self.left_stratagem_pane and self.left_stratagem_pane.is_open and self.left_stratagem_pane.rect.collidepoint(x, y):
                self.left_stratagem_pane.scroll(-scroll_y * 30)
                return
            if self.right_stratagem_pane and self.right_stratagem_pane.is_open and self.right_stratagem_pane.rect.collidepoint(x, y):
                self.right_stratagem_pane.scroll(-scroll_y * 30)
                return
        except Exception:
            pass
        # PRIORITY 2: Check if scrolling in unit detail panel first (highest priority)
        if self.detailed_unit:
            # Use the rect that was set during drawing (if it exists)
            if hasattr(self.unit_detail_panel, 'rect') and self.unit_detail_panel.rect:
                # Check if mouse is over the unit detail panel using the actual rect
                if self.unit_detail_panel.rect.collidepoint(x, y):
                    self.unit_detail_panel.scroll(-scroll_y * 30)  # Scroll speed
                    return  # CRITICAL: Exit early to prevent other panels from handling the event
        
        # PRIORITY 3: Only check roster panes if unit detail panel didn't handle the event
        if self.left_roster_pane.rect.collidepoint(x, y):
            self.left_roster_pane.scroll(-scroll_y * 30)  # Scroll speed
        elif self.right_roster_pane.rect.collidepoint(x, y):
            self.right_roster_pane.scroll(-scroll_y * 30)
        
        # PRIORITY 4: Handle battlefield panning with Shift+Scroll (alternative to middle mouse)
        elif self.battlefield_left < x < self.battlefield_right:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
                # Horizontal panning with Shift+Scroll
                pan_delta = scroll_y * 20 * MOUSE_PAN_SPEED
                self.offset_x += pan_delta
                self.offset_x, self.offset_y = self._apply_pan_limits(self.offset_x, self.offset_y)
            elif keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]:
                # Vertical panning with Ctrl+Scroll
                pan_delta = scroll_y * 20 * MOUSE_PAN_SPEED
                self.offset_y += pan_delta
                self.offset_x, self.offset_y = self._apply_pan_limits(self.offset_x, self.offset_y)

    def reset_unit_position(self, unit, original_unit_position, original_model_positions):
        # Reset models to their original positions
        for model, original_position in zip(unit.models, original_model_positions):
            model.set_location(*original_position)

    def get_hovered_unit(self, x, y):
        # Check if hovering over a unit in the roster panes
        hovered_unit = self.left_roster_pane.get_hovered_unit(x, y)
        if hovered_unit:
            return hovered_unit, self.left_roster_pane
        
        hovered_unit = self.right_roster_pane.get_hovered_unit(x, y)
        if hovered_unit:
            return hovered_unit, self.right_roster_pane
        
        # Check if hovering over a model on the battlefield
        if self.battlefield_left < x < self.battlefield_right:
            battlefield_x, battlefield_y = self.screen_to_game_coords(x, y)
            
            # Create a point for the mouse position
            from shapely.geometry import Point
            mouse_point = Point(battlefield_x, battlefield_y)
            
            # Check all models in all units
            for unit in self.game_map.units:
                try:
                    models = unit.get_models_for_rendering()
                except Exception:
                    models = unit.models
                for model in models:
                    if not model.is_alive:
                        continue
                    # Get the model's base shape and check if mouse point is inside
                    model_shape = model.model_base.get_base_shape()
                    if model_shape.contains(mouse_point):
                        # Use the model's parent_unit to get the unit reference
                        parent_unit = model.parent_unit
                        # If hovering a model from an attached Leader, redirect to the bodyguard unit
                        try:
                            if bool(getattr(parent_unit, "is_leader", False)) and getattr(parent_unit, "attached_to", None) is not None:
                                parent_unit = parent_unit.attached_to
                        except Exception:
                            pass
                        # Determine which roster the unit belongs to (only if armies are loaded)
                        if (self.player1.get_army() and self.player1.get_army().units and 
                            parent_unit in self.player1.get_army().units):
                            return parent_unit, self.left_roster_pane
                        elif (self.player2.get_army() and self.player2.get_army().units and 
                              parent_unit in self.player2.get_army().units):
                            return parent_unit, self.right_roster_pane
        
        return None, None

    def get_unit_at_position(self, x: float, y: float, needs_conversion: bool = True) -> Optional[Unit]:
        """Get the unit at the given coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            needs_conversion: If True, coordinates are screen coordinates that need conversion to game coordinates.
                            If False, coordinates are already game coordinates.
        """
        if needs_conversion:
            # Convert screen coordinates to game coordinates using helper method
            game_x, game_y = self.screen_to_game_coords(x, y)
        else:
            game_x = x
            game_y = y

        # Create a point for the game position
        from shapely.geometry import Point
        game_point = Point(game_x, game_y)

        # Prefer map units (single source of truth for battlefield presence)
        for unit in list(getattr(self.game_map, "units", []) or []):
            if not getattr(unit, "deployed", False):
                continue
            try:
                models = unit.get_models_for_rendering()
            except Exception:
                models = unit.models
            for model in models:
                if not model.is_alive:
                    continue
                model_shape = model.model_base.get_base_shape()
                if model_shape.contains(game_point):
                    u = model.parent_unit
                    try:
                        if bool(getattr(u, "is_leader", False)) and getattr(u, "attached_to", None) is not None:
                            return u.attached_to
                    except Exception:
                        pass
                    return u
        
        return None
    
    def get_model_at_position(self, x: float, y: float, needs_conversion: bool = True) -> Optional['Model']:
        """Get the specific model at the given position.

        Args:
            x: X coordinate (screen or game depending on needs_conversion)
            y: Y coordinate (screen or game depending on needs_conversion)
            needs_conversion: If True, (x,y) are screen coords; if False, already game coords.
        """
        if needs_conversion:
            game_x, game_y = self.screen_to_game_coords(x, y)
        else:
            game_x, game_y = x, y

        # Create a point for the game position
        from shapely.geometry import Point
        game_point = Point(game_x, game_y)

        for unit in list(getattr(self.game_map, "units", []) or []):
            if not getattr(unit, "deployed", False):
                continue
            try:
                models = unit.get_models_for_rendering()
            except Exception:
                models = unit.models
            for model in models:
                if not model.is_alive:
                    continue
                model_shape = model.model_base.get_base_shape()
                if model_shape.contains(game_point):
                    print(f"Found model {model.name} from unit {model.parent_unit.name}")
                    return model
        
        return None
    
    def screen_to_game_coords(self, screen_x: int, screen_y: int) -> Tuple[float, float]:
        """Convert screen coordinates to game coordinates with proper scaling"""
        top_offset = getattr(self, 'top_pane_height_px', 0)
        game_x = (screen_x - self.battlefield_left - self.offset_x) / (TILE_SIZE * self.zoom_level)
        game_y = (screen_y - top_offset - self.offset_y) / (TILE_SIZE * self.zoom_level)
        return game_x, game_y
    
    def game_to_screen_coords(self, game_x: float, game_y: float) -> Tuple[int, int]:
        """Convert game coordinates to screen coordinates with proper scaling"""
        top_offset = getattr(self, 'top_pane_height_px', 0)
        screen_x = int(self.battlefield_left + (game_x * TILE_SIZE * self.zoom_level) + self.offset_x)
        screen_y = int((game_y * TILE_SIZE * self.zoom_level) + self.offset_y + top_offset)
        return screen_x, screen_y

    def draw_move_path(self, unit: Unit):
        for model in unit.models:
            if not model.last_move_path:
                return

            # Convert game coordinates to screen coordinates
            screen_path = [self.game_to_screen_coords(point[0], point[1]) for point in model.last_move_path]

            # Draw the path
            pygame.draw.lines(self.screen, (0, 0, 255), False, screen_path, 2)

            # Draw start and end points
            start_point = screen_path[0]
            end_point = screen_path[-1]
                    # Movement path visualization simplified - removed start/end point circles

            # Draw direction arrows
            for i in range(len(screen_path) - 1):
                mid_point = ((screen_path[i][0] + screen_path[i+1][0]) // 2,
                            (screen_path[i][1] + screen_path[i+1][1]) // 2)
                # Direction indicator simplified - removed red dot

    def old_game_to_screen_coords(self, x: float, y: float) -> Tuple[int, int]:
        # DEPRECATED: Use the new game_to_screen_coords method instead
        # Convert game coordinates to screen coordinates  
        screen_x = int(self.battlefield_left + (x * TILE_SIZE * self.zoom_level) + self.offset_x)
        screen_y = int(y * TILE_SIZE * self.zoom_level + self.offset_y)
        return (screen_x, screen_y)
    
    def old_screen_to_game_coords(self, screen_pos: Tuple[int, int]) -> Tuple[float, float]:
        """DEPRECATED: Convert screen coordinates to game coordinates"""
        x, y = screen_pos
        # Convert from screen coordinates to game coordinates
        # Account for roster pane width, zoom level, and pan offset
        game_x = (x - self.battlefield_left - self.offset_x) / (TILE_SIZE * self.zoom_level)
        game_y = (y - self.offset_y) / (TILE_SIZE * self.zoom_level)
        return game_x, game_y

    def draw(self):
        self.screen.fill(DARK_GREY)

        # Draw stratagem panes
        self._draw_stratagem_panes()

        # Draw roster panes with enhanced styling
        self.left_roster_pane.draw(self.screen, self.game)
        self.right_roster_pane.draw(self.screen, self.game)

        # Draw the battlefield (use scaled viewport size and scaling-aware drawing)
        top_pane_height_px = int(2 * TILE_SIZE)
        self.top_pane_height_px = top_pane_height_px
        battlefield_surface = pygame.Surface((self.scaled_battlefield_width, self.scaled_battlefield_height - top_pane_height_px))
        draw_battlefield(
            battlefield_surface,
            self.zoom_level,
            self.offset_x,
            self.offset_y,
            self.scaled_battlefield_width,
            self.scaled_battlefield_height,
        )

        # Draw terrain features on the battlefield
        for terrain_feature in self.game_map.terrain_features:
            draw_terrain_feature(
                battlefield_surface,
                terrain_feature,
                self.zoom_level,
                self.offset_x,
                self.offset_y,
            )

        # Draw deployment zones (with transparency)
        if hasattr(self.game, 'deployment_zones') and self.game.deployment_zones:
            draw_deployment_zones(
                battlefield_surface,
                self.game.deployment_zones,
                self.player1,
                self.player2,
                self.zoom_level,
                self.offset_x,
                self.offset_y,
            )

        # Draw objectives on the battlefield
        for objective in self.game_map.objectives:
            draw_objective(
                battlefield_surface,
                objective,
                self.zoom_level,
                self.offset_x,
                self.offset_y,
            )

        # Draw units on the battlefield
        units_to_draw = list(self.game_map.units)
        # Also draw a unit that is currently being deployed per-model (even if not registered yet)
        try:
            if (hasattr(self, 'individual_model_movement_dialog') and
                self.individual_model_movement_dialog and
                self.individual_model_movement_dialog.visible and
                self.individual_model_movement_dialog.unit and
                self.individual_model_movement_dialog.unit not in units_to_draw):
                units_to_draw.append(self.individual_model_movement_dialog.unit)
        except Exception:
            pass

        for unit in units_to_draw:
            # Check if this unit has a highlighted model for individual movement
            highlighted_model_index = None
            if (hasattr(self, 'individual_model_movement_dialog') and 
                self.individual_model_movement_dialog.visible and 
                self.individual_model_movement_dialog.unit == unit):
                highlighted_model_index = self.individual_model_movement_dialog.get_highlighted_model_index()

            # During per-model deployment, only draw models that have actually been placed
            model_indices_to_draw = None
            try:
                if (hasattr(self, 'individual_model_movement_dialog') and
                    self.individual_model_movement_dialog.visible and
                    self.individual_model_movement_dialog.unit == unit and
                    getattr(self.individual_model_movement_dialog, 'movement_type', '') == 'deploy'):
                    model_indices_to_draw = {
                        idx for idx, data in (self.individual_model_movement_dialog.model_movements or {}).items()
                        if data.get('completed', False)
                    }
            except Exception:
                model_indices_to_draw = None
            
            draw_units(
                battlefield_surface,
                unit,
                self.zoom_level,
                self.offset_x,
                self.offset_y,
                pygame.mouse.get_pos(),
                self.player1,
                self.player2,
                highlighted_model_index,
                model_indices_to_draw=model_indices_to_draw,
            )
        
        # Old unit-level movement range drawing removed - now using Individual Model Movement Dialog for all movement

        # Draw movement range indicator for individual model movement dialog
        # NOTE: skip path/range visuals during deployment placement
        if (hasattr(self, 'individual_model_movement_dialog') and
            self.individual_model_movement_dialog.visible and
            self.individual_model_movement_dialog.unit and
            self.individual_model_movement_dialog.selected_model_index is not None and
            getattr(self.individual_model_movement_dialog, 'movement_type', '') != 'deploy'):

            print(f"🔍 DEBUG: Drawing individual model movement visualization")
            unit = self.individual_model_movement_dialog.unit
            model_index = self.individual_model_movement_dialog.selected_model_index

            if model_index < len(unit.models):
                selected_model = unit.models[model_index]
                movement_type = self.individual_model_movement_dialog.movement_type
                max_distance = self.individual_model_movement_dialog.max_distance
                game_map = self.individual_model_movement_dialog.game_map

                print(f"🔍 DEBUG: Drawing range circle for {selected_model.name} (type: {movement_type}, distance: {max_distance})")
                # Draw range circle for the selected model
                draw_individual_model_movement_range(
                    battlefield_surface,
                    selected_model,
                    movement_type,
                    max_distance,
                    self.zoom_level,
                    self.offset_x,
                    self.offset_y,
                    game_map,
                )

                # Draw real-time path preview if mouse is hovering over battlefield
                print(f"🔍 DEBUG: Checking for path preview - has target: {hasattr(self, 'individual_model_preview_target')}")
                if hasattr(self, 'individual_model_preview_target'):
                    print(f"🔍 DEBUG: Preview target value: {self.individual_model_preview_target}")

                if hasattr(self, 'individual_model_preview_target') and self.individual_model_preview_target:
                    print(f"🔍 DEBUG: Drawing path preview for model {model_index} to {self.individual_model_preview_target}")
                    # Use unified pathfinding that accounts for already-moved models
                    from ..utility.calcs import unified_pathfinding, MovementType

                    # Get moved models from the dialog if available
                    moved_models_in_unit = set()
                    preview_movement_type = MovementType.MOVE  # Default
                    if hasattr(self, 'individual_model_movement_dialog') and self.individual_model_movement_dialog.visible:
                        for moved_index, movement_data in self.individual_model_movement_dialog.model_movements.items():
                            if movement_data.get('completed', False):
                                moved_models_in_unit.add(moved_index)

                        # Get the correct movement type from the dialog
                        dialog_movement_type = self.individual_model_movement_dialog.movement_type
                        movement_type_map = {
                            'move': MovementType.MOVE,
                            'advance': MovementType.ADVANCE,
                            'fall_back': MovementType.FALL_BACK,
                            'charge': MovementType.CHARGE,
                            'scout': MovementType.SCOUT,
                            'pile_in': MovementType.PILE_IN,
                            'consolidate': MovementType.CONSOLIDATE
                        }
                        preview_movement_type = movement_type_map.get(dialog_movement_type, MovementType.MOVE)
                        print(f"🔍 DEBUG: Using movement type {preview_movement_type} for path preview (dialog type: {dialog_movement_type})")

                    # Convert 2D target to 3D if needed
                    if len(self.individual_model_preview_target) == 2:
                        target_3d = (self.individual_model_preview_target[0], self.individual_model_preview_target[1], selected_model.model_base.z)
                    else:
                        target_3d = self.individual_model_preview_target

                    # Get target unit for charge movement
                    target_unit = None
                    if hasattr(self, 'individual_model_movement_dialog') and self.individual_model_movement_dialog.visible:
                        target_unit = self.individual_model_movement_dialog.target_unit

                    path_result = unified_pathfinding(
                        model=selected_model,
                        target=target_3d,
                        movement_type=preview_movement_type,
                        max_distance=max_distance,
                        game_map=self.game.map,
                        target_unit=target_unit,
                        moved_models_in_unit=moved_models_in_unit
                    )

                    print(f"🔍 DEBUG: Path result - valid: {path_result['valid']}, path length: {len(path_result['path']) if path_result['path'] else 0}")

                    # Draw the path and model base preview similar to scout movement
                    self._draw_individual_model_path_preview(battlefield_surface, selected_model,
                                                           path_result, self.individual_model_preview_target)
                else:
                    print(f"🔍 DEBUG: No preview target set for individual model movement")

        # Deployment placement: draw hover silhouette (base + facing arrow) while mouse moves over battlefield
        if (hasattr(self, 'individual_model_movement_dialog') and
            self.individual_model_movement_dialog and
            self.individual_model_movement_dialog.visible and
            getattr(self.individual_model_movement_dialog, 'movement_type', '') == 'deploy' and
            self.individual_model_movement_dialog.unit and
            self.individual_model_movement_dialog.selected_model_index is not None and
            hasattr(self, 'individual_model_preview_target') and self.individual_model_preview_target):
            try:
                unit = self.individual_model_movement_dialog.unit
                mi = self.individual_model_movement_dialog.selected_model_index
                if mi < len(unit.models):
                    m = unit.models[mi]
                    fx, fy = self.individual_model_preview_target
                    try:
                        facing = float(self.individual_model_movement_dialog.get_deploy_facing_radians())
                    except Exception:
                        facing = float(getattr(m.model_base, 'facing', 0.0))
                    ghost_color = (0, 255, 255)  # cyan
                    self._draw_model_base_preview(
                        battlefield_surface,
                        m,
                        float(fx),
                        float(fy),
                        ghost_color,
                        facing_override=facing,
                    )
            except Exception:
                pass

        # Draw weapon range indicator if a unit is selected for shooting
        if (hasattr(self, 'selected_unit') and self.selected_unit and
            hasattr(self, 'selected_weapon_profile') and self.selected_weapon_profile):
            draw_weapon_ranges(
                battlefield_surface,
                self.selected_unit,
                self.selected_weapon_profile,
                self.zoom_level,
                self.offset_x,
                self.offset_y,
            )
            # Highlight valid targets in green overlay if targeting mode active
            # Remove precomputed valid target highlighting to avoid heavy per-frame work

        # Draw scout visual feedback if in scout phase (draw on battlefield surface)
        if hasattr(self, 'phase_manager') and self.phase_manager:
            current_handler = self.phase_manager.get_current_handler()
            if isinstance(current_handler, PreBattlePhaseHandler):
                current_handler.draw_scout_visual_feedback(battlefield_surface)

        # Draw top mission/status pane and shift battlefield down
        self._draw_top_status_pane(top_pane_height_px)
        self.screen.blit(battlefield_surface, (self.battlefield_left, top_pane_height_px))

        # Draw repurposed bottom logs pane
        self._draw_bottom_logs_pane()

        # Draw unit details panel if requested
        if self.detailed_unit:
            self.unit_detail_panel.draw(self.screen, self.detailed_unit, 
                                      self.detail_panel_pos[0], self.detail_panel_pos[1])

        # Draw move paths for all units (only if armies are loaded)
        current_player = self.game.get_current_player()
        if current_player and current_player.get_army() and current_player.get_army().units:
            for unit in current_player.get_army().units:
                self.draw_move_path(unit)

        # Draw UI interface components (non-dialog overlays like reserves arrival panel)
        if self.ui_interface:
            self.ui_interface.update(self.screen)

        # Draw all dialogs via the centralized modal stack (includes UI-interface dialogs).
        if hasattr(self, 'dialog_manager') and self.dialog_manager:
            self.dialog_manager.draw(self.screen)

        # Finally, draw mission popup overlay above everything if present
        if getattr(self, '_mission_popup', None):
            self._draw_mission_popup_overlay(
                self._mission_popup.get('title', 'Mission'),
                self._mission_popup.get('body', ''),
                image_path=self._mission_popup.get('image_path'),
            )
        pygame.display.update()

    # Note: on_key_press is now handled by phase-specific handlers in PhaseManager
    # Detail panel scrolling is still handled in handle_pygame_event for universal access
    
    def force_complete_deployment(self):
        """Force complete the deployment phase by auto-deploying remaining units"""
        self.game.complete_deployment_phase()
        
        # Clear any selected units
        self.selected_unit = None
        self.left_roster_pane.selected_unit = None
        self.right_roster_pane.selected_unit = None
        
        print("Deployment phase completed! Press SPACE to start the game.")

    def close_unit_details(self):
        """Close the unit details panel"""
        self.detailed_unit = None
        # Reset scroll position when closing
        self.unit_detail_panel.scroll_offset = 0

    def _apply_pan_limits(self, offset_x: int, offset_y: int) -> Tuple[int, int]:
        """Apply panning limits to prevent moving outside the battlefield"""
        # Calculate world size in pixels
        tile_size_px = TILE_SIZE * self.zoom_level
        world_width_px = int(BATTLEFIELD_WIDTH_INCHES * tile_size_px)
        world_height_px = int(BATTLEFIELD_HEIGHT_INCHES * tile_size_px)

        # Viewport size is the scaled battlefield viewport
        viewport_width_px = int(self.scaled_battlefield_width)
        viewport_height_px = int(self.scaled_battlefield_height)

        # Max scrollable offsets (how far we can pan left/up as negative values)
        max_scroll_x = max(0, world_width_px - viewport_width_px)
        max_scroll_y = max(0, world_height_px - viewport_height_px)

        limited_offset_x = max(-max_scroll_x, min(0, offset_x))
        limited_offset_y = max(-max_scroll_y, min(0, offset_y))
        return limited_offset_x, limited_offset_y

    def get_phase_status(self) -> dict:
        """Get current phase status and allowed actions for debugging/testing"""
        if hasattr(self, 'phase_manager'):
            current_handler = self.phase_manager.get_current_handler()
            return {
                'current_phase': type(current_handler).__name__,
                'game_phase': self.game.phase.name if hasattr(self.game.phase, 'name') else str(self.game.phase),
                'setup_phase': self.game.get_current_setup_phase().name if self.game.is_in_setup_phase() else None,
                'is_deployment': self.game.is_deployment_phase(),
                'allowed_actions': self.phase_manager.get_current_allowed_actions()
            }
        else:
            return {'error': 'Phase manager not initialized'}

    def _draw_individual_model_path_preview(self, surface: pygame.Surface, model, path_result: dict, target_pos: tuple):
        """Draw path preview and model base for individual model movement"""
        if not path_result or not target_pos:
            return

        # Choose color based on pathfinding result
        if path_result['valid']:
            color = (0, 255, 255)  # Cyan for valid path
        else:
            color = (255, 165, 0)  # Orange for invalid path

        # Draw the path if available
        if path_result['path'] and len(path_result['path']) > 1:
            path_points = []
            for pos in path_result['path']:
                screen_x = int(pos[0] * TILE_SIZE * self.zoom_level + self.offset_x)
                screen_y = int(pos[1] * TILE_SIZE * self.zoom_level + self.offset_y)
                path_points.append((screen_x, screen_y))

            if len(path_points) > 1:
                pygame.draw.lines(surface, color, False, path_points, 3)

            # Draw target indicator with actual model base footprint
            final_pos = path_result['path'][-1]
            self._draw_model_base_preview(surface, model, final_pos[0], final_pos[1], color)
        else:
            # No path available, just draw target position
            self._draw_model_base_preview(surface, model, target_pos[0], target_pos[1], color)

    def _draw_model_base_preview(self, surface: pygame.Surface, model, game_x: float, game_y: float, color: tuple, facing_override: Optional[float] = None):
        """Draw the actual model base footprint at the specified game coordinates"""
        try:
            if not model or not hasattr(model, 'model_base'):
                # Fallback to small circle if no base information
                screen_x = int(game_x * TILE_SIZE * self.zoom_level + self.offset_x)
                screen_y = int(game_y * TILE_SIZE * self.zoom_level + self.offset_y)
                pygame.draw.circle(surface, color[:3], (screen_x, screen_y), 8, 2)
                return

            # Get the model's base shape at the target position
            facing = float(facing_override) if facing_override is not None else float(getattr(model.model_base, 'facing', 0.0))
            base_shape = model.model_base.get_base_shape_at(game_x, game_y, facing)

            # Convert the base shape to screen coordinates
            screen_points = []
            for x, y in base_shape.exterior.coords:
                screen_x = int(x * TILE_SIZE * self.zoom_level + self.offset_x)
                screen_y = int(y * TILE_SIZE * self.zoom_level + self.offset_y)
                screen_points.append((screen_x, screen_y))

            # Draw the base footprint
            if len(screen_points) > 2:
                # Draw filled shape with transparency
                alpha_color = (*color[:3], 100) if len(color) == 3 else color
                try:
                    # Create a temporary surface for alpha blending
                    temp_surface = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
                    pygame.draw.polygon(temp_surface, alpha_color, screen_points)
                    surface.blit(temp_surface, (0, 0))
                except:
                    # Fallback to outline only if alpha blending fails
                    pygame.draw.polygon(surface, color[:3], screen_points, 2)

                # Draw outline
                pygame.draw.polygon(surface, color[:3], screen_points, 2)

                # Draw a facing arrow from the base center (matches silhouette rotation)
                try:
                    cx = int(game_x * TILE_SIZE * self.zoom_level + self.offset_x)
                    cy = int(game_y * TILE_SIZE * self.zoom_level + self.offset_y)

                    # Arrow length based on base radius (inches) scaled to pixels
                    try:
                        r = getattr(model.model_base, 'radius', (1.0, 1.0))
                        r_in = float(max(r)) if isinstance(r, (tuple, list)) else float(r)
                    except Exception:
                        r_in = 1.0
                    arrow_len = max(10.0, (r_in * 1.25) * TILE_SIZE * self.zoom_level)

                    ex = int(cx + math.cos(facing) * arrow_len)
                    ey = int(cy + math.sin(facing) * arrow_len)
                    pygame.draw.line(surface, color[:3], (cx, cy), (ex, ey), 3)

                    # Arrow head
                    head_len = max(6.0, arrow_len * 0.25)
                    left_ang = facing + math.radians(150.0)
                    right_ang = facing - math.radians(150.0)
                    lx = int(ex + math.cos(left_ang) * head_len)
                    ly = int(ey + math.sin(left_ang) * head_len)
                    rx = int(ex + math.cos(right_ang) * head_len)
                    ry = int(ey + math.sin(right_ang) * head_len)
                    pygame.draw.line(surface, color[:3], (ex, ey), (lx, ly), 3)
                    pygame.draw.line(surface, color[:3], (ex, ey), (rx, ry), 3)
                except Exception:
                    pass
        except Exception as e:
            # Ultimate fallback - draw simple circle and don't break the rendering
            try:
                screen_x = int(game_x * TILE_SIZE * self.zoom_level + self.offset_x)
                screen_y = int(game_y * TILE_SIZE * self.zoom_level + self.offset_y)
                pygame.draw.circle(surface, color[:3], (screen_x, screen_y), 8, 2)
            except:
                # If even the fallback fails, just skip drawing
                pass


### Battlefield drawing functions
def draw_battlefield(screen: pygame.Surface, zoom_level: float, offset_x: int, offset_y: int, viewport_width: Optional[int] = None, viewport_height: Optional[int] = None) -> None:
    # Always render grid at fixed pixels-per-inch (TILE_SIZE) scaled only by zoom_level, not window size
    screen.fill((0, 0, 0))  # Black background outside battlefield
    tile_size = int(TILE_SIZE * zoom_level)

    # Visible viewport size
    visible_width = viewport_width if viewport_width is not None else screen.get_width()
    visible_height = viewport_height if viewport_height is not None else screen.get_height()

    # Battlefield pixel dimensions at current zoom
    world_w = BATTLEFIELD_WIDTH_INCHES * tile_size
    world_h = BATTLEFIELD_HEIGHT_INCHES * tile_size

    # Battlefield rectangle position within viewport (can be partially offscreen due to pan offsets)
    bf_left = int(offset_x)
    bf_top = int(offset_y)
    bf_rect = pygame.Rect(bf_left, bf_top, world_w, world_h)

    # Draw battlefield background (white) clipped to viewport
    # Compute intersection with viewport
    viewport_rect = pygame.Rect(0, 0, visible_width, visible_height)
    intersect = bf_rect.clip(viewport_rect)
    if intersect.width > 0 and intersect.height > 0:
        pygame.draw.rect(screen, WHITE, intersect)

    # Determine inch range visible in viewport to limit line drawing
    start_x_inch = max(0, int((-offset_x) // tile_size))
    end_x_inch = min(BATTLEFIELD_WIDTH_INCHES, int((visible_width - offset_x) // tile_size) + 1)
    start_y_inch = max(0, int((-offset_y) // tile_size))
    end_y_inch = min(BATTLEFIELD_HEIGHT_INCHES, int((visible_height - offset_y) // tile_size) + 1)

    # Draw vertical grid lines clipped to battlefield rect
    for x_inch in range(start_x_inch, end_x_inch + 1):
        px = int(x_inch * tile_size + offset_x)
        if px < bf_left or px > bf_left + world_w:
            continue
        y1 = max(0, bf_top)
        y2 = min(visible_height, bf_top + world_h)
        if y2 > y1:
            pygame.draw.line(screen, GREY, (px, y1), (px, y2))

    # Draw horizontal grid lines clipped to battlefield rect
    for y_inch in range(start_y_inch, end_y_inch + 1):
        py = int(y_inch * tile_size + offset_y)
        if py < bf_top or py > bf_top + world_h:
            continue
        x1 = max(0, bf_left)
        x2 = min(visible_width, bf_left + world_w)
        if x2 > x1:
            pygame.draw.line(screen, GREY, (x1, py), (x2, py))

    # Draw battlefield border clipped to viewport
    border_rect = bf_rect.clip(viewport_rect)
    if border_rect.width > 0 and border_rect.height > 0:
        pygame.draw.rect(screen, RED, border_rect, 2)

def draw_terrain_feature(screen: pygame.Surface, terrain_feature: TerrainFeature, zoom_level: float, offset_x: int, offset_y: int) -> None:
    # Determine the color based on the terrain type
    if terrain_feature.terrain_type == TerrainType.CRATER_AND_RUBBLE:
        color = (128, 0, 0, 180)  # Dark red for craters
    elif terrain_feature.terrain_type == TerrainType.DEBRIS_AND_STATUARY:
        color = (192, 192, 192, 180)  # Gray for debris and statuary
    elif terrain_feature.terrain_type == TerrainType.HILLS_AND_SEALED_BUILDINGS:
        color = (128, 64, 0, 180)  # Brown for hills and sealed buildings
    elif terrain_feature.terrain_type == TerrainType.WOODS:
        color = (0, 128, 0, 180)  # Green for woods
    elif terrain_feature.terrain_type == TerrainType.RUINS:
        color = (128, 128, 128, 180)  # Gray for ruins
    elif terrain_feature.terrain_type == TerrainType.BARRICADE_AND_FUEL_PIPES:
        color = (139, 69, 19, 180)  # Brown for barricades
    else:
        color = (255, 255, 255, 180)  # Default white

    def to_screen(pt):
        # Use fixed inch grid (TILE_SIZE) scaled only by zoom; offset pans view
        return (
            int((pt[0] * TILE_SIZE) * zoom_level + offset_x),
            int((pt[1] * TILE_SIZE) * zoom_level + offset_y),
        )

    def draw_shapely_polygon(poly, fill_rgba=None, outline_rgb=None, outline_w=1):
        try:
            coords = list(poly.exterior.coords)[:-1]
        except Exception:
            return
        if len(coords) < 3:
            return
        points = [to_screen(v) for v in coords]
        if fill_rgba is not None:
            # Use a temporary surface to support alpha fills
            temp = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
            pygame.draw.polygon(temp, fill_rgba, points)
            screen.blit(temp, (0, 0))
        if outline_rgb is not None and outline_w > 0:
            pygame.draw.polygon(screen, outline_rgb, points, outline_w)

    # Draw the footprint as a base
    footprint_coords = list(terrain_feature.footprint.exterior.coords)[:-1]
    screen_vertices = [to_screen(v) for v in footprint_coords]
    if len(screen_vertices) >= 3:
        pygame.draw.polygon(screen, color, screen_vertices)
        pygame.draw.polygon(screen, (0, 0, 0), screen_vertices, 2)

    # Special rendering for RUINS: draw floors, walls, and openings
    if terrain_feature.terrain_type == TerrainType.RUINS:
        # Floors: translucent bluish overlay
        floors = getattr(terrain_feature, 'floors', []) or []
        for floor in floors:
            poly = floor.get('polygon')
            if poly is None:
                continue
            draw_shapely_polygon(poly, fill_rgba=(80, 120, 200, 90), outline_rgb=(50, 80, 140), outline_w=1)

        # Walls: darker gray blocks
        walls = getattr(terrain_feature, 'walls', []) or []
        for wall in walls:
            poly = wall.get('polygon')
            if poly is None:
                continue
            draw_shapely_polygon(poly, fill_rgba=(80, 80, 80, 220), outline_rgb=(30, 30, 30), outline_w=1)

        # Openings (windows/doors): render as colored overlays to indicate cuts
        openings = getattr(terrain_feature, 'openings', []) or []
        for opening in openings:
            poly = opening.get('polygon')
            if poly is None:
                continue
            allows_movement = opening.get('allows_movement', False)
            allows_los = opening.get('allows_los', False)
            if allows_movement:
                # doors: greenish
                draw_shapely_polygon(poly, fill_rgba=(50, 200, 120, 180), outline_rgb=(0, 120, 60), outline_w=1)
            elif allows_los:
                # windows: yellowish
                draw_shapely_polygon(poly, fill_rgba=(230, 210, 60, 160), outline_rgb=(160, 140, 20), outline_w=1)
            else:
                # generic openings
                draw_shapely_polygon(poly, fill_rgba=(200, 200, 200, 140), outline_rgb=(100, 100, 100), outline_w=1)

def draw_deployment_zones(screen: pygame.Surface, deployment_zones: dict, player1: Player, player2: Player, 
                         zoom_level: float, offset_x: int, offset_y: int) -> None:
    """Draw deployment zones with transparency and appropriate colors for each player."""
    for player_name, zone in deployment_zones.items():
        # Determine player color with more vibrant colors during deployment
        if player_name == player1.name:
            color = (0, 255, 0, 160)  # More visible green for player 1
            border_color = (0, 200, 0)
        elif player_name == player2.name:
            color = (255, 0, 0, 160)  # More visible red for player 2
            border_color = (200, 0, 0)
        else:
            color = (128, 128, 128, 160)  # Semi-transparent gray for unknown players
            border_color = (100, 100, 100)
        
        # Check if this is a mission zone (new system) or old system
        if 'mission_zones' in zone:
            # Draw each mission zone polygon
            for mission_zone in zone['mission_zones']:
                # Convert mission zone vertices to screen coordinates
                screen_points = []
                for x, y in mission_zone.vertices:
                    screen_x = int(x * TILE_SIZE * zoom_level + offset_x)
                    screen_y = int(y * TILE_SIZE * zoom_level + offset_y)
                    screen_points.append((screen_x, screen_y))
                
                # Only draw if we have enough points for a polygon
                if len(screen_points) >= 3:
                    # Create a surface for the polygon with alpha
                    # Get bounding box for the surface
                    min_x = min(p[0] for p in screen_points)
                    max_x = max(p[0] for p in screen_points)
                    min_y = min(p[1] for p in screen_points)
                    max_y = max(p[1] for p in screen_points)
                    
                    surface_width = max_x - min_x + 1
                    surface_height = max_y - min_y + 1
                    
                    if surface_width > 0 and surface_height > 0:
                        # Adjust points relative to surface origin
                        relative_points = [(p[0] - min_x, p[1] - min_y) for p in screen_points]
                        
                        # Create transparent surface
                        zone_surface = pygame.Surface((surface_width, surface_height), pygame.SRCALPHA)
                        
                        # Draw filled polygon
                        pygame.draw.polygon(zone_surface, color, relative_points)
                        
                        # Draw cutouts if any exist
                        if hasattr(mission_zone, 'cutouts') and mission_zone.cutouts:
                            for cutout in mission_zone.cutouts:
                                if cutout.cutout_type.value == 'circle':
                                    # Convert cutout center to screen coordinates
                                    cutout_screen_x = int(cutout.center_x * TILE_SIZE * zoom_level + offset_x)
                                    cutout_screen_y = int(cutout.center_y * TILE_SIZE * zoom_level + offset_y)
                                    cutout_radius = int(cutout.parameters * TILE_SIZE * zoom_level)
                                    
                                    # Calculate cutout position relative to surface
                                    cutout_rel_x = cutout_screen_x - min_x
                                    cutout_rel_y = cutout_screen_y - min_y
                                    
                                    # Only draw cutout if it's within the surface bounds
                                    if (cutout_rel_x + cutout_radius >= 0 and cutout_rel_x - cutout_radius < surface_width and
                                        cutout_rel_y + cutout_radius >= 0 and cutout_rel_y - cutout_radius < surface_height):
                                        
                                        # Draw cutout as no man's land (transparent - shows battlefield background)
                                        # Create a "hole" by drawing with full transparency
                                        pygame.draw.circle(zone_surface, (0, 0, 0, 0), 
                                                         (cutout_rel_x, cutout_rel_y), cutout_radius)
                                        # Draw cutout border to show the boundary
                                        pygame.draw.circle(zone_surface, (100, 100, 100), 
                                                         (cutout_rel_x, cutout_rel_y), cutout_radius, 2)
                        
                        # No zone border per request (keep only filled zone and cutout visuals)
                        
                        # Blit to main screen
                        screen.blit(zone_surface, (min_x, min_y))
                        
                        # Add zone label
                        font = pygame.font.Font(None, int(24 * zoom_level))
                        if zone.get('zone_type') == 'defender':
                            label_text = "DEFENDER"
                        elif zone.get('zone_type') == 'attacker':
                            label_text = "ATTACKER"
                        else:
                            label_text = zone.get('name', 'ZONE')
                        
                        text_surface = font.render(label_text, True, border_color)
                        text_rect = text_surface.get_rect()
                        
                        # Center text in the polygon (approximate)
                        center_x = (min_x + max_x) // 2 - text_rect.width // 2
                        center_y = (min_y + max_y) // 2 - text_rect.height // 2
                        screen.blit(text_surface, (center_x, center_y))
        else:
            # Deployment zones must be mission polygon zones; no rectangular fallback.
            continue
            
            # Add zone label with better positioning
            font = pygame.font.SysFont('Arial', max(14, int(16 * zoom_level)), bold=True)
            label_text = f"{player_name} Deployment Zone"
            text_surface = font.render(label_text, True, border_color)
            
            # Position label at the center-top of the zone for better visibility
            label_x = screen_x_start + (zone_width - text_surface.get_width()) // 2
            label_y = screen_y_start + 15
            
            # Draw a more prominent background for the text
            text_bg = pygame.Surface((text_surface.get_width() + 12, text_surface.get_height() + 6), pygame.SRCALPHA)
            text_bg.fill((255, 255, 255, 220))  # More opaque white background
            screen.blit(text_bg, (label_x - 6, label_y - 3))
            
            # Draw black outline for better text visibility
            outline_positions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
            for dx, dy in outline_positions:
                outline_surface = font.render(label_text, True, (0, 0, 0))
                screen.blit(outline_surface, (label_x + dx, label_y + dy))
            
            # Draw the main text
            screen.blit(text_surface, (label_x, label_y))

def draw_objective(screen: pygame.Surface, objective: Objective, zoom_level: float, offset_x: int, offset_y: int) -> None:
    if isinstance(objective.location, ObjectivePoint):
        # Create a transparent surface for the objective
        objective_radius = int(objective.location.control_radius * TILE_SIZE * zoom_level)
        if objective_radius > 0:
            # Calculate center position
            center_x = int(objective.location.x * TILE_SIZE * zoom_level + offset_x)
            center_y = int(objective.location.y * TILE_SIZE * zoom_level + offset_y)
            
            # Create a surface with per-pixel alpha for transparency
            objective_surface = pygame.Surface((objective_radius * 2, objective_radius * 2), pygame.SRCALPHA)
            
            # Draw objective with 50% transparency (128 alpha instead of 255)
            pygame.draw.circle(objective_surface, (128, 0, 128, 128), (objective_radius, objective_radius), objective_radius)
            
            # Draw border for visibility
            pygame.draw.circle(objective_surface, (128, 0, 128, 255), (objective_radius, objective_radius), objective_radius, 2)
            
            # Blit to main screen
            screen.blit(objective_surface, (center_x - objective_radius, center_y - objective_radius))

def draw_units(
    screen: pygame.Surface,
    unit: Unit,
    zoom_level: float,
    offset_x: int,
    offset_y: int,
    mouse_pos: Tuple[int, int],
    player1: Player,
    player2: Player,
    highlighted_model_index: Optional[int] = None,
    model_indices_to_draw: Optional[set[int]] = None,
) -> None:
    # Determine the color based on which player the unit belongs to (only if armies are loaded)
    color = BLUE  # Default color
    if (player1.get_army() and player1.get_army().units and unit in player1.get_army().units):
        color = GREEN
    elif (player2.get_army() and player2.get_army().units and unit in player2.get_army().units):
        color = RED
    
    # Get all units for color variation calculation (only if armies are loaded)
    all_units = []
    if player1.get_army() and player1.get_army().units:
        all_units.extend(player1.get_army().units)
    if player2.get_army() and player2.get_army().units:
        all_units.extend(player2.get_army().units)

    # For "deploy" previews, the dialog passes a unit-like object where indices must match the dialog's models list.
    if model_indices_to_draw is not None:
        models = unit.models
    else:
        try:
            models = unit.get_models_for_rendering()
        except Exception:
            models = unit.models

    for model_index, model in enumerate(models):
        if model_indices_to_draw is not None and model_index not in model_indices_to_draw:
            continue
        x, y = model.get_location()[:2]
        screen_x = int((x * TILE_SIZE) * zoom_level + offset_x)
        screen_y = int((y * TILE_SIZE) * zoom_level + offset_y)
        base = model.model_base
        
        # Check if this model should be highlighted
        is_highlighted = (highlighted_model_index is not None and 
                         highlighted_model_index == model_index)
        
        draw_enhanced_base(screen, base, screen_x, screen_y, zoom_level, color, unit, model, is_highlighted)
        
        # Draw facing direction with enhanced styling
        draw_facing_direction(screen, base, screen_x, screen_y, zoom_level)
        
        # Draw large prominent icon that overlays the facing arrow
        draw_prominent_unit_icon(screen, screen_x, screen_y, base, zoom_level, unit, model, model_index, all_units, is_highlighted)
    
            # Unit bounding box removed - model-based hover detection is more accurate

def draw_prominent_unit_icon(screen: pygame.Surface, center_x: int, center_y: int, base: Base, zoom_level: float, unit: Unit, model: Model, model_index: int, all_units: List[Unit], is_highlighted: bool = False) -> None:
    """Draw a large, prominent icon that overlays the facing direction"""
    # Calculate icon size - larger and with minimum size
    base_radius = int(base.get_radius() * TILE_SIZE * zoom_level)
    icon_size = max(ICON_MIN_SIZE, int(base_radius * ICON_SCALE_FACTOR))
    
    # Get unit-specific color variation
    icon_tint = get_unit_color_variation(unit, all_units)
    
    # Draw semi-transparent background circle for better visibility
    bg_radius = icon_size // 2 + 4
    bg_surface = pygame.Surface((bg_radius * 2, bg_radius * 2), pygame.SRCALPHA)
    bg_color = (255, 255, 0, 150) if is_highlighted else (0, 0, 0, 100)
    pygame.draw.circle(bg_surface, bg_color, (bg_radius, bg_radius), bg_radius)
    screen.blit(bg_surface, (center_x - bg_radius, center_y - bg_radius))
    
    # Draw the unit type icon with color tinting and rotation
    draw_rotated_tinted_unit_icon(screen, center_x, center_y, icon_size, unit, icon_tint, base.facing)
    
    # For multi-model units, draw individual model identifier
    try:
        models = unit.get_models_for_rendering()
    except Exception:
        models = getattr(unit, "models", []) or []
    if len(models) > 1:
        draw_model_identifier(screen, center_x, center_y, icon_size, model_index, unit, is_highlighted)
    
    # Draw wound indicator if model is damaged
    if not model.is_max_health:
        draw_prominent_wound_indicator(screen, center_x, center_y, icon_size, model)

def draw_rotated_tinted_unit_icon(screen: pygame.Surface, center_x: int, center_y: int, size: int, unit: Unit, tint_color: Tuple[int, int, int], angle: float) -> None:
    """Draw unit icon with color tinting and rotation based on facing direction"""
    # Create a surface for the icon with alpha - make it larger for rotation
    icon_surface = pygame.Surface((size * 3, size * 3), pygame.SRCALPHA)
    icon_center = size * 3 // 2  # Center of the larger icon surface
    
    # Draw the base icon on the surface - prioritize more distinctive unit types
    # Priority order: Vehicle > Monster > Aircraft > Beast > Psyker > Battleline > Character > Generic
    if unit.is_vehicle:
        draw_vehicle_icon(icon_surface, icon_center, icon_center, size)
    elif unit.is_monster:
        draw_monster_icon(icon_surface, icon_center, icon_center, size)
    elif unit.is_aircraft:
        draw_aircraft_icon(icon_surface, icon_center, icon_center, size)
    elif unit.is_beast:
        draw_beast_icon(icon_surface, icon_center, icon_center, size)
    elif unit.is_psyker:
        draw_psyker_icon(icon_surface, icon_center, icon_center, size)
    elif unit.is_battleline:
        draw_battleline_icon(icon_surface, icon_center, icon_center, size)
    elif unit.is_character:
        draw_character_icon(icon_surface, icon_center, icon_center, size)
    else:
        draw_generic_icon(icon_surface, icon_center, icon_center, size)
    
    # Apply color tint if it's not the default white
    if tint_color != (255, 255, 255):
        # Create tint overlay
        tint_surface = pygame.Surface((size * 3, size * 3), pygame.SRCALPHA)
        tint_surface.fill((*tint_color, 120))  # Semi-transparent tint
        icon_surface.blit(tint_surface, (0, 0), special_flags=pygame.BLEND_MULT)
    
    # Rotate the icon surface based on the model's facing direction
    angle_degrees = math.degrees(angle)
    rotated_surface = pygame.transform.rotate(icon_surface, -angle_degrees)  # Negative for correct rotation
    
    # Calculate the position to blit the rotated surface (centered)
    blit_x = center_x - rotated_surface.get_width() // 2
    blit_y = center_y - rotated_surface.get_height() // 2
    
    # Blit the rotated icon to the screen
    screen.blit(rotated_surface, (blit_x, blit_y))

def draw_tinted_unit_icon(screen: pygame.Surface, center_x: int, center_y: int, size: int, unit: Unit, tint_color: Tuple[int, int, int]) -> None:
    """Draw unit icon with color tinting (backward compatibility function for roster)"""
    # Just call the rotated version with 0 rotation for backward compatibility
    draw_rotated_tinted_unit_icon(screen, center_x, center_y, size, unit, tint_color, 0.0)

def draw_model_identifier(screen: pygame.Surface, center_x: int, center_y: int, icon_size: int, model_index: int, unit: Unit, is_highlighted: bool = False) -> None:
    """Draw individual model identifier for multi-model units"""
    # Position the identifier at the top-right of the icon with more offset
    identifier_size = max(12, icon_size // 3)
    identifier_x = center_x + icon_size // 2 - identifier_size // 4  # More to the right
    identifier_y = center_y - icon_size // 2 + identifier_size // 4  # More up
    
    # Draw background circle with highlighting
    bg_color = (255, 255, 100) if is_highlighted else (255, 255, 255)
    border_color = (255, 255, 0) if is_highlighted else (0, 0, 0)
    border_width = 3 if is_highlighted else 2
    
    pygame.draw.circle(screen, bg_color, (identifier_x, identifier_y), identifier_size // 2 + 2)
    pygame.draw.circle(screen, border_color, (identifier_x, identifier_y), identifier_size // 2 + 2, border_width)
    
    # Draw model number (1-indexed for user friendliness)
    font_size = max(10, identifier_size)
    font = pygame.font.Font(None, font_size)
    model_number = str(model_index + 1)
    text_color = (0, 0, 0) if not is_highlighted else (100, 100, 0)
    text_surface = font.render(model_number, True, text_color)
    text_rect = text_surface.get_rect(center=(identifier_x, identifier_y))
    screen.blit(text_surface, text_rect)

def draw_prominent_wound_indicator(screen: pygame.Surface, center_x: int, center_y: int, icon_size: int, model: Model) -> None:
    """Draw a prominent wound indicator for damaged models"""
    if model.is_max_health:
        return
    
    # Position at bottom of icon
    indicator_y = center_y + icon_size // 2 + 8
    
    # Larger background for better visibility
    bg_width = max(30, icon_size // 2)
    bg_height = 14
    bg_rect = pygame.Rect(center_x - bg_width // 2, indicator_y - bg_height // 2, bg_width, bg_height)
    
    # Background with strong contrast
    pygame.draw.rect(screen, (0, 0, 0), bg_rect, border_radius=4)
    pygame.draw.rect(screen, (255, 255, 255), bg_rect, 2, border_radius=4)
    
    # Wound text with larger font
    font_size = max(12, int(14))
    font = pygame.font.Font(None, font_size)
    wound_text = f"{model.wounds}/{model._base_wounds}"
    
    # Color based on health level
    health_percent = model.health_percent
    if health_percent < 25:
        text_color = (255, 100, 100)  # Light red
    elif health_percent < 50:
        text_color = (255, 200, 100)  # Light orange
    elif health_percent < 75:
        text_color = (255, 255, 100)  # Light yellow
    else:
        text_color = (100, 255, 100)  # Light green
    
    text_surface = font.render(wound_text, True, text_color)
    text_rect = text_surface.get_rect(center=(center_x, indicator_y))
    screen.blit(text_surface, text_rect)

def draw_unit_identification(screen: pygame.Surface, screen_x: int, screen_y: int, radius: int, unit: Unit, model: Model, zoom_level: float) -> None:
    """Draw unit identification elements for circular bases - now simplified since we have prominent icons"""
    # This function is now mainly for the health indicator ring
    draw_health_indicator(screen, screen_x, screen_y, radius, model)

def draw_unit_identification_on_surface(surface: pygame.Surface, center_x: int, center_y: int, radius: int, unit: Unit, model: Model, zoom_level: float) -> None:
    """Draw unit identification elements on a surface - now simplified since we have prominent icons"""
    # This function is now mainly for the health indicator ring
    # Note: Health indicator is drawn separately for surface-based rendering
    pass

def draw_model_count_indicator(surface: pygame.Surface, center_x: int, center_y: int, radius: int, unit: Unit) -> None:
    """Draw a small indicator showing model count for multi-model units - now unused since we show individual model numbers"""
    # This function is now unused but kept for compatibility
    pass

def draw_enhanced_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int], unit: Unit, model: Model, is_highlighted: bool = False) -> None:
    """Enhanced base drawing with unit identification features"""
    if base.base_type == BaseType.CIRCULAR:
        draw_enhanced_circular_base(screen, base, screen_x, screen_y, zoom_level, color, unit, model, is_highlighted)
    elif base.base_type == BaseType.ELLIPTICAL:
        draw_enhanced_elliptical_base(screen, base, screen_x, screen_y, zoom_level, color, unit, model, is_highlighted)
    elif base.base_type == BaseType.HULL:
        draw_enhanced_hull_base(screen, base, screen_x, screen_y, zoom_level, color, unit, model, is_highlighted)

def draw_enhanced_circular_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int], unit: Unit, model: Model, is_highlighted: bool = False) -> None:
    """Enhanced circular base with unit identification"""
    radius = int(base.get_radius() * TILE_SIZE * zoom_level)
    
    # Draw highlighting ring if highlighted
    if is_highlighted:
        highlight_radius = radius + 4
        pygame.draw.circle(screen, (255, 255, 0), (screen_x, screen_y), highlight_radius, 3)
    
    # Draw outer ring with gradient effect
    pygame.draw.circle(screen, color, (screen_x, screen_y), radius)
    
    # Draw inner area with unit-specific styling - scale properly with zoom
    inner_radius = max(1, int(radius * 0.85))
    inner_color = get_unit_inner_color(unit, model)
    pygame.draw.circle(screen, inner_color, (screen_x, screen_y), inner_radius)
    
    # Add unit identification elements
    draw_unit_identification(screen, screen_x, screen_y, radius, unit, model, zoom_level)

def draw_enhanced_elliptical_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int], unit: Unit, model: Model, is_highlighted: bool = False) -> None:
    """Enhanced elliptical base with unit identification"""
    width = int(base.radius[0] * 2 * TILE_SIZE * zoom_level)
    height = int(base.radius[1] * 2 * TILE_SIZE * zoom_level)
    
    # Ensure minimum size for visibility
    width = max(4, width)
    height = max(4, height)
    
    # Draw highlighting ellipse if highlighted
    if is_highlighted:
        highlight_width = width + 8
        highlight_height = height + 8
        highlight_rect = pygame.Rect(screen_x - highlight_width//2, screen_y - highlight_height//2, highlight_width, highlight_height)
        pygame.draw.ellipse(screen, (255, 255, 0), highlight_rect, 3)
    
    # Create a surface for the ellipse
    ellipse_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    ellipse_surface.fill((0, 0, 0, 0))  # Transparent background
    
    # Draw the outer ellipse
    pygame.draw.ellipse(ellipse_surface, color, (0, 0, width, height))
    
    # Draw the inner ellipse with unit-specific styling - scale properly with zoom
    inner_width, inner_height = max(1, int(width * 0.85)), max(1, int(height * 0.85))
    inner_rect = pygame.Rect((width - inner_width) // 2, (height - inner_height) // 2, inner_width, inner_height)
    inner_color = get_unit_inner_color(unit, model)
    pygame.draw.ellipse(ellipse_surface, inner_color, inner_rect)
    
    # Add unit identification on the surface before rotation
    draw_unit_identification_on_surface(ellipse_surface, width//2, height//2, min(width, height)//2, unit, model, zoom_level)
    
    # Rotate the surface
    angle_degrees = math.degrees(base.facing)
    rotated_surface = pygame.transform.rotate(ellipse_surface, -angle_degrees)
    
    # Calculate the position to blit the rotated surface
    blit_pos = (screen_x - rotated_surface.get_width() // 2, 
                screen_y - rotated_surface.get_height() // 2)
    
    # Blit the rotated surface onto the screen
    screen.blit(rotated_surface, blit_pos)

def draw_enhanced_hull_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int], unit: Unit, model: Model, is_highlighted: bool = False) -> None:
    """Enhanced hull base with unit identification"""
    width = int(base.radius[0] * 2 * TILE_SIZE * zoom_level)
    height = int(base.radius[1] * 2 * TILE_SIZE * zoom_level)
    
    # Ensure minimum size for visibility
    width = max(4, width)
    height = max(4, height)
    
    # Draw highlighting rectangle if highlighted
    if is_highlighted:
        highlight_width = width + 8
        highlight_height = height + 8
        highlight_rect = pygame.Rect(screen_x - highlight_width//2, screen_y - highlight_height//2, highlight_width, highlight_height)
        pygame.draw.rect(screen, (255, 255, 0), highlight_rect, 3)
    
    # Create a surface for the hull
    hull_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    hull_surface.fill((0, 0, 0, 0))  # Transparent background
    
    # Draw the outer hull
    pygame.draw.rect(hull_surface, color, (0, 0, width, height))
    
    # Draw the inner hull with unit-specific styling - scale properly with zoom
    inner_width, inner_height = max(1, int(width * 0.85)), max(1, int(height * 0.85))
    inner_rect = pygame.Rect((width - inner_width) // 2, (height - inner_height) // 2, inner_width, inner_height)
    inner_color = get_unit_inner_color(unit, model)
    pygame.draw.rect(hull_surface, inner_color, inner_rect)
    
    # Add unit identification on the surface before rotation
    draw_unit_identification_on_surface(hull_surface, width//2, height//2, min(width, height)//2, unit, model, zoom_level)
    
    # Rotate the surface
    angle_degrees = math.degrees(base.facing)
    rotated_surface = pygame.transform.rotate(hull_surface, -angle_degrees)
    
    # Calculate the position to blit the rotated surface
    blit_pos = (screen_x - rotated_surface.get_width() // 2, 
                screen_y - rotated_surface.get_height() // 2)
    
    # Blit the rotated surface onto the screen
    screen.blit(rotated_surface, blit_pos)

def get_unit_inner_color(unit: Unit, model: Model) -> Tuple[int, int, int]:
    """Get the inner color based on unit type and health"""
    # Base inner color based on unit type
    if unit.is_character:
        base_color = (255, 215, 0)  # Gold for characters
    elif unit.is_vehicle:
        base_color = (169, 169, 169)  # Silver for vehicles
    elif unit.is_monster:
        base_color = (139, 69, 19)  # Brown for monsters
    elif unit.is_psyker:
        base_color = (138, 43, 226)  # Blue violet for psykers
    elif unit.is_battleline:
        base_color = (255, 255, 255)  # White for battleline
    else:
        base_color = (220, 220, 220)  # Light gray for others
    
    # Modify color based on health
    health_percent = model.health_percent
    if health_percent < 25:
        # Heavily damaged - add red tint
        return (min(255, base_color[0] + 50), max(0, base_color[1] - 50), max(0, base_color[2] - 50))
    elif health_percent < 50:
        # Moderately damaged - add yellow tint
        return (min(255, base_color[0] + 30), min(255, base_color[1] + 30), max(0, base_color[2] - 30))
    else:
        return base_color

def draw_health_indicator(screen: pygame.Surface, screen_x: int, screen_y: int, radius: int, model: Model) -> None:
    """Draw a health indicator ring around the base"""
    if radius < 8:  # Too small for health indicator
        return
    
    health_percent = model.health_percent
    if health_percent >= 100:
        return  # No indicator needed for full health
    
    # Calculate the arc angle based on health percentage
    arc_angle = int(360 * (health_percent / 100))
    
    # Choose color based on health level
    if health_percent < 25:
        health_color = (255, 0, 0)  # Red
    elif health_percent < 50:
        health_color = (255, 165, 0)  # Orange
    elif health_percent < 75:
        health_color = (255, 255, 0)  # Yellow
    else:
        health_color = (0, 255, 0)  # Green
    
    # Draw health arc (simplified approach using lines)
    health_radius = radius + 2
    for angle in range(0, arc_angle, 5):
        angle_rad = math.radians(angle - 90)  # Start from top
        x1 = screen_x + int(health_radius * math.cos(angle_rad))
        y1 = screen_y + int(health_radius * math.sin(angle_rad))
        x2 = screen_x + int((health_radius + 3) * math.cos(angle_rad))
        y2 = screen_y + int((health_radius + 3) * math.sin(angle_rad))
        pygame.draw.line(screen, health_color, (x1, y1), (x2, y2), 2)

def draw_facing_direction(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float) -> None:
    """Draw enhanced facing direction indicator"""
    # Calculate the facing line end point
    if base.base_type == BaseType.CIRCULAR:
        radius = int(base.get_radius() * TILE_SIZE * zoom_level)
        line_length = radius
    elif base.base_type in [BaseType.ELLIPTICAL, BaseType.HULL]:
        radius = int(base.get_longest_radius() * TILE_SIZE * zoom_level)
        line_length = radius
    else:
        return  # Skip if base type is unknown
    
    end_x = screen_x + int(line_length * math.cos(base.facing))
    end_y = screen_y + int(line_length * math.sin(base.facing))
    
    # Draw the main facing line with enhanced styling
    pygame.draw.line(screen, (0, 0, 0), (screen_x, screen_y), (end_x, end_y), 3)
    
    # Draw arrowhead
    if line_length > 10:  # Only draw arrowhead if line is long enough
        arrow_length = min(8, line_length // 3)
        arrow_angle = 0.5  # radians
        
        # Calculate arrowhead points
        left_x = end_x - int(arrow_length * math.cos(base.facing - arrow_angle))
        left_y = end_y - int(arrow_length * math.sin(base.facing - arrow_angle))
        right_x = end_x - int(arrow_length * math.cos(base.facing + arrow_angle))
        right_y = end_y - int(arrow_length * math.sin(base.facing + arrow_angle))
        
        # Draw arrowhead
        pygame.draw.polygon(screen, (0, 0, 0), [(end_x, end_y), (left_x, left_y), (right_x, right_y)])

# draw_unit_bounding_box function removed - redundant with model-based hover detection

def handle_zoom(zoom_level: float, event: pygame.event.Event) -> float:
    zoom_direction = event.y  # Positive for scroll up, negative for scroll down
    new_zoom = zoom_level + (ZOOM_SPEED * zoom_direction)
    return max(MIN_ZOOM, min(MAX_ZOOM, new_zoom))

def handle_pan(keys_pressed: Dict[int, bool], offset_x: int, offset_y: int, zoom_level: float,
               viewport_width: int, viewport_height: int) -> Tuple[int, int]:
    """Pan offsets constrained so battlefield (60x44 inches) is always visible, plus at most
    one extra row/column (black background) around edges in all directions.
    """
    tile_size = int(TILE_SIZE * zoom_level)
    world_w = BATTLEFIELD_WIDTH_INCHES * tile_size
    world_h = BATTLEFIELD_HEIGHT_INCHES * tile_size

    # Pan speed independent enough of zoom
    pan_speed = max(PAN_SPEED, int(PAN_SPEED * max(1.0, zoom_level)))
    new_offset_x, new_offset_y = offset_x, offset_y

    # Support arrow keys and WASD
    if keys_pressed[pygame.K_LEFT] or keys_pressed[pygame.K_a]:
        new_offset_x += pan_speed
    if keys_pressed[pygame.K_RIGHT] or keys_pressed[pygame.K_d]:
        new_offset_x -= pan_speed
    if keys_pressed[pygame.K_UP] or keys_pressed[pygame.K_w]:
        new_offset_y += pan_speed
    if keys_pressed[pygame.K_DOWN] or keys_pressed[pygame.K_s]:
        new_offset_y -= pan_speed

    # Allow at most one extra inch beyond battlefield on each side
    extra = tile_size  # one inch

    # Horizontal bounds: left <= offset_x <= right
    left_bound = viewport_width - world_w + extra  # when panned far right, world right edge + extra at viewport right
    right_bound = -extra  # when panned far left, world left edge - extra at viewport left
    new_offset_x = max(left_bound, min(right_bound, new_offset_x))

    # Vertical bounds
    top_bound = viewport_height - world_h + extra
    bottom_bound = -extra
    new_offset_y = max(top_bound, min(bottom_bound, new_offset_y))

    return new_offset_x, new_offset_y



# Add these new classes and imports after the existing imports
from abc import ABC, abstractmethod

# Phase-specific event handler protocol
class PhaseEventHandler(Protocol):
    """Protocol for phase-specific event handlers"""
    def handle_event(self, event: pygame.event.Event, game_view: 'GameView') -> bool:
        """Handle pygame event for this phase. Returns True if event was consumed."""
        ...
    
    def get_allowed_actions(self) -> List[str]:
        """Get list of allowed actions for this phase"""
        ...

class BasePhaseHandler(ABC):
    """Base class for phase-specific event handlers"""
    
    def __init__(self, game_view: 'GameView'):
        self.game_view = game_view
        self.game = game_view.game
    
    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame event for this phase. Returns True if event was consumed."""
        pass
    
    @abstractmethod
    def get_allowed_actions(self) -> List[str]:
        """Get list of allowed actions for this phase"""
        pass
    
    def is_valid_action(self, action: str) -> bool:
        """Check if an action is valid for this phase"""
        return action in self.get_allowed_actions()

class SetupPhaseHandler(BasePhaseHandler):
    """Handles events during setup phases"""
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                # Handle setup phase advancement
                current_phase = self.game.get_current_setup_phase()
                
                # Check if we're in deployment phase and waiting for deployment input
                if (current_phase.name == 'DEPLOY_ARMIES' and 
                    hasattr(self.game, 'waiting_for_deployment_input') and 
                    self.game.waiting_for_deployment_input):
                    # Continue deployment
                    self.game.waiting_for_deployment_input = False
                    return True
                
                # Execute the current setup phase
                setup_kwargs = {
                    'player1_army_file': None,  # These would come from game config
                    'player2_army_file': None,
                    'manual_phases': True
                }
                
                # For DEPLOY_ARMIES phase, handle based on player types
                if current_phase.name == 'DEPLOY_ARMIES':
                    has_human_players = any(player.type.name == 'HUMAN' for player in self.game.players)
                    if has_human_players:
                        setup_kwargs['manual_phases'] = True
                
                # Store which phase we're executing to know when to refresh UI
                current_phase_before = self.game.get_current_setup_phase()
                
                # Handle special phase-specific UI interactions
                if current_phase_before.name == 'SELECT_MISSION_OBJECTIVES':
                    # Show mission selection dialog
                    self._show_mission_selection_dialog()
                    return True  # Don't advance phase yet, wait for dialog

                if current_phase_before.name == 'DECLARE_BATTLE_FORMATIONS':
                    # Declare Battle Formations is a 3-step interactive flow:
                    # 1) Attach Leaders (both players confirm)
                    # 2) Embark in Transports (both players confirm)
                    # 3) Allocate Reserves (both players confirm)
                    self._start_declare_battle_formations_flow()
                    return True  # Don't advance phase yet, wait for dialog
                
                self.game.execute_current_setup_phase(**setup_kwargs)
                setup_complete = self.game.advance_setup_phase()
                
                # Update UI after specific phases that change game state
                if current_phase_before.name == 'MUSTER_ARMIES':
                    # Armies were just loaded - refresh roster panes
                    self.game_view.refresh_roster_panes()
                    print("📋 UI updated after armies loaded")
                elif current_phase_before.name == 'DETERMINE_ATTACKER_AND_DEFENDER':
                    # Attacker/Defender roles determined - update titles
                    self.game_view.update_roster_pane_titles()
                    print("📋 UI updated after attacker/defender determined")
                
                if setup_complete:
                    # Final update after all setup phases complete
                    self.game_view.refresh_roster_panes()
                    self.game_view.update_roster_pane_titles()
                    print("📋 UI updated after setup completion")
                
                return True
        
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:  # Right click - show unit details
            hovered_unit, _ = self.game_view.get_hovered_unit(event.pos[0], event.pos[1])
            if hovered_unit:
                self.game_view.detailed_unit = hovered_unit
                self.game_view.detail_panel_pos = event.pos
                return True
        
        return False
    
    def _show_mission_selection_dialog(self):
        """Show the mission selection dialog for SELECT_MISSION_OBJECTIVES phase."""
        from .dialogs import MissionSelectionDialog, MissionSelectionModal
        
        # Create mission selection dialog
        inner = MissionSelectionDialog(
            self.game_view.screen.get_width(),
            self.game_view.screen.get_height()
        )

        modal = MissionSelectionModal(inner)
        self.game_view.mission_selection_dialog = modal  # keep reference for debugging

        def _apply_result(result: dict) -> None:
            combination = result["combination"]
            layout = result["layout"]
            self.game.selected_mission_info = {
                "combination_id": combination["id"],
                "primary": combination["primary"],
                "deployment": combination["deployment"],
                "layout": layout
            }
            print(f"✅ Mission selected: {combination['id']} - {combination['primary']} / {combination['deployment']} / Layout {layout}")

            # Assign Primary Mission card to both players
            try:
                from warhammer40k_ai.classes.mission_cards import (
                    TakeAndHoldPrimary,
                    TerraformPrimary,
                    LinchpinPrimary,
                    PurgeTheFoePrimary,
                    ScorchedEarthPrimary,
                    HiddenSuppliesPrimary,
                    SupplyDropPrimary,
                    BurdenOfTrustPrimary,
                    TheRitualPrimary,
                    UnexplodedOrdnancePrimary,
                    PrimaryMissionCard,
                )
                primary_name = (combination.get('primary') or '').strip().lower()
                card = None
                if primary_name == 'take and hold':
                    card = TakeAndHoldPrimary()
                elif primary_name == 'terraform':
                    card = TerraformPrimary()
                elif primary_name == 'linchpin':
                    card = LinchpinPrimary()
                elif primary_name == 'purge the foe':
                    card = PurgeTheFoePrimary()
                elif primary_name == 'scorched earth':
                    card = ScorchedEarthPrimary()
                elif primary_name == 'hidden supplies':
                    card = HiddenSuppliesPrimary()
                elif primary_name == 'supply drop':
                    card = SupplyDropPrimary()
                elif primary_name == 'burden of trust':
                    card = BurdenOfTrustPrimary()
                elif primary_name == 'the ritual':
                    card = TheRitualPrimary()
                elif primary_name == 'unexploded ordnance':
                    card = UnexplodedOrdnancePrimary()
                else:
                    class _StubPrimary(PrimaryMissionCard):
                        def __init__(self, name):
                            super().__init__(name=name, summary=f"Stub for {name}", scoring_text=f"Stub for {name}")
                        def score_at_command_phase(self, game, player) -> int:
                            return 0
                        def score_at_end_of_turn(self, game, player) -> int:
                            return 0
                    card = _StubPrimary(combination.get('primary', 'Primary'))
                for p in self.game.players:
                    p.set_primary_mission(card)
            except Exception as e:
                print(f"⚠️ Failed to assign primary mission card: {e}")

            # Execute the phase and advance
            self.game.execute_current_setup_phase()
            self.game.advance_setup_phase()

        def _cancel() -> None:
            print("📋 Mission selection cancelled - using default")
            self.game.execute_current_setup_phase()
            self.game.advance_setup_phase()

        modal.show(on_confirm=_apply_result, on_cancel=_cancel)
        # Push to modal stack
        try:
            self.game_view.dialog_manager.open(modal, modal=True)
        except Exception:
            pass

        print("📋 Mission Selection Dialog opened - choose from approved combinations A-T")

    def _show_leader_attachment_dialog(self):
        """Show the leader attachment dialog for DECLARE_BATTLE_FORMATIONS phase."""
        from .dialogs import LeaderAttachmentDialog

        dialog = LeaderAttachmentDialog(
            self.game_view.screen.get_width(),
            self.game_view.screen.get_height()
        )

        # Store dialog in game view for event handling
        self.game_view.leader_attachment_dialog = dialog

        def _on_done():
            # Apply/validate leader attachments, then proceed to transport assignments (then execute/advance)
            try:
                for p in self.game.players:
                    army = p.get_army()
                    if army:
                        army.validate_leaders()
            except Exception as e:
                print(f"⚠️ Leader attachment validation failed: {e}")
                return

            # Refresh roster panes so attached leaders collapse (once implemented)
            try:
                self.game_view.refresh_roster_panes()
            except Exception:
                pass

            # Next: declare which units start embarked within transports
            self._show_transport_assignment_dialog()

        def _on_cancel():
            # Stay in this phase; do nothing else
            return

        # Use player1's and player2's combined units for attachments (each leader can only attach within its army)
        all_units = []
        try:
            if self.game_view.player1 and self.game_view.player1.get_army():
                all_units.extend(self.game_view.player1.get_army().units)
            if self.game_view.player2 and self.game_view.player2.get_army():
                all_units.extend(self.game_view.player2.get_army().units)
        except Exception:
            pass

        dialog.show(all_units, on_confirm=_on_done, on_cancel=_on_cancel)
        dialog.visible = True
        try:
            self.game_view.dialog_manager.open(dialog, modal=True)
        except Exception:
            pass

        print("📋 Leader Attachment Dialog opened - select leaders and attach to eligible units")

    def _show_transport_assignment_dialog(self):
        """Show the transport assignment dialog for DECLARE_BATTLE_FORMATIONS phase."""
        from .dialogs import TransportAssignmentDialog

        dialog = TransportAssignmentDialog(
            self.game_view.screen.get_width(),
            self.game_view.screen.get_height()
        )
        self.game_view.transport_assignment_dialog = dialog

        # Use both armies' units; the dialog filters passengers by transport.can_transport()
        all_units = []
        try:
            if self.game_view.player1 and self.game_view.player1.get_army():
                all_units.extend(self.game_view.player1.get_army().units)
            if self.game_view.player2 and self.game_view.player2.get_army():
                all_units.extend(self.game_view.player2.get_army().units)
        except Exception:
            pass

        def _apply(assignments):
            # assignments: {transport_unit: [passenger_units]}
            try:
                # Clear any previous start-embarked assignments
                for u in list(all_units):
                    if getattr(u, "is_transport", False):
                        continue
                    if getattr(u, "embarked_in", None) is not None and (not getattr(u, "deployed", False)):
                        try:
                            t = u.embarked_in
                            if t is not None:
                                t.remove_passenger(u)
                        except Exception:
                            pass
                # Apply new
                for transport, passengers in (assignments or {}).items():
                    for pu in list(passengers or []):
                        try:
                            pu.embark(transport)
                        except Exception:
                            pass
            except Exception as e:
                print(f"⚠️ Transport assignment failed: {e}")

            # Execute the phase and advance
            self.game.execute_current_setup_phase()
            self.game.advance_setup_phase()

        def _skip():
            # Execute the phase and advance without changing transport assignments
            self.game.execute_current_setup_phase()
            self.game.advance_setup_phase()

        dialog.show(all_units, on_confirm=_apply, on_cancel=_skip)
        dialog.visible = True
        try:
            self.game_view.dialog_manager.open(dialog, modal=True)
        except Exception:
            pass

        print("📋 Transport Assignment Dialog opened - select transports and units to start embarked")

    def _start_declare_battle_formations_flow(self) -> None:
        """
        Run Declare Battle Formations as simultaneous per-player dialogs:
        - Leaders (P1 + P2 at once) -> Transports (P1 + P2 at once) -> Reserves (P1 + P2 at once)
        Only after BOTH players click Done do we proceed to the next step.
        """
        players = list(getattr(self.game, "players", []) or [])
        if not players:
            # Fallback: execute and advance (no UI)
            self.game.execute_current_setup_phase()
            self.game.advance_setup_phase()
            return

        def _army_units(p):
            try:
                a = p.get_army()
                return list(getattr(a, "units", []) or [])
            except Exception:
                return []

        if len(players) != 2:
            print("⚠️ Side-by-side formations UI currently supports exactly 2 players; falling back to sequential flow.")
            # Keep existing behavior by running as two sequential dialogs (old implementation).
            # (We intentionally do not duplicate the old nested functions here.)
            try:
                self._show_leader_attachment_dialog()
                return
            except Exception:
                self.game.execute_current_setup_phase()
                self.game.advance_setup_phase()
                return

        p_left, p_right = players[0], players[1]
        a_left, a_right = p_left.get_army(), p_right.get_army()
        if a_left is None or a_right is None:
            self.game.execute_current_setup_phase()
            self.game.advance_setup_phase()
            return

        from .dialogs.side_by_side_modal import SideBySideModal

        def _position_two(left_dlg, right_dlg) -> None:
            # Place near left/right edges; allow overlap if screen is narrow (dialogs are draggable)
            margin = 12
            left_dlg.x = margin
            left_dlg.y = 60
            try:
                left_dlg._update_title_bar()
                left_dlg._update_buttons()
            except Exception:
                pass
            right_dlg.x = max(margin, self.game_view.screen.get_width() - right_dlg.width - margin)
            right_dlg.y = 60
            try:
                right_dlg._update_title_bar()
                right_dlg._update_buttons()
            except Exception:
                pass

        # Shared helpers
        def _mark_attached_leaders_handled(army) -> None:
            try:
                for u in list(getattr(army, "units", []) or []):
                    if bool(getattr(u, "is_attached_leader", False)):
                        u.deployed = True
            except Exception:
                pass

        def _apply_transport_assignments(army, units, assignments) -> bool:
            try:
                # Clear any previous start-embarked assignments for this army
                for u in list(units):
                    if getattr(u, "is_transport", False):
                        continue
                    if getattr(u, "embarked_in", None) is not None and (not getattr(u, "deployed", False)):
                        try:
                            t = u.embarked_in
                            if t is not None:
                                t.remove_passenger(u)
                        except Exception:
                            pass

                for transport, passengers in (assignments or {}).items():
                    for pu in list(passengers or []):
                        try:
                            pu.embark(transport)
                            pu.deployed = True
                            for l in list(getattr(pu, "attached_leaders", []) or []):
                                try:
                                    l.deployed = True
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception:
                return False
            return True

        def _apply_reserves(army, decisions: Dict[str, str]) -> bool:
            try:
                roots = []
                try:
                    roots = list(getattr(army, "_reserve_group_roots")() or [])
                except Exception:
                    roots = [u for u in getattr(army, "units", []) or [] if not getattr(u, "is_attached_leader", False)]

                for root in roots:
                    rid = str(getattr(root, "_id", None) or "")
                    decision = decisions.get(rid, "deploy")
                    started = decision in ("reserves", "strategic_reserves")
                    if decision == "deploy":
                        root.set_reserve_status("deployed")
                        root.deployed = False
                    elif decision == "reserves":
                        root.set_reserve_status("reserves")
                        root.deployed = True
                    elif decision == "strategic_reserves":
                        root.set_reserve_status("strategic_reserves")
                        root.deployed = True
                    else:
                        root.set_reserve_status("deployed")
                        root.deployed = False

                    try:
                        members = list(getattr(army, "_reserve_group_members")(root) or [])
                    except Exception:
                        members = [root]
                    # Mark which units started the game in reserves (Chapter Approved round-3 destruction applies only to these).
                    for m in members:
                        try:
                            setattr(m, "_started_in_reserves", bool(started))
                        except Exception:
                            pass
                    for m in members:
                        if m is root:
                            continue
                        try:
                            m.set_reserve_status(getattr(root, "reserve_status", "deployed"))
                        except Exception:
                            try:
                                m.reserve_status = getattr(root, "reserve_status", "deployed")
                            except Exception:
                                pass
                        try:
                            m.deployed = True
                        except Exception:
                            pass
            except Exception:
                return False
            return True

        # Step 1: Leaders (both at once)
        from .dialogs import LeaderAttachmentDialog
        left_leaders = LeaderAttachmentDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
        right_leaders = LeaderAttachmentDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
        left_leaders.title = f"Attach Leaders - {p_left.name}"
        right_leaders.title = f"Attach Leaders - {p_right.name}"

        modal = SideBySideModal(self.game_view.screen.get_width(), self.game_view.screen.get_height(), left_leaders, right_leaders)
        _position_two(left_leaders, right_leaders)

        def _maybe_advance_from_leaders():
            if modal.left_done and modal.right_done:
                try:
                    self.game_view.refresh_roster_panes()
                except Exception:
                    pass
                modal.hide()
                _show_transports()

        def _left_done():
            try:
                a_left.validate_leaders()
            except Exception as e:
                print(f"⚠️ {p_left.name} leader attachment validation failed: {e}")
                return
            _mark_attached_leaders_handled(a_left)
            modal.left_done = True
            _maybe_advance_from_leaders()

        def _right_done():
            try:
                a_right.validate_leaders()
            except Exception as e:
                print(f"⚠️ {p_right.name} leader attachment validation failed: {e}")
                return
            _mark_attached_leaders_handled(a_right)
            modal.right_done = True
            _maybe_advance_from_leaders()

        left_leaders.show(_army_units(p_left), on_confirm=_left_done, on_cancel=lambda: None)
        right_leaders.show(_army_units(p_right), on_confirm=_right_done, on_cancel=lambda: None)

        modal.show()
        try:
            self.game_view.dialog_manager.open(modal, modal=True)
        except Exception:
            pass

        def _show_transports():
            from .dialogs import TransportAssignmentDialog
            ldlg = TransportAssignmentDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
            rdlg = TransportAssignmentDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
            ldlg.title = f"Transports - {p_left.name}"
            rdlg.title = f"Transports - {p_right.name}"

            m = SideBySideModal(self.game_view.screen.get_width(), self.game_view.screen.get_height(), ldlg, rdlg)
            _position_two(ldlg, rdlg)

            units_l = _army_units(p_left)
            units_r = _army_units(p_right)

            def _maybe_advance():
                if m.left_done and m.right_done:
                    try:
                        self.game_view.refresh_roster_panes()
                    except Exception:
                        pass
                    m.hide()
                    _show_reserves()

            def _l_done(assignments):
                if not _apply_transport_assignments(a_left, units_l, assignments):
                    print(f"⚠️ {p_left.name} transport assignment failed")
                    return
                m.left_done = True
                _maybe_advance()

            def _r_done(assignments):
                if not _apply_transport_assignments(a_right, units_r, assignments):
                    print(f"⚠️ {p_right.name} transport assignment failed")
                    return
                m.right_done = True
                _maybe_advance()

            ldlg.show(units_l, on_confirm=_l_done, on_cancel=lambda: None)
            rdlg.show(units_r, on_confirm=_r_done, on_cancel=lambda: None)
            m.show()
            try:
                self.game_view.dialog_manager.open(m, modal=True)
            except Exception:
                pass

        def _show_reserves():
            from .dialogs import ReservesAllocationDialog
            ldlg = ReservesAllocationDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
            rdlg = ReservesAllocationDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
            ldlg.title = f"Allocate Reserves - {p_left.name}"
            rdlg.title = f"Allocate Reserves - {p_right.name}"

            m = SideBySideModal(self.game_view.screen.get_width(), self.game_view.screen.get_height(), ldlg, rdlg)
            _position_two(ldlg, rdlg)

            def _maybe_advance():
                if m.left_done and m.right_done:
                    m.hide()
                    # Execute phase logic (validations) and advance setup phase.
                    self.game.execute_current_setup_phase()
                    self.game.advance_setup_phase()
                    try:
                        self.game_view.refresh_roster_panes()
                    except Exception:
                        pass

            def _l_done(decisions):
                if not _apply_reserves(a_left, decisions):
                    print(f"⚠️ {p_left.name} reserves allocation failed")
                    return
                m.left_done = True
                _maybe_advance()

            def _r_done(decisions):
                if not _apply_reserves(a_right, decisions):
                    print(f"⚠️ {p_right.name} reserves allocation failed")
                    return
                m.right_done = True
                _maybe_advance()

            ldlg.show(a_left, on_confirm=_l_done, on_cancel=lambda: None)
            rdlg.show(a_right, on_confirm=_r_done, on_cancel=lambda: None)
            m.show()
            try:
                self.game_view.dialog_manager.open(m, modal=True)
            except Exception:
                pass

    
    def get_allowed_actions(self) -> List[str]:
        return ["advance_setup_phase", "view_unit_details"]

class DeploymentPhaseHandler(BasePhaseHandler):
    """Handles events during deployment phase"""
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        # Per-model deployment: handle hover + facing rotation BEFORE any UI-interface consumes the event.
        if (hasattr(self.game_view, 'individual_model_movement_dialog') and
            self.game_view.individual_model_movement_dialog and
            self.game_view.individual_model_movement_dialog.visible and
            getattr(self.game_view.individual_model_movement_dialog, 'movement_type', '') == 'deploy' and
            self.game_view.individual_model_movement_dialog.selected_model_index is not None):

            # Track hover position for silhouette preview
            if event.type == pygame.MOUSEMOTION:
                x, y = event.pos
                if self.game_view.battlefield_left < x < self.game_view.battlefield_right:
                    battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)
                    self.game_view.individual_model_preview_target = (battlefield_x, battlefield_y)
                    return True
                else:
                    self.game_view.individual_model_preview_target = None

            # Mouse wheel rotates facing in 5° increments (consume to prevent zoom)
            if event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if self.game_view.battlefield_left < mx < self.game_view.battlefield_right:
                    try:
                        self.game_view.individual_model_movement_dialog.rotate_deploy_facing_degrees(float(event.y) * 5.0)
                    except Exception:
                        pass
                    return True

            # Some environments emit wheel as MOUSEBUTTONDOWN with button 4/5.
            if event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
                mx, my = pygame.mouse.get_pos()
                if self.game_view.battlefield_left < mx < self.game_view.battlefield_right:
                    try:
                        delta = 5.0 if event.button == 4 else -5.0
                        self.game_view.individual_model_movement_dialog.rotate_deploy_facing_degrees(delta)
                    except Exception:
                        pass
                    return True

        # Handle UI interface events
        if self.game_view.ui_interface and self.game_view.ui_interface.handle_event(event):
            return True
        
        # Handle deployment-specific mouse events
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._handle_deployment_click(event.pos)
        
        # Handle deployment-specific keyboard events
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                # Force complete deployment phase
                self.game_view.force_complete_deployment()
                return True
            elif event.key == pygame.K_ESCAPE:
                # Cancel current unit selection
                self.game_view.selected_unit = None
                self.game_view.left_roster_pane.selected_unit = None
                self.game_view.right_roster_pane.selected_unit = None
                return True
        
        # Handle right-click for unit details (works in all phases)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:  # Right click - show unit details
            hovered_unit, _ = self.game_view.get_hovered_unit(event.pos[0], event.pos[1])
            if hovered_unit:
                self.game_view.detailed_unit = hovered_unit
                self.game_view.detail_panel_pos = event.pos
                return True
        
        return False
    
    def _handle_deployment_click(self, mouse_pos) -> bool:
        """Handle mouse clicks during deployment phase"""
        x, y = mouse_pos

        print(f"🔍 DEBUG: _handle_deployment_click at ({x}, {y})")
        print(f"🔍 DEBUG: Left roster rect: {self.game_view.left_roster_pane.rect}")
        print(f"🔍 DEBUG: Right roster rect: {self.game_view.right_roster_pane.rect}")

        # Check roster pane clicks first
        if self.game_view.left_roster_pane.rect.collidepoint(x, y):
            print(f"🔍 DEBUG: Click is in LEFT roster pane")
            self.game_view.left_roster_pane.on_mouse_press(x, y, 1)
            self.game_view.selected_unit = self.game_view.left_roster_pane.selected_unit
            return True
        elif self.game_view.right_roster_pane.rect.collidepoint(x, y):
            print(f"🔍 DEBUG: Click is in RIGHT roster pane")
            self.game_view.right_roster_pane.on_mouse_press(x, y, 1)
            self.game_view.selected_unit = self.game_view.right_roster_pane.selected_unit
            return True
        else:
            print(f"🔍 DEBUG: Click is NOT in any roster pane")

        # Handle battlefield deployment clicks
        if (self.game_view.selected_unit and not self.game_view.selected_unit.deployed and
            self.game_view.battlefield_left < x < self.game_view.battlefield_right):
            # Always route to per-model deployment dialog for human deployments
            battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)
            battlefield_z = self.game.map.get_height_at_point(battlefield_x, battlefield_y)

            # If dialog is already visible in deploy mode, forward the click to it
            if (hasattr(self.game_view, 'individual_model_movement_dialog') and
                self.game_view.individual_model_movement_dialog and
                self.game_view.individual_model_movement_dialog.visible and
                getattr(self.game_view.individual_model_movement_dialog, 'movement_type', '') == 'deploy'):
                return self.game_view.individual_model_movement_dialog.handle_battlefield_click(
                    battlefield_x, battlefield_y, battlefield_z
                )

            # Ensure per-model deployment dialog is opened
            def on_deploy_complete(completed: bool):
                # Mark unit deployed and advance turn when completed
                unit = self.game_view.selected_unit
                if completed and unit:
                    unit.deployed = True
                    # Ensure unit is registered on the map for downstream phases
                    if not hasattr(self.game_view, 'game_map') or self.game_view.game_map is None:
                        print("❌ Deployment failed: game map unavailable to register unit")
                        return
                    if unit not in self.game_view.game_map.units:
                        self.game_view.game_map.units.append(unit)
                    current_deployment_player = self.game.get_current_deployment_player()
                    if current_deployment_player:
                        try:
                            locs = [m.get_location() for m in unit.models]
                            ux = sum(loc[0] for loc in locs) / len(locs)
                            uy = sum(loc[1] for loc in locs) / len(locs)
                            uz = sum(loc[2] for loc in locs) / len(locs)
                            unit.position = (ux, uy, uz)
                        except Exception:
                            pass
                        self.game.record_deployment_action(current_deployment_player, unit, 'deployed', getattr(unit, 'position', None))
                    self.game.advance_deployment_turn(unit)
                    # Clear selection
                    self.game_view.selected_unit = None
                    self.game_view.left_roster_pane.selected_unit = None
                    self.game_view.right_roster_pane.selected_unit = None
                # Clear flag
                try:
                    self.game_view.deployment_mode_for_selected_unit = None
                except Exception:
                    pass

            try:
                self.game_view.deployment_mode_for_selected_unit = 'per_model'
            except Exception:
                pass

            # Ensure dialog instance exists
            if not (hasattr(self.game_view, 'individual_model_movement_dialog') and self.game_view.individual_model_movement_dialog):
                try:
                    from .dialogs.individual_model_movement_dialog import IndividualModelMovementDialog
                    self.game_view.individual_model_movement_dialog = IndividualModelMovementDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
                except Exception:
                    pass

            print(f"📣 [DeploymentPhaseHandler] Opening per-model deployment dialog for {self.game_view.selected_unit.name}")
            self.game_view.individual_model_movement_dialog.show(
                self.game_view.selected_unit, 'deploy', on_deploy_complete, self.game_view.game_map, max_distance=0.0
            )

            # Immediately forward this battlefield click to place the first model
            return self.game_view.individual_model_movement_dialog.handle_battlefield_click(
                battlefield_x, battlefield_y, battlefield_z
            )
        
        return False
    
    def _handle_battlefield_deployment(self, x: int, y: int) -> bool:
        """Handle unit deployment on battlefield"""
        # Check if deployment zones are loaded
        if not hasattr(self.game, 'deployment_zones') or not self.game.deployment_zones:
            print(f"📋 Press SPACE to begin deployment sequence first")
            return True
        
        # Convert screen coordinates to game coordinates using helper method
        battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)
        
        # Attempt to deploy the unit
        # Store original model positions for potential rollback
        original_model_positions = [model.get_location() for model in self.game_view.selected_unit.models]
        
        # During deployment, use relaxed friendly unit avoidance to allow tighter formations
        # Use deployment boundary repulsors to keep formation inside mission zones/cutouts
        deployment_repulsors = self.game_view.game.get_boundary_repulsors(self.game_view.selected_unit, context='deployment')
        model_positions = self.game_view.selected_unit.calculate_model_positions(
            battlefield_x, battlefield_y, self.game_view.game_map,
            avoid_friendly_units=False, boundary_repulsors=deployment_repulsors) # TODO - add zoom back -- , 0.0, self.game_view.zoom_level)
        
        if model_positions:
            # Set model positions
            for model, position in zip(self.game_view.selected_unit.models, model_positions):
                model_x, model_y, model_z, model_facing = position
                model.set_location(model_x, model_y, model_z, model_facing)
            
            unit_x = sum(pos[0] for pos in model_positions) / len(model_positions)
            unit_y = sum(pos[1] for pos in model_positions) / len(model_positions)
            
            # Validate deployment position
            current_deployment_player = self.game.get_current_deployment_player()
            player_name = current_deployment_player.name if current_deployment_player else None
            
            if player_name and not self.game.is_valid_deployment_position(
                self.game_view.selected_unit, unit_x, unit_y, player_name):
                # Invalid position - reset and show error
                if self.game_view.selected_unit.has_infiltrate():
                    print(f"❌ Invalid deployment position for {self.game_view.selected_unit.name} (Infiltrate)")
                else:
                    print(f"❌ Invalid deployment position for {self.game_view.selected_unit.name}")
                self.game_view.reset_unit_position(self.game_view.selected_unit,
                                                 None, original_model_positions)
                return True
            
            # Valid deployment - unit position is now determined by model positions
            
            if self.game_view.game_map.place_unit(self.game_view.selected_unit):
                # Print per-model positions; include z only if non-zero
                try:
                    parts = []
                    for m in self.game_view.selected_unit.models:
                        pos = m.get_location()
                        if not pos:
                            continue
                        mx, my = pos[0], pos[1]
                        mz = pos[2] if len(pos) > 2 else 0.0
                        if abs(mz) < 1e-6:
                            parts.append(f"({mx:.1f}, {my:.1f})")
                        else:
                            parts.append(f"({mx:.1f}, {my:.1f}, {mz:.1f})")
                    positions_str = ", ".join(parts)
                    print(f"Unit {self.game_view.selected_unit.name} deployed at: {positions_str}")
                except Exception:
                    print(f"Unit {self.game_view.selected_unit.name} deployed at ({unit_x:.1f}, {unit_y:.1f})")
                self.game_view.selected_unit.deployed = True
                
                # Record deployment action
                if current_deployment_player and self.game_view.selected_unit.position:
                    self.game.record_deployment_action(current_deployment_player, 
                                                     self.game_view.selected_unit, 'deployed', 
                                                     self.game_view.selected_unit.position)
                
                # Advance to next player's deployment turn
                self.game.advance_deployment_turn(self.game_view.selected_unit)
                
                # Clear selection
                self.game_view.selected_unit = None
                self.game_view.left_roster_pane.selected_unit = None
                self.game_view.right_roster_pane.selected_unit = None
            else:
                print("Failed to place unit")
                self.game_view.reset_unit_position(self.game_view.selected_unit,
                                                 None, original_model_positions)
        
        return True
    
    def get_allowed_actions(self) -> List[str]:
        return ["select_unit", "deploy_unit", "view_unit_details", "complete_deployment"]

class BattlePhaseHandler(BasePhaseHandler):
    """Handles events during battle phases (movement, shooting, etc.)"""
    
    def __init__(self, game_view: 'GameView'):
        super().__init__(game_view)
        self.fight_phase_manager = None
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame events during battle phases"""
        if event.type == pygame.MOUSEMOTION:
            # print(f"🔍 DEBUG: BattlePhaseHandler.handle_event - MOUSEMOTION at {event.pos}")
            pass
        
        # Handle keyboard events
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                return self._handle_space_key()

        # Handle mouse events
        if event.type == pygame.MOUSEBUTTONDOWN:
            return self._handle_battle_click(event.pos, event.button)
        elif event.type == pygame.MOUSEMOTION:
            return self._handle_battle_motion(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            return self._handle_battle_release(event.pos, event.button)

        return False

    def _handle_space_key(self) -> bool:
        """Handle SPACE key for manual phase advancement"""
        current_phase = self.game.phase

        # Fight phase - check if we can skip/complete it
        if current_phase.name == 'FIGHT_PHASE':
            if self.fight_phase_manager and not self.fight_phase_manager.is_complete():
                # Force complete the fight phase
                print("⏭️ Manually completing fight phase...")
                self.fight_phase_manager._complete_fight_phase()
                return True
            else:
                # Fight phase already complete, advance to next phase
                print("⏭️ Fight phase complete, advancing to next phase...")
                return False  # Let main loop advance phase

        # For other phases, let main loop handle advancement
        else:
            print(f"⏭️ Manually advancing {current_phase.name}...")
            return False  # Let main loop advance phase

    def _handle_battle_click(self, mouse_pos, button) -> bool:
        """Handle battlefield clicks during battle phases"""
        x, y = mouse_pos

        # Check if shooting declaration dialog is in targeting mode
        if (hasattr(self.game_view, 'shooting_declaration_dialog') and
            self.game_view.shooting_declaration_dialog.is_targeting_mode):
            # Only handle left clicks for targeting
            if button != 1:  # Not a left click
                return True  # Still consume the event in targeting mode

            # Only handle clicks on the battlefield area
            if self.game_view.battlefield_left < x < self.game_view.battlefield_right:
                # Convert screen coordinates to game coordinates for targeting using helper method
                battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)

                # Handle battlefield targeting for shooting declaration
                handled = self.game_view.shooting_declaration_dialog.handle_battlefield_targeting(battlefield_x, battlefield_y)
            return True  # Consume all clicks in targeting mode, but only after trying to handle them
        
        # Handle unit selection and actions based on current phase
        if button == 1:  # Left click
            # Check roster pane clicks
            if self.game_view.left_roster_pane.rect.collidepoint(x, y):
                self.game_view.left_roster_pane.on_mouse_press(x, y, button)
                selected_unit = self.game_view.left_roster_pane.selected_unit
                if selected_unit:
                    self._handle_unit_selection(selected_unit)
                return True
            elif self.game_view.right_roster_pane.rect.collidepoint(x, y):
                self.game_view.right_roster_pane.on_mouse_press(x, y, button)
                selected_unit = self.game_view.right_roster_pane.selected_unit
                if selected_unit:
                    self._handle_unit_selection(selected_unit)
                return True
            
            # Handle battlefield clicks based on current phase
            elif self.game_view.battlefield_left < x < self.game_view.battlefield_right:
                return self._handle_battlefield_action(x, y)
        
        elif button == 3:  # Right click - show unit details
            hovered_unit, _ = self.game_view.get_hovered_unit(x, y)
            if hovered_unit:
                self.game_view.detailed_unit = hovered_unit
                self.game_view.detail_panel_pos = (x, y)
                return True

        return False
    
    def _synchronize_unit_selection(self, unit) -> None:
        """Synchronize unit selection between RosterPane and battlefield"""
        # Update the main selected unit
        self.game_view.selected_unit = unit
        
        # Update roster pane selections to match
        # Find which roster pane this unit belongs to and update its selection
        if unit.parent_army:
            if unit.parent_army.player == self.game_view.player1:
                self.game_view.left_roster_pane.selected_unit = unit
                self.game_view.right_roster_pane.selected_unit = None
            elif unit.parent_army.player == self.game_view.player2:
                self.game_view.right_roster_pane.selected_unit = unit
                self.game_view.left_roster_pane.selected_unit = None
    
    def _handle_unit_selection(self, unit) -> None:
        """Handle unit selection based on current phase"""
        current_phase = self.game.phase
        current_player = self.game.get_current_player()
        
        # Check if this unit belongs to the current player
        if not (unit.parent_army and unit.parent_army.player == current_player):
            print(f"❌ {unit.name} does not belong to current player {current_player.name}")
            return
        
        # Only allow human players to interact with units during their turn
        if current_player.type.name != 'HUMAN':
            print(f"❌ Current player {current_player.name} is AI - no unit interaction allowed")
            return
        
        # Synchronize selection across UI components
        self._synchronize_unit_selection(unit)
        
        # Handle phase-specific unit selection
        if current_phase.name == 'MOVEMENT_PHASE':
            self._handle_movement_phase_selection(unit)
        elif current_phase.name == 'SHOOTING_PHASE':
            self._handle_shooting_phase_selection(unit)
        elif current_phase.name == 'CHARGE_PHASE':
            self._handle_charge_phase_selection(unit)
        elif current_phase.name == 'FIGHT_PHASE':
            self._handle_fight_phase_selection(unit)
        else:
            print(f"❌ Unit selection not available in {current_phase.name}")
    
    def _handle_movement_phase_selection(self, unit) -> None:
        """Handle unit selection during movement phase"""
        # Movement validation is handled by the game logic
        
        def on_movement_choice(choice):
            self._handle_movement_choice(unit, choice)
        
        self.game_view.movement_choice_dialog.show(unit, on_movement_choice, self.game.map)
    
    def _handle_shooting_phase_selection(self, unit) -> None:
        """Handle unit selection during shooting phase"""
        if not unit or not unit.is_alive():
            return
        
        # Check if unit can shoot
        if unit.round_state.shot_this_round:
            print(f"❌ {unit.name} has already shot this round")
            return
        
        if unit.round_state.fell_back_this_round:
            print(f"❌ {unit.name} cannot shoot after falling back")
            return
        
        # Check if unit is engaged and can't shoot with detailed debugging
        enemy_units = self.game.map.get_enemy_units(unit)
        engaged_enemies = []

        for enemy in enemy_units:
            if enemy.is_alive() and self.game.map.is_within_engagement_range(unit, enemy):
                engaged_enemies.append(enemy.name)

        is_engaged = len(engaged_enemies) > 0

        if is_engaged:
            print(f"🔍 DEBUG: {unit.name} is in engagement range of: {', '.join(engaged_enemies)}")

            # Show detailed position information
            if unit.models:
                unit_pos = unit.models[0].get_location() if unit.models[0].is_alive else None
                print(f"🔍 DEBUG: {unit.name} position: {unit_pos}")

                for enemy_name in engaged_enemies:
                    enemy_unit = next((e for e in enemy_units if e.name == enemy_name), None)
                    if enemy_unit and enemy_unit.models:
                        enemy_pos = enemy_unit.models[0].get_location() if enemy_unit.models[0].is_alive else None
                        if unit_pos and enemy_pos:
                            distance = ((unit_pos[0] - enemy_pos[0])**2 + (unit_pos[1] - enemy_pos[1])**2)**0.5
                            print(f"🔍 DEBUG: Distance to {enemy_name}: {distance:.1f}\"")

        if is_engaged:
            # Check if unit has any weapons that can shoot while engaged
            has_eligible_weapons = False
            for model in unit.models:
                if not model.is_alive:
                    continue
                for wargear in model.wargear:
                    if wargear.is_ranged():
                        for profile in wargear.profiles.values():
                            if unit.can_shoot_in_engagement_range(self.game.map, profile):
                                has_eligible_weapons = True
                                break
                        if has_eligible_weapons:
                            break
                if has_eligible_weapons:
                    break
            
            if not has_eligible_weapons:
                print(f"❌ {unit.name} is engaged and has no weapons that can shoot in engagement range")
                return
        
        def _show_shooting_dialog():
            # Show shooting declaration dialog
            def on_shooting_complete(_declarations):
                self._clear_shooting_selection()
            self.game_view.shooting_declaration_dialog.show(unit, on_shooting_complete, self.game.map, self.game_view)

        # Firing Deck X (Transport): allow selecting embarked weapons to be treated as the transport's weapons.
        try:
            has_fd, fd_x = unit.has_firing_deck()
        except Exception:
            has_fd, fd_x = (False, 0)

        if has_fd and int(fd_x or 0) > 0 and list(getattr(unit, "transport_passengers", []) or []):
            entries = []
            per_weapon_count = {}

            try:
                passengers = list(getattr(unit, "transport_passengers", []) or [])
            except Exception:
                passengers = []

            for punit in passengers:
                # Include attached leaders' models as well
                try:
                    models = punit.get_attached_unit_models()
                except Exception:
                    models = list(getattr(punit, "models", []) or [])

                for m in models:
                    if not getattr(m, "is_alive", False):
                        continue
                    for w in list(getattr(m, "wargear", []) or []):
                        try:
                            if not w.is_ranged():
                                continue
                        except Exception:
                            continue

                        for profile_name, profile in (getattr(w, "profiles", {}) or {}).items():
                            # Explicit requirement: do not list ONE SHOT weapons for firing deck selection
                            if profile.is_one_shot():
                                continue
                            key = (str(getattr(w, "name", "Weapon")), str(profile_name))
                            c = int(per_weapon_count.get(key, 0))
                            if c >= int(fd_x or 0):
                                continue
                            per_weapon_count[key] = c + 1
                            entries.append({
                                "model": m,
                                "wargear": w,
                                "profile": profile,
                                "profile_name": profile_name,
                                "passenger_unit": punit,
                            })

            if entries:
                if not hasattr(self.game_view, "firing_deck_dialog") or self.game_view.firing_deck_dialog is None:
                    from .dialogs import FiringDeckDialog
                    self.game_view.firing_deck_dialog = FiringDeckDialog(
                        self.game_view.screen.get_width(),
                        self.game_view.screen.get_height(),
                    )

                def _on_confirm(chosen_entries):
                    try:
                        unit.apply_firing_deck_virtual_wargear(chosen_entries)
                    except Exception:
                        pass
                    _show_shooting_dialog()

                def _on_cancel():
                    try:
                        unit.clear_firing_deck_virtual_wargear()
                    except Exception:
                        pass
                    _show_shooting_dialog()

                self.game_view.firing_deck_dialog.show(unit, fd_x, entries, _on_confirm, _on_cancel)
                return

        _show_shooting_dialog()
    
    def _handle_charge_phase_selection(self, unit) -> None:
        """Handle unit selection during charge phase"""
        # Check if unit has already charged this round
        if hasattr(unit.round_state, 'attempted_charge_this_round') and unit.round_state.attempted_charge_this_round:
            print(f"❌ {unit.name} has already attempted a charge this round")
            return
        
        # Check if unit can charge (not advanced unless allowed, not fell back, etc.)
        if unit.round_state.fell_back_this_round:
            print(f"❌ {unit.name} fell back and cannot charge")
            return
        
        # Show charge declaration dialog
        def on_charge_declaration(charging_unit, target_unit):
            # Single code path: delegate all charge declaration bookkeeping + rolling to Game.
            declared = None
            try:
                declared = self.game.declare_charge(charging_unit, target_unit)
            except Exception:
                declared = None
            if not declared:
                return False

            max_charge_distance = int(declared.get("base_roll", 0) or 0)
            
            # Open individual model movement dialog for charge movement
            def on_charge_movement_complete(completed: bool):
                if completed:
                    # Check if the charge actually achieved engagement range
                    enemy_units = self.game.map.get_enemy_units(charging_unit)
                    in_engagement_range = any(
                        self.game.map.is_within_engagement_range(charging_unit, enemy_unit)
                        for enemy_unit in enemy_units if enemy_unit.is_alive()
                    )
                    
                    if in_engagement_range:
                        print(f"✅ {charging_unit.name} charge successful - achieved engagement range")
                        charging_unit.round_state.charged_this_round = True
                    else:
                        print(f"❌ {charging_unit.name} charge failed - did not achieve engagement range")
                        # Do not set charged_this_round = True for failed charges
                else:
                    print(f"❌ {charging_unit.name} charge movement failed or skipped")
                    # Do not set charged_this_round = True for failed charges

            self.game_view.individual_model_movement_dialog.show(
                charging_unit, 'charge', on_charge_movement_complete, self.game.map, max_charge_distance, target_unit
            )
            return True  # Charge declaration successful

        self.game_view.charge_declaration_dialog.show(unit, on_charge_declaration, self.game.map, self.game_view)
    
    def _handle_fight_phase_selection(self, unit) -> None:
        """Handle unit selection during fight phase"""
        current_player = self.game.get_current_player()
        opponent_player = self.game.get_opponent()
        
        # Initialize fight phase manager if not already done
        if not self.fight_phase_manager:
            self._initialize_fight_phase_manager(current_player, opponent_player)
        
        # Check if it's this player's turn to select a unit
        active_player = self.fight_phase_manager.get_active_player()
        unit_owner = unit.get_parent_army().player if unit.get_parent_army() else None
        
        if not unit_owner:
            print(f"❌ {unit.name} has no owner")
            return
        
        if active_player != unit_owner:
            print(f"❌ It's {active_player.name}'s turn to select a unit, not {unit_owner.name}'s")
            return
        
        # Check if unit is eligible to fight in current stage
        eligible_units = self.fight_phase_manager._get_eligible_units_for_player(unit_owner)
        if unit not in eligible_units:
            print(f"❌ {unit.name} is not eligible to fight in the current stage")
            return
        
        # Unit is valid - process the selection
        print(f"✅ {unit_owner.name} selected {unit.name} to fight")
        self.fight_phase_manager.unit_selected(unit, current_player, opponent_player)
    
    def _initialize_fight_phase_manager(self, current_player: Player, opponent_player: Player) -> None:
        """Initialize the fight phase manager with proper callbacks."""
        print("🎯 Initializing Fight Phase Manager")
        self.fight_phase_manager = FightPhaseManager(self.game)
        try:
            self.game.fight_phase_manager = self.fight_phase_manager
        except Exception:
            pass
        
        # Set up callbacks for human player interaction
        def on_unit_selection_required(active_player: Player, eligible_units: List[Unit], stage: FightStage):
            print(f"🔍 DEBUG: on_unit_selection_required called for {active_player.name} ({active_player.type.name})")
            print(f"🔍 DEBUG: Stage: {stage.value}, Eligible units: {[unit.name for unit in eligible_units]}")

            if active_player.type.name == 'HUMAN':
                print(f"🎯 {active_player.name} must select a unit to fight ({stage.value} stage)")
                print(f"   Eligible units: {[unit.name for unit in eligible_units]}")
                # Show fight unit selection dialog
                if hasattr(self.game_view, 'ui_interface') and self.game_view.ui_interface:
                    def on_unit_selected(selected_unit):
                        print(f"🔍 DEBUG: Unit selected callback called for {selected_unit.name}")
                        self.fight_phase_manager.unit_selected(selected_unit, current_player, opponent_player)

                    def on_cancel():
                        print("❌ Fight unit selection cancelled")

                    print(f"🔍 DEBUG: About to show fight unit selection dialog")
                    self.game_view.ui_interface.show_fight_unit_selection_dialog(
                        stage.value, eligible_units, on_unit_selected, on_cancel
                    )
                    print(f"🔍 DEBUG: Fight unit selection dialog show() called")
            else:
                # AI player - auto-select first eligible unit
                print(f"🤖 AI player {active_player.name} selecting unit automatically")
                if eligible_units:
                    selected_unit = eligible_units[0]
                    print(f"🤖 AI selected {selected_unit.name}")
                    self.fight_phase_manager.unit_selected(selected_unit, current_player, opponent_player)
        
        def on_target_selection_required(fighting_unit: Unit, eligible_targets: List[Unit], active_player: Player):
            if active_player.type.name == 'HUMAN':
                print(f"🎯 {active_player.name} must select targets for {fighting_unit.name}")
                print(f"   Eligible targets: {[target.name for target in eligible_targets]}")
                
                if len(eligible_targets) == 1:
                    # Single target - auto-select
                    target_unit = eligible_targets[0]
                    print(f"🎯 Auto-selecting single target: {target_unit.name}")
                    self._start_comprehensive_fight_sequence(fighting_unit, [target_unit], current_player, opponent_player)
                else:
                    # Multiple targets - show target selection dialog
                    print(f"🎯 Multiple targets available - showing target selection dialog")
                    
                    def on_target_selected(selected_target: Unit):
                        print(f"🎯 Player selected target: {selected_target.name}")
                        self._start_comprehensive_fight_sequence(fighting_unit, [selected_target], current_player, opponent_player)
                    
                    def on_target_selection_cancelled():
                        print("🎯 Target selection cancelled")
                        # Return to unit selection or skip this unit's turn
                        self.fight_phase_manager._switch_active_player(current_player, opponent_player)
                    
                    # Show the target selection dialog
                    self.game_view.fight_target_selection_dialog.show(
                        fighting_unit, eligible_targets, on_target_selected, on_target_selection_cancelled
                    )
            else:
                # AI player - auto-select first target for now
                print(f"🤖 AI player {active_player.name} selecting targets automatically")
                if eligible_targets:
                    target_unit = eligible_targets[0]
                    print(f"🤖 AI selected target: {target_unit.name}")
                    self._start_comprehensive_fight_sequence(fighting_unit, [target_unit], current_player, opponent_player)
        
        def on_stage_complete():
            print("✅ Fight Phase complete")
            self.fight_phase_manager = None
            try:
                self.game.fight_phase_manager = None
            except Exception:
                pass
            # Advance to next phase
            self.game.next_phase()

        def on_movement_required(movement_type: str, unit: Unit, callback):
            """Handle pile-in and consolidate movements using Individual Model Movement Dialog"""
            print(f"📍 {unit.name} needs to perform {movement_type} movement")

            # Determine max distance based on movement type
            max_distance = 3.0  # Default is 3"
            try:
                override = unit.get_fight_phase_move_distance_override(movement_type)
                if override is not None:
                    max_distance = float(override)
            except Exception:
                max_distance = 3.0

            self.game_view.individual_model_movement_dialog.show(
                unit, movement_type, callback, self.game.map, max_distance
            )

        def on_weapon_selection_required(unit: Unit, target_unit: Unit, callback):
            """Handle melee weapon selection using Melee Weapon Declaration Dialog"""
            print(f"⚔️ {unit.name} needs to select melee weapons against {target_unit.name}")

            self.game_view.melee_weapon_declaration_dialog.show(
                unit, callback, self.game.map
            )

        self.fight_phase_manager.on_unit_selection_required = on_unit_selection_required
        self.fight_phase_manager.on_target_selection_required = on_target_selection_required
        self.fight_phase_manager.on_stage_complete = on_stage_complete
        self.fight_phase_manager.on_movement_required = on_movement_required
        self.fight_phase_manager.on_weapon_selection_required = on_weapon_selection_required
        
        # Start the fight phase
        self.fight_phase_manager.start_fight_phase(current_player, opponent_player)
    
    def _start_comprehensive_fight_sequence(self, fighting_unit: Unit, target_units: List[Unit], current_player: Player, opponent_player: Player):
        """Start the comprehensive fight sequence following proper Warhammer 40k rules."""
        print(f"⚔️ Starting comprehensive fight sequence: {fighting_unit.name} vs {[t.name for t in target_units]}")
        
        # Step 1: Pile-in movement
        def on_pile_in_complete(completed: bool):
            print(f"📍 {fighting_unit.name} pile-in completed: {completed}")
            
            if len(target_units) == 1:
                # Single target - proceed directly to weapon allocation
                self._start_weapon_allocation_phase(fighting_unit, target_units[0], current_player, opponent_player)
            else:
                # Multiple targets - implement weapon/attack allocation dialog
                # TODO: Implement multi-target weapon allocation
                print("⚠️ Multi-target weapon allocation not yet implemented - using first target")
                self._start_weapon_allocation_phase(fighting_unit, target_units[0], current_player, opponent_player)
        
        # Start pile-in movement
        print(f"📍 {fighting_unit.name} needs to perform pile_in movement")
        max_distance = 3.0
        try:
            override = fighting_unit.get_fight_phase_move_distance_override("pile_in")
            if override is not None:
                max_distance = float(override)
        except Exception:
            max_distance = 3.0
        self.game_view.individual_model_movement_dialog.show(
            fighting_unit, 'pile_in', on_pile_in_complete, self.game.map, max_distance
        )
    
    def _start_weapon_allocation_phase(self, fighting_unit: Unit, target_unit: Unit, current_player: Player, opponent_player: Player):
        """Handle weapon allocation phase - each model selects one weapon (except EXTRA ATTACKS)."""
        print(f"⚔️ Starting weapon allocation: {fighting_unit.name} vs {target_unit.name}")
        
        def on_weapon_allocation_complete(weapon_declarations):
            print(f"⚔️ Weapon allocation completed with {len(weapon_declarations)} declarations")
            self._start_target_model_selection_phase(fighting_unit, target_unit, weapon_declarations, current_player, opponent_player)
        
        # Show melee weapon declaration dialog for weapon allocation
        self.game_view.melee_weapon_declaration_dialog.show(
            fighting_unit, on_weapon_allocation_complete, self.game.map
        )
    
    def _start_target_model_selection_phase(self, fighting_unit: Unit, target_unit: Unit, weapon_declarations: List, current_player: Player, opponent_player: Player):
        """Handle target model selection phase."""
        print(f"🎯 Starting target model selection phase")
        
        # NOTE: PRECISION (10e) is *not* "pick a target model up-front".
        # It is an allocation override that happens after a successful wound is allocated.
        # We handle this during attack resolution (see _resolve_single_attack) via the
        # engine-level precision_allocation_provider + PrecisionAllocationDialog.

        # Check if target unit has mixed attributes (legacy UI-only flow)
        has_mixed_attributes = self._unit_has_mixed_attributes(target_unit)
        
        if has_mixed_attributes:
            print(f"🎯 Mixed attributes detected - defender selects wound allocation")
            
            def on_wound_model_selected(selected_model):
                print(f"🎯 Wound allocation: {selected_model.name} selected to receive wounds")
                # Store the wound allocation target
                for decl in weapon_declarations:
                    decl['wound_target'] = selected_model
                self._start_attack_resolution_phase(fighting_unit, target_unit, weapon_declarations, current_player, opponent_player)
            
            def on_wound_cancelled():
                print("🎯 Wound allocation cancelled - using automatic allocation")
                self._start_attack_resolution_phase(fighting_unit, target_unit, weapon_declarations, current_player, opponent_player)
            
            self.game_view.target_model_selection_dialog.show(
                fighting_unit, target_unit, weapon_declarations, "wound_allocation",
                on_wound_model_selected, on_wound_cancelled
            )
            
        else:
            print(f"🎯 No special targeting required - proceeding to attack resolution")
            self._start_attack_resolution_phase(fighting_unit, target_unit, weapon_declarations, current_player, opponent_player)
    
    def _unit_has_mixed_attributes(self, unit: Unit) -> bool:
        """Check if a unit has models with different toughness, save, or wounds."""
        if len(unit.models) <= 1:
            return False
        
        first_model = unit.models[0]
        for model in unit.models[1:]:
            if (model.toughness != first_model.toughness or 
                model.save != first_model.save or 
                model.wounds != first_model.wounds):
                return True
        return False
    
    def _start_attack_resolution_phase(self, fighting_unit: Unit, target_unit: Unit, weapon_declarations: List, current_player: Player, opponent_player: Player):
        """Handle sequential attack resolution."""
        print(f"⚔️ Starting attack resolution phase")
        
        # Resolve attacks sequentially
        self._resolve_sequential_attacks(fighting_unit, target_unit, weapon_declarations)
        
        # Step 4: Consolidate movement
        def on_consolidate_complete(completed: bool):
            print(f"🏃 {fighting_unit.name} consolidate completed: {completed}")
            
            self.fight_phase_manager.finalize_unit_fight(fighting_unit, current_player, opponent_player)
        
        # Start consolidate movement
        print(f"🏃 {fighting_unit.name} needs to perform consolidate movement")
        max_distance = 3.0
        try:
            override = fighting_unit.get_fight_phase_move_distance_override("consolidate")
            if override is not None:
                max_distance = float(override)
        except Exception:
            max_distance = 3.0
        self.game_view.individual_model_movement_dialog.show(
            fighting_unit, 'consolidate', on_consolidate_complete, self.game.map, max_distance
        )
    
    def _resolve_sequential_attacks(self, fighting_unit: Unit, target_unit: Unit, weapon_declarations: List):
        """Resolve attacks one at a time with proper wound allocation."""
        print(f"⚔️ Resolving {len(weapon_declarations)} weapon attacks sequentially")
        
        for i, weapon_decl in enumerate(weapon_declarations):
            model = weapon_decl.get('model')
            weapon_profile = weapon_decl.get('weapon_profile')
            wound_target = weapon_decl.get('wound_target')
            
            if not model or not weapon_profile:
                continue
            
            print(f"⚔️ Attack {i+1}/{len(weapon_declarations)}: {model.name} with {weapon_profile.name}")
            
            # Get number of attacks for this weapon
            attacks = self._get_weapon_attacks(weapon_profile)
            print(f"🎲 Rolling {attacks} attacks")

            # Cache PRECISION allocation choice once per weapon profile for this sequence
            precision_choice_model = None
            try:
                if callable(getattr(weapon_profile, "is_precision", None)) and weapon_profile.is_precision():
                    precision_choice_model = self._choose_precision_allocation_target(
                        attacking_model=model,
                        target_unit=target_unit,
                        weapon_profile=weapon_profile,
                    )
            except Exception:
                precision_choice_model = None
            
            # Resolve each attack individually
            for attack_num in range(attacks):
                if not target_unit.is_alive():
                    print("💀 Target unit destroyed - remaining attacks cancelled")
                    break
                
                print(f"  Attack {attack_num + 1}/{attacks}")
                
                # Determine target model for this attack
                target_model = None
                if wound_target and wound_target.is_alive:
                    target_model = wound_target
                    print(f"  🎯 Wound allocation: {target_model.name}")
                else:
                    # Standard wound allocation - wounded models first, then closest
                    target_model = self._select_wound_target(target_unit)
                    if target_model:
                        print(f"  🎯 Auto-allocation: {target_model.name}")
                
                if not target_model:
                    print("  ❌ No valid target model - attack wasted")
                    continue
                
                # Resolve single attack
                # Note: take_damage() method automatically handles model death, FNP saves, etc.
                success = self._resolve_single_attack(
                    model,
                    weapon_profile,
                    target_model,
                    target_unit,
                    precision_choice_model=precision_choice_model,
                )
                
                # The take_damage() method has already handled model death if applicable
                # No need for manual death checking since take_damage() calls die() automatically
        
        print(f"⚔️ All attacks resolved")
    
    def _get_weapon_attacks(self, weapon_profile) -> int:
        """Get the number of attacks for a weapon profile."""
        attacks = getattr(weapon_profile, 'attacks', 1)
        if hasattr(attacks, 'resolve'):
            # Handle dice-based attacks like "D6" or "2D3"
            return attacks.resolve()
        elif isinstance(attacks, str):
            # Handle string-based attacks
            from ..utility.dice import get_roll
            return get_roll(attacks)
        else:
            return int(attacks) if attacks else 1
    
    def _select_wound_target(self, target_unit: Unit):
        """Select the target model for wound allocation following 40k rules."""
        if not target_unit.is_alive():
            return None

        # Use engine wound-allocation candidates (handles attached units: bodyguard -> leaders)
        try:
            candidates = target_unit.get_models_for_wound_allocation()
        except Exception:
            candidates = [model for model in getattr(target_unit, "models", []) if getattr(model, "is_alive", True)]
        if not candidates:
            return None

        # Human defender may choose only when rules allow; otherwise wounded models are forced.
        from ..utility.damage_allocation import DamageAllocationCtx, choose_damage_allocation_model
        try:
            defender_player = target_unit.get_parent_army().player
            is_human = bool(getattr(getattr(defender_player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        provider = getattr(self.game.map, "damage_allocation_provider", None) if getattr(self, "game", None) is not None else None
        return choose_damage_allocation_model(
            target_unit,
            candidates,
            is_human=is_human,
            provider=provider,
            ctx=DamageAllocationCtx(reason="Allocate wound", damage_source="melee"),
        )
    
    def _choose_precision_allocation_target(self, attacking_model, target_unit: Unit, weapon_profile):
        """
        If this is a PRECISION weapon attacking an Attached Unit with visible CHARACTER models,
        prompt the attacker (human) once to choose allocation target for the rest of this weapon profile.
        Returns: chosen CHARACTER model, or None to allocate normally (bodyguards).
        """
        # Attached unit root
        try:
            root = target_unit.get_attached_unit_root()
        except Exception:
            root = target_unit

        try:
            has_attached_leaders = bool(getattr(root, "attached_leaders", []) or [])
        except Exception:
            has_attached_leaders = False
        if not has_attached_leaders:
            return None

        # Collect visible CHARACTER models in the attached unit group
        try:
            all_models = root.get_models_for_collision()
        except Exception:
            all_models = list(getattr(root, "models", []) or [])

        char_models = []
        for m in all_models:
            if not getattr(m, "is_alive", True):
                continue
            pu = getattr(m, "parent_unit", None)
            if pu is None:
                continue
            if not bool(getattr(pu, "is_character", False)):
                continue
            # Visibility requirement (only if map supports it)
            gm = getattr(self, "game", None)
            game_map = getattr(gm, "map", None) if gm is not None else None
            can_see = getattr(game_map, "can_model_see_model", None) if game_map is not None else None
            if callable(can_see):
                if not can_see(attacking_model, m):
                    continue
            char_models.append(m)

        if not char_models:
            return None

        gm = getattr(self, "game", None)
        game_map = getattr(gm, "map", None) if gm is not None else None
        provider = getattr(game_map, "precision_allocation_provider", None) if game_map is not None else None

        # Human-only modal prompt; AI/headless defaults to first available CHARACTER
        try:
            attacker_player = attacking_model.parent_unit.get_parent_army().player
            is_human = bool(getattr(getattr(attacker_player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False

        if callable(provider) and is_human:
            try:
                return provider(attacking_model, root, char_models, weapon_profile)
            except Exception:
                return None
        return char_models[0]

    def _resolve_single_attack(self, attacking_model, weapon_profile, target_model, target_unit, *, precision_choice_model=None) -> bool:
        """Resolve a single attack and return True if it caused damage."""
        try:
            # Get attack stats
            weapon_skill = getattr(weapon_profile, 'skill', 4)
            strength = getattr(weapon_profile, 'strength', attacking_model.strength if hasattr(attacking_model, 'strength') else 4)
            ap = getattr(weapon_profile, 'ap', 0)
            damage = getattr(weapon_profile, 'damage', 1)
            
            # Roll to hit
            from ..utility.dice import get_roll
            hit_roll = get_roll("1D6")
            hit_needed = weapon_skill
            
            print(f"    🎯 Hit: {hit_roll} vs {hit_needed}+ = {'HIT' if hit_roll >= hit_needed else 'MISS'}")
            
            if hit_roll < hit_needed:
                return False
            
            # Roll to wound
            wound_roll = get_roll("1D6")
            wound_needed = self._calculate_wound_target(strength, target_model.toughness)
            
            print(f"    🩸 Wound: {wound_roll} vs {wound_needed}+ = {'WOUND' if wound_roll >= wound_needed else 'NO WOUND'}")
            
            if wound_roll < wound_needed:
                return False

            # PRECISION allocation override: after a successful wound, the attacker may allocate
            # that wound to a visible CHARACTER model in the Attached unit.
            if precision_choice_model is not None:
                try:
                    gm = getattr(self, "game", None)
                    game_map = getattr(gm, "map", None) if gm is not None else None
                    can_see = getattr(game_map, "can_model_see_model", None) if game_map is not None else None
                    if getattr(precision_choice_model, "is_alive", True) and (not callable(can_see) or can_see(attacking_model, precision_choice_model)):
                        target_model = precision_choice_model
                        print(f"    🎯 PRECISION allocation: {getattr(target_model, 'name', 'CHARACTER')}")
                except Exception:
                    pass
            
            # Roll save with proper AP and invulnerable consideration
            save_roll = get_roll("1D6")
            # Normalize AP (e.g., -2)
            try:
                ap_value = int(ap)
            except Exception:
                ap_value = 0
            base_save = getattr(target_model, 'save', 7)
            normal_needed = max(base_save - ap_value, 2)

            # Check invulnerable save and whether its condition applies
            effective_needed = normal_needed
            detail_text = f"{base_save}+ with AP {ap_value}"
            if hasattr(target_model, 'inv_save'):
                inv_value, inv_condition = target_model.inv_save
                if inv_value:
                    # Build a minimal attack_instance for condition checks
                    attack_instance = {'weapon_profile': weapon_profile, 'is_mortal': False}
                    cond_ok = True
                    if inv_condition and hasattr(target_model, '_check_invulnerable_save_condition'):
                        try:
                            cond_ok = target_model._check_invulnerable_save_condition(inv_condition, attack_instance)
                        except Exception:
                            cond_ok = True
                    if cond_ok and inv_value < effective_needed:
                        effective_needed = inv_value
                        detail_text = f"{inv_value}+ Invuln"

            print(f"    🛡️ Save: {save_roll} vs {effective_needed}+ ({detail_text}) = {'SAVED' if save_roll >= effective_needed else 'FAILED'}")
            
            if save_roll >= effective_needed:
                return False
            
            # Apply damage using the proper take_damage method
            if isinstance(damage, str):
                damage_dealt = get_roll(damage)
            else:
                damage_dealt = int(damage) if damage else 1
            
            print(f"    💥 Damage: {damage_dealt}")
            
            # Use the model's take_damage method which handles FNP, death, etc.
            wounds_before = target_model.wounds
            excess_damage = target_model.take_damage(damage_dealt, is_mortal=False, weapon_profile=weapon_profile)
            actual_damage = wounds_before - target_model.wounds
            
            return actual_damage > 0
            
        except Exception as e:
            print(f"    ❌ Attack resolution error: {e}")
            return False
    
    def _calculate_wound_target(self, strength: int, toughness: int) -> int:
        """Calculate the target number needed to wound."""
        if strength >= toughness * 2:
            return 2
        elif strength > toughness:
            return 3
        elif strength == toughness:
            return 4
        elif strength * 2 <= toughness:
            return 6
        else:
            return 5
    
    def get_fight_phase_status(self) -> dict:
        """Get the current fight phase status for UI display"""
        current_player = self.game.get_current_player()
        opponent = self.game.get_opponent()
        
        if self.fight_phase_manager:
            # Use fight phase manager for accurate status
            return self.fight_phase_manager.get_stage_info(current_player, opponent)
        else:
            # Fallback to old logic if manager not initialized
            current_fight_first = self.game.get_fight_first_units(current_player)
            current_remaining = self.game.get_remaining_combatant_units(current_player)
            opponent_fight_first = self.game.get_fight_first_units(opponent)
            opponent_remaining = self.game.get_remaining_combatant_units(opponent)
            
            if current_fight_first or opponent_fight_first:
                current_stage = "Fight First"
            elif current_remaining or opponent_remaining:
                current_stage = "Remaining Combatants"
            else:
                current_stage = "Complete"
            
            return {
                "current_stage": current_stage,
                "active_player": None,
                "current_player_fight_first": len(current_fight_first),
                "current_player_remaining": len(current_remaining),
                "opponent_fight_first": len(opponent_fight_first),
                "opponent_remaining": len(opponent_remaining),
                "fought_units": 0,
                "is_complete": current_stage == "Complete"
            }
    
    def _handle_movement_choice(self, unit, choice: str) -> None:
        """Handle movement choice selection using Unit's movement system"""
        from warhammer40k_ai.classes.unit import MovementAction
        
        # Map UI choices to Unit's MovementAction enum
        choice_mapping = {
            'move': MovementAction.MOVE,
            'advance': MovementAction.ADVANCE,
            'fall_back': MovementAction.FALL_BACK,
            'stationary': MovementAction.REMAIN_STATIONARY
        }
        
        if choice not in choice_mapping:
            # Transport actions (not MovementAction enum)
            if choice == 'embark' and getattr(unit, "is_transport", False):
                return self._show_transport_embark_dialog(unit)
            if choice == 'disembark' and getattr(unit, "is_transport", False):
                return self._show_transport_disembark_dialog(unit)
            print(f"❌ Invalid movement choice: {choice}")
            return
        
        # Get the unit's current engagement state
        engagement_state = unit.get_engagement_state(self.game.map)
        available_actions = unit.get_available_move_actions(engagement_state.value)
        
        # Check if the chosen action is available
        chosen_action = choice_mapping[choice]
        if chosen_action.value not in available_actions:
            print(f"❌ {choice.title()} action not available for {unit.name}")
            return
        
        # Store the chosen action for battlefield click handling
        self.game_view.selected_unit_for_movement = unit
        self.game_view.movement_action = chosen_action
        # Keep the selected model if one was previously selected
        if not hasattr(self.game_view, 'selected_model_for_movement'):
            self.game_view.selected_model_for_movement = None
        
        # Roll advance dice immediately if advancing
        if choice == 'advance':
            advance_roll = unit.prepare_advance()
            max_distance = unit.movement + advance_roll
        else:
            max_distance = unit.movement
        
        if choice == 'stationary':
            # Execute stationary action immediately (no destination needed)
            success = unit._execute_action(chosen_action.value, (0, 0, 0), self.game.map)
            if success:
                print(f"🛑 {unit.name} remains stationary")
            # Clear selection since action is complete
            self.game_view.selected_unit_for_movement = None
            self.game_view.movement_action = None
            self.game_view.selected_model_for_movement = None
        else:
            # Open individual model movement dialog
            def on_movement_complete(completed: bool):
                if completed:
                    print(f"✅ {unit.name} {choice} movement completed")
                else:
                    print(f"⏭️  {unit.name} {choice} movement skipped")
                # Clear selection after movement
                self.game_view.selected_unit_for_movement = None
                self.game_view.movement_action = None
                self.game_view.selected_model_for_movement = None
            
            self.game_view.individual_model_movement_dialog.show(
                unit, choice, on_movement_complete, self.game.map, max_distance
            )

    def _show_transport_embark_dialog(self, transport_unit) -> None:
        """Show a dialog listing only valid units that can embark into the selected transport."""
        from .dialogs import TransportEmbarkDialog

        # Compute candidates using the same checks as the dialog (but here so it stays correct even if dialog not refreshed)
        candidates = []
        if transport_unit.models and transport_unit.models[0].is_alive:
            from ..utility.aura_utils import distance_between_models_bases_3d
            t_model = transport_unit.models[0]
            for u in list(getattr(self.game.map, "units", []) or []):
                if u is None or u == transport_unit:
                    continue
                if not u.is_alive():
                    continue
                if u.get_parent_army() != transport_unit.get_parent_army():
                    continue
                if not transport_unit.can_transport(u):
                    continue
                if getattr(u.round_state, "remained_stationary_this_round", False):
                    continue
                if getattr(u.round_state, "disembarked_this_round", False):
                    continue
                ok = True
                for m in u.models:
                    if not m.is_alive:
                        continue
                    if float(distance_between_models_bases_3d(m, t_model)) > 3.0 + 1e-6:
                        ok = False
                        break
                if not ok:
                    continue
                candidates.append(u)

        if not hasattr(self.game_view, "transport_embark_dialog"):
            self.game_view.transport_embark_dialog = TransportEmbarkDialog(
                self.game_view.screen.get_width(),
                self.game_view.screen.get_height(),
            )

        def _confirm(selected_units):
            if not selected_units:
                return
            for u in selected_units:
                try:
                    u.embark(transport_unit)
                except Exception as e:
                    print(f"❌ Embark failed: {e}")

        self.game_view.transport_embark_dialog.show(transport_unit, candidates, _confirm)

    def _show_transport_disembark_dialog(self, transport_unit) -> None:
        """Show a dialog to pick which embarked unit(s) to disembark from this transport."""
        from .dialogs import TransportDisembarkDialog

        passengers = list(getattr(transport_unit, "transport_passengers", []) or [])
        if not passengers:
            print(f"❌ {transport_unit.name} has no embarked units")
            return

        if not hasattr(self.game_view, "transport_disembark_dialog"):
            self.game_view.transport_disembark_dialog = TransportDisembarkDialog(
                self.game_view.screen.get_width(),
                self.game_view.screen.get_height(),
            )

        def _confirm(selected_units):
            if not selected_units:
                return
            # Disembark sequentially to respect space/collisions
            for u in selected_units:
                try:
                    u.disembark(game_map=self.game.map, transport_unit=transport_unit, destroyed_transport=False, emergency=False, current_turn=self.game.turn)
                except Exception as e:
                    print(f"❌ Disembark failed: {e}")

        self.game_view.transport_disembark_dialog.show(transport_unit, passengers, _confirm)
    
    def _handle_battlefield_action(self, x: int, y: int) -> bool:
        """Handle battlefield actions based on current battle phase"""
        current_phase = self.game.phase
        
        # Phase-specific actions
        if current_phase.name == 'MOVEMENT_PHASE':
            return self._handle_movement_action(x, y)
        elif current_phase.name == 'SHOOTING_PHASE':
            return self._handle_shooting_action(x, y)
        elif current_phase.name == 'CHARGE_PHASE':
            return self._handle_charge_action(x, y)
        elif current_phase.name == 'FIGHT_PHASE':
            return self._handle_fight_action(x, y)
        
        return False
    
    def _handle_movement_action(self, x: int, y: int) -> bool:
        """Handle movement phase actions using Unit's movement system"""
        # Check if individual model movement dialog is active
        if (hasattr(self.game_view, 'individual_model_movement_dialog') and
            self.game_view.individual_model_movement_dialog.visible):
            # Handle battlefield click for individual model movement using helper method
            battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)
            battlefield_z = self.game.map.get_height_at_point(battlefield_x, battlefield_y)
            
            return self.game_view.individual_model_movement_dialog.handle_battlefield_click(
                battlefield_x, battlefield_y, battlefield_z
            )
        
        # Check if we clicked on a model first for selection
        clicked_model = self.game_view.get_model_at_position(x, y)
        if clicked_model:
            # Try to select this unit for movement and track the specific model
            clicked_unit = clicked_model.parent_unit
            self.game_view.selected_unit = clicked_unit
            self.game_view.selected_model_for_movement = clicked_model  # Track the specific model
            self._handle_unit_selection(clicked_unit)
            return True
        
        # Old unit-level movement handling removed - now using Individual Model Movement Dialog for all movement
        
        return False
    
    # Old movement validation method removed - now using Individual Model Movement Dialog for all movement
    
    def _handle_shooting_action(self, x: int, y: int) -> bool:
        """Handle shooting phase actions - allow clicking on units to select them for shooting"""
        # Check if we're in targeting mode from the shooting declaration dialog
        if (hasattr(self.game_view, 'shooting_declaration_dialog') and 
            self.game_view.shooting_declaration_dialog.is_targeting_mode):
            # Let the dialog handle the targeting (expects game coords)
            battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)
            return self.game_view.shooting_declaration_dialog.handle_battlefield_targeting(battlefield_x, battlefield_y)
        
        # If not in targeting mode, handle unit selection
        clicked_unit = self.game_view.get_unit_at_position(x, y)
        if clicked_unit:
            # Try to select this unit for shooting
            self.game_view.selected_unit = clicked_unit
            self._handle_unit_selection(clicked_unit)
            return True
        
        return False
    
    def _show_weapon_choice_dialog(self, unit):
        """Show weapon selection dialog for the unit"""
        if not hasattr(self.game_view, 'weapon_choice_dialog'):
            from .dialogs import WeaponChoiceDialog
        self.game_view.weapon_choice_dialog = WeaponChoiceDialog(
                self.game_view.screen.get_width(), 
                self.game_view.screen.get_height()
            )
        
        def on_weapon_choice(weapon_profile):
            self.game_view.selected_weapon_profile = weapon_profile
            # Clear any previous shooting selection state
            if hasattr(self.game_view, 'selected_shooting_models'):
                self.game_view.selected_shooting_models = []
        
        self.game_view.weapon_choice_dialog.show(unit, on_weapon_choice, self.game.map)
    
    def _clear_shooting_selection(self):
        """Clear shooting selection state"""
        if hasattr(self.game_view, 'selected_weapon_profile'):
            self.game_view.selected_weapon_profile = None
        if hasattr(self.game_view, 'selected_shooting_models'):
            self.game_view.selected_shooting_models = []
    
    def _validate_shooting_target(self, shooting_unit, target_unit, weapon_profile) -> dict:
        """Validate if shooting unit can target the enemy unit with the selected weapon"""
        # Check if target is an enemy unit
        if target_unit.get_parent_army() == shooting_unit.get_parent_army():
            return {"valid": False, "reason": "Cannot target friendly units"}
        
        # Check if target is alive
        if not target_unit.is_alive():
            return {"valid": False, "reason": "Target unit is destroyed"}
        
        # Check if unit can shoot (not advanced unless allowed, not fell back, etc.)
        if shooting_unit.round_state.advanced_this_round:
            # Unit method already checks both weapon-specific and unit-specific abilities
            if not shooting_unit.can_shoot_after_advance(weapon_profile):
                return {"valid": False, "reason": "Unit advanced and cannot shoot with this weapon"}
        
        if shooting_unit.round_state.fell_back_this_round:
            if not shooting_unit.can_shoot_after_fall_back(weapon_profile):
                return {"valid": False, "reason": "Unit fell back and cannot shoot with this weapon"}
        
        # Check if any models in the unit can shoot this weapon at the target
        models_in_range = []
        for model in shooting_unit.models:
            if not model.is_alive:
                continue
                
            # Check if this model has the weapon
            has_weapon = False
            for wargear in model.wargear:
                if weapon_profile.parent_wargear == wargear:
                    has_weapon = True
                    break
            
            if not has_weapon:
                continue
            
            # Check range to target
            closest_target_model, distance = model.return_closest_model_in_unit(target_unit)
            if distance <= weapon_profile.range.max:
                # Check line of sight (placeholder)
                if self._has_line_of_sight(model, closest_target_model):
                    models_in_range.append(model)
        
        if not models_in_range:
            return {"valid": False, "reason": "No models in range with line of sight"}
        
        # Check engagement range restrictions
        is_engaged = any(self.game.map.is_within_engagement_range(shooting_unit, enemy)
                        for enemy in self.game.map.get_enemy_units(shooting_unit) if enemy.is_alive())
        
        if is_engaged and not shooting_unit.can_shoot_in_engagement_range(weapon_profile):
            return {"valid": False, "reason": "Unit is engaged and weapon cannot shoot in engagement range"}
        
        # Check Lone Operative restriction
        if target_unit.has_lone_operative():
            # Check if any shooting model is within 12 inches of the Lone Operative unit
            any_model_in_range = False
            for model in models_in_range:
                closest_target_model, distance = model.return_closest_model_in_unit(target_unit)
                if distance <= 12.0:
                    any_model_in_range = True
                    break
            
            if not any_model_in_range:
                return {"valid": False, "reason": "Lone Operative unit can only be targeted within 12 inches"}
        
        return {"valid": True, "reason": f"{len(models_in_range)} models can shoot"}
    
    def _has_line_of_sight(self, shooting_model, target_model) -> bool:
        """Placeholder line of sight check - always returns True for now"""
        # TODO: Implement proper line of sight calculations considering:
        # - Terrain blocking
        # - Other units blocking  
        # - Model height and visibility
        # - Special rules (e.g., Indirect Fire)
        return True
    
    def _handle_charge_action(self, x: int, y: int) -> bool:
        """Handle charge phase actions"""
        # Check if individual model movement dialog is active (for charge movement)
        if (hasattr(self.game_view, 'individual_model_movement_dialog') and
            self.game_view.individual_model_movement_dialog.visible):
            # Handle battlefield click for individual model movement during charge using helper method
            battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)
            battlefield_z = self.game.map.get_height_at_point(battlefield_x, battlefield_y)

            return self.game_view.individual_model_movement_dialog.handle_battlefield_click(
                battlefield_x, battlefield_y, battlefield_z
            )

        # Always check if a unit was clicked on the battlefield first
        clicked_unit = self.game_view.get_unit_at_position(x, y)
        current_player = self.game.get_current_player()
        if clicked_unit and clicked_unit.get_parent_army() and clicked_unit.get_parent_army().player == current_player:
            self.game_view.selected_unit = clicked_unit
            self._synchronize_unit_selection(clicked_unit)
            self._handle_charge_phase_selection(clicked_unit)
            return True
        # If no unit was clicked, fall back to selected unit (e.g., from RosterPane)
        if self.game_view.selected_unit:
            if self.game_view.selected_unit.get_parent_army() and self.game_view.selected_unit.get_parent_army().player == current_player:
                self._handle_charge_phase_selection(self.game_view.selected_unit)
                return True
        return False
    
    def _handle_fight_action(self, x: int, y: int) -> bool:
        """Handle fight phase actions"""
        current_player = self.game.get_current_player()
        opponent_player = self.game.get_opponent()
        
        # Initialize fight phase manager if not already done
        if not self.fight_phase_manager:
            self._initialize_fight_phase_manager(current_player, opponent_player)
        
        # If fight phase manager is still None after initialization, fight phase is complete
        if not self.fight_phase_manager:
            print("✅ Fight phase is complete - no actions available")
            return False
        
        # Always check if a unit was clicked on the battlefield first
        clicked_unit = self.game_view.get_unit_at_position(x, y)
        
        # If a unit was clicked, check if it's a friendly unit to select for fighting
        if clicked_unit and clicked_unit.get_parent_army():
            unit_owner = clicked_unit.get_parent_army().player
            active_player = self.fight_phase_manager.get_active_player()
            
            # Check if this is the active player's unit
            if unit_owner == active_player:
                self.game_view.selected_unit = clicked_unit
                self._synchronize_unit_selection(clicked_unit)
                self._handle_fight_phase_selection(clicked_unit)
                return True
            else:
                print(f"❌ It's {active_player.name}'s turn to select a unit, not {unit_owner.name}'s")
                return False
        
        # If no unit was clicked, fall back to selected unit (e.g., from RosterPane)
        if self.game_view.selected_unit:
            unit_owner = self.game_view.selected_unit.get_parent_army().player if self.game_view.selected_unit.get_parent_army() else None
            active_player = self.fight_phase_manager.get_active_player()
            
            if unit_owner == active_player:
                self._handle_fight_phase_selection(self.game_view.selected_unit)
                return True
            else:
                print(f"❌ It's {active_player.name}'s turn to select a unit, not {unit_owner.name}'s")
                return False
        
        return False
    
    def get_allowed_actions(self) -> List[str]:
        current_phase = self.game.phase
        current_player = self.game.get_current_player()
        
        # Base actions available in all phases
        base_actions = ["view_unit_details", "advance_phase"]
        
        # Only allow unit selection for human players
        if current_player.type.name == 'HUMAN':
            base_actions.append("select_unit")
        
        # Phase-specific actions
        if current_phase.name == 'MOVEMENT_PHASE':
            if current_player.type.name == 'HUMAN':
                return base_actions + ["move_unit", "advance_unit", "remain_stationary", "fall_back"]
            else:
                return base_actions + ["ai_movement_phase"]
        elif current_phase.name == 'SHOOTING_PHASE':
            if current_player.type.name == 'HUMAN':
                return base_actions + ["select_weapon", "target_unit", "cancel_shooting"]
            else:
                return base_actions + ["ai_shooting_phase"]
        elif current_phase.name == 'CHARGE_PHASE':
            if current_player.type.name == 'HUMAN':
                return base_actions + ["declare_charge", "charge_move"]
            else:
                return base_actions + ["ai_charge_phase"]
        elif current_phase.name == 'FIGHT_PHASE':
            if current_player.type.name == 'HUMAN':
                return base_actions + ["pile_in", "fight", "consolidate"]
            else:
                return base_actions + ["ai_fight_phase"]
        else:
            return base_actions
    
    def _handle_battle_motion(self, mouse_pos) -> bool:
        """Handle mouse motion during battle phases"""
        x, y = mouse_pos
        # print(f"🔍 DEBUG: _handle_battle_motion called with ({x}, {y})")

        # Individual model movement tracking now has priority over old systems

        # Update hover states for UI components
        if hasattr(self.game_view, 'shooting_declaration_dialog') and self.game_view.shooting_declaration_dialog.visible:
            self.game_view.shooting_declaration_dialog.update_hover((x, y))
            return True

        if hasattr(self.game_view, 'movement_choice_dialog') and self.game_view.movement_choice_dialog.visible:
            self.game_view.movement_choice_dialog.update_hover((x, y))
            return True

        # Old unit-level movement tracking removed - now using Individual Model Movement Dialog for all movement

        # Track mouse position for individual model movement preview


        if (hasattr(self.game_view, 'individual_model_movement_dialog') and
            self.game_view.individual_model_movement_dialog.visible and
            self.game_view.individual_model_movement_dialog.selected_model_index is not None):

            print(f"🔍 DEBUG: Individual model movement tracking active at ({x}, {y})")

            # Check if mouse is over battlefield area
            if self.game_view.battlefield_left < x < self.game_view.battlefield_right:
                # Convert to game coordinates using helper method
                battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)

                # Store mouse position for individual model movement preview
                self.game_view.individual_model_preview_target = (battlefield_x, battlefield_y)
                print(f"🔍 DEBUG: Set preview target to ({battlefield_x:.1f}, {battlefield_y:.1f})")
                return True
            else:
                # Clear preview when mouse leaves battlefield
                self.game_view.individual_model_preview_target = None
                # print(f"🔍 DEBUG: Cleared preview target (mouse outside battlefield)")
        else:
            # Debug why tracking isn't active
            if hasattr(self.game_view, 'individual_model_movement_dialog'):
                dialog = self.game_view.individual_model_movement_dialog
                # print(f"🔍 DEBUG: Dialog exists - visible: {dialog.visible}, selected_model: {dialog.selected_model_index}")
            else:
                print(f"🔍 DEBUG: No individual_model_movement_dialog found")

        # Update roster pane hovers
        if self.game_view.left_roster_pane.rect.collidepoint(x, y):
            return True
        elif self.game_view.right_roster_pane.rect.collidepoint(x, y):
            return True

        return False
    
    def _handle_battle_release(self, mouse_pos, button) -> bool:
        """Handle mouse button release during battle phases"""
        # Currently no specific handling needed for mouse release
        return False

class PhaseManager:
    """Manages phase-specific event handling"""
    
    def __init__(self, game_view: 'GameView'):
        self.game_view = game_view
        self.game = game_view.game
        # Initialize phase handlers
        self.setup_handler = SetupPhaseHandler(game_view)
        self.deployment_handler = DeploymentPhaseHandler(game_view)
        self.prebattle_handler = PreBattlePhaseHandler(game_view)
        self.battle_handler = BattlePhaseHandler(game_view)
        
        # Movement system state
        from .dialogs import MovementChoiceDialog, IndividualModelMovementDialog
        from .dialogs.coherency_violation_dialog import CoherencyViolationDialog
        self.game_view.movement_choice_dialog = MovementChoiceDialog(game_view.screen.get_width(), game_view.screen.get_height())
        self.game_view.individual_model_movement_dialog = IndividualModelMovementDialog(game_view.screen.get_width(), game_view.screen.get_height())
        self.game_view.coherency_violation_dialog = CoherencyViolationDialog(game_view.screen.get_width(), game_view.screen.get_height())
        self.game_view.selected_unit_for_movement = None
        self.game_view.movement_action = None  # MovementAction enum value
        self.game_view.movement_preview_target = None  # For real-time movement preview
        
        # Shooting system state
        from .dialogs import ShootingDeclarationDialog
        self.game_view.shooting_declaration_dialog = ShootingDeclarationDialog(game_view.screen.get_width(), game_view.screen.get_height())
        
        # Charge system state
        from .dialogs import ChargeDeclarationDialog
        self.game_view.charge_declaration_dialog = ChargeDeclarationDialog(game_view.screen.get_width(), game_view.screen.get_height())
        
        # Melee weapon declaration system state
        from .dialogs import MeleeWeaponDeclarationDialog
        self.game_view.melee_weapon_declaration_dialog = MeleeWeaponDeclarationDialog(game_view.screen.get_width(), game_view.screen.get_height())
        
        # Fight target selection dialog
        from .dialogs.fight_target_selection_dialog import FightTargetSelectionDialog
        self.game_view.fight_target_selection_dialog = FightTargetSelectionDialog(game_view.screen.get_width(), game_view.screen.get_height())
        
        # Target model selection dialog
        from .dialogs.target_model_selection_dialog import TargetModelSelectionDialog
        self.game_view.target_model_selection_dialog = TargetModelSelectionDialog(game_view.screen.get_width(), game_view.screen.get_height())
    
    def get_current_handler(self) -> BasePhaseHandler:
        """Get the appropriate handler for the current game phase"""
        if self.game.is_in_setup_phase():
            current_setup_phase = self.game.get_current_setup_phase()
            if current_setup_phase.name == 'DEPLOY_ARMIES':
                return self.deployment_handler
            elif current_setup_phase.name == 'RESOLVE_PREBATTLE_RULES':
                # Start the scout phase if not already started for this phase
                if not hasattr(self.prebattle_handler, 'scout_phase_started') or not self.prebattle_handler.scout_phase_started:
                    print("🔍 Starting scout phase...")
                    self.prebattle_handler.start_scout_phase()
                    self.prebattle_handler.scout_phase_started = True
                return self.prebattle_handler
            else:
                return self.setup_handler
        elif self.game.is_deployment_phase():
            return self.deployment_handler
        else:
            # Battle phases
            # Auto-start fight phase if we're in fight phase and it hasn't been started
            if self.game.is_fight_phase():
                if not hasattr(self.battle_handler, 'fight_phase_started') or not self.battle_handler.fight_phase_started:
                    print("⚔️ Auto-starting fight phase...")
                    current_player = self.game.get_current_player()
                    opponent_player = self.game.get_opponent()
                    self.battle_handler._initialize_fight_phase_manager(current_player, opponent_player)
                    self.battle_handler.fight_phase_started = True
            else:
                # Reset fight phase flag when not in fight phase
                if hasattr(self.battle_handler, 'fight_phase_started'):
                    self.battle_handler.fight_phase_started = False
            return self.battle_handler
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Route event to appropriate phase handler"""
        # Global dialog routing (modal stack) always goes first.
        try:
            if hasattr(self.game_view, "dialog_manager") and self.game_view.dialog_manager:
                if self.game_view.dialog_manager.handle_event(event):
                    return True
        except Exception:
            pass

        handler = self.get_current_handler()
        handler_name = handler.__class__.__name__

        # Debug: Log which handler is being used
        # TODO: Uncomment for event debugging
        # if event.type in [pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION]:
        #     event_name = {
        #         pygame.KEYDOWN: "KEYDOWN",
        #         pygame.MOUSEBUTTONDOWN: "MOUSEBUTTONDOWN",
        #         pygame.MOUSEBUTTONUP: "MOUSEBUTTONUP",
        #         pygame.MOUSEMOTION: "MOUSEMOTION"
        #     }.get(event.type, f"TYPE_{event.type}")
        #     print(f"🔍 DEBUG: PhaseManager - Routing {event_name} to {handler_name}")

        result = handler.handle_event(event)

        # TODO: Uncomment for event debugging
        # if event.type in [pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION]:
        #     print(f"🔍 DEBUG: PhaseManager - {handler_name} returned {result}")

        return result
    
    def get_current_allowed_actions(self) -> List[str]:
        """Get allowed actions for current phase"""
        handler = self.get_current_handler()
        return handler.get_allowed_actions()
    
    def is_action_allowed(self, action: str) -> bool:
        """Check if an action is allowed in the current phase"""
        return action in self.get_current_allowed_actions()

    def check_unit_coherency_after_movement(self, unit: 'Unit'):
        """
        Check unit coherency after movement completion and handle violations.

        This should be called after a unit completes its movement to ensure
        coherency is maintained according to Warhammer 40k rules.
        """
        from warhammer40k_ai.utility.calcs import validate_unit_coherency_after_movement

        # Get final positions of all models
        final_positions = []
        for model in unit.models:
            if model.is_alive:
                final_positions.append(model.get_location())

        # Validate coherency
        is_coherent, non_coherent_models = validate_unit_coherency_after_movement(unit, final_positions)

        if not is_coherent:
            # Movement must END in coherency. Do not remove models for movement-caused incoherency.
            print(f"❌ {unit.name} is not in coherency after movement (non-coherent models: {non_coherent_models}). "
                  f"Movement ending out of coherency is not allowed.")
        else:
            print(f"✅ {unit.name} maintains coherency after movement")

    def _on_coherency_resolution(self, models_removed: bool):
        """Called when coherency violation dialog is complete"""
        if models_removed:
            print("✅ Coherency violations resolved")
        else:
            print("❌ Coherency resolution cancelled")


def draw_individual_model_movement_range(screen: pygame.Surface, model, movement_type: str, max_distance: float, zoom_level: float, offset_x: int, offset_y: int, game_map=None) -> None:
    """Draw a visual indicator showing the movement range for an individual model"""
    if not model or not model.is_alive or max_distance <= 0:
        return

    # Get model position
    model_location = model.get_location()
    current_position = (model_location[0], model_location[1], model_location[2])

    # Convert model position to screen coordinates (respect zoom and UI scaling)
    center_x = int(current_position[0] * TILE_SIZE * zoom_level + offset_x)
    center_y = int(current_position[1] * TILE_SIZE * zoom_level + offset_y)

    # Calculate radius in screen pixels (respect scaling)
    radius = int(max_distance * TILE_SIZE * zoom_level)

    # Choose color based on movement type
    if movement_type == 'scout':
        color = (0, 255, 255, 64)  # Cyan for scout moves
        border_color = (0, 200, 200)
    elif movement_type == 'move':
        color = (0, 255, 0, 64)  # Green for normal move
        border_color = (0, 200, 0)
    elif movement_type == 'advance':
        color = (255, 255, 0, 64)  # Yellow for advance
        border_color = (200, 200, 0)
    elif movement_type == 'fall_back':
        color = (255, 165, 0, 64)  # Orange for fall back
        border_color = (200, 130, 0)
    elif movement_type == 'pile_in':
        color = (255, 0, 255, 64)  # Magenta for pile-in
        border_color = (200, 0, 200)
    elif movement_type == 'consolidate':
        color = (255, 128, 255, 64)  # Light magenta for consolidate
        border_color = (200, 100, 200)
    else:
        color = (128, 128, 128, 64)  # Gray for other types
        border_color = (100, 100, 100)

    # Special handling for pile-in movement
    if movement_type == 'pile_in' and game_map:
        draw_pile_in_range(screen, model, current_position, max_distance, zoom_level, offset_x, offset_y, game_map)
    else:
        # Standard circular range for other movement types
        if radius > 0:
            # Create a surface with per-pixel alpha for the range circle
            range_surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(range_surface, color, (radius, radius), radius)

            # Blit the transparent range circle onto the battlefield
            screen.blit(range_surface, (center_x - radius, center_y - radius))

            # Draw the border circle
            pygame.draw.circle(screen, border_color, (center_x, center_y), radius, 2)


def draw_pile_in_range(screen: pygame.Surface, model, current_position: tuple, max_distance: float, 
                      zoom_level: float, offset_x: int, offset_y: int, game_map) -> None:
    """
    Draw pile-in movement range visualization showing intersection of:
    1. 3" movement circle
    2. Area closer to closest enemy model
    """
    from ..utility.constants import BASE_CONTACT_EPSILON
    
    # Find the closest enemy model
    closest_enemy = None
    closest_distance = float('inf')
    
    for unit in game_map.units:
        if unit.faction == model.parent_unit.faction or not unit.is_alive() or not unit.deployed:
            continue
        for enemy_model in unit.models:
            if not enemy_model.is_alive:
                continue
                
            from ..utility.aura_utils import distance_between_models_bases_3d
            distance = float(distance_between_models_bases_3d(model, enemy_model))
            if distance < closest_distance:
                closest_distance = distance
                closest_enemy = enemy_model
    
    if not closest_enemy:
        # No enemies found - draw standard circle
        radius = int(max_distance * TILE_SIZE * zoom_level)
        center_x = int(current_position[0] * TILE_SIZE * zoom_level + offset_x)
        center_y = int(current_position[1] * TILE_SIZE * zoom_level + offset_y)
        
        if radius > 0:
            range_surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(range_surface, (255, 0, 255, 64), (radius, radius), radius)
            screen.blit(range_surface, (center_x - radius, center_y - radius))
            pygame.draw.circle(screen, (200, 0, 200), (center_x, center_y), radius, 2)
        return
    
    # Get enemy position
    enemy_location = closest_enemy.get_location()
    enemy_position = (enemy_location[0], enemy_location[1])
    
    print(f"🔍 DEBUG: Drawing pile-in range for {model.name} vs closest enemy {closest_enemy.name} at {closest_distance:.2f}\"")
    
    # Draw the intersection of movement circle and "closer to enemy" area
    draw_pile_in_intersection(screen, current_position[:2], enemy_position, closest_distance, 
                             max_distance, zoom_level, offset_x, offset_y)
    
    # Draw helpful indicators
    draw_pile_in_indicators(screen, current_position[:2], enemy_position, closest_distance,
                           max_distance, zoom_level, offset_x, offset_y, closest_enemy.name)


def draw_pile_in_intersection(screen: pygame.Surface, model_pos: tuple, enemy_pos: tuple, 
                             current_distance: float, pile_in_distance: float,
                             zoom_level: float, offset_x: int, offset_y: int) -> None:
    """
    Draw the intersection area using polygon approximation for the complex shape
    """
    import numpy as np
    import math
    
    # Convert positions to screen coordinates
    model_screen_x = int(model_pos[0] * TILE_SIZE * zoom_level + offset_x)
    model_screen_y = int(model_pos[1] * TILE_SIZE * zoom_level + offset_y)
    enemy_screen_x = int(enemy_pos[0] * TILE_SIZE * zoom_level + offset_x)
    enemy_screen_y = int(enemy_pos[1] * TILE_SIZE * zoom_level + offset_y)
    
    # Calculate pile-in circle radius in screen pixels
    pile_in_radius = int(pile_in_distance * TILE_SIZE * zoom_level)
    
    # Generate points for the valid pile-in area
    valid_points = []
    
    # Sample points around the pile-in circle
    num_samples = 180  # More samples for smoother curve
    for i in range(num_samples):
        angle = 2 * math.pi * i / num_samples
        
        # Point on the pile-in circle
        test_x = model_screen_x + pile_in_radius * math.cos(angle)
        test_y = model_screen_y + pile_in_radius * math.sin(angle)
        
        # Convert back to game coordinates to test distance
        test_game_x = (test_x - offset_x) / (TILE_SIZE * zoom_level)
        test_game_y = (test_y - offset_y) / (TILE_SIZE * zoom_level)
        
        # Calculate distance from this test point to enemy
        test_distance = math.sqrt((test_game_x - enemy_pos[0])**2 + (test_game_y - enemy_pos[1])**2)
        
        # Only include points that are closer to the enemy than current distance
        if test_distance < current_distance:
            valid_points.append((test_x, test_y))
    
    # Draw the valid area if we have enough points
    if len(valid_points) >= 3:
        # Create surface for the filled area
        pile_in_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        
        # Draw filled polygon for valid pile-in area
        pygame.draw.polygon(pile_in_surface, (255, 0, 255, 80), valid_points)  # Bright magenta
        screen.blit(pile_in_surface, (0, 0))
        
        # Draw border outline
        if len(valid_points) > 1:
            pygame.draw.polygon(screen, (255, 0, 255), valid_points, 3)  # Thick magenta border
    
    # Always draw the full pile-in circle as reference (dimmed)
    pygame.draw.circle(screen, (200, 0, 200, 30), (model_screen_x, model_screen_y), pile_in_radius, 2)


def draw_pile_in_indicators(screen: pygame.Surface, model_pos: tuple, enemy_pos: tuple,
                           current_distance: float, pile_in_distance: float,
                           zoom_level: float, offset_x: int, offset_y: int, enemy_name: str) -> None:
    """
    Draw helpful indicators for pile-in movement
    """
    # Convert positions to screen coordinates
    model_screen_x = int(model_pos[0] * TILE_SIZE * zoom_level + offset_x)
    model_screen_y = int(model_pos[1] * TILE_SIZE * zoom_level + offset_y)
    enemy_screen_x = int(enemy_pos[0] * TILE_SIZE * zoom_level + offset_x)
    enemy_screen_y = int(enemy_pos[1] * TILE_SIZE * zoom_level + offset_y)
    
    # Draw line to closest enemy
    pygame.draw.line(screen, (255, 255, 0), (model_screen_x, model_screen_y), 
                    (enemy_screen_x, enemy_screen_y), 2)  # Yellow line
    
    # Draw enemy highlight circle
    enemy_highlight_radius = int(0.5 * TILE_SIZE * zoom_level)  # 0.5" radius highlight
    pygame.draw.circle(screen, (255, 255, 0), (enemy_screen_x, enemy_screen_y), 
                      enemy_highlight_radius, 3)  # Yellow highlight
    
    # Draw distance text if zoom level is reasonable
    if zoom_level > 0.5:
        font = pygame.font.Font(None, 24)
        
        # Distance text
        distance_text = f"{current_distance:.1f}\""
        text_surface = font.render(distance_text, True, (255, 255, 255))
        
        # Position text at midpoint of line
        mid_x = (model_screen_x + enemy_screen_x) // 2
        mid_y = (model_screen_y + enemy_screen_y) // 2 - 15
        
        # Background rectangle for text
        text_rect = text_surface.get_rect(center=(mid_x, mid_y))
        pygame.draw.rect(screen, (0, 0, 0, 180), text_rect.inflate(6, 4))
        screen.blit(text_surface, text_rect)
        
        # Enemy name text
        enemy_text = f"Closest: {enemy_name}"
        enemy_surface = font.render(enemy_text, True, (255, 255, 0))
        enemy_rect = enemy_surface.get_rect(center=(enemy_screen_x, enemy_screen_y - 40))
        pygame.draw.rect(screen, (0, 0, 0, 180), enemy_rect.inflate(6, 4))
        screen.blit(enemy_surface, enemy_rect)


# Old draw_movement_range function removed - now using Individual Model Movement Dialog for all movement


# Old draw_movement_path_preview function removed - now using Individual Model Movement Dialog for all movement


def draw_weapon_ranges(screen: pygame.Surface, unit, selected_weapon_profile, zoom_level: float, offset_x: int, offset_y: int) -> None:
    """Draw visual indicators showing the weapon range for each model that has the selected weapon"""
    if not selected_weapon_profile or not unit or not unit.models:
        return
    
    # TILE_SIZE is defined at the top of this file
    weapon_range = selected_weapon_profile.range.max
    if weapon_range <= 0:
        return  # Skip melee weapons
    
    # Choose color based on weapon type and special rules
    if selected_weapon_profile.is_pistol():
        range_color = (255, 100, 255, 64)  # Magenta for pistols
        border_color = (200, 50, 200)
    elif selected_weapon_profile.is_assault():
        range_color = (255, 255, 0, 64)  # Yellow for assault
        border_color = (200, 200, 0)  
    elif selected_weapon_profile.is_heavy():
        range_color = (255, 128, 0, 64)  # Orange for heavy
        border_color = (200, 100, 0)
    elif selected_weapon_profile.is_rapid_fire():
        range_color = (0, 255, 255, 64)  # Cyan for rapid fire
        border_color = (0, 200, 200)
    else:
        range_color = (0, 255, 0, 64)  # Green for other ranged weapons
        border_color = (0, 200, 0)
    
    # Draw range circle for each model that has this weapon
    models_with_weapon = []
    for model in unit.models:
        if not model.is_alive:
            continue
        
        # Check if this model has the selected weapon
        has_weapon = False
        for wargear in model.wargear:
            if wargear == selected_weapon_profile.parent_wargear:
                has_weapon = True
                break
        
        if has_weapon:
            models_with_weapon.append(model)
            
            # Get model position
            model_pos = model.get_location()
            
            # Convert model position to screen coordinates
            center_x = int(model_pos[0] * TILE_SIZE * zoom_level + offset_x)
            center_y = int(model_pos[1] * TILE_SIZE * zoom_level + offset_y)
            
            # Calculate radius in screen pixels
            radius = int(weapon_range * TILE_SIZE * zoom_level)
            
            if radius > 0:
                # Create a surface with per-pixel alpha for the range circle
                range_surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(range_surface, range_color, (radius, radius), radius)
                
                # Blit the transparent range circle onto the battlefield
                screen.blit(range_surface, (center_x - radius, center_y - radius))
                
                # Draw the border circle with thinner line for individual models
                pygame.draw.circle(screen, border_color, (center_x, center_y), radius, 1)
    
    # Draw weapon information text
    if models_with_weapon:
        try:
            font = pygame.font.SysFont('Arial', max(14, int(16 * zoom_level)), bold=True)
            weapon_name = selected_weapon_profile.parent_wargear.name
            if len(selected_weapon_profile.parent_wargear.profiles) > 1:
                weapon_name += f" ({selected_weapon_profile.name})"
            
            info_text = f"{weapon_name} - Range {weapon_range}\" ({len(models_with_weapon)} models)"
            text_surface = font.render(info_text, True, border_color)
            
            # Position text at top of screen
            text_rect = text_surface.get_rect()
            text_rect.center = (screen.get_width() // 2, 30)
            
            # Draw background for text
            bg_rect = text_rect.inflate(20, 10)
            pygame.draw.rect(screen, (0, 0, 0, 128), bg_rect)
            pygame.draw.rect(screen, border_color, bg_rect, 2)
            
            screen.blit(text_surface, text_rect)
        except:
            # Fallback if font creation fails
            pass

class PreBattlePhaseHandler(BasePhaseHandler):
    """Handles events during the RESOLVE_PREBATTLE_RULES phase (e.g., Scout moves)"""
    def __init__(self, game_view: 'GameView'):
        super().__init__(game_view)
        self.scout_units_queue = []  # List of (unit, player) tuples
        self.current_scout_unit = None
        self.current_scout_player = None  # Track current player for cache clearing
        self.awaiting_battlefield_click = False
        self.scout_callback = None
        self.scout_distance = 0
        self.mouse_pos = None  # Track mouse position for visual feedback

    def start_scout_phase(self):
        """Initialize the queue of eligible human scout units."""
        print("🔍 Initializing scout phase...")
        self.scout_units_queue = []
        self.current_scout_unit = None
        self.current_scout_player = None  # Reset player tracking
        self.awaiting_battlefield_click = False
        self.scout_callback = None
        self.scout_distance = 0
        self.mouse_pos = None
        # Get all eligible human scout units in correct order
        game = self.game_view.game
        
        # During setup phase, use first_turn_player_index instead of current_player_index
        if game.first_turn_player_index is not None:
            first_turn_player = game.players[game.first_turn_player_index]
        else:
            # Fallback to attacker if first turn not determined yet
            first_turn_player = game.get_attacker() if game.attacker_index is not None else game.players[0]
        
        players_in_order = [first_turn_player] + [p for p in game.players if p != first_turn_player]
        print(f"🔍 DEBUG: Scout phase players in order: {[p.name for p in players_in_order]}")
        
        for player in players_in_order:
            if player.type.name == 'HUMAN' and player.get_army():
                print(f"🔍 DEBUG: Checking {player.name}'s units for scout ability")
                for unit in player.get_army().units:
                    has_scout, scout_distance = unit.has_scout()
                    print(f"🔍 DEBUG: {unit.name} - has_scout={has_scout}, deployed={unit.deployed}, reserve_status={unit.reserve_status}, scout_move_made={getattr(unit, 'scout_move_made', False)}")
                    if has_scout and unit.deployed and unit.reserve_status == 'deployed' and not getattr(unit, 'scout_move_made', False):
                        self.scout_units_queue.append((unit, player, scout_distance))
                        print(f"🔍 DEBUG: Added {unit.name} to scout queue")
        
        print(f"🔍 DEBUG: Scout queue has {len(self.scout_units_queue)} units: {[unit.name for unit, player, distance in self.scout_units_queue]}")
        self._next_scout_unit()

    def _next_scout_unit(self):
        print(f"🔍 DEBUG: _next_scout_unit called, queue has {len(self.scout_units_queue)} units")
        if self.scout_units_queue:
            unit, player, scout_distance = self.scout_units_queue.pop(0)
            print(f"🔍 DEBUG: Processing next scout unit: {unit.name} (Player: {player.name})")

            # Check if player has changed and clear enemy model cache if so
            if self.current_scout_player != player:
                if self.current_scout_player is not None:  # Not the first unit

                    clear_enemy_model_cache(id(self.game_view.game.map))
                    print(f"🔍 Scout phase player switched to {player.name} - cleared enemy model cache")
                self.current_scout_player = player

            self.current_scout_unit = unit
            self.scout_distance = scout_distance
            self.awaiting_battlefield_click = False
            self._show_scout_dialog(unit)
        else:
            # print(f"🔍 DEBUG: Scout queue is empty, scout phase complete")
            self.current_scout_unit = None
            self.current_scout_player = None  # Reset player tracking
            self.awaiting_battlefield_click = False
            self.scout_callback = None
            self.scout_distance = 0
            self.mouse_pos = None
            print("✅ All human SCOUT moves complete. Press SPACE to continue.")

    def _show_scout_dialog(self, unit):
        # print(f"🔍 DEBUG: _show_scout_dialog called for {unit.name}")
        def on_scout_choice(choice):
            # print(f"🔍 DEBUG: Scout choice for {unit.name}: {choice}")
            if choice == 'scout':
                # Open individual model movement dialog for scout movement
                def on_scout_movement_complete(completed: bool):
                    # print(f"🔍 DEBUG: Scout movement complete for {unit.name}: completed={completed}")
                    # print(f"🔍 DEBUG: Setting scout_move_made=True for {unit.name}")
                    if completed:
                        print(f"✅ {unit.name} scout movement completed")
                        unit.scout_move_made = True
                    else:
                        print(f"⏭️  {unit.name} scout movement skipped")
                        unit.scout_move_made = True
                    # print(f"🔍 DEBUG: Calling _next_scout_unit() to proceed to next unit")
                    self._next_scout_unit()

                self.game_view.individual_model_movement_dialog.show(
                    unit, 'scout', on_scout_movement_complete, self.game_view.game.map, self.scout_distance
                )
            elif choice == 'skip':
                unit.scout_move_made = True
                print(f"✅ {unit.name} scout move skipped")
                self._next_scout_unit()
            elif choice == 'defer':
                print(f"⏸️  {unit.name} scout decision deferred - moving to end of current player's queue")
                # Move this unit to the end of the current player's units in the queue
                player = None
                for p in self.game_view.game.players:
                    if unit in p.army.units:
                        player = p
                        break

                if player:
                    # Find where to insert: after the last unit of the same player
                    insert_position = 0
                    last_same_player_position = -1

                    for i in range(len(self.scout_units_queue)):
                        _, queue_player, _ = self.scout_units_queue[i]
                        if queue_player == player:
                            last_same_player_position = i

                    # Insert after the last unit of the same player
                    insert_position = last_same_player_position + 1

                    self.scout_units_queue.insert(insert_position, (unit, player, self.scout_distance))
                    # print(f"🔍 DEBUG: {unit.name} added back to position {insert_position} (after last {player.name} unit). Queue now has {len(self.scout_units_queue)} units")

                    # Debug: show current queue
                    # queue_debug = [(u.name, p.name) for u, p, _ in self.scout_units_queue]
                    # print(f"🔍 DEBUG: Current queue: {queue_debug}")

                self._next_scout_unit()
        # print(f"🔍 DEBUG: About to call ui_interface.show_scout_dialog for {unit.name}")
        self.game_view.ui_interface.show_scout_dialog(unit, on_scout_choice, self.game_view.game.map)
        # print(f"🔍 DEBUG: ui_interface.show_scout_dialog completed for {unit.name}")
        # print(f"🔍 DEBUG: Scout dialog visible: {self.game_view.ui_interface.scout_choice_dialog.visible}")

    def _validate_scout_destination(self, unit, destination: Tuple[float, float]) -> dict:
        """Validate if a destination is valid for a scout move using pathfinding."""
        game_x, game_y = destination

        # Check if destination is within battlefield bounds
        battlefield_width, battlefield_height = self.game_view.game.get_battlefield_size()
        if game_x < 0 or game_x >= battlefield_width or game_y < 0 or game_y >= battlefield_height:
            return {'valid': False, 'reason': 'Outside battlefield bounds'}

        # Use pathfinding to validate the destination

        path_result = get_unit_movement_path_preview(
            unit,
            (game_x, game_y),
            self.scout_distance,
            self.game_view.game.map
        )

        # If pathfinding fails, fall back to basic validation
        if not path_result['valid']:
            return path_result

        # Additional SCOUT-specific validation: 9" restriction from enemy units
        # Use the unit's prospective formation at this destination and measure base-to-base closest-point distance.
        snapshot = [m.get_location() for m in unit.models]
        try:
            prospective = unit.calculate_model_positions(game_x, game_y, self.game_view.game.map, avoid_friendly_units=True)
        finally:
            for m, loc in zip(unit.models, snapshot):
                if loc:
                    m.set_location(*loc)

        if not prospective:
            return {'valid': False, 'reason': 'No valid formation at destination'}

        from ..utility.aura_utils import distance_between_bases_3d
        enemy_units = self.game_view.game.get_enemy_units(unit.get_parent_army().player)
        enemy_models = [em for eu in enemy_units if eu.is_alive() and eu.deployed for em in eu.models if em.is_alive]
        for idx, (x, y, z, facing) in enumerate(prospective):
            if idx >= len(unit.models):
                break
            mb = unit._create_potential_base(x, y, z, facing, model=unit.models[idx])
            for em in enemy_models:
                d = float(distance_between_bases_3d(mb, em.model_base))
                if d < 9.0:
                    return {'valid': False, 'reason': f'Too close to {em.parent_unit.name} ({d:.1f}\")'}

        return path_result

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            # print(f"🔍 DEBUG: PreBattlePhaseHandler received MOUSEMOTION event at {event.pos}")
            pass

        # Track mouse position for visual feedback
        if event.type == pygame.MOUSEMOTION and self.awaiting_battlefield_click:
            self.mouse_pos = event.pos
        
        # Handle mouse motion for path preview during individual model movement
        if event.type == pygame.MOUSEMOTION:
            # print(f"🔍 DEBUG: PreBattlePhaseHandler mouse motion event received")

            # Debug: Check individual model movement dialog visibility
            has_dialog = hasattr(self.game_view, 'individual_model_movement_dialog')
            # print(f"🔍 DEBUG: has_dialog={has_dialog}")

            if has_dialog:
                dialog_obj = self.game_view.individual_model_movement_dialog
                dialog_visible = dialog_obj.visible
                dialog_unit = getattr(dialog_obj, 'unit', None)
                unit_name = dialog_unit.name if dialog_unit else None
                # print(f"🔍 DEBUG: Mouse motion - has_dialog={has_dialog}, dialog_visible={dialog_visible}, dialog_unit={unit_name}")

                if dialog_visible:
                    x, y = event.pos
                    # print(f"🔍 DEBUG: PreBattlePhaseHandler individual model mouse motion at ({x}, {y})")

                    # Check if mouse is over battlefield area
                    if self.game_view.battlefield_left < x < self.game_view.battlefield_right:
                        # Convert to game coordinates using helper method
                        battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)

                        # Store mouse position for individual model movement preview
                        self.game_view.individual_model_preview_target = (battlefield_x, battlefield_y)
                        # print(f"🔍 DEBUG: PreBattlePhaseHandler set individual_model_preview_target to ({battlefield_x:.1f}, {battlefield_y:.1f})")
                        return True
                    else:
                        # Clear preview when mouse leaves battlefield
                        self.game_view.individual_model_preview_target = None
                        # print(f"🔍 DEBUG: PreBattlePhaseHandler cleared individual_model_preview_target (mouse outside battlefield)")
                        return True
            else:
                pass
                # print(f"🔍 DEBUG: Mouse motion - has_dialog={has_dialog}")

        # Handle battlefield clicks for individual model movement during scout phase
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # Left click
            x, y = event.pos
            
            # Check if clicking on battlefield area
            if self.game_view.battlefield_left < x < self.game_view.battlefield_right:
                # Check if individual model movement dialog is active
                if (hasattr(self.game_view, 'individual_model_movement_dialog') and
                    self.game_view.individual_model_movement_dialog.visible):
                    # Convert screen coordinates to game coordinates using helper method
                    battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)
                    battlefield_z = self.game_view.game.map.get_height_at_point(battlefield_x, battlefield_y)
                    
                    # Handle battlefield click for individual model movement
                    return self.game_view.individual_model_movement_dialog.handle_battlefield_click(
                        battlefield_x, battlefield_y, battlefield_z
                    )
        
        # Allow SPACE to skip to next phase if all done
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            if not self.scout_units_queue and not self.awaiting_battlefield_click:
                print("Proceeding to next phase...")
                return False  # Let the main loop advance the phase
        return False

    def draw_scout_visual_feedback(self, battlefield_surface: pygame.Surface):
        """Draw visual feedback for scout moves on the battlefield surface with pathfinding."""
        if not self.awaiting_battlefield_click or not self.current_scout_unit or not self.mouse_pos:
            return

        # Get unit position from first model
        first_model = None
        for model in self.current_scout_unit.models:
            if model.is_alive:
                first_model = model
                break

        if not first_model:
            return

        unit_pos = first_model.get_location()
        if not unit_pos:
            return

        # Convert unit position to battlefield surface coordinates (no roster pane offset)
        unit_surface_x = int(unit_pos[0] * TILE_SIZE * self.game_view.zoom_level + self.game_view.offset_x)
        unit_surface_y = int(unit_pos[1] * TILE_SIZE * self.game_view.zoom_level + self.game_view.offset_y)

        # Get mouse position in game coordinates for validation using helper method
        mouse_x, mouse_y = self.mouse_pos
        mouse_game_x, mouse_game_y = self.game_view.screen_to_game_coords(mouse_x, mouse_y)

        # Convert mouse position to battlefield surface coordinates
        mouse_surface_x = int(mouse_game_x * TILE_SIZE * self.game_view.zoom_level + self.game_view.offset_x)
        mouse_surface_y = int(mouse_game_y * TILE_SIZE * self.game_view.zoom_level + self.game_view.offset_y)

        # Use pathfinding to get movement preview
        from warhammer40k_ai.utility.calcs import get_movement_path_preview

        path_result = get_movement_path_preview(
            self.current_scout_unit,
            (mouse_game_x, mouse_game_y),
            self.scout_distance,
            self.game_view.game.map
        )

        # Choose color based on pathfinding result
        if path_result['valid']:
            color = (0, 255, 255)  # Cyan for valid path
            alpha = 100
        else:
            color = (255, 165, 0)  # Orange for invalid path
            alpha = 150

        # Draw scout range circle around unit (only if unit is visible on battlefield surface)
        if (0 <= unit_surface_x <= battlefield_surface.get_width() and 0 <= unit_surface_y <= battlefield_surface.get_height()):
            circle_radius = int(self.scout_distance * TILE_SIZE * self.game_view.zoom_level)
            pygame.draw.circle(battlefield_surface, (*color, 50), (unit_surface_x, unit_surface_y), circle_radius, 2)

        # Draw pathfinding path if available
        if path_result['path'] and len(path_result['path']) > 1:
            # Convert path points to screen coordinates
            path_points = []
            for point in path_result['path']:
                screen_x = int(point[0] * TILE_SIZE * self.game_view.zoom_level + self.game_view.offset_x)
                screen_y = int(point[1] * TILE_SIZE * self.game_view.zoom_level + self.game_view.offset_y)
                path_points.append((screen_x, screen_y))

            # Draw the path as connected lines
            if len(path_points) > 1:
                pygame.draw.lines(battlefield_surface, (*color, alpha), False, path_points, 3)

                # Draw small circles at path waypoints
                for point in path_points[1:-1]:  # Skip start and end points
                    pygame.draw.circle(battlefield_surface, (*color, alpha//2), point, 3)
        else:
            # Fallback to straight line if no path available
            distance = ((mouse_game_x - unit_pos[0]) ** 2 + (mouse_game_y - unit_pos[1]) ** 2) ** 0.5
            if distance <= self.scout_distance:
                pygame.draw.line(battlefield_surface, (*color, alpha),
                               (unit_surface_x, unit_surface_y), (mouse_surface_x, mouse_surface_y), 3)

        # Draw destination indicator with actual model base footprint at mouse position
        # Get the first alive model to determine base size
        first_model = None
        for model in self.current_scout_unit.models:
            if model.is_alive:
                first_model = model
                break

        if first_model:
            self.game_view._draw_model_base_preview(battlefield_surface, first_model,
                                                  mouse_game_x, mouse_game_y, color)
        
        # Draw distance text using pathfinding results
        try:
            font = pygame.font.Font(None, 24)
            if path_result['path']:
                distance_text = f"{path_result['distance']:.1f}\""
            else:
                # Fallback to straight-line distance
                distance = ((mouse_game_x - unit_pos[0]) ** 2 + (mouse_game_y - unit_pos[1]) ** 2) ** 0.5
                distance_text = f"{distance:.1f}\" (direct)"

            text_surface = font.render(distance_text, True, color)
            text_rect = text_surface.get_rect(center=(mouse_surface_x, mouse_surface_y - 20))
            battlefield_surface.blit(text_surface, text_rect)
        except:
            pass  # Skip text rendering if font fails

        # Draw validation message using pathfinding results
        if not path_result['valid']:
            try:
                error_font = pygame.font.Font(None, 20)
                error_text = path_result['reason']
                # Wrap text if too long
                if len(error_text) > 40:
                    error_text = error_text[:37] + "..."
                error_surface = error_font.render(error_text, True, (255, 255, 255))
                error_rect = error_surface.get_rect(center=(mouse_surface_x, mouse_surface_y + 20))
                # Draw background for error text
                bg_rect = error_rect.inflate(10, 5)
                pygame.draw.rect(battlefield_surface, (0, 0, 0, 180), bg_rect)
                battlefield_surface.blit(error_surface, error_rect)
            except:
                pass  # Skip error text rendering if font fails

    def get_allowed_actions(self) -> List[str]:
        return ["scout_move", "skip_scout", "advance_setup_phase"]
