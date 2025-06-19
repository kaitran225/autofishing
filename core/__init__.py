"""
AutoFisher Core Module
Contains the core functionality for pixel change detection and fishing automation
"""

from core.detector import PixelChangeDetector
from core.action_sequence import FishingActionSequence
from core.processing import capture_screen_region, calculate_frame_difference, enhance_visualization, detect_fishing_bobber

__all__ = [
    'PixelChangeDetector',
    'FishingActionSequence',
    'capture_screen_region',
    'calculate_frame_difference',
    'enhance_visualization',
    'detect_fishing_bobber'
] 