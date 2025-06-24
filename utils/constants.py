# Constants and configurations for the AutoFisher application

# Application version
VERSION = "0.8.00"
VERSION_NAME = "Enhanced Detection Edition"

# Default settings - Enhanced detection parameters
DEFAULT_THRESHOLD = 0.045  # Slightly more sensitive than default
DEFAULT_DETECTION_COOLDOWN = 5.0  # Original cooldown
DEFAULT_FISHING_KEY = "f"
DEFAULT_CAPTURE_INTERVAL = 0.03  # ~33 FPS for faster response

# Performance settings - All enabled by default
DEFAULT_HIGH_PERFORMANCE = True
DEFAULT_RESPECT_FULLSCREEN = True
DEFAULT_DIRECT_CONTROL = True

# Multi-Zone Detection Configuration
# Default zone configurations (can be customized by user)
DEFAULT_DETECTION_ZONES = {
    "main_fishing": {
        "name": "Main Fishing Zone",
        "description": "Primary area for fish bite detection",
        "enabled": True,
        "sensitivity": 1.0,
        "threshold": 0.045,
        "cooldown": 5.0,
        "priority": 1
    },
    "fish_name": {
        "name": "Fish Name Detection Zone",
        "description": "Area to detect fish name/catch notification",
        "enabled": True,
        "sensitivity": 1.2,  # Higher sensitivity for text detection
        "threshold": 0.035,  # Lower threshold for text changes
        "cooldown": 2.0,     # Shorter cooldown for UI elements
        "priority": 2
    },
    "fishing_rod": {
        "name": "Fishing Rod Detection Zone",
        "description": "Area to detect fishing rod movement/state",
        "enabled": True,
        "sensitivity": 0.8,  # Lower sensitivity to avoid false positives
        "threshold": 0.055,  # Higher threshold for rod movement
        "cooldown": 3.0,
        "priority": 3
    },
    "bounce_shadow": {
        "name": "Fish Shadow Bounce Zone",
        "description": "Area to detect fish shadow bouncing/movement",
        "enabled": True,
        "sensitivity": 1.5,  # High sensitivity for subtle shadow movement
        "threshold": 0.025,  # Very low threshold for shadow detection
        "cooldown": 1.5,     # Quick response for shadow movement
        "priority": 4
    }
}

# Error Handling & Recovery Configuration
ERROR_HANDLING_CONFIG = {
    "max_retries": 3,
    "retry_delay": 0.5,
    "max_consecutive_failures": 5,
    "health_check_interval": 5.0,
    "auto_recovery_enabled": True,
    "graceful_degradation": True
}

# Performance Optimization Settings
PERFORMANCE_CONFIG = {
    "adaptive_capture_interval": True,
    "min_capture_interval": 0.01,
    "max_capture_interval": 0.1,
    "memory_cleanup_interval": 30.0,
    "max_frame_history": 10,
    "enable_fast_mode": True,
    "fast_mode_threshold": 0.1  # Switch to fast mode if change > 10%
}

# UI/UX Configuration
UI_CONFIG = {
    "show_performance_metrics": True,
    "show_zone_visualization": True,
    "real_time_status": True,
    "zone_colors": {
        "main_fishing": "#4CAF50",      # Green
        "fish_name": "#2196F3",         # Blue
        "fishing_rod": "#FF9800",       # Orange
        "bounce_shadow": "#9C27B0"      # Purple
    }
}

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

# Button state colors
UI_SUCCESS_HOVER = "#45A049"  # Darker green for hover
UI_SUCCESS_ACTIVE = "#3D8B40"  # Even darker green for active
UI_ERROR_COLOR = "#F44336"  # Red for error/stop
UI_ERROR_HOVER = "#DA190B"  # Darker red for hover
UI_ERROR_ACTIVE = "#C62828"  # Even darker red for active
UI_ACCENT_HOVER = "#8BC34A"  # Lighter accent for hover
UI_ACCENT_ACTIVE = "#689F38"  # Darker accent for active

# Game window detection strings
GAME_WINDOW_NAMES = [
    'PLAY TOGETHER',
    'play together',
    'playtogether',
    'play-together',
    'play_together',
    'playtogether.exe',
    'play together.exe',
    'play together game',
    'playtogether game',
    'play',
    'together'
] 