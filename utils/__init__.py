"""
Utilities package for AutoFisher
Provides window management, input simulation, and other helper functions
"""

# Import commonly used utilities for easier access
from .constants import (
    VERSION, VERSION_NAME,
    DEFAULT_THRESHOLD, DEFAULT_DETECTION_COOLDOWN, DEFAULT_FISHING_KEY,
    DEFAULT_HIGH_PERFORMANCE, DEFAULT_RESPECT_FULLSCREEN, DEFAULT_DIRECT_CONTROL,
    UI_DARK_BG, UI_LIGHT_TEXT, UI_ACCENT_COLOR, UI_WARNING_COLOR
)

from .win32_utils import force_focus_window, direct_key_press, find_window_by_pattern
from .input import send_key_press, send_esc 