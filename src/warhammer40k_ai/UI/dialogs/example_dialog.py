import pygame
from .base_dialog import BaseDialog


class ExampleDialog(BaseDialog):
    """
    Example dialog showing how to use BaseDialog.
    This is a simple dialog with two buttons: OK and Cancel.
    """
    
    def __init__(self, screen_width: int, screen_height: int):
        # Initialize with custom size and draggable enabled
        super().__init__(screen_width, screen_height, width=400, height=300, draggable=True)
        
        # Dialog-specific state
        self.result = None
        
    def show(self, title: str, message: str, callback=None):
        """Show the dialog with a title and message"""
        # Call parent show method
        super().show(callback)
        
        # Store dialog-specific data
        self.title = title
        self.message = message
        
        # Create buttons using the base class button system
        self.add_button('ok', self.width - 160, self.height - 60, 70, 40)
        self.add_button('cancel', self.width - 80, self.height - 60, 70, 40)
        
    def _handle_button_click(self, button_name: str) -> bool:
        """Handle button click events from base class"""
        if button_name == 'ok':
            self.result = 'ok'
            if self.callback:
                self.callback('ok')
            self.hide()
            return True
        elif button_name == 'cancel':
            self.result = 'cancel'
            if self.callback:
                self.callback('cancel')
            self.hide()
            return True
        return False
    
    def draw(self, screen: pygame.Surface):
        """Draw the dialog"""
        if not self.visible:
            return
            
        # Draw dialog background
        self.draw_dialog_background(screen)
        
        # Draw title bar (draggable)
        self.draw_title_bar(screen, self.title)
        
        # Draw message using base class utility
        self.draw_text_centered(screen, self.message, 150, self.font_medium)
        
        # Draw buttons using base class method
        self.draw_button(screen, 'ok', "OK")
        self.draw_button(screen, 'cancel', "Cancel")


# Usage example (commented out to prevent import issues):
"""
# Create dialog
dialog = ExampleDialog(800, 600)

# Show dialog
def on_result(result):
    print(f"User selected: {result}")

dialog.show("Confirm Action", "Are you sure you want to proceed?", on_result)

# In game loop:
# dialog.handle_event(event)
# dialog.draw(screen)
""" 