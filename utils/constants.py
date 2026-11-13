# Constants and configurations for the AutoFisher application

# Application version
VERSION = "2.0.0"
VERSION_NAME = "Prototype Logic + Qt Overlay"

ALERT_VERSION = "2.1.0"
ALERT_VERSION_NAME = "Exclamation Mark Auto-Trigger"
DEFAULT_EXCLAMATION_MATCH = 0.65

# Detection zone: 80% of client, centered
DETECTION_ZONE_SIZE_X = 0.80
DETECTION_ZONE_SIZE_Y = 0.80

# Default settings - Enhanced detection parameters
DEFAULT_THRESHOLD = 0.01
DEFAULT_DETECTION_COOLDOWN = 5.0  # Original cooldown
DEFAULT_FISHING_KEY = "f"
DEFAULT_CAPTURE_INTERVAL = 0.01  # ~100 FPS — balance speed vs CPU

# Performance settings - All enabled by default
DEFAULT_HIGH_PERFORMANCE = True
DEFAULT_RESPECT_FULLSCREEN = True
DEFAULT_DIRECT_CONTROL = True

# UI Constants - Dark Matcha with Dark Oak Wood palette
UI_DARK_BG = "#1A1D1A"  # Very dark green background
UI_PANEL_BG = "#262A23"  # Dark panel background
UI_LIGHT_TEXT = "#E8E8E0"  # Light text
UI_SECONDARY_TEXT = "#A6A69B"  # Secondary text

# Dark Matcha Green theme
UI_ACCENT_COLOR = "#A3D977"  # Matcha green accent
UI_ACCENT_DARK = "#7BA357"  # Darker matcha green 
UI_ACCENT_LIGHT = "#D1EBB8"  # Lighter matcha green

# Dark Oak Wood accents
UI_WOOD_DARK = "#181914"  # Dark wood/oak color
UI_WOOD_MEDIUM = "#2A2C22"  # Medium wood tone
UI_WOOD_LIGHT = "#6B6E58"  # Light wood highlight

# Status colors
UI_WARNING_COLOR = "#FFC107"  # Amber warning
UI_ALERT_COLOR = "#FF6B6B"  # Red alert
UI_SUCCESS_COLOR = "#4CAF50"  # Green success
UI_NORMAL_COLOR = "#F8F5E3"  # Warm off-white text

# Game window detection (prototype list — avoid generic names that match wrong windows)
GAME_WINDOW_NAMES = [
    "play together",
    "playtogether",
    "play-together",
    "play_together",
    "playtogether.exe",
    "play together.exe",
    "play together game",
    "playtogether game",
]

EXCLUDED_WINDOW_TITLES = [
    "play together pixel change detector",
    "pixel change detector",
    "autofisher",
] 