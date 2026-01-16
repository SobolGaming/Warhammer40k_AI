"""
RosterPane component for displaying army rosters and unit selection.
"""

import pygame
from typing import List, Optional, Tuple, Dict

from ...classes.unit import Unit
from ...classes.player import Player
from ...classes.game import Game

# Import icon drawing functions from ui_utils to avoid circular imports
from ..ui_utils import (
    get_unit_color_variation,
    draw_character_icon,
    draw_vehicle_icon,
    draw_monster_icon,
    draw_battleline_icon,
    draw_aircraft_icon,
    draw_beast_icon,
    draw_psyker_icon,
    draw_generic_icon,
    draw_aspect_shrine_token_icon
)

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

# Button dimensions
ROSTER_PANE_BUTTON_HEIGHT = 80

class RosterPane(pygame.sprite.Sprite):
    """UI Panel for displaying army rosters and handling unit selection."""
    
    def __init__(self, left, bottom, width, height, roster, player_name):
        super().__init__()
        self.rect = pygame.Rect(left, bottom, width, height)
        self.roster = roster
        self.player_name = player_name
        self.selected_unit = None
        self.hovered_unit = None
        self.background_color = PANEL_BG
        # Use system fonts for better clarity
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
        self.button_height = ROSTER_PANE_BUTTON_HEIGHT
        self.button_width = width - 20  # 10px padding on each side
        self.buttons = []
        self.scroll_offset = 0
        self.max_scroll = 0
        # Display names (used to disambiguate duplicate unit names, e.g. "Bloodletters 1")
        self._unit_display_names: Dict[str, str] = {}
        self.create_buttons()
        self.game_map = None
        self.game_view = None  # Reference to GameView for deployment dialog
        
        # Find the player object from the units
        self.player = None
        if roster:  # Only try to find player if roster has units
            for unit in roster:
                if unit.parent_army and unit.parent_army.player:
                    self.player = unit.parent_army.player
                    break

    def create_buttons(self):
        """Create button rectangles for each unit in the roster."""
        # Recompute button width from current rect and clamp scroll to new max
        self.button_width = self.rect.width - 20
        total_content_height = len(self.roster) * (self.button_height + 5) + 40  # +40 for header
        visible_height = self.rect.height
        self.max_scroll = max(0, total_content_height - visible_height)
        # Clamp scroll_offset to new bounds
        if self.scroll_offset > self.max_scroll:
            self.scroll_offset = self.max_scroll
        if self.scroll_offset < 0:
            self.scroll_offset = 0

        self.buttons = []
        # Precompute disambiguated display names for units in this roster.
        # If multiple units share a name, enumerate them in roster order: "Name 1", "Name 2", ...
        self._unit_display_names = {}
        try:
            name_counts: Dict[str, int] = {}
            for u in self.roster:
                nm = getattr(u, 'name', '')
                name_counts[nm] = name_counts.get(nm, 0) + 1
            name_running: Dict[str, int] = {}
            for u in self.roster:
                nm = getattr(u, 'name', '')
                uid = getattr(u, '_id', None) or str(id(u))
                if name_counts.get(nm, 0) > 1:
                    name_running[nm] = name_running.get(nm, 0) + 1
                    self._unit_display_names[uid] = f"{nm} {name_running[nm]}"
                else:
                    self._unit_display_names[uid] = nm
        except Exception:
            self._unit_display_names = {}

        for i, unit in enumerate(self.roster):
            button_rect = pygame.Rect(
                self.rect.left + 10,
                self.rect.top + 40 + i * (self.button_height + 5) - self.scroll_offset,  # Account for header
                self.button_width,
                self.button_height
            )
            self.buttons.append((button_rect, unit))

    def get_unit_display_name(self, unit: Unit) -> str:
        """Return a roster-specific display name, enumerating duplicates (e.g. 'Bloodletters 1')."""
        try:
            uid = getattr(unit, '_id', None) or str(id(unit))
            return self._unit_display_names.get(uid, getattr(unit, 'name', 'Unit'))
        except Exception:
            return getattr(unit, 'name', 'Unit')

    def scroll(self, delta):
        """Handle scrolling in the roster pane"""
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset + delta))
        self.create_buttons()  # Recreate buttons with new scroll offset

    def on_mouse_press(self, x, y, button):
        """Handle mouse press events in the roster pane."""
        #print(f"🔍 DEBUG: RosterPane.on_mouse_press called at ({x}, {y}) button={button} for {self.player_name}")

        if button == 1:  # Left mouse button
            for button_rect, unit in self.buttons:
                if button_rect.collidepoint(x, y):
                    print(f"🔍 DEBUG: Clicked on unit {unit.name}")
                    print(f"🔍 DEBUG: unit.deployed = {unit.deployed}")
                    print(f"🔍 DEBUG: game_view exists = {self.game_view is not None}")
                    print(f"🔍 DEBUG: ui_interface exists = {self.game_view.ui_interface is not None if self.game_view else False}")

                    # Check if this is during deployment phase and unit is not deployed
                    if not unit.deployed and self.game_view and self.game_view.ui_interface:
                        # Units that start embarked (Declare Battle Formations) cannot be deployed separately.
                        try:
                            if getattr(unit, "is_embarked", False) or getattr(unit, "embarked_in", None) is not None:
                                t = getattr(unit, "embarked_in", None)
                                tname = getattr(t, "name", "Transport") if t is not None else "a Transport"
                                print(f"🚫 {self.get_unit_display_name(unit)} is embarked in {tname} and cannot be deployed separately.")
                                return
                        except Exception:
                            pass
                        # Check if deployment zones are loaded (deployment has officially started)
                        has_deployment_zones = hasattr(self.game_view.game, 'deployment_zones')
                        zones_exist = self.game_view.game.deployment_zones if has_deployment_zones else None
                        print(f"🔍 DEBUG: has_deployment_zones = {has_deployment_zones}")
                        print(f"🔍 DEBUG: zones_exist = {zones_exist is not None if zones_exist else False}")

                        if not has_deployment_zones or not zones_exist:
                            print(f"📋 Press SPACE to begin deployment sequence first")
                            return
                        
                        # Check if it's this player's turn to deploy
                        can_deploy = self.game_view.game.can_player_deploy_unit(self.player)
                        print(f"🔍 DEBUG: can_player_deploy_unit = {can_deploy}")

                        if not can_deploy:
                            # Not this player's turn - show message
                            print(f"❌ Not {self.player_name}'s turn to deploy")
                            return
                        
                        # Deployment: only units not in reserves can be placed.
                        try:
                            if getattr(unit, "reserve_status", "deployed") in ("reserves", "strategic_reserves"):
                                print(f"🚫 {self.get_unit_display_name(unit)} is in reserves and cannot be deployed during Deployment.")
                                return
                        except Exception:
                            pass
                        # Attached leaders deploy with their bodyguard
                        try:
                            if bool(getattr(unit, "is_attached_leader", False)):
                                print(f"🚫 {self.get_unit_display_name(unit)} is an attached Leader and deploys with its Bodyguard.")
                                return
                        except Exception:
                            pass

                        # Directly open per-model deployment dialog (no deploy/reserves choice here)
                        print(f"🟢 Deploying {unit.name} - enabling per-model deployment mode")
                        unit.set_reserve_status('deployed')
                        unit.deployed = False  # Ready for deployment but not yet placed
                        self.selected_unit = unit
                        self.game_view.selected_unit = unit
                        try:
                            self.game_view.deployment_mode_for_selected_unit = 'per_model'
                        except Exception:
                            pass

                        if not hasattr(self.game_view, 'individual_model_movement_dialog') or not self.game_view.individual_model_movement_dialog:
                            from ..dialogs.individual_model_movement_dialog import IndividualModelMovementDialog
                            self.game_view.individual_model_movement_dialog = IndividualModelMovementDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())

                        def on_deploy_complete(completed: bool):
                            if completed:
                                unit.deployed = True
                                # Attached leaders deploy together
                                try:
                                    for l in list(getattr(unit, "attached_leaders", []) or []):
                                        l.deployed = True
                                        l.reserve_status = getattr(unit, "reserve_status", "deployed")
                                except Exception:
                                    pass
                                if not hasattr(self.game_view, 'game_map') or self.game_view.game_map is None:
                                    print("❌ Deployment failed: game map unavailable to register unit")
                                    return
                                if unit not in self.game_view.game_map.units:
                                    self.game_view.game_map.units.append(unit)
                                current_deployment_player = self.game_view.game.get_current_deployment_player()
                                if current_deployment_player:
                                    try:
                                        locs = [m.get_location() for m in unit.models]
                                        ux = sum(loc[0] for loc in locs) / len(locs)
                                        uy = sum(loc[1] for loc in locs) / len(locs)
                                        uz = sum(loc[2] for loc in locs) / len(locs)
                                        unit.position = (ux, uy, uz)
                                    except Exception:
                                        pass
                                    self.game_view.game.record_deployment_action(current_deployment_player, unit, 'deployed', getattr(unit, 'position', None))
                                self.game_view.game.advance_deployment_turn(unit)
                                self.selected_unit = None
                                self.game_view.selected_unit = None
                            else:
                                print(f"⏭️  {unit.name} deployment cancelled")

                            try:
                                if hasattr(self.game_view, 'deployment_mode_for_selected_unit'):
                                    self.game_view.deployment_mode_for_selected_unit = None
                            except Exception:
                                pass

                        print(f"📣 Opening per-model deployment dialog for {unit.name}")
                        self.game_view.individual_model_movement_dialog.show(unit, 'deploy', on_deploy_complete, self.game_view.game_map, max_distance=0.0)
                        return
                    else:
                        # Normal unit selection (for deployed units or non-deployment phases)
                        self.selected_unit = unit
                        return
            self.selected_unit = None

    def draw(self, surface, game):
        """Draw the roster pane and its contents."""
        # Draw main background
        pygame.draw.rect(surface, self.background_color, self.rect)
        pygame.draw.rect(surface, PANEL_BORDER, self.rect, 2)
        
        # Draw header
        header_rect = pygame.Rect(self.rect.left, self.rect.top, self.rect.width, 35)
        pygame.draw.rect(surface, DARK_GREY, header_rect)
        
        # Player name with AI/Human indicator
        player_type_str = ""
        if self.player and hasattr(self.player, 'type'):
            if self.player.type.name == 'AI':
                player_type_str = " (AI)"
            elif self.player.type.name == 'HUMAN':
                player_type_str = " (HUMAN)"
        
        player_display_name = f"{self.player_name}{player_type_str}"
        player_text = self.font_medium.render(player_display_name, True, TEXT_PRIMARY)
        surface.blit(player_text, (self.rect.left + 10, self.rect.top + 5))
        
        # Army points total (include attached leaders with their bodyguard for display)
        if self.roster:
            def _unit_group_cost(u: Unit) -> int:
                try:
                    cost = int(u.get_unit_cost())
                except Exception:
                    cost = 0
                try:
                    for l in list(getattr(u, "attached_leaders", []) or []):
                        cost += int(l.get_unit_cost())
                except Exception:
                    pass
                return cost

            total_points = sum(_unit_group_cost(unit) for unit in self.roster)
            points_text = self.font_small.render(f"{total_points} pts", True, TEXT_SECONDARY)
            surface.blit(points_text, (self.rect.right - 80, self.rect.top + 8))
        
        # Create clipping rect for scrollable content
        content_rect = pygame.Rect(self.rect.left, self.rect.top + 40, self.rect.width, self.rect.height - 40)
        surface.set_clip(content_rect)
        
        # Draw unit buttons
        for button_rect, unit in self.buttons:
            if button_rect.bottom < self.rect.top + 40 or button_rect.top > self.rect.bottom:
                continue  # Skip buttons outside visible area
                
            # Determine button state and color
            if unit == self.selected_unit:
                button_color = BUTTON_SELECTED
                border_color = TEXT_ACCENT
            elif unit == self.hovered_unit:
                button_color = BUTTON_HOVER
                border_color = PANEL_BORDER
            else:
                button_color = BUTTON_BG
                border_color = PANEL_BORDER
            
            # Draw button background
            pygame.draw.rect(surface, button_color, button_rect, border_radius=5)
            pygame.draw.rect(surface, border_color, button_rect, 2, border_radius=5)
            
            # Draw unit information
            self.draw_unit_info(surface, unit, button_rect)

        # Reset clipping
        surface.set_clip(None)
        
        # Draw scroll indicator if needed
        if self.max_scroll > 0:
            self.draw_scroll_indicator(surface)

    def draw_unit_info(self, surface, unit, button_rect):
        """Draw detailed unit information in the button."""
        y_offset = button_rect.top + 5
        x_left = button_rect.left + 8
        x_right = button_rect.right - 8
        
        # Get unit color variation for visual correlation with battlefield
        all_units = getattr(self, 'all_units', self.roster)  # Use all_units if available, otherwise use roster
        unit_color_tint = get_unit_color_variation(unit, all_units)
        
        # Draw unit type icon in the button with color tint
        icon_size = 16
        icon_x = x_left + icon_size // 2
        icon_y = button_rect.top + 20
        self.draw_roster_unit_icon(surface, icon_x, icon_y, icon_size, unit, unit_color_tint)
        
        # Unit name (truncated if too long) - moved right to make room for icon
        unit_name = self.get_unit_display_name(unit)
        if len(unit_name) > 18:  # Reduced to make room for icon
            unit_name = unit_name[:15] + "..."
        name_text = self.font_medium.render(unit_name, True, TEXT_PRIMARY)
        surface.blit(name_text, (x_left + icon_size + 8, y_offset))

        # For attached units, show leaders on their own line under the name (not on the name line).
        leader_line = ""
        try:
            leaders = list(getattr(unit, "attached_leaders", []) or [])
            if leaders:
                # Use roster display name for leaders too (handles duplicates)
                names = []
                for l in leaders:
                    try:
                        names.append(self.get_unit_display_name(l))
                    except Exception:
                        names.append(getattr(l, "name", "Leader"))
                leader_line = "Leaders: " + ", ".join(names[:2]) + (f" +{len(names)-2}" if len(names) > 2 else "")
        except Exception:
            leader_line = ""
        
        # Unit cost (include attached leaders with their bodyguard for display)
        cost_val = 0
        try:
            cost_val += int(unit.get_unit_cost())
        except Exception:
            cost_val += 0
        try:
            for l in list(getattr(unit, "attached_leaders", []) or []):
                cost_val += int(l.get_unit_cost())
        except Exception:
            pass
        cost_text = self.font_small.render(f"{cost_val}pts", True, TEXT_ACCENT)
        surface.blit(cost_text, (x_right - cost_text.get_width(), y_offset))

        # Aspect Shrine token indicators (read-only)
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            token_total = int(root.get_aspect_shrine_token_total() or 0)
        except Exception:
            token_total = 0
        if token_total > 0:
            try:
                token_remaining = int(root.get_aspect_shrine_token_remaining() or 0)
            except Exception:
                token_remaining = 0
            token_size = 8
            gap = 3
            tokens_y = y_offset + 20
            total_w = token_total * token_size + max(0, token_total - 1) * gap
            start_x = x_right - total_w
            for i in range(token_total):
                cx = start_x + i * (token_size + gap) + token_size // 2
                cy = tokens_y + token_size // 2
                draw_aspect_shrine_token_icon(
                    surface,
                    cx,
                    cy,
                    token_size,
                    filled=(i < token_remaining),
                )

        # Extra roster details (composition + status), like the legacy pane
        def _composition_text(u: Unit) -> str:
            try:
                all_models = []
                try:
                    all_models.extend(list(u.models or []))
                except Exception:
                    pass
                try:
                    for l in list(getattr(u, "attached_leaders", []) or []):
                        all_models.extend(list(getattr(l, "models", []) or []))
                except Exception:
                    pass
                alive_models = [m for m in (all_models or []) if getattr(m, 'is_alive', True)]
                if not alive_models:
                    return "0 models"
                # Count by model name for mixed units
                counts: Dict[str, int] = {}
                for m in alive_models:
                    counts[getattr(m, 'name', 'Model')] = counts.get(getattr(m, 'name', 'Model'), 0) + 1
                if len(counts) == 1:
                    name, n = next(iter(counts.items()))
                    return f"{n}x {name}"
                # Mixed: show up to 2 entries to avoid overflow
                parts = [f"{n}x {name}" for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:2]]
                remaining = len(counts) - len(parts)
                if remaining > 0:
                    parts.append(f"+{remaining} types")
                return " • ".join(parts)
            except Exception:
                try:
                    return f"{len(u.models)} models"
                except Exception:
                    return "models: ?"

        def _tags_text(u: Unit) -> str:
            tags: List[str] = []
            try:
                if bool(getattr(u, 'is_character', False)):
                    tags.append("Character")
                if bool(getattr(u, 'is_vehicle', False)):
                    tags.append("Vehicle")
                if bool(getattr(u, 'is_monster', False)):
                    tags.append("Monster")
                if bool(getattr(u, 'is_aircraft', False)):
                    tags.append("Aircraft")
                if bool(getattr(u, 'is_beast', False)):
                    tags.append("Beast")
                if bool(getattr(u, 'is_psyker', False)):
                    tags.append("Psyker")
                if bool(getattr(u, 'is_battleline', False)):
                    tags.append("Battleline")
            except Exception:
                pass
            return ", ".join(tags)

        def _status_text(u: Unit) -> str:
            try:
                # Embarked status has priority (it explains why you can't deploy the unit)
                if getattr(u, "embarked_in", None) is not None:
                    t = getattr(u, "embarked_in", None)
                    tname = getattr(t, "name", "Transport") if t is not None else "Transport"
                    return f"Embarked in {tname}"
                rs = getattr(u, 'reserve_status', None)
                if rs == 'reserves':
                    return "Reserves"
                if rs == 'strategic_reserves':
                    return "Strategic Reserves"
                if not getattr(u, 'deployed', False):
                    return "Not Deployed"
            except Exception:
                pass
            return ""

        # Layout beneath the name line
        details_x = x_left + icon_size + 8
        line1_y = y_offset + 20
        line2_y = y_offset + 38
        line3_y = y_offset + 52

        # Composition (models + type)
        comp = _composition_text(unit)
        comp_surf = self.font_small.render(comp, True, TEXT_SECONDARY)
        surface.blit(comp_surf, (details_x, line1_y))

        # Optional enhancement line (blue) shown above "Not Deployed"
        status_y = line2_y
        # If leaders exist, render them as a dedicated line and push subsequent content down.
        if leader_line:
            leader_surf = self.font_tiny.render(leader_line, True, TEXT_SECONDARY)
            surface.blit(leader_surf, (details_x, line2_y))
            status_y = line3_y
        try:
            enh = getattr(unit, 'enhancement', None)
        except Exception:
            enh = None
        if enh:
            try:
                enh_points = getattr(enh, 'points', 0)
                enh_name = getattr(enh, 'name', str(enh))
                enh_line = f"{enh_name} ({enh_points}pts)"
            except Exception:
                enh_line = "Enhancement"
            enh_surf = self.font_tiny.render(enh_line, True, TEXT_ACCENT)
            surface.blit(enh_surf, (details_x, line2_y))
            status_y = line3_y

        # Status + tags + health
        status = _status_text(unit)
        tags = _tags_text(unit)
        try:
            all_models = []
            try:
                all_models.extend(list(unit.models or []))
            except Exception:
                pass
            try:
                for l in list(getattr(unit, "attached_leaders", []) or []):
                    all_models.extend(list(getattr(l, "models", []) or []))
            except Exception:
                pass
            total_wounds = sum(getattr(m, '_base_wounds', getattr(m, 'wounds', 0)) for m in (all_models or []))
            current_wounds = sum(getattr(m, 'wounds', 0) for m in (all_models or []))
            hp = f"HP {current_wounds}/{total_wounds}" if total_wounds else ""
        except Exception:
            hp = ""

        parts = [p for p in [status, tags, hp] if p]
        if parts:
            line2 = " • ".join(parts)
            # Trim if it gets too long
            if len(line2) > 40:
                line2 = line2[:37] + "..."
            line2_surf = self.font_tiny.render(line2, True, TEXT_SECONDARY)
            surface.blit(line2_surf, (details_x, status_y))

        # Extra transport info: show embarked passengers on the transport's card
        try:
            if bool(getattr(unit, "is_transport", False)):
                passengers = list(getattr(unit, "transport_passengers", []) or [])
                if passengers:
                    # Display up to 2 passenger unit names (roster display names), then "+N"
                    names = []
                    for pu in passengers:
                        try:
                            names.append(self.get_unit_display_name(pu))
                        except Exception:
                            names.append(getattr(pu, "name", "Unit"))
                    shown = names[:2]
                    extra = len(names) - len(shown)
                    tail = f" +{extra}" if extra > 0 else ""
                    p_line = f"Embarked: {', '.join(shown)}{tail}"
                    # Draw on the lowest line slot (or below status)
                    py = min(button_rect.bottom - 14, status_y + 14)
                    p_surf = self.font_tiny.render(p_line[:46] + ("..." if len(p_line) > 46 else ""), True, TEXT_SECONDARY)
                    surface.blit(p_surf, (details_x, py))
        except Exception:
            pass

    def draw_roster_unit_icon(self, surface: pygame.Surface, center_x: int, center_y: int, size: int, unit: Unit, tint_color: Tuple[int, int, int] = (255, 255, 255)) -> None:
        """Draw the unit's icon in the roster with appropriate tinting."""
        # Create a surface for the icon
        icon_surface = pygame.Surface((size, size), pygame.SRCALPHA)
        
        # Draw the appropriate icon based on unit type
        # NOTE: these are booleans in this codebase, not callables
        if bool(getattr(unit, 'is_vehicle', False)):
            draw_vehicle_icon(icon_surface, size//2, size//2, size)
        elif bool(getattr(unit, 'is_monster', False)):
            draw_monster_icon(icon_surface, size//2, size//2, size)
        elif bool(getattr(unit, 'is_aircraft', False)):
            draw_aircraft_icon(icon_surface, size//2, size//2, size)
        elif bool(getattr(unit, 'is_beast', False)):
            draw_beast_icon(icon_surface, size//2, size//2, size)
        elif bool(getattr(unit, 'is_psyker', False)):
            draw_psyker_icon(icon_surface, size//2, size//2, size)
        elif bool(getattr(unit, 'is_battleline', False)):
            draw_battleline_icon(icon_surface, size//2, size//2, size)
        elif bool(getattr(unit, 'is_character', False)):
            draw_character_icon(icon_surface, size//2, size//2, size)
        else:
            draw_generic_icon(icon_surface, size//2, size//2, size)
        
        # Apply tint color
        for x in range(size):
            for y in range(size):
                color = icon_surface.get_at((x, y))
                if color.a > 0:  # Only tint non-transparent pixels
                    tinted_color = (
                        min(255, int(color[0] * tint_color[0] / 255)),
                        min(255, int(color[1] * tint_color[1] / 255)),
                        min(255, int(color[2] * tint_color[2] / 255)),
                        color[3]
                    )
                    icon_surface.set_at((x, y), tinted_color)
        
        # Draw the tinted icon
        surface.blit(icon_surface, (center_x - size//2, center_y - size//2))

    def draw_scroll_indicator(self, surface):
        """Draw scroll indicator when content is scrollable."""
        # Calculate scroll percentage
        scroll_percent = self.scroll_offset / self.max_scroll
        
        # Draw scroll track
        track_width = 4
        track_rect = pygame.Rect(self.rect.right - track_width - 2, self.rect.top + 40, track_width, self.rect.height - 40)
        pygame.draw.rect(surface, PANEL_BORDER, track_rect)
        
        # Draw scroll handle
        handle_height = max(20, (self.rect.height - 40) * (self.rect.height - 40) / (self.rect.height - 40 + self.max_scroll))
        handle_y = self.rect.top + 40 + scroll_percent * (self.rect.height - 40 - handle_height)
        handle_rect = pygame.Rect(track_rect.left, handle_y, track_width, handle_height)
        pygame.draw.rect(surface, TEXT_SECONDARY, handle_rect)

    def get_hovered_unit(self, x, y):
        """Get the unit being hovered over, if any."""
        for button_rect, unit in self.buttons:
            if button_rect.collidepoint(x, y):
                return unit
        return None 
