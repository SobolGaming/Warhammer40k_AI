import pygame
import math
from typing import Callable, Optional, Dict, Any
from abc import ABC, abstractmethod

# Font sizes
FONT_LARGE = 20
FONT_MEDIUM = 16
FONT_SMALL = 14
FONT_TINY = 12

# Enhanced Colors
PANEL_BG = (45, 45, 48)  # Dark background
PANEL_BORDER = (63, 63, 70)  # Subtle border
BUTTON_BG = (60, 60, 67)  # Button background
BUTTON_HOVER = (75, 75, 82)  # Button hover
BUTTON_SELECTED = (100, 149, 237)  # Selected button
BUTTON_DISABLED = (40, 40, 40)  # Disabled button
TEXT_PRIMARY = (255, 255, 255)  # Primary text
TEXT_SECONDARY = (200, 200, 200)  # Secondary text
TEXT_DISABLED = (100, 100, 100)  # Disabled text
TEXT_SUCCESS = (100, 255, 100)  # Success/completed text
TEXT_WARNING = (255, 200, 100)  # Warning text
TEXT_ERROR = (255, 100, 100)  # Error text


class BaseDialog(ABC):
    """
    Base class for all dialog implementations.
    Provides common functionality like positioning, dragging, ESC handling, fonts, and button management.
    """

    # UI constants for dialog positioning
    DIALOG_MARGIN = 20  # Minimum margin from screen edges
    DIALOG_OVERLAP_MARGIN = 30  # Minimum space between dialogs to avoid overlap
    
    def __init__(self, screen_width: int, screen_height: int, width: int, height: int, 
                 draggable: bool = True, center: bool = True):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.width = width
        self.height = height
        self.visible = False
        
        # Positioning
        if center:
            self.x = (screen_width - width) // 2
            self.y = (screen_height - height) // 2
        else:
            self.x = 50
            self.y = 50
        
        # Dragging functionality
        self.draggable = draggable
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.title_bar_height = 50
        
        # Callback mechanism
        self.callback = None
        
        # Initialize fonts
        self._init_fonts()
        
        # UI state
        self.hovered_button = None
        self.buttons = {}  # Button registry: name -> pygame.Rect
        self.button_states = {}  # Button state tracking: name -> state
        
        # Create title bar rectangle for dragging
        self.title_bar_rect = None
        self._update_title_bar()
        
    def _init_fonts(self):
        """Initialize fonts with explicit fall-through."""
        try:
            # Prefer a modern, clean UI font stack (best-effort across OSes).
            # On Windows, Segoe UI Variable / Segoe UI is typically available.
            candidates = [
                "Segoe UI Variable",
                "Segoe UI",
                "Inter",
                "Roboto",
                "Helvetica Neue",
                "Helvetica",
                "Arial",
            ]

            def _font(size: int, bold: bool) -> pygame.font.Font:
                try:
                    path = pygame.font.match_font(candidates, bold=bold)
                    if path:
                        return pygame.font.Font(path, size)
                except Exception:
                    pass
                # Fallback to SysFont lookup
                try:
                    return pygame.font.SysFont(candidates, size, bold=bold)
                except Exception:
                    return pygame.font.Font(None, size)

            self.font_large = _font(FONT_LARGE, bold=True)
            self.font_medium = _font(FONT_MEDIUM, bold=True)
            self.font_small = _font(FONT_SMALL, bold=False)
            self.font_tiny = _font(FONT_TINY, bold=False)
        except:
            self.font_large = pygame.font.Font(None, FONT_LARGE)
            self.font_medium = pygame.font.Font(None, FONT_MEDIUM)
            self.font_small = pygame.font.Font(None, FONT_SMALL)
            self.font_tiny = pygame.font.Font(None, FONT_TINY)

    def draw_text_wrapped(
        self,
        screen: pygame.Surface,
        text: str,
        x: int,
        y: int,
        max_width: int,
        font: pygame.font.Font,
        color: tuple,
        line_height: int = 18,
    ) -> int:
        """
        Draw word-wrapped text within max_width.

        - Respects explicit newlines in `text` (each paragraph is wrapped independently).
        - Returns the y position just after the final rendered line.
        """
        if not text:
            return y
        font = font or self.font_small
        color = color or TEXT_SECONDARY

        cur_y = y
        # Respect explicit newlines
        for para in str(text).split("\n"):
            words = para.split(" ")
            line = ""
            for w in words:
                trial = (line + " " + w).strip() if line else w
                try:
                    if font.size(trial)[0] <= max_width:
                        line = trial
                    else:
                        if line:
                            surf = font.render(line, True, color)
                            screen.blit(surf, (x, cur_y))
                            cur_y += line_height
                        line = w
                except Exception:
                    # If size() fails, fall back to naive single-line
                    line = trial
            if line:
                surf = font.render(line, True, color)
                screen.blit(surf, (x, cur_y))
                cur_y += line_height
            # Blank line between explicit paragraphs
            if para == "" and words == [""]:
                cur_y += max(0, line_height // 2)
        return cur_y
    
    def _update_title_bar(self):
        """Update title bar rectangle for dragging"""
        if self.draggable:
            self.title_bar_rect = pygame.Rect(self.x, self.y, self.width, self.title_bar_height)
    
    def show(self, callback: Optional[Callable] = None, **kwargs):
        """
        Show the dialog. Subclasses can override to handle specific show logic.
        """
        self.visible = True
        self.callback = callback
        self.dragging = False
        self._update_title_bar()
        self._update_buttons()
        
    def hide(self):
        """Hide the dialog and clean up state"""
        self.visible = False
        self.callback = None
        self.dragging = False
        self.hovered_button = None
        
    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Handle pygame events for the dialog.
        Returns True if event was consumed, False otherwise.
        """
        if not self.visible:
            return False

        # Debug: Log all events handled by this dialog
        dialog_name = self.__class__.__name__
        # if event.type == pygame.KEYDOWN:
        #     print(f"🔍 DEBUG: {dialog_name}.handle_event - KEYDOWN: key={pygame.key.name(event.key)}")
        # elif event.type == pygame.MOUSEBUTTONDOWN:
        #     print(f"🔍 DEBUG: {dialog_name}.handle_event - MOUSEBUTTONDOWN: button={event.button}, pos={event.pos}")
        # elif event.type == pygame.MOUSEBUTTONUP:
        #     print(f"🔍 DEBUG: {dialog_name}.handle_event - MOUSEBUTTONUP: button={event.button}, pos={event.pos}")
        # elif event.type == pygame.MOUSEMOTION:
        #     print(f"🔍 DEBUG: {dialog_name}.handle_event - MOUSEMOTION: pos={event.pos}")
        # else:
        #     print(f"🔍 DEBUG: {dialog_name}.handle_event - OTHER: type={event.type}")

        # Handle ESC key to close dialog
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            print(f"🔍 DEBUG: {dialog_name} - ESC key pressed, hiding dialog")
            self.hide()
            return True
        
        # Handle mouse events
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # Left click
            mouse_pos = event.pos
            dialog_name = self.__class__.__name__
            print(f"🔍 DEBUG: {dialog_name} - Left click at {mouse_pos}")

            # Ensure button positions are up-to-date
            self._update_buttons()

            # Check if clicking on title bar to start dragging
            if self.draggable and self.title_bar_rect and self.title_bar_rect.collidepoint(mouse_pos):
                print(f"🔍 DEBUG: {dialog_name} - Starting drag from title bar")
                self.dragging = True
                self.drag_offset_x = mouse_pos[0] - self.x
                self.drag_offset_y = mouse_pos[1] - self.y
                return True

            # Check button clicks
            for button_name, button_rect in self.buttons.items():
                if button_rect.collidepoint(mouse_pos):
                    print(f"🔍 DEBUG: {dialog_name} - Button '{button_name}' clicked")
                    if self._handle_button_click(button_name):
                        return True

            # Check if click is within dialog bounds
            dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
            if dialog_rect.collidepoint(mouse_pos):
                print(f"🔍 DEBUG: {dialog_name} - Click inside dialog, delegating to subclass")
                # Let subclass handle the click
                if self._handle_dialog_click(mouse_pos):
                    return True
            else:
                print(f"🔍 DEBUG: {dialog_name} - Click outside dialog, hiding")
                # Click outside dialog - close it
                self.hide()
                return True
                
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:  # Left click release
            dialog_name = self.__class__.__name__
            if self.dragging:
                print(f"🔍 DEBUG: {dialog_name} - Ending drag")
                self.dragging = False
                return True

        elif event.type == pygame.MOUSEMOTION:
            dialog_name = self.__class__.__name__
            if self.dragging:
                print(f"🔍 DEBUG: {dialog_name} - Dragging to {event.pos}")
                # Update dialog position
                self.x = event.pos[0] - self.drag_offset_x
                self.y = event.pos[1] - self.drag_offset_y

                # Keep dialog within screen bounds
                self.x = max(0, min(self.screen_width - self.width, self.x))
                self.y = max(0, min(self.screen_height - self.height, self.y))

                # Update button positions
                self._update_title_bar()
                self._update_buttons()
                return True
            else:
                # Update hover state (don't log every motion event to avoid spam)
                self._update_hover(event.pos)
                return True
        
        # Let subclass handle other events
        return self._handle_other_events(event)

    def find_non_overlapping_position(self, existing_dialogs: list) -> tuple:
        """
        Find a position for this dialog that doesn't overlap with existing visible dialogs.

        Args:
            existing_dialogs: List of other BaseDialog instances that are currently visible

        Returns:
            tuple: (x, y) position that avoids overlap
        """
        # Start with the default centered position
        preferred_x = (self.screen_width - self.width) // 2
        preferred_y = (self.screen_height - self.height) // 2

        print(f"🔍 DEBUG: Dialog positioning - preferred position: ({preferred_x}, {preferred_y})")
        print(f"🔍 DEBUG: Dialog positioning - {len(existing_dialogs)} existing dialogs to avoid")

        # If no existing dialogs, use preferred position
        if not existing_dialogs:
            print(f"🔍 DEBUG: Dialog positioning - no existing dialogs, using preferred position")
            return preferred_x, preferred_y

        # Get rectangles of all visible dialogs
        existing_rects = []
        for dialog in existing_dialogs:
            if hasattr(dialog, 'visible') and dialog.visible:
                existing_rects.append(pygame.Rect(dialog.x, dialog.y, dialog.width, dialog.height))

        # If no visible dialogs, use preferred position
        if not existing_rects:
            return preferred_x, preferred_y

        # Try the preferred position first
        test_rect = pygame.Rect(preferred_x, preferred_y, self.width, self.height)
        if not self._rect_overlaps_any(test_rect, existing_rects):
            return preferred_x, preferred_y

        # Try positions in a spiral pattern around the preferred position
        max_attempts = 20
        step_size = 50

        for attempt in range(max_attempts):
            # Calculate spiral positions
            angle_step = 2 * 3.14159 / 8  # 8 directions per ring
            ring = attempt // 8 + 1
            direction = attempt % 8

            offset_x = int(ring * step_size * math.cos(direction * angle_step))
            offset_y = int(ring * step_size * math.sin(direction * angle_step))

            test_x = preferred_x + offset_x
            test_y = preferred_y + offset_y

            # Keep within screen bounds
            test_x = max(self.DIALOG_MARGIN, min(self.screen_width - self.width - self.DIALOG_MARGIN, test_x))
            test_y = max(self.DIALOG_MARGIN, min(self.screen_height - self.height - self.DIALOG_MARGIN, test_y))

            test_rect = pygame.Rect(test_x, test_y, self.width, self.height)
            if not self._rect_overlaps_any(test_rect, existing_rects):
                return test_x, test_y

        # If all else fails, position to the right of the rightmost dialog
        rightmost_x = max(rect.right for rect in existing_rects)
        next_x = min(rightmost_x + self.DIALOG_OVERLAP_MARGIN,
                        self.screen_width - self.width - self.DIALOG_MARGIN)
        next_y = max(self.DIALOG_MARGIN,
                        min(preferred_y, self.screen_height - self.height - self.DIALOG_MARGIN))

        return next_x, next_y

    def _rect_overlaps_any(self, test_rect: pygame.Rect, existing_rects: list) -> bool:
        """
        Check if a rectangle overlaps with any rectangle in a list, with margin.

        Args:
            test_rect: Rectangle to test
            existing_rects: List of existing rectangles

        Returns:
            bool: True if test_rect overlaps with any existing rectangle (including margin)
        """
        # Expand test rect by margin to ensure minimum spacing
        expanded_test = test_rect.inflate(self.DIALOG_OVERLAP_MARGIN * 2, self.DIALOG_OVERLAP_MARGIN * 2)

        for existing_rect in existing_rects:
            if expanded_test.colliderect(existing_rect):
                return True

        return False
    
    def _update_hover(self, mouse_pos):
        """Update hover state for buttons"""
        self.hovered_button = None
        for button_name, button_rect in self.buttons.items():
            if button_rect.collidepoint(mouse_pos):
                self.hovered_button = button_name
                break
    
    def add_button(self, name: str, x: int, y: int, width: int, height: int, 
                   enabled: bool = True, state: str = 'normal'):
        """Add a button to the dialog"""
        # Convert relative coordinates to absolute
        abs_x = self.x + x
        abs_y = self.y + y
        
        self.buttons[name] = pygame.Rect(abs_x, abs_y, width, height)
        self.button_states[name] = {
            'enabled': enabled,
            'state': state,
            'relative_x': x,
            'relative_y': y,
            'width': width,
            'height': height
        }
    
    def _update_buttons(self):
        """Update button positions when dialog is moved"""
        for button_name, button_state in self.button_states.items():
            abs_x = self.x + button_state['relative_x']
            abs_y = self.y + button_state['relative_y']
            self.buttons[button_name] = pygame.Rect(
                abs_x, abs_y, 
                button_state['width'], 
                button_state['height']
            )
    
    def draw_button(self, screen: pygame.Surface, name: str, text: str, 
                    color: tuple = None, text_color: tuple = None):
        """Draw a button with proper styling"""
        if name not in self.buttons:
            return
            
        button_rect = self.buttons[name]
        button_state = self.button_states[name]
        
        # Determine button color
        if not button_state['enabled']:
            bg_color = BUTTON_DISABLED
            text_col = TEXT_DISABLED
        elif self.hovered_button == name:
            bg_color = BUTTON_HOVER
            text_col = TEXT_PRIMARY
        elif button_state['state'] == 'selected':
            bg_color = BUTTON_SELECTED
            text_col = TEXT_PRIMARY
        else:
            bg_color = color or BUTTON_BG
            text_col = text_color or TEXT_PRIMARY
        
        # Draw button
        pygame.draw.rect(screen, bg_color, button_rect)
        pygame.draw.rect(screen, PANEL_BORDER, button_rect, 1)
        
        # Draw button text
        text_surface = self.font_small.render(text, True, text_col)
        text_rect = text_surface.get_rect(center=button_rect.center)
        screen.blit(text_surface, text_rect)
    
    def draw_title_bar(self, screen: pygame.Surface, title: str, subtitle: str = None):
        """Draw the title bar with drag functionality indication"""
        if not self.draggable:
            return
            
        # Draw title bar background
        title_bar_rect = pygame.Rect(self.x, self.y, self.width, self.title_bar_height)
        pygame.draw.rect(screen, (55, 55, 58), title_bar_rect)
        pygame.draw.rect(screen, PANEL_BORDER, title_bar_rect, 1)
        
        # Draw title
        title_surface = self.font_medium.render(title, True, TEXT_PRIMARY)
        screen.blit(title_surface, (self.x + 20, self.y + 10))
        
        # Draw drag hint
        if subtitle:
            subtitle_surface = self.font_small.render(subtitle, True, TEXT_SECONDARY)
            screen.blit(subtitle_surface, (self.x + 20, self.y + 30))
        else:
            drag_hint = "[Drag to move]"
            drag_surface = self.font_small.render(drag_hint, True, TEXT_SECONDARY)
            screen.blit(drag_surface, (self.x + 20, self.y + 30))
    
    def draw_dialog_background(self, screen: pygame.Surface):
        """Draw the dialog background and border"""
        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(screen, PANEL_BG, dialog_rect)
        pygame.draw.rect(screen, PANEL_BORDER, dialog_rect, 2)
    
    def draw_text_centered(self, screen: pygame.Surface, text: str, 
                          y_offset: int, font=None, color: tuple = None):
        """Draw centered text at the specified y offset"""
        font = font or self.font_medium
        color = color or TEXT_PRIMARY
        
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect(center=(self.x + self.width // 2, self.y + y_offset))
        screen.blit(text_surface, text_rect)
    
    def draw_instructions(self, screen: pygame.Surface, instructions: str, 
                         y_offset: int = None):
        """Draw instruction text"""
        y_offset = y_offset or (self.title_bar_height + 20 if self.draggable else 60)
        
        # Handle multi-line instructions
        lines = instructions.split('\n')
        for i, line in enumerate(lines):
            text_surface = self.font_small.render(line, True, TEXT_SECONDARY)
            screen.blit(text_surface, (self.x + 20, self.y + y_offset + i * 20))
    
    # Abstract methods for subclasses to implement
    @abstractmethod
    def _handle_button_click(self, button_name: str) -> bool:
        """Handle button click events. Return True if handled."""
        pass
    
    def _handle_dialog_click(self, mouse_pos) -> bool:
        """Handle clicks within dialog area. Return True if handled."""
        return False
    
    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        """Handle other events not covered by base class. Return True if handled."""
        return False
    
    @abstractmethod
    def draw(self, screen: pygame.Surface):
        """Draw the dialog. Subclasses must implement this."""
        pass 
