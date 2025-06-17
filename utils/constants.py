# Constants and configurations for the AutoFisher application

# Application version
VERSION = "0.6.00"
VERSION_NAME = "Direct Control Edition"

# Default settings
DEFAULT_THRESHOLD = 0.05
DEFAULT_DETECTION_COOLDOWN = 5.0
DEFAULT_FISHING_KEY = "f"
DEFAULT_CAPTURE_INTERVAL = 0.1  # 10 FPS default

# Performance settings
DEFAULT_HIGH_PERFORMANCE = True
DEFAULT_RESPECT_FULLSCREEN = True
DEFAULT_DIRECT_CONTROL = True

# UI Constants - Dark Matcha with Dark Oak Wood palette
UI_DARK_BG = "#1A1D1A"  # Very dark green background
UI_PANEL_BG = "#262A23"  # Dark panel background
UI_LIGHT_TEXT = "#E8E8E0"  # Light text
UI_SECONDARY_TEXT = "#A6A69B"  # Secondary text

# Dark Matcha Green theme
UI_ACCENT_COLOR = "#94B181"  # Matcha green accent
UI_ACCENT_DARK = "#5D7356"  # Darker matcha green 
UI_ACCENT_LIGHT = "#B7CBA8"  # Lighter matcha green

# Dark Oak Wood accents
UI_WOOD_DARK = "#483C32"  # Dark wood/oak color
UI_WOOD_MEDIUM = "#6F5B3E"  # Medium wood tone
UI_WOOD_LIGHT = "#9C826B"  # Light wood highlight

# Status colors
UI_WARNING_COLOR = "#D97E6A"  # Reddish warning
UI_ALERT_COLOR = "#E8B255"  # Amber alert
UI_SUCCESS_COLOR = "#94B181"  # Success (matches accent)

# Game window detection strings
GAME_WINDOW_NAMES = [
    'play together',
    'playtogether',
    'play-together',
    'play_together',
    'playtogether.exe',
    'play together.exe',
    'play together game',
    'playtogether game'
] 