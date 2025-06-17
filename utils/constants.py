# Constants and configurations for the AutoFisher application

# Application version
VERSION = "1.6"
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

# UI Constants
UI_DARK_BG = "#1E1E1E"
UI_LIGHT_TEXT = "#E0E0E0"
UI_ACCENT_COLOR = "#77DD77"  # Green accent
UI_WARNING_COLOR = "#FF6961"  # Red warning
UI_HIGHLIGHT_COLOR = "#FFB347"  # Orange highlight

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