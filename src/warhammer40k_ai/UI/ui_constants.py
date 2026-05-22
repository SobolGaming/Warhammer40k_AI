TILE_SIZE = 20  # 20 pixels per inch
BATTLEFIELD_WIDTH_INCHES = 60
BATTLEFIELD_HEIGHT_INCHES = 44
BATTLEFIELD_WIDTH = BATTLEFIELD_WIDTH_INCHES * TILE_SIZE
BATTLEFIELD_HEIGHT = BATTLEFIELD_HEIGHT_INCHES * TILE_SIZE

# Cult Ambush marker size (32mm ~= 1.26" diameter)
CULT_AMBUSH_MARKER_RADIUS_INCHES = 0.63

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

# Supported rules (display indicator only)
SUPPORTED_ARMY_RULES = {
    "BLESSINGS OF KHORNE",
    "BATTLE FOCUS",
    "DISPARATE PATHS",
    "THE SHADOW OF CHAOS",
    "OATH OF MOMENT",
    "TEMPLAR VOWS",
    "HARBINGERS OF DREAD",
    "DARK PACTS",
    "CULT OF THE DARK GODS",
    "CABAL OF SORCERERS",
    "PACT OF SORCERY",
    "REANIMATION PROTOCOLS",
    "SYNAPSE",
    "SHADOW IN THE WARP",
    "POWER FROM PAIN",
    "CORSAIRS AND TRAVELLING PLAYERS",
    "PRIORITISED EFFICIENCY",
    "CULT AMBUSH",
    "ACTS OF FAITH",
    "DOCTRINA IMPERATIVES",
    "VOICE OF COMMAND",
    "GATE OF INFINITY",
    "ASSIGNED AGENTS",
    "KILL TEAM",
    "CODE CHIVALRIC",
    "BONDSMAN",
    "FREEBLADES",
}
SUPPORTED_DETACHMENT_RULES = {
    "MARTIAL GRACE",
    "RELENTLESS RAGE",
    "BLOOD TITHE",
    "WARP RIFTS",
    "QUICKSILVER GRACE",
    "COMBAT DRUGS",
    "EXQUISITE SWORDSMANSHIP",
    "MECHANISED MURDER",
    "DAEMONIC EMPOWERMENT",
    "PLEDGES TO THE DARK PRINCE",
    "INTERNAL RIVALRIES",
    "SENSATIONAL PERFORMANCE",
    "MASTER OF THE PAGEANT",
}

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

# Dynamic player-color UI tuning
PLAYER_UI_FALLBACK_RGB = (128, 128, 128)
PLAYER_ACTIVE_HEADER_BLEND = 0.52
PLAYER_ZONE_ALPHA = 96
PLAYER_ZONE_BORDER_SHADE = 0.72
PLAYER_SWATCH_SIZE = 12

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

# Zoom and pan constants
MIN_ZOOM = 1.0
MAX_ZOOM = 2.0
ZOOM_SPEED = 0.1
PAN_SPEED = 15  # Increased from 5 for faster keyboard panning
MOUSE_PAN_SPEED = 1.0  # Mouse panning sensitivity

# Roster pane layout
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

# Icon drawing
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
