import pygame
from typing import List
from warhammer40k_ai.classes.unit import Unit

# Font sizes
FONT_LARGE = 20
FONT_MEDIUM = 16
FONT_SMALL = 14
FONT_TINY = 12

# Enhanced Colors
PANEL_BG = (45, 45, 48)  # Dark background
PANEL_BORDER = (63, 63, 70)  # Subtle border
TEXT_PRIMARY = (255, 255, 255)  # Primary text
TEXT_SECONDARY = (200, 200, 200)  # Secondary text
TEXT_ACCENT = (100, 149, 237)  # Accent text
DARK_GREY = (40, 40, 40)


class UnitDetailPanel(pygame.sprite.Sprite):
    """Detailed unit information panel that appears when hovering over units"""
    def __init__(self, width=500, height=600):
        super().__init__()
        self.width = width
        self.height = height
        self.visible = True  # Add visible attribute
        # Use system fonts for better clarity
        try:
            self.font_large = pygame.font.SysFont('Arial', FONT_LARGE, bold=True)
            self.font_medium = pygame.font.SysFont('Arial', FONT_MEDIUM, bold=True)
            self.font_small = pygame.font.SysFont('Arial', FONT_SMALL, bold=False)
            self.font_tiny = pygame.font.SysFont('Arial', FONT_TINY, bold=False)
        except:
            # Use default fonts if system fonts fail
            self.font_large = pygame.font.Font(None, FONT_LARGE)
            self.font_medium = pygame.font.Font(None, FONT_MEDIUM)
            self.font_small = pygame.font.Font(None, FONT_SMALL)
            self.font_tiny = pygame.font.Font(None, FONT_TINY)
        self.background_color = PANEL_BG
        self.border_color = PANEL_BORDER
        self.scroll_offset = 0
        self.max_scroll = 0

    def scroll(self, delta):
        """Handle scrolling in the unit detail panel"""
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset + delta))

    def draw(self, surface: pygame.Surface, unit: Unit, x: int, y: int):
        """Draw detailed unit information at the specified position"""
        # Adjust position to keep panel on screen
        screen_width, screen_height = surface.get_size()
        if x + self.width > screen_width:
            x = screen_width - self.width - 10
        if y + self.height > screen_height:
            y = screen_height - self.height - 10
        
        self.rect = pygame.Rect(x, y, self.width, self.height)
        
        # Draw background with shadow effect
        shadow_rect = pygame.Rect(x + 3, y + 3, self.width, self.height)
        pygame.draw.rect(surface, (0, 0, 0, 100), shadow_rect, border_radius=8)
        pygame.draw.rect(surface, self.background_color, self.rect, border_radius=8)
        pygame.draw.rect(surface, self.border_color, self.rect, 2, border_radius=8)
        
        # Create clipping area for scrollable content
        content_rect = pygame.Rect(x + 10, y + 10, self.width - 20, self.height - 20)
        surface.set_clip(content_rect)
        
        y_pos = y + 15 - self.scroll_offset
        x_left = x + 15
        x_right = x + self.width - 15
        
        # Unit name and cost
        unit_name = self.font_large.render(unit.name, True, TEXT_PRIMARY)
        surface.blit(unit_name, (x_left, y_pos))
        
        cost_text = self.font_medium.render(f"{unit.get_unit_cost()} points", True, TEXT_ACCENT)
        cost_rect = cost_text.get_rect()
        surface.blit(cost_text, (x_right - cost_rect.width, y_pos))
        
        y_pos += 35
        
        # Faction and keywords
        faction_text = self.font_small.render(f"Faction: {unit.faction}", True, TEXT_SECONDARY)
        surface.blit(faction_text, (x_left, y_pos))
        y_pos += 20
        
        # Keywords (single line, no wrapping)
        if unit.keywords:
            keywords_str = "Keywords: " + ", ".join(unit.keywords)
            keyword_text = self.font_tiny.render(keywords_str, True, TEXT_SECONDARY)
            surface.blit(keyword_text, (x_left, y_pos))
            y_pos += 14
        
        y_pos += 10
        
        # Unit composition header
        comp_header = self.font_medium.render("Unit Composition:", True, TEXT_PRIMARY)
        surface.blit(comp_header, (x_left, y_pos))
        y_pos += 25
        
        # Model details
        model_groups = {}
        for model in unit.models:
            if model.name not in model_groups:
                model_groups[model.name] = []
            model_groups[model.name].append(model)
        
        for model_name, models in model_groups.items():
            count = len(models)
            model_info = f"• {count}x {model_name}"
            
            # Add stats
            if models:
                m = models[0]  # Use first model as reference
                stats = f" (M:{m.movement}\" T:{m.toughness} Sv:{m.save}+ W:{m.wounds} Ld:{m.leadership}+ OC:{m.objective_control})"
                model_info += stats
            
            model_text = self.font_small.render(model_info, True, TEXT_SECONDARY)
            surface.blit(model_text, (x_left + 5, y_pos))
            y_pos += 18
            
            # Show wargear for this model type
            if models and models[0].wargear:
                wargear_header = self.font_tiny.render("  Wargear:", True, TEXT_ACCENT)
                surface.blit(wargear_header, (x_left + 10, y_pos))
                y_pos += 14
                
                for wargear in models[0].wargear:
                    if wargear:
                        # Wargear name
                        wargear_text = f"    • {wargear.name}"
                        wargear_surface = self.font_tiny.render(wargear_text, True, TEXT_SECONDARY)
                        surface.blit(wargear_surface, (x_left + 15, y_pos))
                        y_pos += 12
                        
                        # Show wargear profiles
                        if hasattr(wargear, 'profiles') and wargear.profiles:
                            for profile_name, profile in wargear.profiles.items():
                                y_pos = self.draw_wargear_profile(surface, profile, profile_name, x_left + 25, y_pos)
                        y_pos += 5  # Extra spacing between wargear items
        
        y_pos += 15
        
        # Abilities
        if unit.possible_abilities:
            abilities_header = self.font_medium.render("Abilities:", True, TEXT_PRIMARY)
            surface.blit(abilities_header, (x_left, y_pos))
            y_pos += 25
            
            for ability in unit.possible_abilities:  # Show all abilities
                # Include parameter in ability name if available (e.g., "Feel No Pain 5+")
                ability_display_name = ability.name
                if hasattr(ability, 'parameter') and ability.parameter:
                    ability_display_name = f"{ability.name} {ability.parameter}"
                
                ability_name = self.font_small.render(f"• {ability_display_name}", True, TEXT_ACCENT)
                surface.blit(ability_name, (x_left + 5, y_pos))
                y_pos += 18
                
                # Wrap ability description
                if ability.description:
                    # Strip trailing semicolon if present
                    description = ability.description.rstrip(';')
                    desc_wrapped = self.wrap_text(description, self.font_tiny, self.width - 40)
                    for line in desc_wrapped:  # Show all lines
                        desc_text = self.font_tiny.render(line, True, TEXT_SECONDARY)
                        surface.blit(desc_text, (x_left + 10, y_pos))
                        y_pos += 12
                    y_pos += 5  # Extra spacing after each ability
        
        # Enhancement
        if unit.enhancement:
            y_pos += 10
            enh_header = self.font_medium.render("Enhancement:", True, TEXT_PRIMARY)
            surface.blit(enh_header, (x_left, y_pos))
            y_pos += 20
            
            enh_name = self.font_small.render(f"• {unit.enhancement.name} ({unit.enhancement.points}pts)", True, TEXT_ACCENT)
            surface.blit(enh_name, (x_left + 5, y_pos))
            y_pos += 18
            
            # Enhancement description
            if hasattr(unit.enhancement, 'description') and unit.enhancement.description:
                desc_wrapped = self.wrap_text(unit.enhancement.description, self.font_tiny, self.width - 40)
                for line in desc_wrapped:
                    desc_text = self.font_tiny.render(line, True, TEXT_SECONDARY)
                    surface.blit(desc_text, (x_left + 10, y_pos))
                    y_pos += 12
                y_pos += 5  # Extra spacing after description
        
        # Calculate max scroll
        total_content_height = y_pos - (y + 15) + self.scroll_offset
        self.max_scroll = max(0, total_content_height - (self.height - 30))
        
        # Reset clipping
        surface.set_clip(None)
        
        # Draw scroll indicator if needed
        if self.max_scroll > 0:
            self.draw_scroll_indicator(surface, x, y)

    def draw_scroll_indicator(self, surface: pygame.Surface, x: int, y: int):
        """Draw scroll indicator on the right side of the panel"""
        if self.max_scroll <= 0:
            return
        
        # Scroll bar background
        scrollbar_x = x + self.width - 15
        scrollbar_y = y + 10
        scrollbar_height = self.height - 20
        scrollbar_rect = pygame.Rect(scrollbar_x, scrollbar_y, 10, scrollbar_height)
        pygame.draw.rect(surface, DARK_GREY, scrollbar_rect, border_radius=5)
        
        # Scroll thumb
        thumb_height = max(20, int(scrollbar_height * (self.height - 30) / (self.max_scroll + self.height - 30)))
        thumb_y = scrollbar_y + int((scrollbar_height - thumb_height) * (self.scroll_offset / self.max_scroll))
        thumb_rect = pygame.Rect(scrollbar_x + 1, thumb_y, 8, thumb_height)
        pygame.draw.rect(surface, TEXT_SECONDARY, thumb_rect, border_radius=4)

    def draw_wargear_profile(self, surface: pygame.Surface, profile, profile_name: str, x_pos: int, y_pos: int) -> int:
        """Draw detailed wargear profile information and return new y position"""
        # Profile name (if not 'default')
        if profile_name != 'default':
            profile_header = self.font_tiny.render(f"      {profile_name}:", True, TEXT_ACCENT)
            surface.blit(profile_header, (x_pos, y_pos))
            y_pos += 12
        
        # Determine if weapon is melee or ranged
        is_melee = False
        if hasattr(profile, 'range'):
            if hasattr(profile.range, 'max') and profile.range.max == 0:
                is_melee = True
            elif hasattr(profile.range, 'min') and hasattr(profile.range, 'max') and profile.range.min == 0 and profile.range.max == 0:
                is_melee = True
        
        # Format profile stats - display all on one line
        stats_parts = []
        
        # Weapon type and range
        if hasattr(profile, 'range'):
            if is_melee:
                stats_parts.append("Melee")
            elif hasattr(profile.range, 'max'):
                stats_parts.append(f"Ranged {profile.range.max}\"")
            else:
                stats_parts.append(f"Ranged {profile.range}")
        
        # Attacks
        if hasattr(profile, 'attacks'):
            if hasattr(profile.attacks, 'value'):
                stats_parts.append(f"A: {profile.attacks.value}")
            else:
                stats_parts.append(f"A: {profile.attacks}")
        
        # Skill (BS for ranged, WS for melee)
        if hasattr(profile, 'skill'):
            if is_melee:
                stats_parts.append(f"WS: {profile.skill}+")
            else:
                stats_parts.append(f"BS: {profile.skill}+")
        
        # Strength
        if hasattr(profile, 'strength'):
            stats_parts.append(f"S: {profile.strength}")
        
        # AP
        if hasattr(profile, 'ap'):
            ap_val = profile.ap
            if ap_val == 0:
                stats_parts.append("AP: -")
            else:
                stats_parts.append(f"AP: {ap_val}")
        
        # Damage
        if hasattr(profile, 'damage'):
            if hasattr(profile.damage, 'value'):
                stats_parts.append(f"D: {profile.damage.value}")
            else:
                stats_parts.append(f"D: {profile.damage}")
        
        # Display stats in one line
        stats_text = " | ".join(stats_parts)
        stats_surface = self.font_tiny.render(f"      {stats_text}", True, TEXT_SECONDARY)
        surface.blit(stats_surface, (x_pos, y_pos))
        y_pos += 12
        
        # Keywords
        if hasattr(profile, 'get_keywords') and profile.get_keywords():
            keywords_text = f"      Keywords: {', '.join(profile.get_keywords())}"
            keywords_surface = self.font_tiny.render(keywords_text, True, TEXT_ACCENT)
            surface.blit(keywords_surface, (x_pos, y_pos))
            y_pos += 12
        
        # Special abilities
        if hasattr(profile, 'abilities') and profile.abilities:
            abilities_text = f"      {', '.join(profile.abilities)}"
            abilities_surface = self.font_tiny.render(abilities_text, True, TEXT_ACCENT)
            surface.blit(abilities_surface, (x_pos, y_pos))
            y_pos += 12
        
        return y_pos + 3  # Small gap after profile

    def wrap_text(self, text: str, font: pygame.font.Font, max_width: int) -> List[str]:
        """Wrap text to fit within the specified width"""
        words = text.split(' ')
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + word + " "
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line.strip())
                    current_line = word + " "
                else:
                    # Word too long for the line
                    lines.append(word)
                    current_line = ""
        
        if current_line:
            lines.append(current_line.strip())
        
        return lines

    def handle_event(self, event):
        """Handle events for the unit detail panel."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return True  # Signal that we want to close the panel
        return False 