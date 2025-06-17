"""
Core functionality for AutoFisher
Provides detection, image processing, and action sequence handling
"""

from .detector import PixelChangeDetector
from .processing import capture_screen_region, calculate_frame_difference
from .action_sequence import FishingActionSequence 