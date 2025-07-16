import pygame
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
        """Initialize fonts with fallbacks"""
        try:
            self.font_large = pygame.font.SysFont('Arial', FONT_LARGE, bold=True)
            self.font_medium = pygame.font.SysFont('Arial', FONT_MEDIUM, bold=True)
            self.font_small = pygame.font.SysFont('Arial', FONT_SMALL, bold=False)
            self.font_tiny = pygame.font.SysFont('Arial', FONT_TINY, bold=False)
        except:
            self.font_large = pygame.font.Font(None, FONT_LARGE)
            self.font_medium = pygame.font.Font(None, FONT_MEDIUM)
            self.font_small = pygame.font.Font(None, FONT_SMALL)
            self.font_tiny = pygame.font.Font(None, FONT_TINY)
    
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
            
        # Handle ESC key to close dialog
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.hide()
            return True
        
        # Handle mouse events
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # Left click
            mouse_pos = event.pos
            
            # Ensure button positions are up-to-date
            self._update_buttons()
            
            # Check if clicking on title bar to start dragging
            if self.draggable and self.title_bar_rect and self.title_bar_rect.collidepoint(mouse_pos):
                self.dragging = True
                self.drag_offset_x = mouse_pos[0] - self.x
                self.drag_offset_y = mouse_pos[1] - self.y
                return True
            
            # Check button clicks
            for button_name, button_rect in self.buttons.items():
                if button_rect.collidepoint(mouse_pos):
                    if self._handle_button_click(button_name):
                        return True
            
            # Check if click is within dialog bounds
            dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
            if dialog_rect.collidepoint(mouse_pos):
                # Let subclass handle the click
                if self._handle_dialog_click(mouse_pos):
                    return True
            else:
                # Click outside dialog - close it
                self.hide()
                return True
                
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:  # Left click release
            if self.dragging:
                self.dragging = False
                return True
                
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
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
                # Update hover state
                self._update_hover(event.pos)
                return True
        
        # Let subclass handle other events
        return self._handle_other_events(event)
    
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